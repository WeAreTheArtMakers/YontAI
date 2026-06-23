from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from yontai.db.models import BenchmarkRun, Model, RunStatus
from yontai.repositories.benchmarks import BenchmarkRepository
from yontai.repositories.models import ModelRepository


def find_model_for_ollama_name(db: Session, model_name: str) -> Model | None:
    for model in ModelRepository(db).list():
        if model.source != "ollama":
            continue
        if model.provider_id == model_name or model.name == model_name:
            return model
    return None


def persist_ollama_benchmark(
    db: Session,
    *,
    model_name: str,
    prompt: str,
    result: dict[str, Any],
) -> BenchmarkRun | None:
    model = find_model_for_ollama_name(db, model_name)
    if model is None:
        return None

    run = BenchmarkRun(
        model_id=model.id,
        benchmark_type="ollama_latency",
        config={"prompt": prompt, "ollama_model": model_name},
        results=result,
        status=RunStatus.COMPLETED.value,
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
    )
    return BenchmarkRepository(db).add(run)


def serialize_benchmark_run(run: BenchmarkRun) -> dict[str, object]:
    config = run.config or {}
    return {
        "id": run.id,
        "model_id": run.model_id,
        "model_name": config.get("ollama_model"),
        "benchmark_type": run.benchmark_type,
        "status": run.status,
        "config": config,
        "results": run.results,
        "created_at": run.created_at.isoformat(),
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
    }
