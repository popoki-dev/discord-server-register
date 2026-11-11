from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import current_user
from app.models import User, UserStatus
from app.schemas import Credentials, UserOut
from app.security import DUMMY_HASH, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(body: Credentials, db: Session = Depends(get_db)) -> dict:
    if db.scalar(select(User).where(User.email == body.email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email is already registered")
    db.add(User(email=body.email, password_hash=hash_password(body.password)))
    db.commit()
    return {"message": "Application submitted. An administrator will review it."}


@router.post("/login")
def login(body: Credentials, request: Request, db: Session = Depends(get_db)) -> UserOut:
    user = db.scalar(select(User).where(User.email == body.email))
    password_ok = verify_password(body.password, user.password_hash if user else DUMMY_HASH)
    if user is None or not password_ok:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    if user.status == UserStatus.pending:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your application is still awaiting approval")
    if user.status == UserStatus.rejected:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your application was rejected")
    request.session.clear()
    request.session["user_id"] = user.id
    return UserOut.model_validate(user)


@router.post("/logout")
def logout(request: Request) -> dict:
    request.session.clear()
    return {"message": "Logged out"}


@router.get("/me")
def me(user: User = Depends(current_user)) -> UserOut:
    return UserOut.model_validate(user)
