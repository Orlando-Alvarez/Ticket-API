from pathlib import Path

import pytest

from app.core.config import Settings, settings
from app.db.session import engine


def test_database_url_uses_postgresql_psycopg_driver() -> None:
    assert settings.database_url.startswith("postgresql+psycopg://")


def test_engine_uses_postgresql_psycopg_driver() -> None:
    assert engine.url.drivername == "postgresql+psycopg"


def test_settings_ignore_compose_only_dotenv_keys(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "JWT_SECRET_KEY=test-secret-key\n"
        "DATABASE_URL=sqlite+pysqlite:///:memory:\n"
        "POSTGRES_USER=ticket_user\n"
        "POSTGRES_PASSWORD=ticket_password\n"
        "POSTGRES_DB=ticket_api",
        encoding="utf-8",
    )

    monkeypatch.setenv("DEBUG", "release")
    monkeypatch.delenv("APP_DEBUG", raising=False)
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    loaded = Settings(_env_file=env_file)

    assert loaded.debug is False
    assert loaded.jwt_secret_key.get_secret_value() == "test-secret-key"
    assert loaded.database_url == "sqlite+pysqlite:///:memory:"


def test_settings_use_app_debug_environment_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEBUG", "release")
    monkeypatch.setenv("APP_DEBUG", "true")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")

    loaded = Settings(_env_file=None)

    assert loaded.debug is True
