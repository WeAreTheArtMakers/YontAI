from datetime import datetime
from typing import Literal

from pydantic import Field

from yontai.schemas.common import JsonDict, OrmModel

TrainingMethod = Literal[
    "lora",
    "qlora",
    "full",
    "sft",
    "dpo",
    "orpo",
    "kto",
    "ppo",
    "rlhf",
    "rlaif",
    "grpo",
    "dapo",
    "rlvr",
    "sdpo",
]
TrainingFramework = Literal["transformers", "trl", "unsloth", "peft", "axolotl"]


class FineTuneRequest(OrmModel):
    base_model_id: str = Field(min_length=1)
    dataset_id: str = Field(min_length=1)
    project_id: str | None = None
    method: TrainingMethod = "lora"
    framework: TrainingFramework = "trl"
    epochs: int = Field(default=3, ge=1, le=20)
    batch_size: int = Field(default=4, ge=1, le=128)
    learning_rate: float = Field(default=2e-4, gt=0, le=1)
    max_seq_length: int = Field(default=2048, ge=128, le=131_072)
    lora_rank: int = Field(default=16, ge=1, le=256)
    notes: str | None = Field(default=None, max_length=2000)


class FineTunePlan(OrmModel):
    ready: bool
    model_id: str
    dataset_id: str
    method: str
    framework: str
    estimated_vram_gb: float
    estimated_steps: int
    warnings: list[str]
    recommendations: list[str]
    config: JsonDict


class TrainingRunRead(OrmModel):
    id: str
    project_id: str | None
    base_model_id: str
    dataset_id: str
    output_model_id: str | None
    job_id: str | None
    method: str
    framework: str
    config: JsonDict
    metrics: JsonDict
    mlflow_run_id: str | None
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class TrainingRunCreated(OrmModel):
    run: TrainingRunRead
    job: JsonDict
    plan: FineTunePlan
    message_tr: str


class KnowledgePackRequest(OrmModel):
    model_id: str = Field(min_length=1)
    dataset_id: str = Field(min_length=1)
    name: str | None = Field(default=None, max_length=240)
    include_full_preview: bool = False


class KnowledgePackResponse(OrmModel):
    model_id: str
    dataset_id: str
    artifact_id: str
    artifact_path: str
    message_tr: str
    details: JsonDict
