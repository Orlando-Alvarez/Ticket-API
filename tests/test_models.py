from app.db.base import Base
import app.models  # noqa: F401


def test_database_models_are_registered():
    expected_tables = {"users", "tickets", "incidents"}

    assert expected_tables.issubset(Base.metadata.tables.keys())