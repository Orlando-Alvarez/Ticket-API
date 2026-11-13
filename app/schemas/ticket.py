from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_core import PydanticCustomError

TicketTitle = Annotated[str, Field(min_length=1, max_length=200)]
TicketLabel = Annotated[str, Field(min_length=1, max_length=50)]


class TicketBase(BaseModel):
    title: str
    description: str | None = None
    status: str = "open"
    priority: str = "medium"
    requester_id: int
    assignee_id: int | None = None


class TicketCreate(TicketBase):
    title: TicketTitle
    status: TicketLabel = "open"
    priority: TicketLabel = "medium"


class TicketUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: TicketTitle | None = None
    description: str | None = None
    status: TicketLabel | None = None
    priority: TicketLabel | None = None
    requester_id: int | None = None
    assignee_id: int | None = None

    @field_validator("title", "status", "priority", "requester_id")
    @classmethod
    def reject_explicit_null(cls, value: str | int | None) -> str | int:
        if value is None:
            raise PydanticCustomError("null_not_allowed", "This field cannot be null.")
        return value


class TicketResponse(TicketBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime | None = None
