from datetime import datetime, timezone
from typing import Annotated

from pydantic import BaseModel, EmailStr, Field, PlainSerializer, field_validator

from app.models import UserStatus


def _utc_iso(value: datetime) -> str:
    if value.tzinfo is None:  # treat naive values as UTC rather than the server's local zone
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


# Every time in the API is sent as UTC ISO 8601 ending in "Z"; the browser converts it to the viewer's zone.
UTCDateTime = Annotated[datetime, PlainSerializer(_utc_iso, return_type=str)]


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


class RegisterIn(Credentials):
    full_name: str = Field(min_length=1, max_length=100)

    @field_validator("full_name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("Full name must not be blank")
        return v


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    status: UserStatus
    is_admin: bool
    created_at: UTCDateTime
    reviewed_at: UTCDateTime | None

    model_config = {"from_attributes": True}


class InviteCheckIn(BaseModel):
    invite: str = Field(min_length=1, max_length=255)


class ServerInfo(BaseModel):
    guild_id: str
    name: str
    icon_url: str | None
    description: str | None
    member_count: int | None
    online_count: int | None
    invite_url: str
    expires_at: UTCDateTime | None
    already_registered: bool
    # True when the server was registered before and then deleted by an admin (permanently blocked).
    removed: bool


class LinkIn(BaseModel):
    invite: str = Field(min_length=1, max_length=255)
    source: str = Field(min_length=1, max_length=255)

    @field_validator("source")
    @classmethod
    def strip_text(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Must not be blank")
        return v


class LinkOut(BaseModel):
    """A link as its submitter sees it. Deliberately has no submitter field."""

    id: int
    guild_id: str
    name: str
    icon_url: str | None
    description: str | None
    member_count: int | None
    online_count: int | None
    invite_url: str
    expires_at: UTCDateTime | None
    source: str
    register_time: UTCDateTime
    removed: bool

    model_config = {"from_attributes": True}


class Submitter(BaseModel):
    id: int
    full_name: str
    email: str

    model_config = {"from_attributes": True}


class AdminLinkOut(LinkOut):
    """Admin view of a link, including who submitted it and whether it has been joined."""

    joined: bool
    register_account: Submitter
