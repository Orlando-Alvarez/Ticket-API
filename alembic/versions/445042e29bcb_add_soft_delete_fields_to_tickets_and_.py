"""Add soft delete fields to tickets and incidents.

Revision ID: 445042e29bcb
Revises: 20261112_0002
Create Date: 2026-11-13 07:21:27.121333

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "445042e29bcb"
down_revision: str | Sequence[str] | None = "20261112_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "incidents",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "incidents",
        sa.Column("deleted_by_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_incidents_deleted_by_id_users",
        "incidents",
        "users",
        ["deleted_by_id"],
        ["id"],
    )
    op.add_column(
        "tickets",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tickets",
        sa.Column("deleted_by_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_tickets_deleted_by_id_users",
        "tickets",
        "users",
        ["deleted_by_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_tickets_deleted_by_id_users",
        "tickets",
        type_="foreignkey",
    )
    op.drop_column("tickets", "deleted_by_id")
    op.drop_column("tickets", "deleted_at")
    op.drop_constraint(
        "fk_incidents_deleted_by_id_users",
        "incidents",
        type_="foreignkey",
    )
    op.drop_column("incidents", "deleted_by_id")
    op.drop_column("incidents", "deleted_at")
