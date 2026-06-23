from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from yontai.db.base import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return str(uuid4())


class ModelSource(StrEnum):
    LOCAL = "local"
    HUGGINGFACE = "huggingface"
    OLLAMA = "ollama"


class DatasetFormat(StrEnum):
    JSON = "json"
    JSONL = "jsonl"
    CSV = "csv"
    XLSX = "xlsx"
    TXT = "txt"
    PARQUET = "parquet"


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    FAILED = "failed"
    COMPLETED = "completed"


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    workspaces: Mapped[list[Workspace]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    models: Mapped[list[Model]] = relationship(back_populates="project")
    datasets: Mapped[list[Dataset]] = relationship(back_populates="project")
    jobs: Mapped[list[Job]] = relationship(back_populates="project")

    __table_args__ = (Index("ix_projects_name", "name"),)


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    root_path: Mapped[str] = mapped_column(Text, nullable=False)
    models_path: Mapped[str] = mapped_column(Text, nullable=False)
    datasets_path: Mapped[str] = mapped_column(Text, nullable=False)
    artifacts_path: Mapped[str] = mapped_column(Text, nullable=False)
    is_default: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    project: Mapped[Project] = relationship(back_populates="workspaces")

    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_workspaces_project_name"),
        Index("ix_workspaces_project_id", "project_id"),
    )


class Model(Base):
    __tablename__ = "models"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    path: Mapped[str | None] = mapped_column(Text)
    provider_id: Mapped[str | None] = mapped_column(String(300))
    model_family: Mapped[str | None] = mapped_column(String(120))
    parameter_count: Mapped[int | None] = mapped_column(Integer)
    quantization: Mapped[str | None] = mapped_column(String(80))
    context_length: Mapped[int | None] = mapped_column(Integer)
    architecture: Mapped[str | None] = mapped_column(String(180))
    actual_license: Mapped[str | None] = mapped_column(String(160))
    user_license_notes: Mapped[str | None] = mapped_column(Text)
    tokenizer: Mapped[str | None] = mapped_column(String(240))
    dtype: Mapped[str | None] = mapped_column(String(80))
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[dict[str, object]] = mapped_column("metadata", JSON, default=dict)
    analysis: Mapped[dict[str, object] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    project: Mapped[Project | None] = relationship(back_populates="models")
    training_runs_as_base: Mapped[list[TrainingRun]] = relationship(
        back_populates="base_model", foreign_keys="TrainingRun.base_model_id"
    )
    evaluations: Mapped[list[EvaluationRun]] = relationship(back_populates="model")
    benchmarks: Mapped[list[BenchmarkRun]] = relationship(back_populates="model")
    deployments: Mapped[list[Deployment]] = relationship(back_populates="model")

    __table_args__ = (
        Index("ix_models_project_id", "project_id"),
        Index("ix_models_source", "source"),
        Index("ix_models_name", "name"),
        Index("ix_models_family", "model_family"),
    )


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    source_type: Mapped[str] = mapped_column(String(80), nullable=False, default="local_file")
    path: Mapped[str] = mapped_column(Text, nullable=False)
    format: Mapped[str] = mapped_column(String(20), nullable=False)
    task_type: Mapped[str | None] = mapped_column(String(80))
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    token_count_estimate: Mapped[int] = mapped_column(Integer, default=0)
    average_tokens: Mapped[float] = mapped_column(Float, default=0)
    duplicate_ratio: Mapped[float] = mapped_column(Float, default=0)
    empty_ratio: Mapped[float] = mapped_column(Float, default=0)
    quality_score: Mapped[float] = mapped_column(Float, default=0)
    dataset_schema: Mapped[dict[str, object]] = mapped_column("schema", JSON, default=dict)
    preview: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    statistics: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    report: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    project: Mapped[Project | None] = relationship(back_populates="datasets")
    training_runs: Mapped[list[TrainingRun]] = relationship(back_populates="dataset")
    evaluations: Mapped[list[EvaluationRun]] = relationship(back_populates="dataset")
    benchmarks: Mapped[list[BenchmarkRun]] = relationship(back_populates="dataset")

    __table_args__ = (
        Index("ix_datasets_project_id", "project_id"),
        Index("ix_datasets_name", "name"),
        Index("ix_datasets_format", "format"),
    )


class TrainingRun(Base):
    __tablename__ = "training_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"))
    base_model_id: Mapped[str] = mapped_column(ForeignKey("models.id", ondelete="RESTRICT"))
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id", ondelete="RESTRICT"))
    output_model_id: Mapped[str | None] = mapped_column(
        ForeignKey("models.id", ondelete="SET NULL")
    )
    job_id: Mapped[str | None] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"))
    method: Mapped[str] = mapped_column(String(80), nullable=False)
    framework: Mapped[str] = mapped_column(String(80), nullable=False)
    config: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    metrics: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    mlflow_run_id: Mapped[str | None] = mapped_column(String(180))
    status: Mapped[str] = mapped_column(String(40), nullable=False, default=RunStatus.QUEUED.value)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    base_model: Mapped[Model] = relationship(
        back_populates="training_runs_as_base", foreign_keys=[base_model_id]
    )
    output_model: Mapped[Model | None] = relationship(foreign_keys=[output_model_id])
    dataset: Mapped[Dataset] = relationship(back_populates="training_runs")
    job: Mapped[Job | None] = relationship(back_populates="training_run")

    __table_args__ = (
        Index("ix_training_runs_project_id", "project_id"),
        Index("ix_training_runs_status", "status"),
    )


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"))
    model_id: Mapped[str] = mapped_column(ForeignKey("models.id", ondelete="RESTRICT"))
    dataset_id: Mapped[str | None] = mapped_column(ForeignKey("datasets.id", ondelete="SET NULL"))
    job_id: Mapped[str | None] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"))
    evaluation_type: Mapped[str] = mapped_column(String(120), nullable=False)
    config: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    results: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default=RunStatus.QUEUED.value)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    model: Mapped[Model] = relationship(back_populates="evaluations")
    dataset: Mapped[Dataset | None] = relationship(back_populates="evaluations")
    job: Mapped[Job | None] = relationship(back_populates="evaluation_run")

    __table_args__ = (
        Index("ix_evaluation_runs_project_id", "project_id"),
        Index("ix_evaluation_runs_model_id", "model_id"),
    )


class BenchmarkRun(Base):
    __tablename__ = "benchmark_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"))
    model_id: Mapped[str] = mapped_column(ForeignKey("models.id", ondelete="RESTRICT"))
    dataset_id: Mapped[str | None] = mapped_column(ForeignKey("datasets.id", ondelete="SET NULL"))
    job_id: Mapped[str | None] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"))
    benchmark_type: Mapped[str] = mapped_column(String(120), nullable=False)
    config: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    results: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default=RunStatus.QUEUED.value)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    model: Mapped[Model] = relationship(back_populates="benchmarks")
    dataset: Mapped[Dataset | None] = relationship(back_populates="benchmarks")
    job: Mapped[Job | None] = relationship(back_populates="benchmark_run")

    __table_args__ = (
        Index("ix_benchmark_runs_project_id", "project_id"),
        Index("ix_benchmark_runs_model_id", "model_id"),
    )


class Deployment(Base):
    __tablename__ = "deployments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"))
    model_id: Mapped[str] = mapped_column(ForeignKey("models.id", ondelete="RESTRICT"))
    name: Mapped[str] = mapped_column(String(220), nullable=False)
    deployment_type: Mapped[str] = mapped_column(String(80), nullable=False)
    endpoint_url: Mapped[str | None] = mapped_column(Text)
    port: Mapped[int | None] = mapped_column(Integer)
    config: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="stopped")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    model: Mapped[Model] = relationship(back_populates="deployments")

    __table_args__ = (
        Index("ix_deployments_project_id", "project_id"),
        Index("ix_deployments_model_id", "model_id"),
    )


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"))
    owner_type: Mapped[str] = mapped_column(String(80), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(36), nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(80), nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    checksum: Mapped[str | None] = mapped_column(String(128))
    metadata_json: Mapped[dict[str, object]] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    __table_args__ = (
        Index("ix_artifacts_project_id", "project_id"),
        Index("ix_artifacts_owner", "owner_type", "owner_id"),
    )


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"))
    type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default=RunStatus.QUEUED.value)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    progress: Mapped[float] = mapped_column(Float, default=0)
    current_step: Mapped[str | None] = mapped_column(String(240))
    error_message: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    result: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    project: Mapped[Project | None] = relationship(back_populates="jobs")
    events: Mapped[list[JobEvent]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )
    training_run: Mapped[TrainingRun | None] = relationship(back_populates="job")
    evaluation_run: Mapped[EvaluationRun | None] = relationship(back_populates="job")
    benchmark_run: Mapped[BenchmarkRun | None] = relationship(back_populates="job")

    __table_args__ = (
        Index("ix_jobs_project_id", "project_id"),
        Index("ix_jobs_status", "status"),
        Index("ix_jobs_type", "type"),
        Index("ix_jobs_created_at", "created_at"),
    )


class JobEvent(Base):
    __tablename__ = "job_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    job: Mapped[Job] = relationship(back_populates="events")

    __table_args__ = (
        Index("ix_job_events_job_id", "job_id"),
        Index("ix_job_events_created_at", "created_at"),
    )
