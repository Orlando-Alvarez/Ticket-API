from datetime import datetime

from pydantic import BaseModel, ConfigDict


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


class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
