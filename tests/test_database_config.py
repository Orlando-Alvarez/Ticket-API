from app.core.config import settings
from app.db.session import engine


def test_database_url_uses_postgresql_psycopg_driver() -> None:
    assert settings.database_url.startswith("postgresql+psycopg://")


def test_engine_uses_postgresql_psycopg_driver() -> None:
    assert engine.url.drivername == "postgresql+psycopg"
