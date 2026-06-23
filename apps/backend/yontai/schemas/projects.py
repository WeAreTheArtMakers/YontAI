from datetime import datetime

from pydantic import Field

from yontai.schemas.common import OrmModel


class ProjectCreate(OrmModel):
    name: str = Field(min_length=1, max_length=180)
    description: str | None = None


class ProjectRead(OrmModel):
    id: str
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime


class WorkspaceCreate(OrmModel):
    project_id: str
    name: str = Field(min_length=1, max_length=180)
    root_path: str = Field(min_length=1)
    models_path: str = Field(min_length=1)
    datasets_path: str = Field(min_length=1)
    artifacts_path: str = Field(min_length=1)
    is_default: bool = False


class WorkspaceRead(WorkspaceCreate):
    id: str
    created_at: datetime
    updated_at: datetime
