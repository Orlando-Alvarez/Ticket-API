
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

    finally:

        engine.dispose()
