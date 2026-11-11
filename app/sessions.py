"""Session helpers shared by the API and the HTML pages."""

from fastapi import Request
from sqlalchemy.orm import Session

from app.models import User

USER_KEY = "user_id"
VERSION_KEY = "session_version"


def start_session(request: Request, user: User) -> None:
    request.session.clear()
    request.session[USER_KEY] = user.id
    request.session[VERSION_KEY] = user.session_version


def session_account(request: Request, db: Session) -> User | None:
    """The account this session belongs to, or None if there is none or the session was revoked."""
    user_id = request.session.get(USER_KEY)
    user = db.get(User, user_id) if user_id else None
    if user is None or request.session.get(VERSION_KEY) != user.session_version:
        request.session.clear()
        return None
    return user


def revoke_sessions(user: User, db: Session) -> None:
    """Invalidate every session cookie issued to this user so far."""
    user.session_version += 1
    db.commit()
