import os
from datetime import timedelta
from uuid import uuid4

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from alembic import command
from app.crud.incidents import soft_delete_incident
from app.crud.tickets import soft_delete_ticket
from app.models.incident import Incident
from app.models.ticket import Ticket


def get_test_database_url() -> str:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL is not configured")

    url = make_url(database_url)
    if url.get_backend_name() != "postgresql" or url.database != "ticket_api_test":
        pytest.fail("Integration tests require the isolated PostgreSQL test database")

    return database_url


def get_alembic_config(database_url: str) -> Config:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


def test_postgres_has_required_tables() -> None:
    database_url = get_test_database_url()
    engine = create_engine(database_url)

    try:
        inspector = inspect(engine)
        existing_tables = set(inspector.get_table_names())

        expected_tables = {
            "users",
            "tickets",
            "incidents",
            "alembic_version",
        }

        assert expected_tables.issubset(existing_tables), (
            expected_tables - existing_tables
        )

        incident_columns = {
            column["name"]: column for column in inspector.get_columns("incidents")
        }
        incident_constraints = {
            constraint["name"]
            for constraint in inspector.get_check_constraints("incidents")
        }
        incident_indexes = {
            index["name"] for index in inspector.get_indexes("incidents")
        }

        assert incident_columns["severity"]["default"] is not None
        assert incident_columns["status"]["default"] is not None
        assert "ck_incidents_severity" in incident_constraints
        assert "ck_incidents_status" in incident_constraints
        assert "ix_incidents_reported_by_created_id" in incident_indexes

        for table_name, constraint_name in (
            ("tickets", "fk_tickets_deleted_by_id_users"),
            ("incidents", "fk_incidents_deleted_by_id_users"),
        ):
            columns = {
                column["name"]: column
                for column in inspector.get_columns(table_name)
            }
            foreign_keys = {
                foreign_key["name"]: foreign_key
                for foreign_key in inspector.get_foreign_keys(table_name)
            }

            assert columns["deleted_at"]["nullable"] is True
            assert columns["deleted_by_id"]["nullable"] is True
            assert foreign_keys[constraint_name]["constrained_columns"] == [
                "deleted_by_id"
            ]
            assert foreign_keys[constraint_name]["referred_table"] == "users"
            assert foreign_keys[constraint_name]["referred_columns"] == ["id"]

    finally:
        engine.dispose()


def test_soft_delete_migration_round_trip_preserves_records() -> None:
    database_url = get_test_database_url()
    config = get_alembic_config(database_url)
    engine = create_engine(database_url)
    unique_suffix = uuid4().hex
    user_id: int | None = None
    ticket_id: int | None = None
    incident_id: int | None = None

    try:
        command.downgrade(config, "20261112_0002")

        with engine.begin() as connection:
            user_id = connection.execute(
                text(
                    """
                    INSERT INTO users (
                        email,
                        full_name,
                        hashed_password,
                        role,
                        is_active
                    )
                    VALUES (
                        :email,
                        'Migration Admin',
                        'test-hash',
                        'admin',
                        true
                    )
                    RETURNING id
                    """
                ),
                {"email": f"migration-{unique_suffix}@example.com"},
            ).scalar_one()
            ticket_id = connection.execute(
                text(
                    """
                    INSERT INTO tickets (
                        title,
                        description,
                        status,
                        priority,
                        requester_id
                    )
                    VALUES (
                        'Migration ticket',
                        'Must survive the migration',
                        'open',
                        'medium',
                        :user_id
                    )
                    RETURNING id
                    """
                ),
                {"user_id": user_id},
            ).scalar_one()
            incident_id = connection.execute(
                text(
                    """
                    INSERT INTO incidents (
                        title,
                        description,
                        severity,
                        status,
                        reported_by_id
                    )
                    VALUES (
                        'Migration incident',
                        'Must survive the migration',
                        'medium',
                        'open',
                        :user_id
                    )
                    RETURNING id
                    """
                ),
                {"user_id": user_id},
            ).scalar_one()

        command.upgrade(config, "445042e29bcb")

        with engine.connect() as connection:
            ticket_row = connection.execute(
                text(
                    """
                    SELECT title, deleted_at, deleted_by_id
                    FROM tickets
                    WHERE id = :ticket_id
                    """
                ),
                {"ticket_id": ticket_id},
            ).one()
            incident_row = connection.execute(
                text(
                    """
                    SELECT title, deleted_at, deleted_by_id
                    FROM incidents
                    WHERE id = :incident_id
                    """
                ),
                {"incident_id": incident_id},
            ).one()

        assert ticket_row.title == "Migration ticket"
        assert ticket_row.deleted_at is None
        assert ticket_row.deleted_by_id is None
        assert incident_row.title == "Migration incident"
        assert incident_row.deleted_at is None
        assert incident_row.deleted_by_id is None

        with Session(engine) as session:
            assert soft_delete_ticket(session, ticket_id, user_id) is True
            assert soft_delete_ticket(session, ticket_id, user_id) is False
            assert soft_delete_incident(session, incident_id, user_id) is True
            assert soft_delete_incident(session, incident_id, user_id) is False

            stored_ticket = session.get(Ticket, ticket_id)
            stored_incident = session.get(Incident, incident_id)
            assert stored_ticket is not None
            assert stored_incident is not None
            assert stored_ticket.deleted_by_id == user_id
            assert stored_incident.deleted_by_id == user_id
            assert stored_ticket.deleted_at is not None
            assert stored_incident.deleted_at is not None
            assert stored_ticket.deleted_at.utcoffset() == timedelta(0)
            assert stored_incident.deleted_at.utcoffset() == timedelta(0)

        command.downgrade(config, "20261112_0002")

        inspector = inspect(engine)
        assert "deleted_at" not in {
            column["name"] for column in inspector.get_columns("tickets")
        }
        assert "deleted_by_id" not in {
            column["name"] for column in inspector.get_columns("incidents")
        }

        with engine.connect() as connection:
            assert connection.scalar(
                text("SELECT title FROM tickets WHERE id = :ticket_id"),
                {"ticket_id": ticket_id},
            ) == "Migration ticket"
            assert connection.scalar(
                text("SELECT title FROM incidents WHERE id = :incident_id"),
                {"incident_id": incident_id},
            ) == "Migration incident"

        command.upgrade(config, "head")
        command.check(config)
    finally:
        command.upgrade(config, "head")
        if ticket_id is not None and incident_id is not None and user_id is not None:
            with engine.begin() as connection:
                connection.execute(
                    text("DELETE FROM tickets WHERE id = :ticket_id"),
                    {"ticket_id": ticket_id},
                )
                connection.execute(
                    text("DELETE FROM incidents WHERE id = :incident_id"),
                    {"incident_id": incident_id},
                )
                connection.execute(
                    text("DELETE FROM users WHERE id = :user_id"),
                    {"user_id": user_id},
                )
        engine.dispose()
