from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_core import PydanticCustomError


UserText = Annotated[str, Field(min_length=1, max_length=255)]
UserRole = Annotated[str, Field(min_length=1, max_length=50)]


class UserBase(BaseModel):
    email: str
    full_name: str
    role: str = "requester"
    is_active: bool = True


class UserCreate(UserBase):
    email: UserText
    full_name: UserText
    role: UserRole = "requester"
    hashed_password: UserText


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: UserText | None = None
    full_name: UserText | None = None
    hashed_password: UserText | None = None
    role: UserRole | None = None
    is_active: bool | None = None

    @field_validator("email", "full_name", "hashed_password", "role", "is_active")
    @classmethod
    def reject_null(cls, value: str | bool | None) -> str | bool:
        if value is None:
            raise PydanticCustomError("null_not_allowed", "Field cannot be null")
        return value


class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
