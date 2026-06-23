from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


JsonDict = dict[str, Any]


class JobRead(OrmModel):
    id: str
    project_id: str | None
    type: str
    status: str
    priority: int
    progress: float
    current_step: str | None
    error_message: str | None
    payload: JsonDict
    result: JsonDict
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class JobEventRead(OrmModel):
    id: str
    job_id: str
    event_type: str
    message: str
    payload: JsonDict
    created_at: datetime
