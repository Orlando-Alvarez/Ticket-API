import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User


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


USER_TEXT_LIMITS = [("email", 255), ("full_name", 255), ("hashed_password", 255), ("role", 50)]


@pytest.mark.parametrize("field", ["email", "full_name", "hashed_password", "role", "is_active"])
def test_patch_user_rejects_null(client: TestClient, field: str) -> None:
    user = create_user(client)
    url = f"/api/v1/users/{user['id']}"
    response = client.patch(url, json={field: None})

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["loc"] == ["body", field]
    assert client.get(url).json() == user


@pytest.mark.parametrize("field,limit", USER_TEXT_LIMITS)
def test_user_text_boundaries(client: TestClient, db_session: Session, field: str, limit: int) -> None:
    payload = create_user_payload()
    for invalid in ("", "a" * (limit + 1)):
        response = client.post("/api/v1/users", json={**payload, field: invalid})
        assert response.status_code == 422, response.text
        assert response.json()["error"]["details"][0]["loc"] == ["body", field]

    created = client.post("/api/v1/users", json={**payload, field: "a" * limit})
    assert created.status_code == 201, created.text
    user_id = created.json()["id"]
    url = f"/api/v1/users/{user_id}"

    for invalid in ("", "b" * (limit + 1)):
        response = client.patch(url, json={field: invalid})
        assert response.status_code == 422, response.text
        assert response.json()["error"]["details"][0]["loc"] == ["body", field]

    assert getattr(db_session.get(User, user_id), field) == "a" * limit
    response = client.patch(url, json={field: "b" * limit})
    assert response.status_code == 200, response.text
    assert "hashed_password" not in response.json()
    assert getattr(db_session.get(User, user_id), field) == "b" * limit


def test_patch_user_rejects_unknown_field(client: TestClient) -> None:
    user = create_user(client)
    url = f"/api/v1/users/{user['id']}"
    response = client.patch(url, json={"full_nam": "Ana", "is_active": False})

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["loc"] == ["body", "full_nam"]
    assert client.get(url).json() == user
