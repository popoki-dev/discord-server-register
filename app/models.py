import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, false, func
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
    # Stored in the session cookie at login. Logging out increments it, which invalidates every
    # cookie issued before, including copies on other devices or stolen ones.
    session_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    links: Mapped[list["Link"]] = relationship(back_populates="submitter")

    @property
    def needs_setup(self) -> bool:
        """Accounts created by an administrator have no name until the user signs in and sets one."""
        return not self.full_name


class Link(Base):
    """A registered Discord server. The server details are captured from Discord when it's submitted."""

    __tablename__ = "links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # One entry per Discord server, regardless of which invite code was used.
    guild_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    icon_url: Mapped[str | None] = mapped_column(String(255))
    # The server's own description on Discord.
    description: Mapped[str | None] = mapped_column(Text)
    member_count: Mapped[int | None] = mapped_column(Integer)
    online_count: Mapped[int | None] = mapped_column(Integer)
    invite_url: Mapped[str] = mapped_column(String(255))
    # When the invite expires, if it's temporary.
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Where the submitter found the link.
    source: Mapped[str] = mapped_column(String(255))
    # Whether the server has been joined. New submissions start as not joined.
    joined: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    register_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    # The account that submitted the link. Kept for moderation; never exposed through the public link API.
    register_account: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    # Set when an admin deletes the link. The row is kept so the server stays blocked
    # (guild_id is unique) and can never be submitted again.
    removed: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false(), index=True)

    submitter: Mapped[User] = relationship(back_populates="links")
