from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import admin_user
from app.models import User, UserStatus
from app.schemas import UserOut

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/users")
def list_users(
    status_filter: UserStatus | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
    _: User = Depends(admin_user),
) -> list[UserOut]:
    query = select(User).order_by(User.created_at.desc())
    if status_filter is not None:
        query = query.where(User.status == status_filter)
    return [UserOut.model_validate(u) for u in db.scalars(query)]


def _set_status(user_id: int, new_status: UserStatus, admin: User, db: Session) -> UserOut:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if user.id == admin.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot change your own status")
    if user.is_admin:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Administrator accounts cannot be changed here")
    user.status = new_status
    user.reviewed_at = func.now()
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


@router.post("/users/{user_id}/approve")
def approve_user(user_id: int, db: Session = Depends(get_db), admin: User = Depends(admin_user)) -> UserOut:
    return _set_status(user_id, UserStatus.approved, admin, db)


@router.post("/users/{user_id}/reject")
def reject_user(user_id: int, db: Session = Depends(get_db), admin: User = Depends(admin_user)) -> UserOut:
    return _set_status(user_id, UserStatus.rejected, admin, db)
