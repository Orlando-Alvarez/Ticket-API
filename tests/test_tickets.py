from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.user import User
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


def create_user(db: Session, email: str = "requester@example.com") -> User:
    user = User(
        email=email,
        full_name="Test User",
        hashed_password="not-a-real-password-hash",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_ticket_payload(requester_id: int, assignee_id: int | None = None) -> dict[str, object]:
    return {
        "title": "Cannot access dashboard",
        "description": "The dashboard returns an error after login.",
        "priority": "high",
        "requester_id": requester_id,
        "assignee_id": assignee_id,
    }


def test_create_ticket_returns_created_ticket(client: TestClient, db_session: Session) -> None:
    requester = create_user(db_session)

    response = client.post(
        "/api/v1/tickets",
        json=create_ticket_payload(requester.id),
    )

    assert response.status_code == 201

    data = response.json()
    assert data["id"] == 1
    assert data["title"] == "Cannot access dashboard"
    assert data["description"] == "The dashboard returns an error after login."
    assert data["status"] == "open"
    assert data["priority"] == "high"
    assert data["requester_id"] == requester.id
    assert data["assignee_id"] is None
    assert "created_at" in data


def test_list_tickets_returns_created_tickets(client: TestClient, db_session: Session) -> None:
    requester = create_user(db_session)
    client.post("/api/v1/tickets", json=create_ticket_payload(requester.id))

    response = client.get("/api/v1/tickets")

    assert response.status_code == 200

    data = response.json()
    assert len(data) == 1
    assert data[0]["title"] == "Cannot access dashboard"


def test_get_ticket_returns_existing_ticket(client: TestClient, db_session: Session) -> None:
    requester = create_user(db_session)
    create_response = client.post("/api/v1/tickets", json=create_ticket_payload(requester.id))
    ticket_id = create_response.json()["id"]

    response = client.get(f"/api/v1/tickets/{ticket_id}")

    assert response.status_code == 200
    assert response.json()["id"] == ticket_id


def test_get_ticket_returns_not_found_for_missing_ticket(client: TestClient) -> None:
    response = client.get("/api/v1/tickets/999")

    assert response.status_code == 404
    assert response.json()["error"]["message"] == "Ticket not found."


def test_update_ticket_partially_updates_existing_ticket(
    client: TestClient,
    db_session: Session,
) -> None:
    requester = create_user(db_session)
    assignee = create_user(db_session, email="assignee@example.com")
    create_response = client.post("/api/v1/tickets", json=create_ticket_payload(requester.id))
    ticket_id = create_response.json()["id"]

    response = client.patch(
        f"/api/v1/tickets/{ticket_id}",
        json={
            "status": "in_progress",
            "assignee_id": assignee.id,
        },
    )

    assert response.status_code == 200

    data = response.json()
    assert data["id"] == ticket_id
    assert data["status"] == "in_progress"
    assert data["assignee_id"] == assignee.id
    assert data["title"] == "Cannot access dashboard"


def test_create_ticket_returns_not_found_for_missing_requester(client: TestClient) -> None:
    response = client.post(
        "/api/v1/tickets",
        json=create_ticket_payload(requester_id=999),
    )

    assert response.status_code == 404
    assert response.json()["error"]["message"] == "Requester not found."


def test_create_ticket_returns_not_found_for_missing_assignee(
    client: TestClient,
    db_session: Session,
) -> None:
    requester = create_user(db_session)

    response = client.post(
        "/api/v1/tickets",
        json=create_ticket_payload(requester_id=requester.id, assignee_id=999),
    )

    assert response.status_code == 404
    assert response.json()["error"]["message"] == "Assignee not found."
