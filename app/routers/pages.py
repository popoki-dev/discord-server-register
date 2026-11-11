from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserStatus

router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")


def session_user(request: Request, db: Session) -> User | None:
    user_id = request.session.get("user_id")
    user = db.get(User, user_id) if user_id else None
    if user is None or user.status != UserStatus.approved:
        request.session.clear()
        return None
    return user


@router.get("/")
def links_page(request: Request, db: Session = Depends(get_db)):
    user = session_user(request, db)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    return templates.TemplateResponse(request, "links.html", {"user": user, "page": "links"})


@router.get("/admin")
def admin_page(request: Request, db: Session = Depends(get_db)):
    user = session_user(request, db)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    if not user.is_admin:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request, "admin.html", {"user": user, "page": "admin"})


@router.get("/login")
def login_page(request: Request, db: Session = Depends(get_db)):
    if session_user(request, db):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request, "login.html", {"user": None, "page": "login"})
