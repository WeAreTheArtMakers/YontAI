"""
Background Job Worker
Handles long-running tasks like training, dataset processing, benchmarking
"""

from __future__ import annotations

import asyncio
import traceback
from datetime import UTC, datetime
from typing import Any

from yontai.db.session import SessionLocal
from yontai.repositories.jobs import JobRepository


class JobWorker:
    """Background job worker for processing long-running tasks"""

    def __init__(self):
        self.running = False
        self.handlers: dict[str, Any] = {}

    def register_handler(self, job_type: str, handler: Any) -> None:
        """Register a handler function for a specific job type"""
        self.handlers[job_type] = handler

    async def start(self) -> None:
        """Start the worker loop"""
        self.running = True
        print("🚀 Job worker started")

        while self.running:
            try:
                await self._process_pending_jobs()
                await asyncio.sleep(2)  # Check every 2 seconds
            except Exception as e:
                print(f"❌ Worker error: {e}")
                await asyncio.sleep(5)

    async def stop(self) -> None:
        """Stop the worker loop"""
        self.running = False
        print("🛑 Job worker stopped")

    async def _process_pending_jobs(self) -> None:
        """Process all pending jobs"""
        with SessionLocal() as db:
            repo = JobRepository(db)
            pending_jobs = [j for j in repo.list() if j.status in {"pending", "queued"}]

            for job in pending_jobs:
                await self._process_job(job.id)

    async def _process_job(self, job_id: str) -> None:
        """Process a single job"""
        with SessionLocal() as db:
            repo = JobRepository(db)
            job = repo.get(job_id)

            if not job or job.status not in {"pending", "queued"}:
                return

            # Mark as running
            job.status = "running"
            job.progress = 0
            job.started_at = datetime.now(UTC)
            repo.save(job)
            repo.add_event(
                job_id=job.id,
                event_type="started",
                message="Job başlatıldı",
                data={"started_at": job.started_at.isoformat()},
            )

            try:
                # Get handler for job type
                handler = self.handlers.get(job.type)

                if not handler:
                    raise ValueError(f"Handler bulunamadı: {job.type}")

                # Execute handler
                await handler(job, repo)

                # Mark as completed
                job.status = "completed"
                job.progress = 100
                job.completed_at = datetime.now(UTC)
                job.current_step = "Job başarıyla tamamlandı"
                repo.save(job)
                repo.add_event(
                    job_id=job.id,
                    event_type="completed",
                    message="Job tamamlandı",
                    data={"completed_at": job.completed_at.isoformat()},
                )

            except Exception as e:
                # Mark as failed
                job.status = "failed"
                job.error_message = str(e)
                job.completed_at = datetime.now(UTC)
                repo.save(job)
                repo.add_event(
                    job_id=job.id,
                    event_type="failed",
                    message=f"Job başarısız: {str(e)}",
                    data={"error": str(e), "traceback": traceback.format_exc()},
                )
                print(f"❌ Job {job_id} failed: {e}")


# Global worker instance
_worker: JobWorker | None = None


def get_worker() -> JobWorker:
    """Get or create global worker instance"""
    global _worker
    if _worker is None:
        _worker = JobWorker()
    return _worker


async def start_worker() -> None:
    """Start the global worker"""
    worker = get_worker()
    await worker.start()


async def stop_worker() -> None:
    """Stop the global worker"""
    worker = get_worker()
    await worker.stop()
