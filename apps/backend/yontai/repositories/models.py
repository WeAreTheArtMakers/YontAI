from sqlalchemy import select
from sqlalchemy.orm import Session

from yontai.db.models import Model


class ModelRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list(self) -> list[Model]:
        return list(self.db.scalars(select(Model).order_by(Model.created_at.desc())))

    def get(self, model_id: str) -> Model | None:
        return self.db.get(Model, model_id)

    def get_by_path(self, path: str) -> Model | None:
        return self.db.scalar(select(Model).where(Model.path == path))

    def get_by_provider(self, source: str, provider_id: str) -> Model | None:
        return self.db.scalar(
            select(Model).where(Model.source == source, Model.provider_id == provider_id)
        )

    def add(self, model: Model) -> Model:
        self.db.add(model)
        self.db.commit()
        self.db.refresh(model)
        return model

    def save(self, model: Model) -> Model:
        self.db.add(model)
        self.db.commit()
        self.db.refresh(model)
        return model

    def delete(self, model: Model) -> None:
        self.db.delete(model)
        self.db.commit()
