from pydantic import Field

from yontai.schemas.common import JsonDict, OrmModel


class DoctorRequest(OrmModel):
    model_id: str = Field(min_length=1)
    dataset_id: str = Field(min_length=1)


class DoctorDiagnosis(OrmModel):
    risk_level: str
    confidence_score: int
    reasons: list[str]
    recommendations: list[str]
    expected_impact: str
    evidence: JsonDict
    summary_tr: str


class DoctorFixRequest(OrmModel):
    action: str = Field(min_length=1)
    model_id: str | None = None
    dataset_id: str | None = None


class DoctorFixResponse(OrmModel):
    action: str
    status: str
    message_tr: str
    changed: bool
    details: JsonDict
