from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import signed_in_user
from app.models import User, UserStatus
from app.ratelimit import LOGIN_FAILURES_PER_EMAIL, LOGIN_FAILURES_PER_IP, client_ip, too_many
from app.schemas import Credentials, SetupIn, UserOut
from app.security import DUMMY_HASH, hash_password, verify_password
from app.sessions import revoke_sessions, session_account, start_session

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
def login(body: Credentials, request: Request, db: Session = Depends(get_db)) -> UserOut:
    ip = client_ip(request)
    # Checked before the password, so a locked-out account can't be guessed at all.
    if wait := max(LOGIN_FAILURES_PER_EMAIL.retry_after(body.email), LOGIN_FAILURES_PER_IP.retry_after(ip)):
        raise too_many(wait, "failed sign-in attempts")
    user = db.scalar(select(User).where(User.email == body.email))
    password_ok = verify_password(body.password, user.password_hash if user else DUMMY_HASH)
    if user is None or not password_ok:
        LOGIN_FAILURES_PER_EMAIL.record(body.email)
        LOGIN_FAILURES_PER_IP.record(ip)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    if user.status == UserStatus.pending:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your application is still awaiting approval")
    if user.status == UserStatus.rejected:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your application was rejected")
    start_session(request, user)
    return UserOut.model_validate(user)


@router.post("/setup")
def setup(body: SetupIn, request: Request, db: Session = Depends(get_db), user: User = Depends(signed_in_user)) -> UserOut:
    """First sign-in: set your name and replace the password the administrator gave you."""
    # Only allowed once, so it can't be used to change a password without knowing the current one.
    if not user.needs_setup:
        raise HTTPException(status.HTTP_409_CONFLICT, "Your account is already set up")
    if verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Choose a new password, not the one you were given")
    user.full_name = body.full_name
    user.password_hash = hash_password(body.password)
    # Sign out every other session that used the first password, then keep this one signed in.
    revoke_sessions(user, db)
    start_session(request, user)
    return UserOut.model_validate(user)


@router.post("/logout")
def logout(request: Request, db: Session = Depends(get_db)) -> dict:
    """Sign out everywhere: every session cookie issued to this account stops working."""
    user = session_account(request, db)
    if user is not None:
        revoke_sessions(user, db)
    request.session.clear()
    return {"message": "Logged out"}


@router.get("/me")
def me(user: User = Depends(signed_in_user)) -> UserOut:
    return UserOut.model_validate(user)
