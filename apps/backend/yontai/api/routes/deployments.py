from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from yontai.db.models import Job
from yontai.db.session import get_db
from yontai.repositories.jobs import JobRepository
from yontai.schemas.common import JobRead

router = APIRouter()


class DeploymentRequest(BaseModel):
    model_id: str
    target: str  # ollama, huggingface, local_server
    name: str
    config: dict | None = None


@router.post("/deploy", response_model=JobRead, status_code=201)
def create_deployment(payload: DeploymentRequest, db: Session = Depends(get_db)) -> Job:
    """
    Create a model deployment job
    
    Supported targets:
    - ollama: Deploy to local Ollama
    - huggingface: Push to HuggingFace Hub
    - local_server: Start local inference server
    """
    repo = JobRepository(db)

    # Validate target
    valid_targets = ["ollama", "huggingface", "local_server"]
    if payload.target not in valid_targets:
        raise HTTPException(
            status_code=400,
            detail=f"Geçersiz target. Desteklenen: {', '.join(valid_targets)}",
        )

    # Create deployment job
    job = Job(
        type="model_deployment",
        status="pending",
        progress=0,
        current_step=f"Deployment job oluşturuldu: {payload.target}",
        payload={
            "model_id": payload.model_id,
            "target": payload.target,
            "name": payload.name,
            "config": payload.config or {},
        },
    )

    created_job = repo.add(job)
    return created_job


@router.get("/targets")
def list_deployment_targets() -> dict[str, object]:
    """List available deployment targets"""
    return {
        "targets": [
            {
                "name": "ollama",
                "title": "Ollama",
                "description": "Deploy to local Ollama for chat and completion",
                "requirements": ["GGUF model", "Ollama installed"],
            },
            {
                "name": "huggingface",
                "title": "HuggingFace Hub",
                "description": "Push model to HuggingFace Hub for sharing",
                "requirements": ["HF token", "Model in HF format"],
            },
            {
                "name": "local_server",
                "title": "Local Inference Server",
                "description": "Start local FastAPI inference server",
                "requirements": ["Model weights", "Available port"],
            },
        ]
    }


@router.get("/status/{deployment_id}")
def get_deployment_status(deployment_id: str, db: Session = Depends(get_db)) -> dict[str, object]:
    """Get deployment status"""
    repo = JobRepository(db)
    job = repo.get(deployment_id)

    if not job or job.type != "model_deployment":
        raise HTTPException(status_code=404, detail="Deployment bulunamadı")

    payload_data = job.payload or {}
    return {
        "id": job.id,
        "status": job.status,
        "progress": job.progress,
        "message": job.current_step or job.error_message,
        "target": payload_data.get("target"),
        "name": payload_data.get("name"),
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }


@router.get("")
def list_deployments(db: Session = Depends(get_db)) -> list[dict[str, object]]:
    repo = JobRepository(db)
    deployments: list[dict[str, object]] = []
    for job in repo.list():
        if job.type != "model_deployment":
            continue
        payload_data = job.payload or {}
        deployments.append(
            {
                "id": job.id,
                "status": job.status,
                "progress": job.progress,
                "target": payload_data.get("target"),
                "model_id": payload_data.get("model_id"),
                "name": payload_data.get("name"),
                "result": job.result,
                "created_at": job.created_at.isoformat(),
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            }
        )
    return deployments
