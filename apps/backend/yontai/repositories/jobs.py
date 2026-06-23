from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from yontai.db.models import Job, JobEvent


class JobRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list(self) -> list[Job]:
        return list(self.db.scalars(select(Job).order_by(Job.created_at.desc())))

    def list_incomplete(self) -> list[Job]:
        return list(
            self.db.scalars(
                select(Job)
                .where(Job.status.in_(("failed", "cancelled")))
                .order_by(Job.created_at.desc())
            )
        )

    def list_events(self, job_id: str) -> list[JobEvent]:
        return list(
            self.db.scalars(
                select(JobEvent)
                .where(JobEvent.job_id == job_id)
                .order_by(JobEvent.created_at.asc())
            )
        )

    def get(self, job_id: str) -> Job | None:
        return self.db.get(Job, job_id)

    def add(self, job: Job) -> Job:
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def add_event(
        self,
        event: JobEvent | None = None,
        *,
        job_id: str | None = None,
        event_type: str | None = None,
        message: str | None = None,
        data: dict[str, object] | None = None,
    ) -> JobEvent:
        if event is None:
            if not job_id or not event_type or message is None:
                raise ValueError("Job event için job_id, event_type ve message zorunludur.")
            event = JobEvent(
                job_id=job_id,
                event_type=event_type,
                message=message,
                payload=data or {},
            )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def save(self, job: Job) -> Job:
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def delete(self, job: Job) -> None:
        self.db.delete(job)
        self.db.commit()

    def delete_incomplete(self) -> int:
        result = self.db.execute(
            delete(Job).where(Job.status.in_(("failed", "cancelled")))
        )
        self.db.commit()
        return int(result.rowcount or 0)
