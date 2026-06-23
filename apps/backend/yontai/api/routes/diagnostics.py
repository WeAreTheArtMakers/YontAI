from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from yontai.datasets.service import DatasetRegistryService
from yontai.db.session import get_db
from yontai.diagnostics.service import DiagnosticService
from yontai.models.service import ModelRegistryService
from yontai.schemas.doctor import (
    DoctorDiagnosis,
    DoctorFixRequest,
    DoctorFixResponse,
    DoctorRequest,
)

router = APIRouter()


@router.get("/runs")
def list_diagnostic_runs() -> list[dict[str, object]]:
    return []


@router.post("/doctor", response_model=DoctorDiagnosis)
def run_model_doctor(payload: DoctorRequest, db: Session = Depends(get_db)) -> DoctorDiagnosis:
    diagnosis = DiagnosticService(db).diagnose_model_dataset(payload.model_id, payload.dataset_id)
    if diagnosis is None:
        raise HTTPException(status_code=404, detail="Model veya veri seti bulunamadı.")
    return diagnosis


@router.post("/doctor/fix", response_model=DoctorFixResponse)
def apply_doctor_fix(
    payload: DoctorFixRequest,
    db: Session = Depends(get_db),
) -> DoctorFixResponse:
    if payload.action == "fetch_metadata":
        if not payload.model_id:
            raise HTTPException(status_code=400, detail="model_id zorunludur.")
        model = ModelRegistryService(db).refresh_metadata(payload.model_id)
        if model is None:
            raise HTTPException(status_code=404, detail="Model bulunamadı.")
        return DoctorFixResponse(
            action=payload.action,
            status="completed",
            message_tr="Model metadata bilgileri güncellendi ve analiz yeniden üretildi.",
            changed=True,
            details={
                "model_id": model.id,
                "metadata_fields": sorted((model.metadata_json or {}).keys()),
                "context_length": model.context_length,
                "architecture": model.architecture,
                "quantization": model.quantization,
            },
        )

    if payload.action in {"remove_duplicates", "remove_low_quality"}:
        if not payload.dataset_id:
            raise HTTPException(status_code=400, detail="dataset_id zorunludur.")
        service = DatasetRegistryService(db)
        original = service.get_dataset(payload.dataset_id)
        if original is None:
            raise HTTPException(status_code=404, detail="Veri seti bulunamadı.")
        cleaned = service.create_cleaned_dataset(payload.dataset_id, payload.action)
        if cleaned is None:
            raise HTTPException(status_code=404, detail="Veri seti bulunamadı.")
        changed = cleaned.id != original.id
        return DoctorFixResponse(
            action=payload.action,
            status="completed",
            message_tr=(
                "Temizlenmiş yeni veri seti oluşturuldu."
                if changed
                else "Temizlenecek kayıt bulunamadı; veri seti değişmedi."
            ),
            changed=changed,
            details={
                "source_dataset_id": original.id,
                "dataset_id": cleaned.id,
                "removed_rows": max(0, original.row_count - cleaned.row_count),
                "row_count": cleaned.row_count,
                "quality_score": cleaned.quality_score,
            },
        )

    if payload.action == "ai_self_diagnosis":
        if not payload.model_id or not payload.dataset_id:
            raise HTTPException(status_code=400, detail="model_id ve dataset_id zorunludur.")
        details = DiagnosticService(db).ai_self_diagnosis(payload.model_id, payload.dataset_id)
        if details is None:
            raise HTTPException(status_code=404, detail="Model veya veri seti bulunamadı.")
        return DoctorFixResponse(
            action=payload.action,
            status="completed",
            message_tr="AI self-diagnosis tamamlandı ve model analizine işlendi.",
            changed=True,
            details=details,
        )

    if payload.action == "validate_dataset":
        if not payload.dataset_id:
            raise HTTPException(status_code=400, detail="dataset_id zorunludur.")
        details = DiagnosticService(db).validate_dataset(payload.dataset_id)
        if details is None:
            raise HTTPException(status_code=404, detail="Veri seti bulunamadı.")
        return DoctorFixResponse(
            action=payload.action,
            status="completed",
            message_tr="Veri validasyonu tamamlandı ve veri seti raporuna işlendi.",
            changed=True,
            details=details,
        )

    if payload.action == "trace_analysis":
        if not payload.model_id:
            raise HTTPException(status_code=400, detail="model_id zorunludur.")
        details = DiagnosticService(db).trace_analysis(payload.model_id, payload.dataset_id)
        if details is None:
            raise HTTPException(status_code=404, detail="Model bulunamadı.")
        return DoctorFixResponse(
            action=payload.action,
            status="completed",
            message_tr="Trace-based analysis tamamlandı ve model metadata kaydına işlendi.",
            changed=True,
            details=details,
        )

    if payload.action == "doctor_approve_model":
        if not payload.model_id or not payload.dataset_id:
            raise HTTPException(status_code=400, detail="model_id ve dataset_id zorunludur.")
        details = DiagnosticService(db).create_doctor_approved_model(
            payload.model_id,
            payload.dataset_id,
        )
        if details is None:
            raise HTTPException(status_code=404, detail="Model veya veri seti bulunamadı.")
        return DoctorFixResponse(
            action=payload.action,
            status="completed",
            message_tr=(
                "Doctor onaylı model varyantı kaydedildi. "
                "Ağırlıkların değişmesi için Fine-Tuning Studio'da eğitim çalıştırın."
            ),
            changed=True,
            details=details,
        )

    raise HTTPException(status_code=400, detail=f"Desteklenmeyen aksiyon: {payload.action}")
