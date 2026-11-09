import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User


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


@pytest.mark.parametrize("field,limit", [("title", 200), ("status", 50), ("priority", 50)])
def test_ticket_text_boundaries(client: TestClient, db_session: Session, field: str, limit: int) -> None:
    payload = create_ticket_payload(create_user(db_session).id)
    for invalid in ("", "a" * (limit + 1)):
        response = client.post("/api/v1/tickets", json={**payload, field: invalid})
        assert response.status_code == 422, response.text
        assert response.json()["error"]["details"][0]["loc"] == ["body", field]

    created = client.post("/api/v1/tickets", json={**payload, field: "a" * limit})
    assert created.status_code == 201, created.text
    url = f"/api/v1/tickets/{created.json()['id']}"

    for invalid in ("", "b" * (limit + 1)):
        response = client.patch(url, json={field: invalid})
        assert response.status_code == 422, response.text
        assert response.json()["error"]["details"][0]["loc"] == ["body", field]

    assert client.get(url).json()[field] == "a" * limit
    response = client.patch(url, json={field: "b" * limit})
    assert response.status_code == 200, response.text
    assert client.get(url).json()[field] == "b" * limit


@pytest.mark.parametrize("field", ["title", "status", "priority", "requester_id"])
def test_patch_rejects_null_and_preserves_ticket(client: TestClient, db_session: Session, field: str) -> None:
    payload = create_ticket_payload(create_user(db_session).id)
    created = client.post("/api/v1/tickets", json=payload)
    assert created.status_code == 201
    url = f"/api/v1/tickets/{created.json()['id']}"

    response = client.patch(url, json={field: None, "description": "Should not be saved"})

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["loc"] == ["body", field]
    assert client.get(url).json() == created.json()


@pytest.mark.parametrize("field", ["description", "assignee_id"])
def test_patch_can_clear_nullable_field(client: TestClient, db_session: Session, field: str) -> None:
    user = create_user(db_session)
    created = client.post("/api/v1/tickets", json=create_ticket_payload(user.id, user.id))
    assert created.status_code == 201
    original = created.json()
    url = f"/api/v1/tickets/{original['id']}"
    assert original[field] is not None

    response = client.patch(url, json={field: None})

    assert response.status_code == 200
    saved = client.get(url).json()
    assert saved[field] is None
    for key in ("title", "description", "status", "priority", "requester_id", "assignee_id"):
        if key != field:
            assert saved[key] == original[key]


def test_patch_ticket_rejects_unknown_field(client: TestClient, db_session: Session) -> None:
    payload = create_ticket_payload(create_user(db_session).id)
    created = client.post("/api/v1/tickets", json=payload)
    assert created.status_code == 201
    url = f"/api/v1/tickets/{created.json()['id']}"
    response = client.patch(url, json={"priorty": "high", "status": "closed"})

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["loc"] == ["body", "priorty"]
    assert client.get(url).json() == created.json()
