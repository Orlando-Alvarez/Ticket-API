import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.models.ticket import Ticket
from app.models.user import User


def create_user(
    db: Session,
    email: str = "requester@example.com",
    role: str = "requester",
) -> User:
    user = User(
        email=email,
        full_name="Test User",
        hashed_password="not-a-real-password-hash",
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_ticket_record(
    db: Session,
    requester: User,
    assignee: User | None = None,
    title: str = "Cannot access dashboard",
) -> Ticket:
    ticket = Ticket(
        title=title,
        description="The dashboard returns an error after login.",
        priority="high",
        requester_id=requester.id,
        assignee_id=assignee.id if assignee is not None else None,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


def create_ticket_payload(
    requester_id: int,
    assignee_id: int | None = None,
) -> dict[str, object]:
    return {
        "title": "Cannot access dashboard",
        "description": "The dashboard returns an error after login.",
        "priority": "high",
        "requester_id": requester_id,
        "assignee_id": assignee_id,
    }


def auth_headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


def test_ticket_endpoints_require_authentication(
    client: TestClient,
    db_session: Session,
) -> None:
    requester = create_user(db_session)
    ticket = create_ticket_record(db_session, requester)

    responses = [
        client.post(
            "/api/v1/tickets",
            json=create_ticket_payload(requester.id),
        ),
        client.get("/api/v1/tickets"),
        client.get(f"/api/v1/tickets/{ticket.id}"),
        client.patch(
            f"/api/v1/tickets/{ticket.id}",
            json={"status": "closed"},
        ),
    ]

    for response in responses:
        assert response.status_code == 401, response.text
        assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("role", ["requester", "assignee"])
def test_non_admin_can_create_ticket_for_self(
    client: TestClient,
    db_session: Session,
    role: str,
) -> None:
    actor = create_user(db_session, role=role)

    response = client.post(
        "/api/v1/tickets",
        json=create_ticket_payload(actor.id),
        headers=auth_headers(actor),
    )

    assert response.status_code == 201, response.text
    assert response.json()["requester_id"] == actor.id
    assert response.json()["assignee_id"] is None


@pytest.mark.parametrize("role", ["requester", "assignee"])
def test_non_admin_cannot_create_ticket_for_another_user(
    client: TestClient,
    db_session: Session,
    role: str,
) -> None:
    actor = create_user(db_session, email=f"{role}@example.com", role=role)
    other = create_user(db_session, email="other@example.com")

    response = client.post(
        "/api/v1/tickets",
        json=create_ticket_payload(other.id),
        headers=auth_headers(actor),
    )

    assert response.status_code == 403, response.text
    assert db_session.query(Ticket).count() == 0


@pytest.mark.parametrize("role", ["requester", "assignee"])
def test_non_admin_cannot_assign_ticket_during_creation(
    client: TestClient,
    db_session: Session,
    role: str,
) -> None:
    actor = create_user(db_session, email=f"{role}@example.com", role=role)
    assignee = create_user(db_session, email="target-assignee@example.com", role="assignee")

    response = client.post(
        "/api/v1/tickets",
        json=create_ticket_payload(actor.id, assignee.id),
        headers=auth_headers(actor),
    )

    assert response.status_code == 403, response.text
    assert db_session.query(Ticket).count() == 0


def test_admin_can_create_and_assign_ticket_for_another_user(
    client: TestClient,
    db_session: Session,
) -> None:
    admin = create_user(db_session, email="admin@example.com", role="admin")
    requester = create_user(db_session)
    assignee = create_user(db_session, email="assignee@example.com", role="assignee")

    response = client.post(
        "/api/v1/tickets",
        json=create_ticket_payload(requester.id, assignee.id),
        headers=auth_headers(admin),
    )

    assert response.status_code == 201, response.text
    assert response.json()["requester_id"] == requester.id
    assert response.json()["assignee_id"] == assignee.id


def test_requester_assignee_and_admin_can_get_related_ticket(
    client: TestClient,
    db_session: Session,
) -> None:
    requester = create_user(db_session)
    assignee = create_user(db_session, email="assignee@example.com", role="assignee")
    admin = create_user(db_session, email="admin@example.com", role="admin")
    ticket = create_ticket_record(db_session, requester, assignee)

    for actor in (requester, assignee, admin):
        response = client.get(
            f"/api/v1/tickets/{ticket.id}",
            headers=auth_headers(actor),
        )
        assert response.status_code == 200, response.text
        assert response.json()["id"] == ticket.id


@pytest.mark.parametrize("role", ["requester", "assignee"])
def test_unrelated_non_admin_cannot_get_ticket(
    client: TestClient,
    db_session: Session,
    role: str,
) -> None:
    owner = create_user(db_session, email="owner@example.com")
    actor = create_user(db_session, email=f"{role}@example.com", role=role)
    ticket = create_ticket_record(db_session, owner)

    response = client.get(
        f"/api/v1/tickets/{ticket.id}",
        headers=auth_headers(actor),
    )

    assert response.status_code == 403, response.text


def test_non_admin_lists_only_requested_or_assigned_tickets(
    client: TestClient,
    db_session: Session,
) -> None:
    requester = create_user(db_session, email="requester@example.com")
    assignee = create_user(db_session, email="assignee@example.com", role="assignee")
    other = create_user(db_session, email="other@example.com")
    requester_ticket = create_ticket_record(
        db_session,
        requester,
        title="Requested ticket",
    )
    assigned_ticket = create_ticket_record(
        db_session,
        other,
        assignee,
        title="Assigned ticket",
    )
    create_ticket_record(db_session, other, title="Unrelated ticket")

    requester_response = client.get(
        "/api/v1/tickets",
        headers=auth_headers(requester),
    )
    assignee_response = client.get(
        "/api/v1/tickets",
        headers=auth_headers(assignee),
    )

    assert requester_response.status_code == 200, requester_response.text
    assert {item["id"] for item in requester_response.json()} == {requester_ticket.id}
    assert assignee_response.status_code == 200, assignee_response.text
    assert {item["id"] for item in assignee_response.json()} == {assigned_ticket.id}


def test_admin_lists_all_tickets(
    client: TestClient,
    db_session: Session,
) -> None:
    admin = create_user(db_session, email="admin@example.com", role="admin")
    requester_a = create_user(db_session, email="a@example.com")
    requester_b = create_user(db_session, email="b@example.com")
    ticket_a = create_ticket_record(db_session, requester_a, title="A")
    ticket_b = create_ticket_record(db_session, requester_b, title="B")

    response = client.get("/api/v1/tickets", headers=auth_headers(admin))

    assert response.status_code == 200, response.text
    assert {item["id"] for item in response.json()} == {ticket_a.id, ticket_b.id}


def test_requester_and_assignee_can_patch_related_ticket(
    client: TestClient,
    db_session: Session,
) -> None:
    requester = create_user(db_session)
    assignee = create_user(db_session, email="assignee@example.com", role="assignee")
    ticket = create_ticket_record(db_session, requester, assignee)

    requester_response = client.patch(
        f"/api/v1/tickets/{ticket.id}",
        json={"description": "More diagnostic details"},
        headers=auth_headers(requester),
    )
    assignee_response = client.patch(
        f"/api/v1/tickets/{ticket.id}",
        json={"status": "in_progress"},
        headers=auth_headers(assignee),
    )

    assert requester_response.status_code == 200, requester_response.text
    assert requester_response.json()["description"] == "More diagnostic details"
    assert assignee_response.status_code == 200, assignee_response.text
    assert assignee_response.json()["status"] == "in_progress"


def test_admin_can_patch_unrelated_ticket_and_relationships(
    client: TestClient,
    db_session: Session,
) -> None:
    admin = create_user(db_session, email="admin@example.com", role="admin")
    original_requester = create_user(db_session, email="original@example.com")
    new_requester = create_user(db_session, email="new@example.com")
    new_assignee = create_user(db_session, email="assignee@example.com", role="assignee")
    ticket = create_ticket_record(db_session, original_requester)

    response = client.patch(
        f"/api/v1/tickets/{ticket.id}",
        json={
            "requester_id": new_requester.id,
            "assignee_id": new_assignee.id,
            "status": "in_progress",
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 200, response.text
    assert response.json()["requester_id"] == new_requester.id
    assert response.json()["assignee_id"] == new_assignee.id
    assert response.json()["status"] == "in_progress"


@pytest.mark.parametrize("role", ["requester", "assignee"])
def test_unrelated_non_admin_cannot_patch_ticket(
    client: TestClient,
    db_session: Session,
    role: str,
) -> None:
    owner = create_user(db_session, email="owner@example.com")
    actor = create_user(db_session, email=f"{role}@example.com", role=role)
    ticket = create_ticket_record(db_session, owner)

    response = client.patch(
        f"/api/v1/tickets/{ticket.id}",
        json={"status": "closed"},
        headers=auth_headers(actor),
    )

    assert response.status_code == 403, response.text
    db_session.refresh(ticket)
    assert ticket.status == "open"


def test_non_admin_cannot_change_ticket_relationships(
    client: TestClient,
    db_session: Session,
) -> None:
    requester = create_user(db_session, email="requester@example.com")
    assignee = create_user(db_session, email="assignee@example.com", role="assignee")
    other = create_user(db_session, email="other@example.com")
    ticket = create_ticket_record(db_session, requester, assignee)

    requester_response = client.patch(
        f"/api/v1/tickets/{ticket.id}",
        json={"assignee_id": other.id},
        headers=auth_headers(requester),
    )
    assignee_response = client.patch(
        f"/api/v1/tickets/{ticket.id}",
        json={"requester_id": other.id},
        headers=auth_headers(assignee),
    )

    assert requester_response.status_code == 403, requester_response.text
    assert assignee_response.status_code == 403, assignee_response.text
    db_session.refresh(ticket)
    assert ticket.requester_id == requester.id
    assert ticket.assignee_id == assignee.id


def test_admin_get_and_patch_missing_ticket_return_not_found(
    client: TestClient,
    db_session: Session,
) -> None:
    admin = create_user(db_session, email="admin@example.com", role="admin")
    headers = auth_headers(admin)

    get_response = client.get("/api/v1/tickets/999", headers=headers)
    patch_response = client.patch(
        "/api/v1/tickets/999",
        json={"status": "closed"},
        headers=headers,
    )

    for response in (get_response, patch_response):
        assert response.status_code == 404
        assert response.json()["error"]["message"] == "Ticket not found."


def test_create_ticket_returns_not_found_for_missing_requester(
    client: TestClient,
    db_session: Session,
) -> None:
    admin = create_user(db_session, email="admin@example.com", role="admin")

    response = client.post(
        "/api/v1/tickets",
        json=create_ticket_payload(requester_id=999),
        headers=auth_headers(admin),
    )

    assert response.status_code == 404
    assert response.json()["error"]["message"] == "Requester not found."


def test_create_ticket_returns_not_found_for_missing_assignee(
    client: TestClient,
    db_session: Session,
) -> None:
    admin = create_user(db_session, email="admin@example.com", role="admin")
    requester = create_user(db_session)

    response = client.post(
        "/api/v1/tickets",
        json=create_ticket_payload(requester.id, assignee_id=999),
        headers=auth_headers(admin),
    )

    assert response.status_code == 404
    assert response.json()["error"]["message"] == "Assignee not found."


@pytest.mark.parametrize(
    "field,limit",
    [("title", 200), ("status", 50), ("priority", 50)],
)
def test_ticket_text_boundaries(
    client: TestClient,
    db_session: Session,
    field: str,
    limit: int,
) -> None:
    requester = create_user(db_session)
    headers = auth_headers(requester)
    payload = create_ticket_payload(requester.id)

    for invalid in ("", "a" * (limit + 1)):
        response = client.post(
            "/api/v1/tickets",
            json={**payload, field: invalid},
            headers=headers,
        )
        assert response.status_code == 422, response.text
        assert response.json()["error"]["details"][0]["loc"] == ["body", field]

    created = client.post(
        "/api/v1/tickets",
        json={**payload, field: "a" * limit},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    url = f"/api/v1/tickets/{created.json()['id']}"

    for invalid in ("", "b" * (limit + 1)):
        response = client.patch(url, json={field: invalid}, headers=headers)
        assert response.status_code == 422, response.text
        assert response.json()["error"]["details"][0]["loc"] == ["body", field]

    response = client.patch(
        url,
        json={field: "b" * limit},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()[field] == "b" * limit


@pytest.mark.parametrize("field", ["title", "status", "priority", "requester_id"])
def test_patch_rejects_null_and_preserves_ticket(
    client: TestClient,
    db_session: Session,
    field: str,
) -> None:
    requester = create_user(db_session)
    headers = auth_headers(requester)
    created = client.post(
        "/api/v1/tickets",
        json=create_ticket_payload(requester.id),
        headers=headers,
    )
    assert created.status_code == 201, created.text
    url = f"/api/v1/tickets/{created.json()['id']}"

    response = client.patch(
        url,
        json={field: None, "description": "Should not be saved"},
        headers=headers,
    )

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["loc"] == ["body", field]
    saved = client.get(url, headers=headers)
    assert saved.status_code == 200
    assert saved.json() == created.json()


@pytest.mark.parametrize("field", ["description", "assignee_id"])
def test_admin_patch_can_clear_nullable_field(
    client: TestClient,
    db_session: Session,
    field: str,
) -> None:
    admin = create_user(db_session, email="admin@example.com", role="admin")
    requester = create_user(db_session)
    assignee = create_user(db_session, email="assignee@example.com", role="assignee")
    ticket = create_ticket_record(db_session, requester, assignee)
    headers = auth_headers(admin)

    response = client.patch(
        f"/api/v1/tickets/{ticket.id}",
        json={field: None},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()[field] is None


def test_patch_ticket_rejects_unknown_field(
    client: TestClient,
    db_session: Session,
) -> None:
    requester = create_user(db_session)
    ticket = create_ticket_record(db_session, requester)

    response = client.patch(
        f"/api/v1/tickets/{ticket.id}",
        json={"priorty": "high", "status": "closed"},
        headers=auth_headers(requester),
    )

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["loc"] == ["body", "priorty"]
    db_session.refresh(ticket)
    assert ticket.status == "open"
