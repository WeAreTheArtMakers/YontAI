from pydantic import Field

from yontai.schemas.common import OrmModel


class BenchmarkRunRequest(OrmModel):
    models: list[str] = Field(..., min_length=1, max_length=2)
    prompt: str = Field(..., min_length=1, max_length=4000)
    max_tokens: int = Field(default=128, ge=16, le=256)

class BenchmarkResult(OrmModel):
    model: str
    response: str | None = None
    latency_ms: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    token_per_sec: float | None = None
    ttft_ms: float | None = None
    total_time_ms: float | None = None
    error: str | None = None
