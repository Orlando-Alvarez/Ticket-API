from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class Incident(Base):
    __tablename__ = "incidents"
    __table_args__ = (
        CheckConstraint(
            "severity IN ('low', 'medium', 'high', 'critical')",
            name="ck_incidents_severity",
        ),
        CheckConstraint(
            "status IN ('open', 'investigating', 'resolved', 'closed')",
            name="ck_incidents_status",
        ),
        Index(
            "ix_incidents_reported_by_created_id",
            "reported_by_id",
            "created_at",
            "id",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    severity: Mapped[str] = mapped_column(
        String(50),
        default="medium",
        server_default="medium",
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="open",
        server_default="open",
        nullable=False,
    )

    reported_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True,
    )

    reporter: Mapped["User"] = relationship(
        back_populates="reported_incidents",
    )
