from __future__ import annotations

import json
import re
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import quote

from sqlalchemy.orm import Session

from yontai.core.config import get_settings
from yontai.core.paths import storage_path
from yontai.db.models import Model
from yontai.models.metadata import MetadataRecoveryEngine
from yontai.repositories.models import ModelRepository
from yontai.schemas.models import ModelAnalysisRead, ModelCreate, ModelDiscoveryResult, ModelUpdate

PARAMETER_PATTERNS = [
    (re.compile(r"(?P<count>\d+(?:\.\d+)?)\s*b", re.IGNORECASE), 1_000_000_000),
    (re.compile(r"(?P<count>\d+(?:\.\d+)?)\s*m", re.IGNORECASE), 1_000_000),
]
SUPPORTED_MODEL_EXTENSIONS = {".gguf", ".safetensors", ".bin"}


class ModelRegistryService:
    def __init__(self, db: Session) -> None:
        self.repo = ModelRepository(db)

    def list_models(self) -> list[Model]:
        return self.repo.list()

    def get_model(self, model_id: str) -> Model | None:
        return self.repo.get(model_id)

    def register(self, payload: ModelCreate) -> Model:
        metadata = self._compact_metadata(self._load_metadata(payload))
        source_path = self._normalize_path(payload.path)
        existing = self._find_existing(payload.source, source_path, payload.provider_id)
        if existing:
            return existing
        model = Model(
            project_id=payload.project_id,
            name=payload.name.strip(),
            source=payload.source,
            path=source_path,
            provider_id=payload.provider_id,
            model_family=payload.model_family
            or self._infer_family(payload.name, payload.provider_id),
            parameter_count=payload.parameter_count
            or self._infer_parameter_count(payload.name, payload.provider_id, metadata),
            quantization=payload.quantization
            or self._infer_quantization(payload.name, payload.provider_id, metadata),
            context_length=payload.context_length or self._infer_context_length(metadata),
            architecture=payload.architecture or self._infer_architecture(metadata),
            actual_license=payload.actual_license or self._infer_license(metadata),
            user_license_notes=payload.user_license_notes,
            tokenizer=self._infer_tokenizer(source_path, metadata),
            dtype=self._infer_dtype(metadata),
            size_bytes=self._calculate_model_size(source_path),
            metadata_json=metadata,
        )
        model.analysis = self._build_analysis(model)
        return self.repo.add(model)

    def import_uploaded_file(
        self,
        *,
        filename: str,
        file_object: Any,
        project_id: str | None = None,
    ) -> Model:
        suffix = Path(filename).suffix.lower()
        if suffix not in SUPPORTED_MODEL_EXTENSIONS:
            raise ValueError("Desteklenen model dosyaları: .gguf, .safetensors, .bin")
        imports_dir = storage_path("models") / "imported"
        imports_dir.mkdir(parents=True, exist_ok=True)
        target = self._unique_target(imports_dir / Path(filename).name.replace(" ", "_"))
        with target.open("wb") as output:
            shutil.copyfileobj(file_object, output)
        return self.register_local_file(target, project_id=project_id)

    def register_local_file(self, path: Path, project_id: str | None = None) -> Model:
        resolved = path.expanduser().resolve()
        if not resolved.exists() or not resolved.is_file():
            raise ValueError(f"Model dosyası bulunamadı: {resolved}")
        if resolved.suffix.lower() not in SUPPORTED_MODEL_EXTENSIONS:
            raise ValueError("Desteklenen model dosyaları: .gguf, .safetensors, .bin")
        existing = self.repo.get_by_path(str(resolved))
        if existing:
            return existing
        metadata = self._read_model_file_metadata(resolved)
        return self.register(
            ModelCreate(
                project_id=project_id,
                name=resolved.stem,
                source="local",
                path=str(resolved),
                model_family=self._infer_family(resolved.name, None),
                parameter_count=self._infer_parameter_count(resolved.name, None, metadata),
                quantization=self._infer_quantization(resolved.name, None, metadata),
                architecture=self._infer_architecture(metadata),
                context_length=self._infer_context_length(metadata),
                actual_license=self._infer_license(metadata),
            )
        )

    def scan_folder(self, folder_path: str, project_id: str | None = None) -> ModelDiscoveryResult:
        folder = Path(folder_path).expanduser().resolve()
        if not folder.exists() or not folder.is_dir():
            raise ValueError(f"Klasör bulunamadı: {folder}")
        imported: list[Model] = []
        skipped: list[str] = []
        errors: list[str] = []
        for file_path in sorted(folder.rglob("*")):
            if (
                not file_path.is_file()
                or file_path.suffix.lower() not in SUPPORTED_MODEL_EXTENSIONS
            ):
                continue
            try:
                before = self.repo.get_by_path(str(file_path.resolve()))
                model = self.register_local_file(file_path, project_id=project_id)
                if before:
                    skipped.append(str(file_path))
                else:
                    imported.append(model)
            except ValueError as exc:
                errors.append(f"{file_path}: {exc}")
        return ModelDiscoveryResult(imported=imported, skipped=skipped, errors=errors)

    def discover_ollama(self, project_id: str | None = None) -> ModelDiscoveryResult:
        imported: list[Model] = []
        skipped: list[str] = []
        errors: list[str] = []
        try:
            import os
            env = os.environ.copy()
            env["PATH"] = f"/usr/local/bin:/opt/homebrew/bin:{env.get('PATH', '')}"
            completed = subprocess.run(
                ["ollama", "list"],
                check=True,
                capture_output=True,
                text=True,
                timeout=8,
                env=env,
            )
        except FileNotFoundError as exc:
            raise ValueError(
                "Ollama komutu bulunamadı. Ollama kurulu değil veya PATH içinde değil."
            ) from exc
        except subprocess.CalledProcessError as exc:
            raise ValueError(f"Ollama listeleme başarısız oldu: {exc.stderr.strip()}") from exc
        except subprocess.TimeoutExpired as exc:
            raise ValueError("Ollama listeleme zaman aşımına uğradı.") from exc

        for name in self._parse_ollama_list(completed.stdout):
            try:
                existing = self.repo.get_by_provider("ollama", name)
                model = self.register(
                    ModelCreate(
                        project_id=project_id,
                        name=name,
                        source="ollama",
                        provider_id=name,
                    )
                )
                if existing:
                    self.refresh_metadata(existing.id)
                    skipped.append(name)
                else:
                    imported.append(model)
            except ValueError as exc:
                errors.append(f"{name}: {exc}")
        return ModelDiscoveryResult(imported=imported, skipped=skipped, errors=errors)

    def register_huggingface(self, repository_id: str, project_id: str | None = None) -> Model:
        metadata = self._fetch_huggingface_metadata(repository_id)
        return self.register(
            ModelCreate(
                project_id=project_id,
                name=str(metadata.get("modelId") or repository_id),
                source="huggingface",
                provider_id=repository_id,
                model_family=self._infer_family(repository_id, repository_id),
                parameter_count=self._infer_parameter_count(repository_id, repository_id, metadata),
                quantization=self._infer_quantization(repository_id, repository_id, metadata),
                architecture=self._infer_architecture(metadata),
                context_length=self._infer_context_length(metadata),
                actual_license=self._infer_license(metadata),
            )
        )

    def update_model(self, model_id: str, payload: ModelUpdate) -> Model | None:
        model = self.repo.get(model_id)
        if model is None:
            return None
        if payload.user_license_notes is not None:
            model.user_license_notes = payload.user_license_notes
        self.repo.save(model)
        return model

    def refresh_metadata(self, model_id: str) -> Model | None:
        model = self.repo.get(model_id)
        if model is None:
            return None

        recovered: dict[str, Any] = {}
        if model.source == "local" and model.path:
            recovered.update(MetadataRecoveryEngine.recover_local(Path(model.path)))
        elif model.source == "ollama" and model.provider_id:
            recovered.update(self._read_ollama_metadata(model.provider_id))
            recovered.update(MetadataRecoveryEngine.recover_ollama(model.provider_id))
        elif model.source == "huggingface" and model.provider_id:
            recovered.update(self._fetch_huggingface_metadata(model.provider_id))
            recovered.update(MetadataRecoveryEngine.recover_huggingface(model.provider_id))

        model.metadata_json = self._compact_metadata({**(model.metadata_json or {}), **recovered})
        model.model_family = model.model_family or self._infer_family(model.name, model.provider_id)
        model.parameter_count = model.parameter_count or self._infer_parameter_count(
            model.name,
            model.provider_id,
            model.metadata_json,
        )
        model.quantization = model.quantization or self._infer_quantization(
            model.name,
            model.provider_id,
            model.metadata_json,
        )
        model.context_length = model.context_length or self._infer_context_length(
            model.metadata_json,
        )
        model.architecture = model.architecture or self._infer_architecture(model.metadata_json)
        model.actual_license = model.actual_license or self._infer_license(model.metadata_json)
        model.tokenizer = model.tokenizer or self._infer_tokenizer(model.path, model.metadata_json)
        model.dtype = model.dtype or self._infer_dtype(model.metadata_json)
        model.size_bytes = model.size_bytes or self._calculate_model_size(model.path)
        model.analysis = self._build_analysis(model)
        return self.repo.save(model)

    def analyze(self, model_id: str) -> ModelAnalysisRead | None:
        model = self.repo.get(model_id)
        if model is None:
            return None
        model.analysis = self._build_analysis(model)
        self.repo.save(model)
        return ModelAnalysisRead(
            model_id=model.id,
            summary_tr=str(model.analysis["summary_tr"]),
            strengths=list(model.analysis["strengths"]),
            weaknesses=list(model.analysis["weaknesses"]),
            details=dict(model.analysis["details"]),
            memory_requirements=dict(model.analysis["memory_requirements"]),
        )

    def delete(self, model_id: str) -> bool:
        model = self.repo.get(model_id)
        if model is None:
            return False
        self.repo.delete(model)
        return True

    def _load_metadata(self, payload: ModelCreate) -> dict[str, Any]:
        metadata: dict[str, Any] = {"provider_id": payload.provider_id, "source": payload.source}
        if payload.source == "local" and payload.path:
            metadata.update(self._read_local_metadata(Path(payload.path).expanduser()))
            metadata.update(MetadataRecoveryEngine.recover_local(Path(payload.path).expanduser()))
        elif payload.source == "ollama" and payload.provider_id:
            metadata.update(self._read_ollama_metadata(payload.provider_id))
            metadata.update(MetadataRecoveryEngine.recover_ollama(payload.provider_id))
        elif payload.source == "huggingface" and payload.provider_id:
            metadata.update(self._fetch_huggingface_metadata(payload.provider_id))
            metadata.update(MetadataRecoveryEngine.recover_huggingface(payload.provider_id))
        return metadata

    def _find_existing(
        self, source: str, source_path: str | None, provider_id: str | None
    ) -> Model | None:
        if source_path:
            return self.repo.get_by_path(source_path)
        if provider_id:
            return self.repo.get_by_provider(source, provider_id)
        return None

    def _read_local_metadata(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            raise ValueError(f"Model yolu bulunamadı: {path}")
        config_path = path / "config.json" if path.is_dir() else path
        tokenizer_path = path / "tokenizer_config.json" if path.is_dir() else None
        metadata: dict[str, Any] = {"local_path": str(path)}
        if config_path.exists() and config_path.name.endswith(".json"):
            with config_path.open("r", encoding="utf-8") as file:
                loaded = json.load(file)
            if isinstance(loaded, dict):
                metadata.update(loaded)
        if tokenizer_path and tokenizer_path.exists():
            with tokenizer_path.open("r", encoding="utf-8") as file:
                tokenizer_config = json.load(file)
            if isinstance(tokenizer_config, dict):
                metadata["tokenizer_config"] = tokenizer_config
        return metadata

    def _read_model_file_metadata(self, path: Path) -> dict[str, Any]:
        return {
            "local_path": str(path),
            "file_name": path.name,
            "file_extension": path.suffix.lower(),
            "file_size_bytes": path.stat().st_size,
            "format": path.suffix.lower().lstrip("."),
        }

    def _read_ollama_metadata(self, name: str) -> dict[str, Any]:
        settings = get_settings()
        request = urllib.request.Request(
            f"{settings.ollama_host.rstrip('/')}/api/show",
            data=json.dumps({"name": name}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=2) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if not isinstance(payload, dict):
                return {"ollama_name": name}
            return self._compact_metadata({"ollama_name": name, **payload})
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            return {"ollama_name": name, "ollama_status": "unavailable"}

    def _compact_metadata(self, metadata: dict[str, Any]) -> dict[str, Any]:
        compact: dict[str, Any] = {}
        allowed_keys = {
            "architecture",
            "capabilities",
            "config_status",
            "context_length",
            "details",
            "family",
            "file_extension",
            "file_hash",
            "file_name",
            "file_size_bytes",
            "format",
            "license",
            "local_path",
            "max_position_embeddings",
            "modelId",
            "model_info",
            "model_max_length",
            "model_type",
            "modified_at",
            "ollama_name",
            "ollama_status",
            "parameter_count",
            "parameter_size",
            "parameters",
            "provider_id",
            "quantization",
            "source",
            "template",
            "tokenizer",
            "tokenizer_config",
            "torch_dtype",
        }
        for key, value in metadata.items():
            if key not in allowed_keys:
                continue
            if key == "model_info" and isinstance(value, dict):
                compact[key] = {
                    info_key: info_value
                    for info_key, info_value in value.items()
                    if not isinstance(info_value, list) and "tensor" not in info_key.lower()
                }
                continue
            if key == "license" and isinstance(value, str):
                compact[key] = value.strip().splitlines()[0][:160] if value.strip() else value
                continue
            if key == "template" and isinstance(value, str):
                compact[key] = value[:4000]
                continue
            compact[key] = value
        return compact

    def _fetch_huggingface_metadata(self, repository_id: str) -> dict[str, Any]:
        encoded_id = quote(repository_id, safe="/")
        metadata: dict[str, Any] = {"provider_id": repository_id, "source": "huggingface"}
        api_url = f"https://huggingface.co/api/models/{encoded_id}"
        try:
            with urllib.request.urlopen(api_url, timeout=8) as response:
                api_payload = json.loads(response.read().decode("utf-8"))
            if isinstance(api_payload, dict):
                metadata.update(api_payload)
        except urllib.error.HTTPError as exc:
            raise ValueError(f"HuggingFace modeli bulunamadı: {repository_id}") from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise ValueError(f"HuggingFace metadata alınamadı: {repository_id}") from exc

        config_url = f"https://huggingface.co/{encoded_id}/resolve/main/config.json"
        try:
            with urllib.request.urlopen(config_url, timeout=8) as response:
                config_payload = json.loads(response.read().decode("utf-8"))
            if isinstance(config_payload, dict):
                metadata.update(config_payload)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            metadata["config_status"] = "unavailable"
        return metadata

    def _parse_ollama_list(self, output: str) -> list[str]:
        names: list[str] = []
        for line in output.splitlines():
            stripped = line.strip()
            if not stripped or stripped.lower().startswith("name"):
                continue
            name = stripped.split()[0]
            if name:
                names.append(name)
        return names

    def _unique_target(self, target: Path) -> Path:
        if not target.exists():
            return target
        stem = target.stem
        suffix = target.suffix
        for index in range(1, 10_000):
            candidate = target.with_name(f"{stem}_{index}{suffix}")
            if not candidate.exists():
                return candidate
        raise ValueError("Benzersiz dosya adı üretilemedi.")

    def _normalize_path(self, path: str | None) -> str | None:
        return str(Path(path).expanduser().resolve()) if path else None

    def _infer_family(self, name: str, provider_id: str | None) -> str | None:
        text = f"{name} {provider_id or ''}".lower()
        families = ["llama", "mistral", "gemma", "qwen", "deepseek", "phi", "bert", "t5"]
        for family in families:
            if family in text:
                return family
        return None

    def _infer_parameter_count(
        self, name: str, provider_id: str | None, metadata: dict[str, Any]
    ) -> int | None:
        for key in ("parameter_count", "num_parameters", "parameters"):
            value = metadata.get(key)
            if isinstance(value, int):
                return value
            if isinstance(value, str):
                parsed = self._parse_parameter_text(value)
                if parsed:
                    return parsed
        return self._parse_parameter_text(f"{name} {provider_id or ''}")

    def _parse_parameter_text(self, text: str) -> int | None:
        for pattern, multiplier in PARAMETER_PATTERNS:
            match = pattern.search(text.replace("-", " "))
            if match:
                return int(float(match.group("count")) * multiplier)
        return None

    def _infer_quantization(
        self, name: str, provider_id: str | None, metadata: dict[str, Any]
    ) -> str | None:
        text = f"{name} {provider_id or ''} {json.dumps(metadata, ensure_ascii=False)}".lower()
        for marker in ("q2", "q3", "q4", "q5", "q6", "q8", "int8", "int4", "fp16", "bf16"):
            if marker in text:
                return marker.upper()
        return None

    def _infer_context_length(self, metadata: dict[str, Any]) -> int | None:
        for key in ("max_position_embeddings", "n_ctx", "context_length", "model_max_length"):
            value = metadata.get(key)
            if isinstance(value, int):
                return value
        tokenizer = metadata.get("tokenizer_config")
        if isinstance(tokenizer, dict) and isinstance(tokenizer.get("model_max_length"), int):
            return int(tokenizer["model_max_length"])
        return None

    def _infer_architecture(self, metadata: dict[str, Any]) -> str | None:
        architectures = metadata.get("architectures")
        if isinstance(architectures, list) and architectures:
            return str(architectures[0])
        for key in ("architecture", "model_type"):
            if metadata.get(key):
                return str(metadata[key])
        details = metadata.get("details")
        if isinstance(details, dict) and details.get("family"):
            return str(details["family"])
        return None

    def _infer_license(self, metadata: dict[str, Any]) -> str | None:
        for key in ("license", "license_name"):
            if metadata.get(key):
                return str(metadata[key]).strip().splitlines()[0][:160]
        return None

    def _infer_tokenizer(self, source_path: str | None, metadata: dict[str, Any]) -> str | None:
        if source_path:
            path = Path(source_path)
            if path.is_dir() and (path / "tokenizer.json").exists():
                return str(path / "tokenizer.json")
        if "tokenizer_config" in metadata:
            return "tokenizer_config.json"
        return None

    def _infer_dtype(self, metadata: dict[str, Any]) -> str | None:
        value = metadata.get("torch_dtype") or metadata.get("dtype")
        return str(value) if value else None

    def _calculate_model_size(self, source_path: str | None) -> int | None:
        if not source_path:
            return None
        path = Path(source_path)
        if not path.exists():
            return None
        if path.is_file():
            return path.stat().st_size
        total = 0
        for file_path in path.rglob("*"):
            if file_path.is_file():
                total += file_path.stat().st_size
        return total

    def _build_analysis(self, model: Model) -> dict[str, object]:
        params = model.parameter_count
        memory = self._estimate_memory(params, model.quantization, model.size_bytes)
        strengths, weaknesses = self._summarize_capabilities(model)
        capabilities = self._estimate_capabilities(model)
        target_fields = [
            ("Parametre Sayısı", params),
            ("Mimari", model.architecture),
            ("Context Length", model.context_length),
            ("Quantization", model.quantization),
            ("Tokenizer", model.tokenizer),
            ("Dosya Boyutu", model.size_bytes),
            ("Kaynak", model.source),
            ("Model Ailesi", model.model_family),
            ("Lisans", model.actual_license),
        ]
        
        filled = [name for name, val in target_fields if val is not None]
        missing = [name for name, val in target_fields if val is None]
        total_fields = len(target_fields)
        
        coverage = {
            "quality_score": int((len(filled) / total_fields) * 100) if total_fields > 0 else 0,
            "filled_count": len(filled),
            "total_count": total_fields,
            "missing_fields": missing,
        }

        details = {
            "parametre_sayisi": params,
            "mimari": model.architecture,
            "context_length": model.context_length,
            "quantization": model.quantization,
            "tokenizer": model.tokenizer,
            "boyut_byte": model.size_bytes,
            "kaynak": model.source,
            "model_ailesi": model.model_family,
            "actual_license": model.actual_license,
            "user_license_notes": model.user_license_notes,
            "kaynak_yolu": model.path,
            "provider_id": model.provider_id,
            "capabilities": capabilities,
            "metadata_coverage": coverage,
        }
        return {
            "summary_tr": self._summary_sentence(model, memory),
            "strengths": strengths,
            "weaknesses": weaknesses,
            "details": details,
            "memory_requirements": memory,
        }

    def _estimate_capabilities(self, model: Model) -> dict[str, int]:
        family = (model.model_family or "").lower()
        params = model.parameter_count or 0
        context = model.context_length or 0
        
        # Base scores
        scores = {
            "Türkçe": 40,
            "İngilizce": 70,
            "Kodlama": 30,
            "Muhakeme": 40,
            "Uzun Belge İşleme": 30,
            "Araç Kullanımı": 20,
            "RAG Uyumu": 40
        }
        
        if params > 7_000_000_000:
            scores["Muhakeme"] += 30
            scores["Kodlama"] += 20
            scores["İngilizce"] += 15
        elif params > 3_000_000_000:
            scores["Muhakeme"] += 15
            
        if context >= 8_000:
            scores["Uzun Belge İşleme"] += 20
            scores["RAG Uyumu"] += 15
        if context >= 32_000:
            scores["Uzun Belge İşleme"] += 30
            scores["RAG Uyumu"] += 20
            
        if "qwen" in family:
            scores["Türkçe"] += 35
            scores["Kodlama"] += 25
            scores["Araç Kullanımı"] += 30
        elif "llama" in family:
            scores["Muhakeme"] += 20
            scores["İngilizce"] += 10
        elif "mistral" in family:
            scores["Araç Kullanımı"] += 25
            scores["İngilizce"] += 10
        elif "gemma" in family:
            scores["Muhakeme"] += 10
            scores["Türkçe"] += 10
        elif "trendyol" in family or "kanarya" in family:
            scores["Türkçe"] += 45
            
        # Cap all scores at 100 and min 0
        return {k: min(100, max(0, v)) for k, v in scores.items()}

    def _estimate_memory(
        self, parameter_count: int | None, quantization: str | None, size_bytes: int | None
    ) -> dict[str, object]:
        if size_bytes:
            base_gb = size_bytes / 1_073_741_824
        elif parameter_count:
            bytes_per_param = 2.0
            if quantization:
                q = quantization.lower()
                if "q4" in q or "int4" in q:
                    bytes_per_param = 0.65
                elif "q8" in q or "int8" in q:
                    bytes_per_param = 1.05
                elif "bf16" in q or "fp16" in q:
                    bytes_per_param = 2.0
            base_gb = parameter_count * bytes_per_param / 1_073_741_824
        else:
            return {
                "durum": "bilinmiyor",
                "tahmini_ram_gb": None,
                "not": "Parametre veya dosya boyutu yok.",
            }
        inference_gb = round(base_gb * 1.25 + 1.0, 2)
        training_gb = round(max(inference_gb * 2.5, inference_gb + 4), 2)
        return {
            "durum": "hesaplandi",
            "tahmini_inference_ram_gb": inference_gb,
            "tahmini_lora_ram_gb": training_gb,
            "hesaplama": "Yerel dosya boyutu veya parametre sayısından yaklaşık tahmin.",
        }

    def _summarize_capabilities(self, model: Model) -> tuple[list[str], list[str]]:
        strengths: list[str] = []
        weaknesses: list[str] = []
        family = (model.model_family or "").lower()
        params = model.parameter_count or 0
        context = model.context_length or 0

        if family in {"deepseek", "qwen", "llama"}:
            strengths.append("Kod üretimi ve teknik talimat takibi")
        if params >= 7_000_000_000:
            strengths.append("Genel muhakeme ve çok adımlı cevap üretimi")
        if context >= 16_000:
            strengths.append("Uzun bağlamlı belge işleme")
        if model.quantization:
            strengths.append("Tüketici donanımında daha düşük bellek kullanımı")

        if params and params < 3_000_000_000:
            weaknesses.append("Karmaşık muhakeme ve uzun cevap tutarlılığı")
        if not context or context < 8_000:
            weaknesses.append("Uzun belge analizi")
        if family not in {"qwen", "llama", "mistral", "gemma", "deepseek"}:
            weaknesses.append("Türkçe talimat performansı model ailesine göre doğrulanmalı")
        if not model.actual_license:
            weaknesses.append("Lisans bilgisi eksik olduğu için ticari kullanım riski")

        return strengths or ["Temel yerel çıkarım ve deneysel kullanım"], weaknesses or [
            "Belirgin zayıf yön tespit edilmedi"
        ]

    def _summary_sentence(self, model: Model, memory: dict[str, object]) -> str:
        family = model.model_family or "bilinmeyen aile"
        source = {"local": "yerel", "huggingface": "HuggingFace", "ollama": "Ollama"}.get(
            model.source, model.source
        )
        ram = memory.get("tahmini_inference_ram_gb")
        ram_text = f" Yaklaşık çıkarım bellek ihtiyacı {ram} GB." if ram else ""
        return (
            f"{model.name}, {source} kaynaklı {family} tabanlı bir model olarak kayıtlı.{ram_text}"
        )
