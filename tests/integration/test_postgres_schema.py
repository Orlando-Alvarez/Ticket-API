
import os

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import make_url


def test_postgres_has_required_tables() -> None:

    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        pytest.skip("DATABASE_URL is not configured")

    url = make_url(database_url)

    if (
        url.get_backend_name() != "postgresql"
        or url.database != "ticket_api_test"
    ):
        pytest.fail(
            "Integration tests require the isolated "
            "PostgreSQL test database"
        )

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

    finally:

        engine.dispose()
