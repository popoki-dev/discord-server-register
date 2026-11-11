from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models import UserStatus


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("password")
    @classmethod
    def bcrypt_limit(cls, v: str) -> str:
        if len(v.encode()) > 72:
            raise ValueError("Password must be at most 72 bytes")
        return v


class UserOut(BaseModel):
    id: int
    email: str
    status: UserStatus
    is_admin: bool
    created_at: datetime
    reviewed_at: datetime | None

    model_config = {"from_attributes": True}
