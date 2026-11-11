from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import current_user
from app.models import User, UserStatus
from app.ratelimit import LOGIN_FAILURES_PER_EMAIL, LOGIN_FAILURES_PER_IP, REGISTRATIONS_PER_IP, client_ip, too_many
from app.schemas import Credentials, RegisterIn, UserOut
from app.security import DUMMY_HASH, hash_password, verify_password
from app.sessions import revoke_sessions, session_account, start_session

router = APIRouter(prefix="/api/auth", tags=["auth"])

REGISTERED_MESSAGE = (
    "Application received. If this email isn't already registered, an administrator will review it "
    "and you can sign in once it's approved."
)


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn, request: Request, db: Session = Depends(get_db)) -> dict:
    if wait := REGISTRATIONS_PER_IP.hit(client_ip(request)):
        raise too_many(wait, "applications from your network")
    # The response is the same whether or not the email is already registered, so the form can't be
    # used to find out who has an account. The password is hashed either way so timing matches too.
    password_hash = hash_password(body.password)
    if db.scalar(select(User).where(User.email == body.email)) is None:
        db.add(User(email=body.email, full_name=body.full_name, password_hash=password_hash))
        try:
            db.commit()
        except IntegrityError:  # the same email registered at the same moment
            db.rollback()
    return {"message": REGISTERED_MESSAGE}


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


@router.post("/logout")
def logout(request: Request, db: Session = Depends(get_db)) -> dict:
    """Sign out everywhere: every session cookie issued to this account stops working."""
    user = session_account(request, db)
    if user is not None:
        revoke_sessions(user, db)
    request.session.clear()
    return {"message": "Logged out"}


@router.get("/me")
def me(user: User = Depends(current_user)) -> UserOut:
    return UserOut.model_validate(user)
