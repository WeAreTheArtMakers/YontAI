from datetime import datetime
from typing import Literal

from pydantic import Field

from yontai.schemas.common import JsonDict, OrmModel

DatasetFormatLiteral = Literal["json", "jsonl", "csv", "xlsx", "txt", "parquet"]


class DatasetCreate(OrmModel):
    name: str = Field(min_length=1, max_length=240)
    path: str = Field(min_length=1)
    format: DatasetFormatLiteral
    project_id: str | None = None
    task_type: str | None = None


class DatasetRead(OrmModel):
    id: str
    project_id: str | None
    name: str
    source_type: str
    path: str
    format: str
    task_type: str | None
    row_count: int
    token_count_estimate: int
    average_tokens: float
    duplicate_ratio: float
    empty_ratio: float
    quality_score: float
    dataset_schema: JsonDict = Field(
        validation_alias="dataset_schema",
        serialization_alias="schema",
    )
    preview: list[JsonDict]
    statistics: JsonDict
    report: JsonDict
    created_at: datetime
    updated_at: datetime


class PublicDatasetCatalogItem(OrmModel):
    repository_id: str
    title: str
    task_type: str
    language: str
    license: str | None = None
    description_tr: str
    recommended_limit: int = 1000


class PublicDatasetImport(OrmModel):
    repository_id: str = Field(min_length=3, max_length=240)
    name: str | None = Field(default=None, max_length=240)
    project_id: str | None = None
    task_type: str | None = None
    max_rows: int = Field(default=1000, ge=10, le=20_000)
