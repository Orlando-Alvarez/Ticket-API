import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.models.incident import Incident
from app.models.user import User


def create_user(
    db: Session,
    email: str,
    role: str = "requester",
    is_active: bool = True,
) -> User:
    user = User(
        email=email,
        full_name="Incident Test User",
        hashed_password="not-a-real-password-hash",
        role=role,
        is_active=is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_incident_record(
    db: Session,
    reporter: User,
    *,
    title: str = "Service unavailable",
    severity: str = "medium",
    status: str = "open",
) -> Incident:
    incident = Incident(
        title=title,
        description="The service is returning errors.",
        severity=severity,
        status=status,
        reported_by_id=reporter.id,
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)
    return incident


def auth_headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


def test_incident_endpoints_require_authentication(
    client: TestClient,
    db_session: Session,
) -> None:
    reporter = create_user(db_session, "reporter@example.com")
    incident = create_incident_record(db_session, reporter)

    responses = [
        client.post("/api/v1/incidents", json={"title": "New incident"}),
        client.get("/api/v1/incidents"),
        client.get(f"/api/v1/incidents/{incident.id}"),
        client.patch(
            f"/api/v1/incidents/{incident.id}",
            json={"severity": "high"},
        ),
    ]

    for response in responses:
        assert response.status_code == 401, response.text
        assert response.headers["www-authenticate"] == "Bearer"


def test_inactive_user_cannot_access_incidents(
    client: TestClient,
    db_session: Session,
) -> None:
    inactive_user = create_user(
        db_session,
        "inactive@example.com",
        is_active=False,
    )

    response = client.get(
        "/api/v1/incidents",
        headers=auth_headers(inactive_user),
    )

    assert response.status_code == 403
    assert response.json()["error"]["message"] == "Inactive user"


def test_create_incident_uses_authenticated_reporter_and_defaults(
    client: TestClient,
    db_session: Session,
) -> None:
    reporter = create_user(db_session, "reporter@example.com")

    response = client.post(
        "/api/v1/incidents",
        json={
            "title": "Payment service unavailable",
            "description": "Customers cannot complete checkout.",
        },
        headers=auth_headers(reporter),
    )

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["reported_by_id"] == reporter.id
    assert data["severity"] == "medium"
    assert data["status"] == "open"
    assert data["created_at"] is not None
    assert data["updated_at"] is None


@pytest.mark.parametrize("field", ["reported_by_id", "status", "unexpected"])
def test_create_incident_rejects_server_controlled_or_unknown_fields(
    client: TestClient,
    db_session: Session,
    field: str,
) -> None:
    reporter = create_user(db_session, "reporter@example.com")

    response = client.post(
        "/api/v1/incidents",
        json={"title": "New incident", field: 999 if field == "reported_by_id" else "open"},
        headers=auth_headers(reporter),
    )

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["loc"] == ["body", field]
    assert db_session.query(Incident).count() == 0


@pytest.mark.parametrize(
    "payload,field",
    [
        ({"title": ""}, "title"),
        ({"title": "   "}, "title"),
        ({"title": "a" * 201}, "title"),
        ({"title": "Valid", "severity": "urgent"}, "severity"),
    ],
)
def test_create_incident_validates_input(
    client: TestClient,
    db_session: Session,
    payload: dict[str, object],
    field: str,
) -> None:
    reporter = create_user(db_session, "reporter@example.com")

    response = client.post(
        "/api/v1/incidents",
        json=payload,
        headers=auth_headers(reporter),
    )

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["loc"] == ["body", field]


def test_list_incidents_scopes_users_and_allows_admin_access(
    client: TestClient,
    db_session: Session,
) -> None:
    reporter = create_user(db_session, "reporter@example.com")
    other = create_user(db_session, "other@example.com")
    admin = create_user(db_session, "admin@example.com", role="admin")
    own_incident = create_incident_record(db_session, reporter, title="Own incident")
    other_incident = create_incident_record(db_session, other, title="Other incident")

    reporter_response = client.get(
        "/api/v1/incidents",
        headers=auth_headers(reporter),
    )
    admin_response = client.get(
        "/api/v1/incidents",
        headers=auth_headers(admin),
    )

    assert reporter_response.status_code == 200, reporter_response.text
    assert reporter_response.json()["total"] == 1
    assert [item["id"] for item in reporter_response.json()["items"]] == [
        own_incident.id
    ]
    assert admin_response.status_code == 200, admin_response.text
    assert admin_response.json()["total"] == 2
    assert {item["id"] for item in admin_response.json()["items"]} == {
        own_incident.id,
        other_incident.id,
    }


def test_list_incidents_filters_and_paginates(
    client: TestClient,
    db_session: Session,
) -> None:
    admin = create_user(db_session, "admin@example.com", role="admin")
    reporter = create_user(db_session, "reporter@example.com")
    first = create_incident_record(
        db_session,
        reporter,
        title="First",
        severity="high",
        status="open",
    )
    second = create_incident_record(
        db_session,
        reporter,
        title="Second",
        severity="high",
        status="investigating",
    )
    create_incident_record(
        db_session,
        reporter,
        title="Third",
        severity="low",
        status="open",
    )

    filtered = client.get(
        "/api/v1/incidents?status=open&severity=high",
        headers=auth_headers(admin),
    )
    paged = client.get(
        "/api/v1/incidents?offset=1&limit=1",
        headers=auth_headers(admin),
    )

    assert filtered.status_code == 200, filtered.text
    assert filtered.json()["total"] == 1
    assert [item["id"] for item in filtered.json()["items"]] == [first.id]
    assert paged.status_code == 200, paged.text
    assert paged.json()["total"] == 3
    assert paged.json()["offset"] == 1
    assert paged.json()["limit"] == 1
    assert [item["id"] for item in paged.json()["items"]] == [second.id]


@pytest.mark.parametrize(
    "query",
    [
        "offset=-1",
        "limit=0",
        "limit=101",
        "status=unknown",
        "severity=urgent",
    ],
)
def test_list_incidents_rejects_invalid_query_parameters(
    client: TestClient,
    db_session: Session,
    query: str,
) -> None:
    reporter = create_user(db_session, "reporter@example.com")

    response = client.get(
        f"/api/v1/incidents?{query}",
        headers=auth_headers(reporter),
    )

    assert response.status_code == 422


def test_incident_openapi_does_not_expose_reporter_filter(client: TestClient) -> None:
    operation = client.get("/openapi.json").json()["paths"]["/api/v1/incidents"]["get"]
    parameter_names = {parameter["name"] for parameter in operation["parameters"]}

    assert parameter_names == {"offset", "limit", "status", "severity"}


def test_reporter_and_admin_can_get_incident(
    client: TestClient,
    db_session: Session,
) -> None:
    reporter = create_user(db_session, "reporter@example.com")
    admin = create_user(db_session, "admin@example.com", role="admin")
    incident = create_incident_record(db_session, reporter)

    for actor in (reporter, admin):
        response = client.get(
            f"/api/v1/incidents/{incident.id}",
            headers=auth_headers(actor),
        )
        assert response.status_code == 200, response.text
        assert response.json()["id"] == incident.id


def test_unrelated_user_cannot_get_or_patch_incident(
    client: TestClient,
    db_session: Session,
) -> None:
    reporter = create_user(db_session, "reporter@example.com")
    unrelated = create_user(db_session, "unrelated@example.com")
    incident = create_incident_record(db_session, reporter)

    get_response = client.get(
        f"/api/v1/incidents/{incident.id}",
        headers=auth_headers(unrelated),
    )
    patch_response = client.patch(
        f"/api/v1/incidents/{incident.id}",
        json={"severity": "critical"},
        headers=auth_headers(unrelated),
    )

    assert get_response.status_code == 404
    assert patch_response.status_code == 404
    db_session.refresh(incident)
    assert incident.severity == "medium"


def test_reporter_can_update_content_and_severity_but_not_status(
    client: TestClient,
    db_session: Session,
) -> None:
    reporter = create_user(db_session, "reporter@example.com")
    incident = create_incident_record(db_session, reporter)
    url = f"/api/v1/incidents/{incident.id}"
    headers = auth_headers(reporter)

    allowed = client.patch(
        url,
        json={
            "title": "Updated incident",
            "description": None,
            "severity": "critical",
        },
        headers=headers,
    )
    denied = client.patch(
        url,
        json={"status": "resolved", "title": "Must not be saved"},
        headers=headers,
    )

    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["title"] == "Updated incident"
    assert allowed.json()["description"] is None
    assert allowed.json()["severity"] == "critical"
    assert denied.status_code == 403
    db_session.refresh(incident)
    assert incident.status == "open"
    assert incident.title == "Updated incident"


def test_admin_can_update_incident_status(
    client: TestClient,
    db_session: Session,
) -> None:
    reporter = create_user(db_session, "reporter@example.com")
    admin = create_user(db_session, "admin@example.com", role="admin")
    incident = create_incident_record(db_session, reporter)

    response = client.patch(
        f"/api/v1/incidents/{incident.id}",
        json={"status": "investigating"},
        headers=auth_headers(admin),
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "investigating"
    assert response.json()["reported_by_id"] == reporter.id


@pytest.mark.parametrize("field", ["title", "severity", "status"])
def test_patch_incident_rejects_null_and_preserves_record(
    client: TestClient,
    db_session: Session,
    field: str,
) -> None:
    admin = create_user(db_session, "admin@example.com", role="admin")
    incident = create_incident_record(db_session, admin)

    response = client.patch(
        f"/api/v1/incidents/{incident.id}",
        json={field: None, "description": "Must not be saved"},
        headers=auth_headers(admin),
    )

    assert response.status_code == 422
    db_session.refresh(incident)
    assert incident.description == "The service is returning errors."


def test_patch_incident_rejects_unknown_field(
    client: TestClient,
    db_session: Session,
) -> None:
    reporter = create_user(db_session, "reporter@example.com")
    incident = create_incident_record(db_session, reporter)

    response = client.patch(
        f"/api/v1/incidents/{incident.id}",
        json={"reported_by_id": reporter.id, "severity": "high"},
        headers=auth_headers(reporter),
    )

    assert response.status_code == 422
    db_session.refresh(incident)
    assert incident.severity == "medium"


def test_admin_get_and_patch_missing_incident_return_not_found(
    client: TestClient,
    db_session: Session,
) -> None:
    admin = create_user(db_session, "admin@example.com", role="admin")
    headers = auth_headers(admin)

    responses = [
        client.get("/api/v1/incidents/999", headers=headers),
        client.patch(
            "/api/v1/incidents/999",
            json={"status": "closed"},
            headers=headers,
        ),
    ]

    for response in responses:
        assert response.status_code == 404
        assert response.json()["error"]["message"] == "Incident not found."


def test_empty_patch_returns_unchanged_incident(
    client: TestClient,
    db_session: Session,
) -> None:
    reporter = create_user(db_session, "reporter@example.com")
    incident = create_incident_record(db_session, reporter)

    response = client.patch(
        f"/api/v1/incidents/{incident.id}",
        json={},
        headers=auth_headers(reporter),
    )

    assert response.status_code == 200, response.text
    assert response.json()["title"] == incident.title
    assert response.json()["status"] == incident.status


def test_incident_update_rejects_whitespace_only_title():
    import pytest
    from pydantic import ValidationError

    from app.schemas.incident import IncidentUpdate

    with pytest.raises(ValidationError):
        IncidentUpdate(title="   ")
