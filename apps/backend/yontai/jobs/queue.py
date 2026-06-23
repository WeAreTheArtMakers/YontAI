from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from yontai.jobs.schemas import JobStatus, JobType


@dataclass(frozen=True)
class JobRequest:
    type: JobType
    payload: dict[str, Any]
    project_id: str | None = None
    priority: int = 0


@dataclass
class QueuedJob:
    id: str
    request: JobRequest
    status: JobStatus = JobStatus.QUEUED
    progress: float = 0
    current_step: str | None = None


@dataclass
class LocalJobQueue:
    jobs: dict[str, QueuedJob] = field(default_factory=dict)

    def enqueue(self, request: JobRequest) -> QueuedJob:
        job = QueuedJob(id=str(uuid4()), request=request)
        self.jobs[job.id] = job
        return job


job_queue = LocalJobQueue()
