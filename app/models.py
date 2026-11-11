import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(100), default="", server_default="")
    password_hash: Mapped[str] = mapped_column(String(255))
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, name="user_status"), default=UserStatus.pending, index=True
    )
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    links: Mapped[list["Link"]] = relationship(back_populates="submitter")


class Link(Base):
    __tablename__ = "links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # One entry per Discord server, regardless of which invite code was used.
    guild_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    invite_code: Mapped[str] = mapped_column(String(64))
    category: Mapped[str] = mapped_column(String(64), index=True)
    description: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(255))
    guild_name: Mapped[str] = mapped_column(String(255))
    guild_icon: Mapped[str | None] = mapped_column(String(255))
    member_count: Mapped[int | None] = mapped_column(Integer)
    # Kept for moderation; never exposed through the public link API.
    submitted_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    # Set when an admin deletes the link. The row is kept so the server stays blocked
    # (guild_id is unique) and can never be submitted again.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    submitter: Mapped[User] = relationship(back_populates="links")
