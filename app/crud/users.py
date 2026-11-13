from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate


def create_user(db: Session, user_in: UserCreate) -> User:

    user = User(
        email= user_in.email,
        full_name= user_in.full_name,
        hashed_password= hash_password(user_in.password),
        role="requester",
        is_active = True,
        )

    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def get_user(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email))


def get_users(db: Session) -> list[User]:
    return list(db.scalars(select(User)).all())


def update_user(db: Session, user: User, user_in: UserUpdate) -> User:
    update_data = user_in.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(user, field, value)

    db.add(user)
    db.commit()
    db.refresh(user)
    return user
