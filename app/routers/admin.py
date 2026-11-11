from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.deps import admin_user
from app.models import Link, User, UserStatus
from app.schemas import AdminLinkOut, LinkOut, Submitter, UserOut

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


# ---------------------------------------------------------------- link management


def _admin_link(link: Link) -> AdminLinkOut:
    return AdminLinkOut(
        **LinkOut.model_validate(link).model_dump(),
        joined=link.joined,
        register_account=Submitter.model_validate(link.submitter),
        removed=link.removed,
    )


@router.get("/links")
def list_links(
    submitter_id: int | None = None,
    date_from: datetime | None = Query(None, description="Registered at or after (ISO 8601)"),
    date_to: datetime | None = Query(None, description="Registered before (ISO 8601, exclusive)"),
    include_removed: bool = False,
    db: Session = Depends(get_db),
    _: User = Depends(admin_user),
) -> list[AdminLinkOut]:
    query = select(Link).options(joinedload(Link.submitter)).order_by(Link.register_time.desc())
    if not include_removed:
        query = query.where(Link.removed.is_(False))
    if submitter_id is not None:
        query = query.where(Link.register_account == submitter_id)
    if date_from is not None:
        query = query.where(Link.register_time >= date_from)
    if date_to is not None:
        query = query.where(Link.register_time < date_to)
    return [_admin_link(link) for link in db.scalars(query)]


@router.get("/submitters")
def list_submitters(db: Session = Depends(get_db), _: User = Depends(admin_user)) -> list[Submitter]:
    """Users who have submitted at least one link, for the submitter filter."""
    query = select(User).where(User.id.in_(select(Link.register_account))).order_by(User.full_name, User.email)
    return [Submitter.model_validate(u) for u in db.scalars(query)]


@router.post("/links/{link_id}/joined")
def mark_joined(link_id: int, db: Session = Depends(get_db), _: User = Depends(admin_user)) -> AdminLinkOut:
    """Record that the server has been joined. Clicking it again leaves it joined."""
    link = db.get(Link, link_id, options=[joinedload(Link.submitter)])
    if link is None or link.removed:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Link not found")
    link.joined = True
    db.commit()
    return _admin_link(link)


@router.delete("/links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_link(link_id: int, db: Session = Depends(get_db), _: User = Depends(admin_user)) -> Response:
    """Soft-delete: the link disappears from the list, and its server can never be submitted again."""
    link = db.get(Link, link_id)
    if link is None or link.removed:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Link not found")
    link.removed = True
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
