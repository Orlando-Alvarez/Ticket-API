from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.security import (
    create_access_token,
    inactive_user_exception,
    invalid_credentials_exception,
    verify_password,
)
from app.crud.users import get_user_by_email
from app.db.session import get_db
from app.schemas.auth import Token

router = APIRouter()


@router.post("/auth/token", response_model=Token)
def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[Session, Depends(get_db)],
) -> Token:
    user = get_user_by_email(db, form_data.username)

    if user is None or not verify_password(form_data.password, user.hashed_password):
        raise invalid_credentials_exception()
    if not user.is_active:
        raise inactive_user_exception()

    return Token(access_token=create_access_token(user.id))
