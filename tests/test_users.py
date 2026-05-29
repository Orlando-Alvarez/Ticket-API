from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
import app.models as models  # noqa: F401


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def create_user_payload(email: str = "user@example.com") -> dict[str, object]:
    return {
        "email": email,
        "full_name": "Test User",
        "hashed_password": "not-a-real-password-hash",
    }


def create_user(client: TestClient, email: str = "user@example.com") -> dict[str, object]:
    response = client.post("/api/v1/users", json=create_user_payload(email=email))
    assert response.status_code == 201
    return response.json()


def test_create_user_returns_created_user_without_hashed_password(client: TestClient) -> None:
    response = client.post("/api/v1/users", json=create_user_payload())

    assert response.status_code == 201

    data = response.json()
    assert data["id"] == 1
    assert data["email"] == "user@example.com"
    assert data["full_name"] == "Test User"
    assert data["role"] == "requester"
    assert data["is_active"] is True
    assert "created_at" in data
    assert "hashed_password" not in data


def test_list_users_returns_created_users(client: TestClient) -> None:
    create_user(client)

    response = client.get("/api/v1/users")

    assert response.status_code == 200

    data = response.json()
    assert len(data) == 1
    assert data[0]["email"] == "user@example.com"
    assert "hashed_password" not in data[0]


def test_get_user_returns_existing_user(client: TestClient) -> None:
    user = create_user(client)

    response = client.get(f"/api/v1/users/{user['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == user["id"]
    assert response.json()["email"] == "user@example.com"


def test_get_user_returns_not_found_for_missing_user(client: TestClient) -> None:
    response = client.get("/api/v1/users/999")

    assert response.status_code == 404
    assert response.json()["error"]["message"] == "User not found."


def test_update_user_partially_updates_existing_user(client: TestClient) -> None:
    user = create_user(client)

    response = client.patch(
        f"/api/v1/users/{user['id']}",
        json={
            "full_name": "Updated User",
            "is_active": False,
        },
    )

    assert response.status_code == 200

    data = response.json()
    assert data["id"] == user["id"]
    assert data["email"] == "user@example.com"
    assert data["full_name"] == "Updated User"
    assert data["is_active"] is False
    assert "hashed_password" not in data


def test_create_user_returns_conflict_for_duplicate_email(client: TestClient) -> None:
    create_user(client)

    response = client.post("/api/v1/users", json=create_user_payload())

    assert response.status_code == 409
    assert response.json()["error"]["message"] == "Email already exists."


def test_update_user_returns_conflict_for_duplicate_email(client: TestClient) -> None:
    create_user(client, email="first@example.com")
    second_user = create_user(client, email="second@example.com")

    response = client.patch(
        f"/api/v1/users/{second_user['id']}",
        json={"email": "first@example.com"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["message"] == "Email already exists."
