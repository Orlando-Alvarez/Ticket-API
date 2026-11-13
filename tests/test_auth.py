from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import ALGORITHM, create_access_token, decode_token
from app.models.user import User


PASSWORD = "SecurePassword123!"


def create_user(
    client: TestClient,
    email: str = "user@example.com",
) -> dict[str, object]:
    response = client.post(
        "/api/v1/users",
        json={
            "email": email,
            "full_name": "Test User",
            "password": PASSWORD,
        },
    )
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


def encode_payload(payload: dict[str, object]) -> str:
    return jwt.encode(
        payload,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=ALGORITHM,
    )


def test_get_current_user_without_token(client: TestClient) -> None:
    response = client.get("/api/v1/users/me")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_get_current_user_with_invalid_signature(client: TestClient) -> None:
    invalid_token = jwt.encode(
        {
            "sub": "1",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
        },
        "wrong-secret-for-testing-only-123456789",
        algorithm=ALGORITHM,
    )

    response = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {invalid_token}"},
    )

    assert response.status_code == 401, response.text
    assert response.json()["error"]["message"] == "Invalid credentials"
    assert response.headers["www-authenticate"] == "Bearer"


def test_get_current_user_with_expired_token(client: TestClient) -> None:
    expired_token = encode_payload(
        {
            "sub": "1",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
        }
    )

    response = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )

    assert response.status_code == 401, response.text
    assert response.json()["error"]["message"] == "Token expired"
    assert response.headers["www-authenticate"] == "Bearer"


def test_get_current_user_rejects_token_without_expiration(
    client: TestClient,
) -> None:
    token = encode_payload({"sub": "1"})

    response = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401, response.text
    assert response.json()["error"]["message"] == "Invalid credentials"
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("subject", ["not-a-number", -1, 1])
def test_get_current_user_rejects_invalid_subject(
    client: TestClient,
    subject: object,
) -> None:
    token = encode_payload(
        {
            "sub": subject,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
        }
    )

    response = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401, response.text
    assert response.headers["www-authenticate"] == "Bearer"


def test_get_current_user_rejects_unknown_user(client: TestClient) -> None:
    response = client.get(
        "/api/v1/users/me",
        headers=auth_headers(999),
    )

    assert response.status_code == 401, response.text
    assert response.headers["www-authenticate"] == "Bearer"


def test_inactive_user_cannot_access_me(
    client: TestClient,
    db_session: Session,
) -> None:
    created = create_user(client, email="inactive@example.com")
    user = db_session.get(User, created["id"])
    assert user is not None
    user.is_active = False
    db_session.commit()

    response = client.get("/api/v1/users/me", headers=auth_headers(user.id))

    assert response.status_code == 403, response.text
    assert response.json()["error"]["message"] == "Inactive user"


def test_login_returns_valid_bearer_token(client: TestClient) -> None:
    created = create_user(client, email="login@example.com")

    response = client.post(
        "/api/v1/auth/token",
        data={"username": "login@example.com", "password": PASSWORD},
    )

    assert response.status_code == 200, response.text
    assert response.json()["token_type"] == "bearer"
    payload = decode_token(response.json()["access_token"])
    assert payload["sub"] == str(created["id"])
    assert "exp" in payload


@pytest.mark.parametrize(
    "username,password",
    [
        ("missing@example.com", PASSWORD),
        ("login@example.com", "WrongPassword123!"),
    ],
)
def test_login_rejects_invalid_credentials(
    client: TestClient,
    username: str,
    password: str,
) -> None:
    create_user(client, email="login@example.com")

    response = client.post(
        "/api/v1/auth/token",
        data={"username": username, "password": password},
    )

    assert response.status_code == 401, response.text
    assert response.json()["error"]["message"] == "Invalid credentials"
    assert response.headers["www-authenticate"] == "Bearer"


def test_inactive_user_cannot_login(
    client: TestClient,
    db_session: Session,
) -> None:
    created = create_user(client, email="inactive-login@example.com")
    user = db_session.get(User, created["id"])
    assert user is not None
    user.is_active = False
    db_session.commit()

    response = client.post(
        "/api/v1/auth/token",
        data={"username": "inactive-login@example.com", "password": PASSWORD},
    )

    assert response.status_code == 403, response.text
    assert response.json()["error"]["message"] == "Inactive user"


def test_requester_cannot_promote_self(
    client: TestClient,
    db_session: Session,
) -> None:
    created = create_user(client, email="requester@example.com")

    response = client.patch(
        f"/api/v1/users/{created['id']}",
        json={"role": "admin"},
        headers=auth_headers(int(created["id"])),
    )

    assert response.status_code == 403, response.text
    user = db_session.get(User, created["id"])
    assert user is not None
    assert user.role == "requester"


def test_admin_can_update_user(
    client: TestClient,
    db_session: Session,
) -> None:
    admin = create_admin(client, db_session)
    user = create_user(client, email="normal@example.com")

    response = client.patch(
        f"/api/v1/users/{user['id']}",
        json={"full_name": "Updated by Admin"},
        headers=auth_headers(admin.id),
    )

    assert response.status_code == 200, response.text
    assert response.json()["full_name"] == "Updated by Admin"


def test_requester_cannot_list_users(client: TestClient) -> None:
    requester = create_user(client, email="requester-list@example.com")

    response = client.get(
        "/api/v1/users",
        headers=auth_headers(int(requester["id"])),
    )

    assert response.status_code == 403, response.text


def test_admin_can_list_users(
    client: TestClient,
    db_session: Session,
) -> None:
    admin = create_admin(client, db_session)
    user = create_user(client, email="normal-list@example.com")

    response = client.get("/api/v1/users", headers=auth_headers(admin.id))

    assert response.status_code == 200, response.text
    returned_ids = {item["id"] for item in response.json()}
    assert {admin.id, user["id"]}.issubset(returned_ids)


def test_requester_cannot_get_another_user(client: TestClient) -> None:
    user_a = create_user(client, email="user-a@example.com")
    user_b = create_user(client, email="user-b@example.com")

    response = client.get(
        f"/api/v1/users/{user_b['id']}",
        headers=auth_headers(int(user_a["id"])),
    )

    assert response.status_code == 403, response.text


def test_requester_can_get_own_user(client: TestClient) -> None:
    user = create_user(client, email="own-profile@example.com")

    response = client.get(
        f"/api/v1/users/{user['id']}",
        headers=auth_headers(int(user["id"])),
    )

    assert response.status_code == 200, response.text
    assert response.json()["id"] == user["id"]
    assert "hashed_password" not in response.json()
    assert "password" not in response.json()


def test_admin_can_get_another_user(
    client: TestClient,
    db_session: Session,
) -> None:
    admin = create_admin(client, db_session)
    user = create_user(client, email="target-profile@example.com")

    response = client.get(
        f"/api/v1/users/{user['id']}",
        headers=auth_headers(admin.id),
    )

    assert response.status_code == 200, response.text
    assert response.json()["id"] == user["id"]


def test_get_user_by_id_without_token(client: TestClient) -> None:
    user = create_user(client, email="no-token@example.com")

    response = client.get(f"/api/v1/users/{user['id']}")

    assert response.status_code == 401, response.text
    assert response.headers["www-authenticate"] == "Bearer"
