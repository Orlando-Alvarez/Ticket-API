"""Constrain and index incidents.

Revision ID: 20261112_0002
Revises: 20260523_0001
Create Date: 2026-11-12

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import context, op

revision: str = "20261112_0002"
down_revision: str | Sequence[str] | None = "20260523_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _ensure_existing_values_are_supported() -> None:
    if context.is_offline_mode():
        op.execute(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM incidents
                    WHERE severity NOT IN ('low', 'medium', 'high', 'critical')
                ) OR EXISTS (
                    SELECT 1
                    FROM incidents
                    WHERE status NOT IN ('open', 'investigating', 'resolved', 'closed')
                ) THEN
                    RAISE EXCEPTION
                        'Incident rows contain unsupported severity or status values.';
                END IF;
            END
            $$
            """
        )
        return
    connection = op.get_bind()
    invalid_severity_count = connection.scalar(
        sa.text(
            """
            SELECT count(*)
            FROM incidents
            WHERE severity NOT IN ('low', 'medium', 'high', 'critical')
            """
        )
    )
    invalid_status_count = connection.scalar(
        sa.text(
            """
            SELECT count(*)
            FROM incidents
            WHERE status NOT IN ('open', 'investigating', 'resolved', 'closed')
            """
        )
    )

    if invalid_severity_count or invalid_status_count:
        raise RuntimeError(
            "Incident rows contain unsupported severity or status values. "
            "Correct those values before applying this migration."
        )


def upgrade() -> None:
    _ensure_existing_values_are_supported()

    op.alter_column(
        "incidents",
        "severity",
        existing_type=sa.String(length=50),
        server_default=sa.text("'medium'"),
        existing_nullable=False,
    )
    op.alter_column(
        "incidents",
        "status",
        existing_type=sa.String(length=50),
        server_default=sa.text("'open'"),
        existing_nullable=False,
    )
    op.create_check_constraint(
        "ck_incidents_severity",
        "incidents",
        "severity IN ('low', 'medium', 'high', 'critical')",
    )
    op.create_check_constraint(
        "ck_incidents_status",
        "incidents",
        "status IN ('open', 'investigating', 'resolved', 'closed')",
    )
    op.create_index(
        "ix_incidents_reported_by_created_id",
        "incidents",
        ["reported_by_id", "created_at", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_incidents_reported_by_created_id", table_name="incidents")
    op.drop_constraint("ck_incidents_status", "incidents", type_="check")
    op.drop_constraint("ck_incidents_severity", "incidents", type_="check")
    op.alter_column(
        "incidents",
        "status",
        existing_type=sa.String(length=50),
        server_default=None,
        existing_nullable=False,
    )
    op.alter_column(
        "incidents",
        "severity",
        existing_type=sa.String(length=50),
        server_default=None,
        existing_nullable=False,
    )
