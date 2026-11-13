from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator
from pydantic_core import PydanticCustomError

IncidentTitle = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=200,
    ),
]
IncidentSeverity = Literal["low", "medium", "high", "critical"]
IncidentStatus = Literal["open", "investigating", "resolved", "closed"]


class IncidentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: IncidentTitle
    description: str | None = None
    severity: IncidentSeverity = "medium"


class IncidentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: IncidentTitle | None = None
    description: str | None = None
    severity: IncidentSeverity | None = None
    status: IncidentStatus | None = None

    @field_validator("title", "severity", "status")
    @classmethod
    def reject_explicit_null(cls, value: str | None) -> str:
        if value is None:
            raise PydanticCustomError("null_not_allowed", "This field cannot be null.")
        return value


class IncidentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    severity: IncidentSeverity
    status: IncidentStatus
    reported_by_id: int
    created_at: datetime
    updated_at: datetime | None


class IncidentListResponse(BaseModel):
    items: list[IncidentResponse]
    total: int
    offset: int
    limit: int
