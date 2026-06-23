from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from yontai.db.models import TrainingRun
from yontai.db.session import get_db
from yontai.schemas.training import (
    FineTunePlan,
    FineTuneRequest,
    KnowledgePackRequest,
    KnowledgePackResponse,
    TrainingRunCreated,
    TrainingRunRead,
)
from yontai.training.service import TrainingService

router = APIRouter()


@router.get("/runs", response_model=list[TrainingRunRead])
def list_training_runs(db: Session = Depends(get_db)) -> list[TrainingRun]:
    return TrainingService(db).list_runs()


@router.post("/plan", response_model=FineTunePlan)
def plan_training_run(payload: FineTuneRequest, db: Session = Depends(get_db)) -> FineTunePlan:
    try:
        return TrainingService(db).build_plan(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/runs", response_model=TrainingRunCreated, status_code=201)
def create_training_run(
    payload: FineTuneRequest,
    db: Session = Depends(get_db),
) -> TrainingRunCreated:
    try:
        return TrainingService(db).create_run(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/knowledge-pack", response_model=KnowledgePackResponse, status_code=201)
def attach_knowledge_pack(
    payload: KnowledgePackRequest,
    db: Session = Depends(get_db),
) -> KnowledgePackResponse:
    try:
        return TrainingService(db).attach_knowledge_pack(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/runs/{run_id}/cancel", response_model=TrainingRunRead)
def cancel_training_run(run_id: str, db: Session = Depends(get_db)) -> TrainingRun:
    run = TrainingService(db).cancel_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Training run bulunamadı.")
    return run
