import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.models.user import User

PASSWORD = "SecurePassword123!"


def create_user_payload(email: str = "user@example.com") -> dict[str, object]:
    return {
        "email": email,
        "full_name": "Test User",
        "password": PASSWORD,
    }


def create_user(client: TestClient, email: str = "user@example.com") -> dict[str, object]:
    response = client.post("/api/v1/users", json=create_user_payload(email=email))
    assert response.status_code == 201, response.text
    return response.json()


def auth_headers(user_id: int) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


def create_admin(
    client: TestClient,
    db_session: Session,
    email: str = "admin@example.com",
) -> User:
    created = create_user(client, email=email)
    admin = db_session.get(User, created["id"])
    assert admin is not None
    admin.role = "admin"
    db_session.commit()
    return admin


def test_create_user_returns_created_user_without_password(client: TestClient) -> None:
    response = client.post("/api/v1/users", json=create_user_payload())

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["id"] == 1
    assert data["email"] == "user@example.com"
    assert data["full_name"] == "Test User"
    assert data["role"] == "requester"
    assert data["is_active"] is True
    assert "created_at" in data
    assert "hashed_password" not in data
    assert "password" not in data


def test_registration_cannot_set_privileged_fields(client: TestClient) -> None:
    payload = {
        **create_user_payload(),
        "role": "admin",
        "is_active": False,
    }

    response = client.post("/api/v1/users", json=payload)

    assert response.status_code == 201, response.text
    assert response.json()["role"] == "requester"
    assert response.json()["is_active"] is True


def test_admin_can_list_created_users(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(client)
    admin = create_admin(client, db_session)

    response = client.get("/api/v1/users", headers=auth_headers(admin.id))

    assert response.status_code == 200, response.text
    returned_ids = {item["id"] for item in response.json()}
    assert returned_ids == {user["id"], admin.id}
    assert all("hashed_password" not in item for item in response.json())


def test_user_can_get_own_profile(client: TestClient) -> None:
    user = create_user(client)

    response = client.get(
        f"/api/v1/users/{user['id']}",
        headers=auth_headers(int(user["id"])),
    )

    assert response.status_code == 200, response.text
    assert response.json()["id"] == user["id"]
    assert response.json()["email"] == "user@example.com"


def test_admin_gets_not_found_for_missing_user(
    client: TestClient,
    db_session: Session,
) -> None:
    admin = create_admin(client, db_session)

    response = client.get("/api/v1/users/999", headers=auth_headers(admin.id))

    assert response.status_code == 404
    assert response.json()["error"]["message"] == "User not found."


def test_admin_partially_updates_user(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(client)
    admin = create_admin(client, db_session)

    response = client.patch(
        f"/api/v1/users/{user['id']}",
        json={"full_name": "Updated User", "is_active": False},
        headers=auth_headers(admin.id),
    )

    assert response.status_code == 200, response.text
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


def test_admin_update_returns_conflict_for_duplicate_email(
    client: TestClient,
    db_session: Session,
) -> None:
    create_user(client, email="first@example.com")
    second_user = create_user(client, email="second@example.com")
    admin = create_admin(client, db_session)

    response = client.patch(
        f"/api/v1/users/{second_user['id']}",
        json={"email": "first@example.com"},
        headers=auth_headers(admin.id),
    )

    assert response.status_code == 409
    assert response.json()["error"]["message"] == "Email already exists."


@pytest.mark.parametrize("field", ["email", "full_name", "role", "is_active"])
def test_admin_patch_rejects_null(
    client: TestClient,
    db_session: Session,
    field: str,
) -> None:
    user = create_user(client)
    admin = create_admin(client, db_session)

    response = client.patch(
        f"/api/v1/users/{user['id']}",
        json={field: None},
        headers=auth_headers(admin.id),
    )

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["loc"] == ["body", field]


@pytest.mark.parametrize("invalid", ["not-an-email", "missing-at.example.com"])
def test_create_user_rejects_invalid_email(
    client: TestClient,
    invalid: str,
) -> None:
    response = client.post(
        "/api/v1/users",
        json={**create_user_payload(), "email": invalid},
    )

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["loc"] == ["body", "email"]


@pytest.mark.parametrize("invalid", ["", "a" * 256])
def test_create_user_rejects_invalid_full_name(
    client: TestClient,
    invalid: str,
) -> None:
    response = client.post(
        "/api/v1/users",
        json={**create_user_payload(), "full_name": invalid},
    )

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["loc"] == ["body", "full_name"]


@pytest.mark.parametrize("invalid", ["a" * 7, "a" * 129])
def test_create_user_rejects_invalid_password_length(
    client: TestClient,
    invalid: str,
) -> None:
    response = client.post(
        "/api/v1/users",
        json={**create_user_payload(), "password": invalid},
    )

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["loc"] == ["body", "password"]


@pytest.mark.parametrize(
    "field,limit",
    [("full_name", 255), ("role", 50)],
)
def test_admin_patch_user_text_boundaries(
    client: TestClient,
    db_session: Session,
    field: str,
    limit: int,
) -> None:
    user = create_user(client)
    admin = create_admin(client, db_session)
    url = f"/api/v1/users/{user['id']}"
    headers = auth_headers(admin.id)

    for invalid in ("", "a" * (limit + 1)):
        response = client.patch(url, json={field: invalid}, headers=headers)
        assert response.status_code == 422, response.text
        assert response.json()["error"]["details"][0]["loc"] == ["body", field]

    response = client.patch(url, json={field: "a" * limit}, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()[field] == "a" * limit


def test_admin_patch_user_rejects_unknown_field(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(client)
    admin = create_admin(client, db_session)

    response = client.patch(
        f"/api/v1/users/{user['id']}",
        json={"full_nam": "Ana", "is_active": False},
        headers=auth_headers(admin.id),
    )

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["loc"] == ["body", "full_nam"]
    saved_user = db_session.get(User, int(user["id"]))
    assert saved_user is not None
    assert saved_user.is_active is True
