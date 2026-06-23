from __future__ import annotations

import hashlib
import json
from math import ceil

from sqlalchemy import select
from sqlalchemy.orm import Session

from yontai.core.hardware import detect_hardware_profile
from yontai.core.paths import storage_path
from yontai.db.models import Artifact, Dataset, Job, JobEvent, Model, RunStatus, TrainingRun
from yontai.schemas.common import JobRead
from yontai.schemas.training import (
    FineTunePlan,
    FineTuneRequest,
    KnowledgePackRequest,
    KnowledgePackResponse,
    TrainingRunCreated,
)


class TrainingService:
    """Coordinates persistent PEFT, TRL and Unsloth fine-tuning jobs."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_runs(self) -> list[TrainingRun]:
        return list(
            self.db.scalars(select(TrainingRun).order_by(TrainingRun.created_at.desc()))
        )

    def build_plan(self, payload: FineTuneRequest) -> FineTunePlan:
        model = self.db.get(Model, payload.base_model_id)
        dataset = self.db.get(Dataset, payload.dataset_id)
        if model is None:
            raise ValueError("Temel model bulunamadı.")
        if dataset is None:
            raise ValueError("Eğitim veri seti bulunamadı.")

        warnings: list[str] = []
        recommendations: list[str] = []
        hardware = detect_hardware_profile()
        ram_total_gb = float(hardware.get("ram_total_gb") or 0)
        estimated_vram_gb = self._estimate_vram_gb(model, payload.method)
        steps_per_epoch = max(1, ceil(dataset.row_count / payload.batch_size))
        estimated_steps = steps_per_epoch * payload.epochs

        if model.source == "ollama":
            warnings.append(
                "Ollama modelleri doğrudan fine-tuning için uygun değildir; "
                "HF veya yerel ağırlık kaydı kullanın."
            )
        if dataset.row_count < 500:
            warnings.append(
                "Veri seti 500 örneğin altında; sonuçlar kararsız olabilir."
            )
        elif dataset.row_count < 5_000:
            recommendations.append(
                "Daha güçlü sonuç için 5000+ kaliteli örnek hedefleyin."
            )
        if dataset.duplicate_ratio > 0.1:
            warnings.append(
                "Tekrar oranı yüksek; eğitimden önce temizlenmiş dataset üretin."
            )
        if payload.method == "full" and ram_total_gb and estimated_vram_gb > ram_total_gb:
            warnings.append(
                "Full fine-tune bu donanım için yüksek bellek riski taşıyor."
            )
        if payload.framework == "unsloth" and not self._is_apple_silicon_or_linux():
            recommendations.append(
                "Unsloth desteğini doğrulayın; "
                "Windows tarafında TRL daha güvenli olabilir."
            )

        recommendations.extend(
            [
                "İlk deneme için LoRA/QLoRA ve küçük epoch sayısı kullanın.",
                "Model Doktoru ile veri seti kalitesini eğitimden önce kontrol edin.",
            ]
        )
        config = {
            "epochs": payload.epochs,
            "method": payload.method,
            "framework": payload.framework,
            "batch_size": payload.batch_size,
            "learning_rate": payload.learning_rate,
            "max_seq_length": payload.max_seq_length,
            "lora_rank": payload.lora_rank,
            "model_name": model.name,
            "dataset_name": dataset.name,
            "dataset_rows": dataset.row_count,
            "knowledge_packs": self._model_knowledge_pack_summary(model),
            "knowledge_dataset": self._dataset_knowledge_summary(dataset),
            "hardware": hardware,
        }
        return FineTunePlan(
            ready=model.source != "ollama" and dataset.row_count > 0,
            model_id=model.id,
            dataset_id=dataset.id,
            method=payload.method,
            framework=payload.framework,
            estimated_vram_gb=estimated_vram_gb,
            estimated_steps=estimated_steps,
            warnings=warnings,
            recommendations=recommendations,
            config=config,
        )

    def create_run(self, payload: FineTuneRequest) -> TrainingRunCreated:
        plan = self.build_plan(payload)
        if not plan.ready:
            raise ValueError("Bu model/veri seti kombinasyonu eğitim için hazır değil.")

        job = Job(
            project_id=payload.project_id,
            type="training",
            status=RunStatus.QUEUED.value,
            progress=0,
            current_step="Fine-tuning işi kuyruğa alındı",
            payload={
                "model_id": payload.base_model_id,
                "base_model_id": payload.base_model_id,
                "dataset_id": payload.dataset_id,
                "method": payload.method,
                "framework": payload.framework,
                "config": plan.config,
            },
        )
        self.db.add(job)
        self.db.flush()

        run = TrainingRun(
            project_id=payload.project_id,
            base_model_id=payload.base_model_id,
            dataset_id=payload.dataset_id,
            job_id=job.id,
            method=payload.method,
            framework=payload.framework,
            config=plan.config,
            status=RunStatus.QUEUED.value,
        )
        self.db.add(run)
        self.db.flush()

        self.db.add(
            JobEvent(
                job_id=job.id,
                event_type="training.queued",
                message="Fine-tuning işi kalıcı kuyruğa kaydedildi.",
                payload={"training_run_id": run.id, "ready": plan.ready},
            )
        )
        self.db.commit()
        self.db.refresh(job)
        self.db.refresh(run)
        return TrainingRunCreated(
            run=run,
            job=JobRead.model_validate(job).model_dump(mode="json"),
            plan=plan,
            message_tr=(
                "Fine-tuning işi oluşturuldu. Eğitim worker süreci bağlandığında bu job "
                "kuyruktan çalıştırılacak."
            ),
        )

    def attach_knowledge_pack(self, payload: KnowledgePackRequest) -> KnowledgePackResponse:
        model = self.db.get(Model, payload.model_id)
        dataset = self.db.get(Dataset, payload.dataset_id)
        if model is None:
            raise ValueError("Model bulunamadı.")
        if dataset is None:
            raise ValueError("Veri seti bulunamadı.")
        if dataset.row_count <= 0:
            raise ValueError("Boş veri seti bilgi paketi olarak bağlanamaz.")

        manifest = {
            "name": payload.name or f"{model.name} knowledge pack",
            "model": {
                "id": model.id,
                "name": model.name,
                "source": model.source,
                "provider_id": model.provider_id,
                "path": model.path,
            },
            "dataset": self._dataset_knowledge_summary(dataset),
            "training_contract": {
                "mode": "adapter_or_full_finetune_required",
                "statement_tr": (
                    "Bu manifest modele bağlanmış bilgi paketidir. Bilginin ağırlıklara "
                    "işlenmesi için Fine-Tuning job çıktısı veya adapter export gerekir."
                ),
            },
            "preview": dataset.preview if payload.include_full_preview else dataset.preview[:5],
        }
        manifest_bytes = json.dumps(manifest, ensure_ascii=False, indent=2, default=str).encode(
            "utf-8"
        )
        digest = hashlib.sha256(manifest_bytes).hexdigest()
        artifact_dir = storage_path("artifacts") / "knowledge_packs"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = artifact_dir / f"{model.id}_{dataset.id}_{digest[:12]}.json"
        artifact_path.write_bytes(manifest_bytes)

        artifact = Artifact(
            project_id=model.project_id or dataset.project_id,
            owner_type="model",
            owner_id=model.id,
            artifact_type="knowledge_pack",
            path=str(artifact_path),
            size_bytes=len(manifest_bytes),
            checksum=digest,
            metadata_json={
                "model_id": model.id,
                "dataset_id": dataset.id,
                "dataset_name": dataset.name,
                "row_count": dataset.row_count,
                "quality_score": dataset.quality_score,
            },
        )
        self.db.add(artifact)
        self.db.flush()

        metadata = dict(model.metadata_json or {})
        packs = list(metadata.get("knowledge_packs") or [])
        packs.append(
            {
                "artifact_id": artifact.id,
                "artifact_path": str(artifact_path),
                "dataset_id": dataset.id,
                "dataset_name": dataset.name,
                "row_count": dataset.row_count,
                "quality_score": dataset.quality_score,
                "checksum": digest,
            }
        )
        metadata["knowledge_packs"] = packs[-20:]
        model.metadata_json = metadata
        model.analysis = self._append_knowledge_to_analysis(model, dataset, model.analysis)
        self.db.add(model)
        self.db.commit()
        self.db.refresh(artifact)
        self.db.refresh(model)

        return KnowledgePackResponse(
            model_id=model.id,
            dataset_id=dataset.id,
            artifact_id=artifact.id,
            artifact_path=str(artifact_path),
            message_tr=(
                "Bilgi paketi modele bağlandı. Export manifestine dahil edilecek; "
                "ağırlıklara işlemek için fine-tuning job çalıştırın."
            ),
            details={
                "dataset_name": dataset.name,
                "row_count": dataset.row_count,
                "quality_score": dataset.quality_score,
                "checksum": digest,
                "knowledge_pack_count": len(metadata["knowledge_packs"]),
            },
        )

    def cancel_run(self, run_id: str) -> TrainingRun | None:
        run = self.db.get(TrainingRun, run_id)
        if run is None:
            return None
        if run.status in {RunStatus.COMPLETED.value, RunStatus.FAILED.value}:
            return run
        run.status = RunStatus.CANCELLED.value
        if run.job is not None:
            run.job.status = RunStatus.CANCELLED.value
            run.job.current_step = "Fine-tuning işi iptal edildi"
            run.job.progress = 0
            self.db.add(
                JobEvent(
                    job_id=run.job.id,
                    event_type="training.cancelled",
                    message="Fine-tuning işi kullanıcı tarafından iptal edildi.",
                    payload={"training_run_id": run.id},
                )
            )
        self.db.commit()
        self.db.refresh(run)
        return run

    def _estimate_vram_gb(self, model: Model, method: str) -> float:
        if model.size_bytes:
            base_gb = model.size_bytes / (1024**3)
        elif model.parameter_count:
            bytes_per_param = 0.5 if method == "qlora" else 2
            base_gb = (model.parameter_count * bytes_per_param) / (1024**3)
        else:
            base_gb = 4.0
        multiplier = {
            "qlora": 1.6,
            "lora": 2.2,
            "sft": 2.4,
            "dpo": 2.8,
            "orpo": 2.6,
            "kto": 2.6,
            "grpo": 3.0,
            "dapo": 3.2,
            "rlvr": 3.1,
            "sdpo": 2.8,
            "ppo": 3.4,
            "rlhf": 3.6,
            "rlaif": 3.6,
            "full": 4.5,
        }.get(method, 2.0)
        return round(max(2.0, base_gb * multiplier), 2)

    def _dataset_knowledge_summary(self, dataset: Dataset) -> dict[str, object]:
        return {
            "id": dataset.id,
            "name": dataset.name,
            "source_type": dataset.source_type,
            "path": dataset.path,
            "format": dataset.format,
            "task_type": dataset.task_type,
            "row_count": dataset.row_count,
            "average_tokens": dataset.average_tokens,
            "duplicate_ratio": dataset.duplicate_ratio,
            "empty_ratio": dataset.empty_ratio,
            "quality_score": dataset.quality_score,
            "statistics": dataset.statistics,
            "report": dataset.report,
        }

    def _model_knowledge_pack_summary(self, model: Model) -> list[dict[str, object]]:
        metadata = model.metadata_json or {}
        packs = metadata.get("knowledge_packs")
        return packs if isinstance(packs, list) else []

    def _append_knowledge_to_analysis(
        self,
        model: Model,
        dataset: Dataset,
        analysis: dict[str, object] | None,
    ) -> dict[str, object]:
        updated = dict(analysis or {})
        details = dict(updated.get("details") or {})
        details["bagli_bilgi_paketleri"] = self._model_knowledge_pack_summary(model)
        updated["details"] = details
        strengths = list(updated.get("strengths") or [])
        note = f"{dataset.name} veri setinden bilgi paketi bağlı"
        if note not in strengths:
            strengths.append(note)
        updated["strengths"] = strengths
        updated.setdefault(
            "summary_tr",
            f"{model.name} için {dataset.name} kaynaklı bilgi paketi bağlı.",
        )
        return updated

    def _is_apple_silicon_or_linux(self) -> bool:
        hardware = detect_hardware_profile()
        os_name = str(hardware.get("os") or "").lower()
        machine = str(hardware.get("machine") or "").lower()
        return os_name == "linux" or (os_name == "darwin" and machine in {"arm64", "aarch64"})
