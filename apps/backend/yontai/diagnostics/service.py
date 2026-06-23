from sqlalchemy.orm import Session

from yontai.db.models import Model, utc_now
from yontai.repositories.datasets import DatasetRepository
from yontai.repositories.models import ModelRepository
from yontai.schemas.doctor import DoctorDiagnosis


class DiagnosticService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.models = ModelRepository(db)
        self.datasets = DatasetRepository(db)

    def diagnose_model_dataset(self, model_id: str, dataset_id: str) -> DoctorDiagnosis | None:
        model = self.models.get(model_id)
        dataset = self.datasets.get(dataset_id)
        if model is None or dataset is None:
            return None

        reasons: list[str] = []
        recommendations: list[str] = []
        score = 0
        confidence = 100

        # Eksik Metadata kontrolü
        missing_metadata = []
        if not model.parameter_count:
            missing_metadata.append("Parametre sayısı")
        if not model.context_length:
            missing_metadata.append("Context Length")
        if missing_metadata:
            confidence -= len(missing_metadata) * 20
            score += 15
            reasons.append(f"Eksik metadata: {', '.join(missing_metadata)}.")
            recommendations.append(
                "Daha doğru analiz için eksik metadata'ları giderin "
                "(örn: HuggingFace entegrasyonu kullanın)."
            )

        # 1. Dataset büyüklüğü ve model kapasitesi
        if model.parameter_count:
            if model.parameter_count < 3_000_000_000 and dataset.row_count > 100_000:
                score += 30
                reasons.append(
                    f"Model kapasitesi ({model.parameter_count / 1_000_000_000:.1f}B), "
                    f"veri setinin karmaşıklığı ({dataset.row_count} örnek) için yetersiz "
                    "kalabilir. Underfitting riski yüksek."
                )
                recommendations.append("Daha büyük bir base model kullanın (örn: 7B+).")
            elif model.parameter_count >= 13_000_000_000 and dataset.row_count < 5000:
                score += 25
                reasons.append(
                    f"Model çok büyük ({model.parameter_count / 1_000_000_000:.1f}B) "
                    f"ancak veri seti nispeten küçük ({dataset.row_count} örnek). "
                    "Catastrophic forgetting ve overfitting riski yüksek."
                )
                recommendations.append(
                    "Daha küçük bir model (örn: 3B/7B) kullanın veya LoRA rank değerini "
                    "(r=4/8) düşük tutarak sınırlı eğitim yapın."
                )
            elif model.parameter_count >= 7_000_000_000 and dataset.row_count < 1000:
                score += 20
                reasons.append(
                    f"Orta-büyük model ({model.parameter_count / 1_000_000_000:.1f}B) "
                    f"için {dataset.row_count} örnek yetersiz kalabilir."
                )
                recommendations.append("En az 5000-10000 kaliteli örnek hedefleyin.")

        if dataset.row_count < 500:
            score += 35
            reasons.append(
                f"Veri seti yalnızca {dataset.row_count} örnek içeriyor. "
                "Her model boyutu için aşırı ezberleme riski yüksektir."
            )
            recommendations.append("Minimum 5000 kaliteli örnek hedefleyin.")

        # 2. Context Overflow
        if model.context_length and dataset.average_tokens > model.context_length:
            score += 40
            reasons.append(
                f"Veri seti ortalama token sayısı ({dataset.average_tokens:.0f}), "
                f"modelin context uzunluğunu ({model.context_length}) aşıyor. "
                "Context overflow riski."
            )
            recommendations.append(
                "Uzun örnekleri parçalayın veya context limitini artıran bir model "
                "(örn: 32k/128k) seçin."
            )
        elif model.context_length and dataset.average_tokens > model.context_length * 0.75:
            score += 20
            reasons.append("Ortalama örnek uzunluğu model context limitine çok yakın.")
            recommendations.append(
                "Context taşmalarına karşı padding/truncation ayarlarını kontrol edin."
            )

        # 3. Dil Uyumsuzluğu
        dataset_lang = dataset.statistics.get("dominant_language", "tr")
        family = (model.model_family or "").lower()
        if dataset_lang == "tr" and family not in ["qwen", "gemma", "trendyol", "kanarya"]:
            score += 20
            reasons.append(
                "Veri seti dili (Türkçe) ile modelin öncelikli dilleri arasında "
                "uyumsuzluk olabilir."
            )
            recommendations.append("Türkçe veya çok dilli (Qwen, Trendyol) modelleri tercih edin.")

        # 4. Tekrar Oranı (Ezberleme Riski)
        if dataset.duplicate_ratio >= 0.3:
            score += 35
            reasons.append(
                f"Tekrar oranı %{dataset.duplicate_ratio * 100:.1f} seviyesinde. "
                "Aşırı uyum ve ezberleme riski çok yüksek."
            )
            recommendations.append("Tekrar eden (duplicate) kayıtları veri setinden temizleyin.")
        elif dataset.duplicate_ratio > 0.1:
            score += 25
            reasons.append(f"Tekrar oranı %{dataset.duplicate_ratio * 100:.1f}.")
            recommendations.append("Veri setinde çeşitliliği artırın.")

        if dataset.empty_ratio > 0.05:
            score += 15
            reasons.append(f"Boş kayıt oranı %{dataset.empty_ratio * 100:.1f}.")
            recommendations.append("Boş veya eksik örnekleri eğitimden önce temizleyin.")

        if not reasons:
            reasons.append("Model ve veri seti arasında belirgin uyumsuzluk bulunmadı.")
            recommendations.append("Model fine-tuning işlemine hazır görünüyor.")

        confidence = max(0, min(100, confidence))
        risk_level = "Yüksek" if score >= 50 else "Orta" if score >= 25 else "Düşük"
        impact = (
            "Düşük model başarımı"
            if score >= 50
            else "Beklenmeyen çıktı kalitesi"
            if score >= 25
            else "Optimum sonuç"
        )
        summary = (
            f"Risk seviyesi {risk_level}. Güven skoru: %{confidence}. "
            f"En önemli neden: {reasons[0]}"
        )
        return DoctorDiagnosis(
            risk_level=risk_level,
            confidence_score=confidence,
            reasons=reasons,
            recommendations=recommendations,
            expected_impact=impact,
            evidence={
                "dataset_sample_count": dataset.row_count,
                "duplicate_ratio": dataset.duplicate_ratio,
                "average_tokens": dataset.average_tokens,
                "model_context_length": model.context_length,
                "model_parameter_count": model.parameter_count,
                "risk_score": score,
                "confidence_score": confidence,
            },
            summary_tr=summary,
        )

    def validate_dataset(self, dataset_id: str) -> dict[str, object] | None:
        dataset = self.datasets.get(dataset_id)
        if dataset is None:
            return None

        checks: list[dict[str, object]] = []
        checks.append(
            {
                "name": "Örnek sayısı",
                "status": "pass" if dataset.row_count >= 500 else "warning",
                "message": (
                    f"{dataset.row_count} örnek var."
                    if dataset.row_count >= 500
                    else f"{dataset.row_count} örnek düşük; 5000+ hedefleyin."
                ),
            }
        )
        checks.append(
            {
                "name": "Tekrar oranı",
                "status": "pass" if dataset.duplicate_ratio <= 0.1 else "fail",
                "message": f"Tekrar oranı %{dataset.duplicate_ratio * 100:.1f}.",
            }
        )
        checks.append(
            {
                "name": "Boş kayıt",
                "status": "pass" if dataset.empty_ratio <= 0.05 else "fail",
                "message": f"Boş kayıt oranı %{dataset.empty_ratio * 100:.1f}.",
            }
        )
        checks.append(
            {
                "name": "Token dağılımı",
                "status": "pass" if dataset.average_tokens >= 8 else "warning",
                "message": f"Ortalama token: {dataset.average_tokens:.1f}.",
            }
        )
        failed = sum(1 for item in checks if item["status"] == "fail")
        warnings = sum(1 for item in checks if item["status"] == "warning")
        report = dict(dataset.report or {})
        report["validation_2026"] = {
            "checks": checks,
            "failed": failed,
            "warnings": warnings,
            "status": "fail" if failed else "warning" if warnings else "pass",
        }
        dataset.report = report
        self.datasets.save(dataset)
        return report["validation_2026"]

    def ai_self_diagnosis(self, model_id: str, dataset_id: str) -> dict[str, object] | None:
        model = self.models.get(model_id)
        diagnosis = self.diagnose_model_dataset(model_id, dataset_id)
        if model is None or diagnosis is None:
            return None

        next_actions = []
        if any("metadata" in reason.lower() for reason in diagnosis.reasons):
            next_actions.append("Metadata Tamamla")
        duplicate_ratio = diagnosis.evidence.get("duplicate_ratio", 0)
        if duplicate_ratio and duplicate_ratio > 0.1:
            next_actions.append("Tekrarları Temizle")
        if diagnosis.evidence.get("dataset_sample_count", 0) < 5000:
            next_actions.append("Public veri seti veya doküman tabanlı ek veri ile çoğalt")

        analysis = dict(model.analysis or {})
        details = dict(analysis.get("details") or {})
        details["ai_self_diagnosis_2026"] = {
            "risk_level": diagnosis.risk_level,
            "confidence_score": diagnosis.confidence_score,
            "next_actions": next_actions,
            "evidence": diagnosis.evidence,
        }
        analysis["details"] = details
        weaknesses = list(analysis.get("weaknesses") or [])
        for reason in diagnosis.reasons[:3]:
            if reason not in weaknesses:
                weaknesses.append(reason)
        analysis["weaknesses"] = weaknesses
        model.analysis = analysis
        self.models.save(model)
        return details["ai_self_diagnosis_2026"]

    def trace_analysis(
        self,
        model_id: str,
        dataset_id: str | None = None,
    ) -> dict[str, object] | None:
        model = self.models.get(model_id)
        dataset = self.datasets.get(dataset_id) if dataset_id else None
        if model is None:
            return None

        context_length = model.context_length or 0
        average_tokens = dataset.average_tokens if dataset is not None else 0
        bottlenecks: list[str] = []
        if not model.context_length:
            bottlenecks.append("Context length metadata eksik; truncation riski ölçülemiyor.")
        elif dataset is not None and average_tokens > context_length * 0.75:
            bottlenecks.append(
                "Dataset örnekleri context limitine yakın; chunking/truncation gerekli."
            )
        if not model.quantization:
            bottlenecks.append("Quantization metadata eksik; bellek tahmini düşük güvenilirlikte.")
        if model.source == "ollama" and not model.provider_id:
            bottlenecks.append("Ollama provider id eksik; inference trace çalıştırılamaz.")

        result = {
            "trace_type": "static_inference_trace",
            "model_id": model.id,
            "dataset_id": dataset.id if dataset is not None else None,
            "bottlenecks": bottlenecks or ["Belirgin statik trace darboğazı tespit edilmedi."],
            "recommendations": [
                "Benchmark öncesi max token değerini 128-256 arasında tutun.",
                "Uzun dokümanları 512-1024 token arası parçalara bölün.",
                "Aynı anda tek Ollama modelini bellekte tutarak test edin.",
            ],
        }
        metadata = dict(model.metadata_json or {})
        metadata["trace_analysis_2026"] = result
        model.metadata_json = metadata
        self.models.save(model)
        return result

    def create_doctor_approved_model(
        self,
        model_id: str,
        dataset_id: str,
    ) -> dict[str, object] | None:
        model = self.models.get(model_id)
        dataset = self.datasets.get(dataset_id)
        if model is None or dataset is None:
            return None

        diagnosis = self.diagnose_model_dataset(model_id, dataset_id)
        validation = self.validate_dataset(dataset_id)
        self_diagnosis = self.ai_self_diagnosis(model_id, dataset_id)
        trace = self.trace_analysis(model_id, dataset_id)
        if diagnosis is None:
            return None

        approved_at = utc_now().isoformat()
        approval_manifest = {
            "variant_kind": "doctor_approved",
            "approved_at": approved_at,
            "parent_model_id": model.id,
            "source_dataset_id": dataset.id,
            "source_dataset_name": dataset.name,
            "weights_modified": False,
            "weights_note_tr": (
                "Bu kayıt model ağırlıklarını değiştirmez. Doctor analizleri, metadata ve "
                "veri kalitesi manifesti modele bağlanır. Bilginin ağırlıklara işlenmesi için "
                "Fine-Tuning Studio'da eğitim/adaptor üretimi çalıştırılmalıdır."
            ),
            "diagnosis": diagnosis.model_dump(mode="json"),
            "validation": validation or {},
            "self_diagnosis": self_diagnosis or {},
            "trace_analysis": trace or {},
        }

        metadata = dict(model.metadata_json or {})
        doctor_history = list(metadata.get("doctor_approvals") or [])
        doctor_history.append(approval_manifest)
        metadata["doctor_approval_2026"] = approval_manifest
        metadata["doctor_approvals"] = doctor_history[-10:]

        analysis = dict(model.analysis or {})
        strengths = list(analysis.get("strengths") or [])
        for item in [
            "Doctor 2026 kontrollerinden geçirilmiş model kaydı",
            "Veri validasyonu, self-diagnosis ve trace analizi manifestte kayıtlı",
        ]:
            if item not in strengths:
                strengths.append(item)
        weaknesses = list(analysis.get("weaknesses") or [])
        for reason in diagnosis.reasons[:3]:
            if reason not in weaknesses:
                weaknesses.append(reason)
        details = dict(analysis.get("details") or {})
        details["doctor_approval_2026"] = approval_manifest
        analysis.update(
            {
                "summary_tr": (
                    f"{model.name} için Doctor onaylı varyant oluşturuldu. "
                    f"Risk seviyesi: {diagnosis.risk_level}. Bu kayıt ağırlık değil, "
                    "analiz ve iyileştirme manifesti taşır."
                ),
                "strengths": strengths,
                "weaknesses": weaknesses,
                "details": details,
            }
        )

        approved_model = Model(
            project_id=model.project_id,
            name=f"{model.name} · Doctor Onaylı",
            source=model.source,
            path=model.path,
            provider_id=model.provider_id,
            model_family=model.model_family,
            parameter_count=model.parameter_count,
            quantization=model.quantization,
            context_length=model.context_length,
            architecture=model.architecture,
            actual_license=model.actual_license,
            user_license_notes=model.user_license_notes,
            tokenizer=model.tokenizer,
            dtype=model.dtype,
            size_bytes=model.size_bytes,
            metadata_json=metadata,
            analysis=analysis,
        )
        approved_model = self.models.add(approved_model)
        return {
            "model_id": approved_model.id,
            "model_name": approved_model.name,
            "parent_model_id": model.id,
            "dataset_id": dataset.id,
            "risk_level": diagnosis.risk_level,
            "weights_modified": False,
            "approved_at": approved_at,
        }
