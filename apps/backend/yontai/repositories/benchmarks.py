from sqlalchemy import select
from sqlalchemy.orm import Session

from yontai.db.models import BenchmarkRun


class BenchmarkRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list(self) -> list[BenchmarkRun]:
        return list(
            self.db.scalars(select(BenchmarkRun).order_by(BenchmarkRun.created_at.desc()))
        )

    def add(self, run: BenchmarkRun) -> BenchmarkRun:
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run
