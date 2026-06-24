"""
FastAPI router for training management.
Endpoints for planning, starting, monitoring, and cancelling training runs.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/training", tags=["training"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class TrainingPlanRequest(BaseModel):
    """Request body for creating a training plan."""

    base_model: str = Field(..., description="HuggingFace model identifier")
    dataset_path: str = Field(..., description="Path to training dataset (JSONL)")
    method: str = Field("lora", pattern=r"^(lora|qlora|full)$")
    framework: str = Field("mlx", pattern=r"^(mlx|transformers|unsloth)$")
    lora_rank: int = Field(16, ge=1, le=256)
    lora_alpha: float = Field(32.0, ge=1.0)
    learning_rate: float = Field(2e-4, ge=1e-6, le=1.0)
    num_epochs: int = Field(3, ge=1, le=100)
    batch_size: int = Field(4, ge=1, le=64)
    max_seq_length: int = Field(2048, ge=128, le=8192)


class TrainingPlanResponse(BaseModel):
    """Estimated plan for a training run."""

    plan_id: str
    base_model: str
    dataset_path: str
    method: str
    framework: str
    estimated_steps: int
    estimated_vram_gb: float
    estimated_adapter_size_mb: float
    warnings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)


class TrainingStartRequest(BaseModel):
    """Request body to start a previously planned training run."""

    plan_id: str = Field(..., description="Plan ID returned by /training/plan")
    job_name: str | None = None


class TrainingStartResponse(BaseModel):
    """Response after starting a training job."""

    job_id: str
    status: str = "queued"
    started_at: str
    message: str = "Training job queued successfully."


class TrainingStatusResponse(BaseModel):
    """Current status of a training job."""

    job_id: str
    status: str
    progress: float = 0.0
    current_step: str = ""
    loss: float | None = None
    best_loss: float | None = None
    elapsed_seconds: float = 0.0
    started_at: str | None = None
    completed_at: str | None = None
    error: str | None = None


class CancelResponse(BaseModel):
    """Response after cancelling a training job."""

    job_id: str
    status: str = "cancelled"
    message: str = "Training job cancelled."


# ---------------------------------------------------------------------------
# In-memory job store (production would use a DB)
# ---------------------------------------------------------------------------

_jobs: dict[str, dict[str, Any]] = {}
_plans: dict[str, dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/plan", response_model=TrainingPlanResponse)
async def plan_training_run(req: TrainingPlanRequest) -> TrainingPlanResponse:
    """Analyze the model and dataset, return an estimated training plan."""
    plan_id = str(uuid.uuid4())

    # Estimate vRAM based on method and model size (heuristic)
    base_vram = _estimate_base_vram(req.base_model)
    vram_multipliers = {"lora": 2.2, "qlora": 1.6, "full": 4.5}
    multiplier = vram_multipliers.get(req.method, 2.2)
    estimated_vram = round(base_vram * multiplier, 2)

    # Estimate steps
    try:
        dataset_rows = _count_dataset_rows(req.dataset_path)
    except Exception:
        dataset_rows = 1000  # fallback guess

    steps_per_epoch = max(1, dataset_rows // req.batch_size)
    estimated_steps = steps_per_epoch * req.num_epochs

    # Estimate adapter size
    num_layers = 32  # typical for 7B model
    param_count = num_layers * 2 * req.lora_rank * (
        req.lora_rank + 4096  # q_proj + v_proj hidden dim
    )
    adapter_size_mb = round(param_count * 2 / (1024 * 1024), 2)  # fp16

    # Warnings & recommendations
    warnings: list[str] = []
    recommendations: list[str] = []

    if estimated_vram > 14:
        warnings.append(
            f"Estimated vRAM ({estimated_vram} GB) may exceed 16 GB limit. "
            "Consider QLoRA or smaller batch size."
        )
    if req.method == "full" and estimated_vram > 12:
        warnings.append(
            "Full fine-tune is memory-intensive. LoRA/QLoRA recommended."
        )
    if dataset_rows < 500:
        warnings.append(
            f"Dataset has only {dataset_rows} rows. Results may be poor."
        )
    elif dataset_rows < 5000:
        recommendations.append(
            "Consider adding more data (5000+ rows) for better results."
        )

    recommendations.extend([
        "Start with a small number of steps (e.g. 100) to verify the setup.",
        "Use qlora if vRAM is a concern.",
        "Monitor loss — if it diverges, lower the learning rate.",
    ])

    config = {
        "base_model": req.base_model,
        "dataset_path": req.dataset_path,
        "method": req.method,
        "framework": req.framework,
        "lora_rank": req.lora_rank,
        "lora_alpha": req.lora_alpha,
        "learning_rate": req.learning_rate,
        "num_epochs": req.num_epochs,
        "batch_size": req.batch_size,
        "max_seq_length": req.max_seq_length,
        "estimated_steps": estimated_steps,
        "dataset_rows": dataset_rows,
    }

    _plans[plan_id] = config

    return TrainingPlanResponse(
        plan_id=plan_id,
        base_model=req.base_model,
        dataset_path=req.dataset_path,
        method=req.method,
        framework=req.framework,
        estimated_steps=estimated_steps,
        estimated_vram_gb=estimated_vram,
        estimated_adapter_size_mb=adapter_size_mb,
        warnings=warnings,
        recommendations=recommendations,
        config=config,
    )


@router.post("/start", response_model=TrainingStartResponse)
async def start_training(req: TrainingStartRequest) -> TrainingStartResponse:
    """Start a training job from a previously created plan."""
    plan = _plans.get(req.plan_id)
    if plan is None:
        raise HTTPException(
            status_code=404,
            detail=f"Plan '{req.plan_id}' not found. Call /training/plan first.",
        )

    job_id = str(uuid.uuid4())
    now = datetime.now(UTC).isoformat()

    job: dict[str, Any] = {
        "job_id": job_id,
        "plan_id": req.plan_id,
        "job_name": req.job_name or f"train-{job_id[:8]}",
        "status": "queued",
        "progress": 0.0,
        "current_step": "Queued — waiting for execution...",
        "config": plan,
        "started_at": now,
        "completed_at": None,
        "loss": None,
        "best_loss": None,
        "elapsed_seconds": 0.0,
        "error": None,
        "events": [],
    }
    _jobs[job_id] = job

    # In a real system, this would enqueue a background task
    # e.g. asyncio.create_task or Celery / RQ
    logger.info("Training job %s queued (plan=%s)", job_id, req.plan_id)

    return TrainingStartResponse(
        job_id=job_id,
        status="queued",
        started_at=now,
        message="Training job queued. Poll /training/status/{job_id} for updates.",
    )


@router.get("/status/{job_id}", response_model=TrainingStatusResponse)
async def get_training_status(job_id: str) -> TrainingStatusResponse:
    """Get the current status of a training job."""
    job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail=f"Training job '{job_id}' not found.",
        )

    return TrainingStatusResponse(
        job_id=job["job_id"],
        status=job["status"],
        progress=job["progress"],
        current_step=job["current_step"],
        loss=job.get("loss"),
        best_loss=job.get("best_loss"),
        elapsed_seconds=job["elapsed_seconds"],
        started_at=job["started_at"],
        completed_at=job.get("completed_at"),
        error=job.get("error"),
    )


@router.post("/cancel/{job_id}", response_model=CancelResponse)
async def cancel_training_job(job_id: str) -> CancelResponse:
    """Cancel a running or queued training job."""
    job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail=f"Training job '{job_id}' not found.",
        )

    if job["status"] in ("completed", "failed", "cancelled"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel job in '{job['status']}' state.",
        )

    job["status"] = "cancelled"
    job["current_step"] = "Cancelled by user."
    job["completed_at"] = datetime.now(UTC).isoformat()
    job["progress"] = 0.0

    logger.info("Training job %s cancelled by user.", job_id)

    return CancelResponse(
        job_id=job_id,
        status="cancelled",
        message="Training job cancelled successfully.",
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _estimate_base_vram(model_name: str) -> float:
    """Heuristic: return estimated base model size in GB."""
    model_name_lower = model_name.lower()
    if "70b" in model_name_lower or "70" in model_name_lower:
        return 16.0
    if "13b" in model_name_lower or "13" in model_name_lower:
        return 8.0
    if "8b" in model_name_lower or "8" in model_name_lower:
        return 6.0
    if "7b" in model_name_lower or "7" in model_name_lower:
        return 5.0
    if "3b" in model_name_lower or "3" in model_name_lower:
        return 3.0
    if "1b" in model_name_lower or "1" in model_name_lower:
        return 1.5
    return 4.0  # default for unknown / ~7B


def _count_dataset_rows(path_str: str) -> int:
    """Count lines in a JSONL file."""
    path = Path(path_str)
    if not path.is_file():
        raise FileNotFoundError(f"Dataset not found: {path_str}")
    count = 0
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                count += 1
    return count
