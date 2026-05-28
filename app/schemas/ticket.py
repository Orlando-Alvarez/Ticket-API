from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TicketBase(BaseModel):
    title: str
    description: str | None = None
    status: str = "open"
    priority: str = "medium"
    requester_id: int
    assignee_id: int | None = None


class TicketCreate(TicketBase):
    pass


class TicketUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None
    priority: str | None = None
    requester_id: int | None = None
    assignee_id: int | None = None


class TicketResponse(TicketBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime | None = None
