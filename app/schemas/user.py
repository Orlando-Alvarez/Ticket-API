from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator
from pydantic_core import PydanticCustomError


class UserBase(BaseModel):
    email: str
    full_name: str
    role: str = "requester"
    is_active: bool = True


class UserCreate(UserBase):
    hashed_password: str


class UserUpdate(BaseModel):
    email: str | None = None
    full_name: str | None = None
    hashed_password: str | None = None
    role: str | None = None
    is_active: bool | None = None
    
    @field_validator(
    "email",
    "full_name",
    "hashed_password",
    "role",
    "is_active",
    mode="before"
    )
    @classmethod
    def reject_null(cls, value):
        if value is None:
            raise PydanticCustomError(
                "null_not_allowed",
                "Field cannot be null"
            )
        return value


class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
