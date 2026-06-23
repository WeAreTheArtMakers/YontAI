from sqlalchemy import select
from sqlalchemy.orm import Session

from yontai.db.models import Dataset


class DatasetRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list(self) -> list[Dataset]:
        return list(self.db.scalars(select(Dataset).order_by(Dataset.created_at.desc())))

    def get(self, dataset_id: str) -> Dataset | None:
        return self.db.get(Dataset, dataset_id)

    def add(self, dataset: Dataset) -> Dataset:
        self.db.add(dataset)
        self.db.commit()
        self.db.refresh(dataset)
        return dataset

    def save(self, dataset: Dataset) -> Dataset:
        self.db.add(dataset)
        self.db.commit()
        self.db.refresh(dataset)
        return dataset

    def delete(self, dataset: Dataset) -> None:
        self.db.delete(dataset)
        self.db.commit()
