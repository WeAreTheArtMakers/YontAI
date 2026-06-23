
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from yontai.benchmarking.persistence import (
    persist_ollama_benchmark,
    serialize_benchmark_run,
)
from yontai.benchmarking.service import BenchmarkService
from yontai.db.session import get_db
from yontai.repositories.benchmarks import BenchmarkRepository
from yontai.schemas.benchmarking import BenchmarkResult, BenchmarkRunRequest

router = APIRouter()


@router.get("/runs")
def list_benchmark_runs(db: Session = Depends(get_db)) -> list[dict[str, object]]:
    return [serialize_benchmark_run(run) for run in BenchmarkRepository(db).list()]


@router.post("/execute", response_model=list[BenchmarkResult])
async def execute_benchmark(
    request: BenchmarkRunRequest,
    db: Session = Depends(get_db),
) -> list[BenchmarkResult]:
    if len(request.models) > 2:
        raise HTTPException(
            status_code=400,
            detail="Yerel benchmark aynı anda en fazla 2 modelle çalıştırılabilir.",
        )
    service = BenchmarkService()
    results: list[BenchmarkResult] = []
    for model in request.models:
        res = await service.run_ollama_benchmark(model, request.prompt, request.max_tokens)
        persist_ollama_benchmark(db, model_name=model, prompt=request.prompt, result=res)
        results.append(BenchmarkResult(**res))
    return results
