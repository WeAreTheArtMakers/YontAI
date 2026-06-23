from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from yontai.schemas.common import JsonDict, OrmModel

ModelSourceLiteral = Literal["local", "huggingface", "ollama"]


class ModelCreate(OrmModel):
    name: str = Field(min_length=1, max_length=240)
    source: ModelSourceLiteral
    path: str | None = None
    provider_id: str | None = None
    project_id: str | None = None
    model_family: str | None = None
    parameter_count: int | None = Field(default=None, ge=0)
    quantization: str | None = None
    context_length: int | None = Field(default=None, ge=1)
    architecture: str | None = None
    actual_license: str | None = None
    user_license_notes: str | None = None

    @model_validator(mode="after")
    def validate_source_fields(self) -> "ModelCreate":
        if self.source == "local" and not self.path:
            raise ValueError("Yerel model kaydı için dosya veya klasör yolu zorunludur.")
        if self.source in {"huggingface", "ollama"} and not self.provider_id:
            raise ValueError("HuggingFace ve Ollama kayıtları için model kimliği zorunludur.")
        return self


class FolderScanRequest(OrmModel):
    folder_path: str = Field(min_length=1)
    project_id: str | None = None


class HuggingFaceRegistrationRequest(OrmModel):
    repository_id: str = Field(min_length=1, max_length=300)
    project_id: str | None = None


class ModelUpdate(OrmModel):
    user_license_notes: str | None = None


class ChatRequest(OrmModel):
    model_id: str = Field(min_length=1, max_length=240)
    prompt: str = Field(min_length=1, max_length=10000)
    images: list[str] | None = Field(
        default=None, description="Base64 encoded images for vision models"
    )


class ChatResponse(OrmModel):
    response: str
    model_id: str
    model_name: str


class ModelRead(OrmModel):
    id: str
    project_id: str | None
    name: str
    source: str
    path: str | None
    provider_id: str | None
    model_family: str | None
    parameter_count: int | None
    quantization: str | None
    context_length: int | None
    architecture: str | None
    actual_license: str | None
    user_license_notes: str | None
    tokenizer: str | None
    dtype: str | None
    size_bytes: int | None
    metadata_json: JsonDict
    analysis: JsonDict | None
    created_at: datetime
    updated_at: datetime


class ModelAnalysisRead(OrmModel):
    model_id: str
    summary_tr: str
    strengths: list[str]
    weaknesses: list[str]
    details: JsonDict
    memory_requirements: JsonDict


class ModelDiscoveryResult(OrmModel):
    imported: list[ModelRead]
    skipped: list[str]
    errors: list[str]
