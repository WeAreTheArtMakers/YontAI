import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from yontai.db.models import Job, JobEvent
from yontai.db.session import SessionLocal, get_db
from yontai.repositories.jobs import JobRepository
from yontai.schemas.common import JobEventRead, JobRead

router = APIRouter()


def _job_recovery_note(job: Job) -> dict[str, object]:
    error = (job.error_message or "").lower()
    notes: list[str] = []
    can_retry = job.status in {"failed", "cancelled"}

    if "cleaned up during maintenance" in error or "interrupted" in error:
        notes.append(
            "Bu kayıt eski bir çalışmadan kalmış. Backend yeniden başlatılırken job yarıda kalmış; "
            "model dosyası bozulmaz, kayıt güvenle temizlenebilir."
        )
        can_retry = False
    if job.type == "model_export":
        notes.append(
            "GGUF export için kaynak model yolu ve hedef export dizini yazma izni "
            "kontrol edilmeli. Gerçek dönüştürme aracı henüz bağlı değilse export "
            "yalnızca manifest/placeholder üretir."
        )
    if job.type == "training":
        notes.append(
            "Fine-tuning job iptal edilmişse aynı model/veri setiyle yeni bir plan "
            "oluşturup tekrar başlatın."
        )
    if not notes and job.status in {"failed", "cancelled"}:
        notes.append(
            "Bu job tamamlanmamış. Detay olaylarını kontrol edip tekrar çalıştırabilirsiniz."
        )

    return {
        "job_id": job.id,
        "status": job.status,
        "can_retry": can_retry,
        "can_delete": job.status in {"failed", "cancelled", "completed"},
        "notes_tr": notes,
    }


@router.get("", response_model=list[JobRead])
def list_jobs(db: Session = Depends(get_db)) -> list[Job]:
    return JobRepository(db).list()


@router.get("/maintenance/advice")
def job_maintenance_advice(db: Session = Depends(get_db)) -> dict[str, object]:
    jobs = JobRepository(db).list_incomplete()
    return {
        "count": len(jobs),
        "items": [_job_recovery_note(job) for job in jobs],
        "summary_tr": (
            "Temizlenecek başarısız veya iptal edilmiş job kaydı yok."
            if not jobs
            else (
                f"{len(jobs)} tamamlanmamış job kaydı bulundu. "
                "Eski hata kayıtlarını temizleyebilirsiniz."
            )
        ),
    }


@router.delete("/maintenance/incomplete")
def delete_incomplete_jobs(db: Session = Depends(get_db)) -> dict[str, object]:
    deleted_count = JobRepository(db).delete_incomplete()
    return {
        "deleted_count": deleted_count,
        "message_tr": f"{deleted_count} başarısız/iptal job kaydı temizlendi.",
    }


@router.get("/stream")
async def stream_jobs() -> EventSourceResponse:
    async def event_generator():
        previous_snapshot = ""
        while True:
            with SessionLocal() as db:
                jobs = JobRepository(db).list()
                payload = [JobRead.model_validate(job).model_dump(mode="json") for job in jobs]

            snapshot = json.dumps(payload, ensure_ascii=False, sort_keys=True)
            if snapshot != previous_snapshot:
                previous_snapshot = snapshot
                yield {
                    "event": "jobs",
                    "data": snapshot,
                }
            else:
                yield {
                    "event": "heartbeat",
                    "data": json.dumps({"status": "ok"}, ensure_ascii=False),
                }
            await asyncio.sleep(1)

    return EventSourceResponse(event_generator())


@router.get("/{job_id}", response_model=JobRead)
def get_job(job_id: str, db: Session = Depends(get_db)) -> Job:
    job = JobRepository(db).get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="İş bulunamadı.")
    return job


@router.get("/{job_id}/events", response_model=list[JobEventRead])
def list_job_events(job_id: str, db: Session = Depends(get_db)) -> list[JobEvent]:
    repo = JobRepository(db)
    if repo.get(job_id) is None:
        raise HTTPException(status_code=404, detail="İş bulunamadı.")
    return repo.list_events(job_id)


@router.delete("/{job_id}")
def delete_job(job_id: str, db: Session = Depends(get_db)) -> dict[str, object]:
    repo = JobRepository(db)
    job = repo.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="İş bulunamadı.")
    if job.status == "running":
        raise HTTPException(status_code=409, detail="Çalışan job silinemez.")
    repo.delete(job)
    return {"deleted": True, "message_tr": "Job kaydı temizlendi."}
