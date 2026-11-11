from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.deps import admin_user
from app.models import Link, User, UserStatus
from app.routers.links import admin_link_out
from app.schemas import AdminLinkOut, NewUserIn, Submitter, UserOut
from app.security import hash_password

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


EMAIL_TAKEN = "A user with this email already exists"


@router.post("/users", status_code=status.HTTP_201_CREATED)
def create_user(body: NewUserIn, db: Session = Depends(get_db), _: User = Depends(admin_user)) -> UserOut:
    """Create an approved account. The user sets their name and their own password on first sign-in."""
    if db.scalar(select(User).where(User.email == body.email)) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, EMAIL_TAKEN)
    user = User(email=body.email, full_name="", password_hash=hash_password(body.password), status=UserStatus.approved)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:  # created by another admin at the same moment
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, EMAIL_TAKEN) from None
    db.refresh(user)
    return UserOut.model_validate(user)


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


# ---------------------------------------------------------------- link management


@router.get("/submitters")
def list_submitters(db: Session = Depends(get_db), _: User = Depends(admin_user)) -> list[Submitter]:
    """Users who have submitted at least one link, for the submitter filter."""
    query = select(User).where(User.id.in_(select(Link.register_account))).order_by(User.full_name, User.email)
    return [Submitter.model_validate(u) for u in db.scalars(query)]


def _set_joined(link_id: int, joined: bool, db: Session) -> AdminLinkOut:
    link = db.get(Link, link_id, options=[joinedload(Link.submitter)])
    if link is None or link.removed:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Link not found")
    link.joined = joined
    db.commit()
    return admin_link_out(link)


@router.post("/links/{link_id}/joined")
def mark_joined(link_id: int, db: Session = Depends(get_db), _: User = Depends(admin_user)) -> AdminLinkOut:
    """Mark the link's server as joined."""
    return _set_joined(link_id, True, db)


@router.delete("/links/{link_id}/joined")
def mark_unjoined(link_id: int, db: Session = Depends(get_db), _: User = Depends(admin_user)) -> AdminLinkOut:
    """Mark the link's server as not joined."""
    return _set_joined(link_id, False, db)


@router.delete("/links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_link(link_id: int, db: Session = Depends(get_db), _: User = Depends(admin_user)) -> Response:
    """Soft-delete: the link disappears from the list, and its server can never be submitted again."""
    link = db.get(Link, link_id)
    if link is None or link.removed:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Link not found")
    link.removed = True
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/links/{link_id}/restore")
def restore_link(link_id: int, db: Session = Depends(get_db), _: User = Depends(admin_user)) -> AdminLinkOut:
    """Undo a delete: the link is listed again and keeps its original details and submitter."""
    link = db.get(Link, link_id, options=[joinedload(Link.submitter)])
    if link is None or not link.removed:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Deleted link not found")
    link.removed = False
    db.commit()
    return admin_link_out(link)
