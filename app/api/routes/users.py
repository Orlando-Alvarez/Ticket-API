from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.crud.users import create_user, get_user, get_user_by_email, get_users, update_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse, UserUpdate

router = APIRouter()


def _validate_unique_email(db: Session, email: str, current_user: User | None = None) -> None:
    existing_user = get_user_by_email(db, email)

    if existing_user is not None and (
        current_user is None or existing_user.id != current_user.id
    ):
        raise AppError("Email already exists.", status.HTTP_409_CONFLICT)


@router.post(
    "/users",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create user",
)
def create_user_endpoint(
    user_in: UserCreate,
    db: Session = Depends(get_db),
) -> UserResponse:
    _validate_unique_email(db, user_in.email)
    return create_user(db, user_in)


@router.get(
    "/users",
    response_model=list[UserResponse],
    summary="List users",
)
def list_users_endpoint(db: Session = Depends(get_db)) -> list[UserResponse]:
    return get_users(db)


@router.get(
    "/users/{user_id}",
    response_model=UserResponse,
    summary="Get user",
)
def get_user_endpoint(
    user_id: int,
    db: Session = Depends(get_db),
) -> UserResponse:
    user = get_user(db, user_id)

    if user is None:
        raise AppError("User not found.", status.HTTP_404_NOT_FOUND)

    return user


@router.patch(
    "/users/{user_id}",
    response_model=UserResponse,
    summary="Update user",
)
def update_user_endpoint(
    user_id: int,
    user_in: UserUpdate,
    db: Session = Depends(get_db),
) -> UserResponse:
    user = get_user(db, user_id)

    if user is None:
        raise AppError("User not found.", status.HTTP_404_NOT_FOUND)

    if user_in.email is not None:
        _validate_unique_email(db, user_in.email, current_user=user)

    return update_user(db, user, user_in)
