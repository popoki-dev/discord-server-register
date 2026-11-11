from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserStatus
from app.sessions import session_account


def signed_in_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Any approved, signed-in account, including one that hasn't finished first-time setup."""
    user = session_account(request, db)
    if user is None:
        request.session.clear()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not logged in")
    # Re-checked on every request so revoking approval takes effect immediately.
    if user.status != UserStatus.approved:
        request.session.clear()
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is not approved")
    return user


def current_user(user: User = Depends(signed_in_user)) -> User:
    """A signed-in account that has set its name and password. Required by everything except setup."""
    if user.needs_setup:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Set your name and a new password first")
    return user


def admin_user(user: User = Depends(current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin only")
    return user
