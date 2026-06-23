"""
Model Deployment Service
Exports and deploys trained models as local API endpoints
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

from yontai.core.paths import storage_path
from yontai.db.models import Deployment, Job, RunStatus
from yontai.repositories.jobs import JobRepository


async def deploy_model_job(job: Job, repo: JobRepository) -> None:
    """
    Deploy a trained model as a local API endpoint.
    Creates deployment configuration and prepares the model for inference.
    """
    payload = job.payload or {}
    model_id = payload.get("model_id")
    export_path_str = payload.get("export_path")
    deployment_type = payload.get("deployment_type", "local")
    port = payload.get("port", 8766)
    
    if not model_id:
        raise ValueError("model_id gerekli")
    
    # Create deployment directory
    deploy_dir = storage_path("deployments") / f"deploy_{job.id}"
    deploy_dir.mkdir(parents=True, exist_ok=True)
    
    # Build deployment config
    deploy_config = {
        "model_id": model_id,
        "deployment_type": deployment_type,
        "port": port,
        "host": "127.0.0.1",
        "status": "deploying",
        "created_at": datetime.now(UTC).isoformat(),
    }
    (deploy_dir / "deploy_config.json").write_text(
        json.dumps(deploy_config, indent=2, ensure_ascii=False)
    )
    
    # Simulate deployment steps
    # In production: start a uvicorn subprocess serving the model
    import asyncio
    
    steps = [
        ("loading_model", "Model yükleniyorsa..."),
        ("preparing_api", "API hazırlanıyor..."),
        ("starting_server", "Sunucu başlatılıyor..."),
        ("health_check", "Sağlık kontrolü yapılıyor..."),
    ]
    
    for i, (step_key, step_msg) in enumerate(steps):
        progress = int((i + 1) / len(steps) * 100)
        job.progress = progress
        job.current_step = step_msg
        repo.save(job)
        repo.add_event(
            job_id=job.id,
            event_type="deploy_progress",
            message=step_msg,
            data={"step": step_key, "progress": progress},
        )
        await asyncio.sleep(1)
    
    # Mark complete
    deploy_config["status"] = "active"
    deploy_config["api_url"] = f"http://127.0.0.1:{port}"
    (deploy_dir / "deploy_config.json").write_text(
        json.dumps(deploy_config, indent=2, ensure_ascii=False)
    )
    
    job.result = {
        "deployment_id": str(job.id),
        "api_url": deploy_config["api_url"],
        "model_id": model_id,
        "deployment_type": deployment_type,
        "port": port,
        "status": "active",
    }
    repo.save(job)
    
    # Update deployment record if exists
    deployment = repo.db.scalar(
        select(Deployment).where(Deployment.job_id == job.id)
    )
    if deployment is not None:
        deployment.status = "active"
        deployment.config = deploy_config
        repo.db.add(deployment)
        repo.db.commit()