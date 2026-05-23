from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.incident import Incident
    from app.models.ticket import Ticket


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    role: Mapped[str] = mapped_column(String(50), default="requester", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    requested_tickets: Mapped[list["Ticket"]] = relationship(
        back_populates="requester",
        foreign_keys="Ticket.requester_id",
    )

    assigned_tickets: Mapped[list["Ticket"]] = relationship(
        back_populates="assignee",
        foreign_keys="Ticket.assignee_id",
    )

    reported_incidents: Mapped[list["Incident"]] = relationship(
        back_populates="reporter",
    )
