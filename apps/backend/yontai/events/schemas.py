from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DomainEvent(BaseModel):
    event_type: str
    message_tr: str
    project_id: str | None = None
    job_id: str | None = None
    severity: str = "info"
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
