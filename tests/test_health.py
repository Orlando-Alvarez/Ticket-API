from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.db.session import get_db
from app.main import app


class FailingDatabaseSession:
    def execute(self, _: object) -> None:
        raise SQLAlchemyError(
            "Connection refused for "
            "postgresql+psycopg://ticket_user:super-secret-password@db:5432/ticket_api "
            "while executing SELECT 1 through SQLAlchemy"
        )


def override_failing_database() -> Generator[FailingDatabaseSession, None, None]:
    yield FailingDatabaseSession()


def test_health_endpoint_returns_ok(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "ok"
    assert data["service"] == settings.app_name
    assert data["version"] == settings.app_version


def test_readiness_endpoint_is_public_when_database_is_available(
    client: TestClient,
) -> None:
    response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
    assert "www-authenticate" not in response.headers


def test_readiness_database_failure_is_safe_and_dependency_override_is_isolated(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with monkeypatch.context() as patch:
        patch.setitem(
            app.dependency_overrides,
            get_db,
            override_failing_database,
        )
        response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json() == {"error": {"message": "Service not ready"}}
    assert "www-authenticate" not in response.headers

    response_text = response.text.lower()
    for sensitive_value in (
        "super-secret-password",
        "postgresql+psycopg://",
        "select 1",
        "sqlalchemy",
        "connection refused",
        "ticket_user",
    ):
        assert sensitive_value not in response_text

    recovered_response = client.get("/api/v1/health/ready")
    assert recovered_response.status_code == 200
    assert recovered_response.json() == {"status": "ready"}
