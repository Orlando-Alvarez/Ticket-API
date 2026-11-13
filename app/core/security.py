from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pwdlib import PasswordHash
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.user import User

ALGORITHM = "HS256"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")
password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hash.verify(plain_password, hashed_password)


def create_access_token(user_id: int) -> str:
    expires_at = datetime.now(UTC) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {
        "sub": str(user_id),
        "exp": expires_at,
    }
    return jwt.encode(
        payload,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=ALGORITHM,
    )


def expired_token_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token expired",
        headers={"WWW-Authenticate": "Bearer"},
    )


def inactive_user_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Inactive user",
    )


def invalid_credentials_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def decode_token(token: str) -> dict:
    return jwt.decode(
        token,
        settings.jwt_secret_key.get_secret_value(),
        algorithms=[ALGORITHM],
        options={"require": ["sub", "exp"]},
    )


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError as exc:
        raise expired_token_exception() from exc
    except jwt.InvalidTokenError as exc:
        raise invalid_credentials_exception() from exc

    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject.isdecimal():
        raise invalid_credentials_exception()

    user = db.get(User, int(subject))
    if user is None:
        raise invalid_credentials_exception()
    if not user.is_active:
        raise inactive_user_exception()

    return user
