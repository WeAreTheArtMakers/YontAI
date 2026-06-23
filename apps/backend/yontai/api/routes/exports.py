from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from yontai.db.models import Job, Model
from yontai.db.session import get_db
from yontai.models.service import ModelRegistryService
from yontai.repositories.jobs import JobRepository
from yontai.schemas.common import JobRead

router = APIRouter()


def _resolve_export_model(db: Session, model_id: str) -> tuple[Model, str]:
    model = ModelRegistryService(db).get_model(model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Model bulunamadı.")
    if model.path:
        return model, model.path
    if model.provider_id:
        return model, model.provider_id
    raise HTTPException(
        status_code=400,
        detail=(
            "Model için export edilebilir yol bulunamadı. "
            "Yerel dosya import edin veya metadata güncelleyin."
        ),
    )


class ExportRequest(BaseModel):
    model_id: str
    format: str  # gguf, safetensors, onnx, ollama
    output_name: str
    quantization: str | None = "Q4_K_M"  # For GGUF


@router.post("/model", response_model=JobRead, status_code=201)
def export_model(payload: ExportRequest, db: Session = Depends(get_db)) -> Job:
    """
    Create a model export job
    
    Supported formats:
    - gguf: GGUF format for llama.cpp (with quantization)
    - safetensors: SafeTensors format
    - onnx: ONNX format for optimized inference
    - ollama: Prepare for Ollama import
    """
    repo = JobRepository(db)

    # Validate format
    valid_formats = ["gguf", "safetensors", "onnx", "ollama"]
    if payload.format not in valid_formats:
        raise HTTPException(
            status_code=400,
            detail=f"Geçersiz format. Desteklenen: {', '.join(valid_formats)}",
        )

    model, model_path = _resolve_export_model(db, payload.model_id)

    # Create export job
    job = Job(
        type="model_export",
        status="pending",
        progress=0,
        current_step=f"Model export job oluşturuldu: {payload.format}",
        payload={
            "model_id": payload.model_id,
            "model_path": model_path,
            "output_name": payload.output_name,
            "format": payload.format,
            "quantization": payload.quantization,
            "knowledge_packs": (model.metadata_json or {}).get("knowledge_packs", []),
        },
    )

    created_job = repo.add(job)
    return created_job


@router.get("/formats")
def list_export_formats() -> dict[str, object]:
    """List available export formats and their options"""
    return {
        "formats": [
            {
                "name": "gguf",
                "title": "GGUF (llama.cpp)",
                "description": "Quantized format for CPU inference with llama.cpp",
                "quantization_options": [
                    "Q4_K_M",
                    "Q5_K_M",
                    "Q6_K",
                    "Q8_0",
                    "F16",
                    "F32",
                ],
                "recommended": "Q4_K_M",
            },
            {
                "name": "safetensors",
                "title": "SafeTensors",
                "description": "Safe serialization format for PyTorch models",
                "quantization_options": None,
            },
            {
                "name": "onnx",
                "title": "ONNX",
                "description": "Open Neural Network Exchange format for optimized inference",
                "quantization_options": None,
            },
            {
                "name": "ollama",
                "title": "Ollama",
                "description": "Prepare model for Ollama import with Modelfile",
                "quantization_options": None,
            },
        ]
    }


@router.get("")
def list_exports(db: Session = Depends(get_db)) -> list[dict[str, object]]:
    repo = JobRepository(db)
    exports: list[dict[str, object]] = []
    for job in repo.list():
        if job.type != "model_export":
            continue
        payload_data = job.payload or {}
        exports.append(
            {
                "id": job.id,
                "status": job.status,
                "progress": job.progress,
                "format": payload_data.get("format"),
                "model_id": payload_data.get("model_id"),
                "output_name": payload_data.get("output_name"),
                "result": job.result,
                "created_at": job.created_at.isoformat(),
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            }
        )
    return exports
