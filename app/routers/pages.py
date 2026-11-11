import hashlib
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserStatus
from app.sessions import session_account

router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@lru_cache(maxsize=256)
def _file_hash(path: Path, mtime_ns: int) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def static_url(name: str) -> str:
    """URL for a static file with a content hash, so browsers fetch it again whenever it changes."""
    path = STATIC_DIR / name
    try:
        return f"/static/{name}?v={_file_hash(path, path.stat().st_mtime_ns)}"
    except FileNotFoundError:
        return f"/static/{name}"


templates.env.globals["static_url"] = static_url


def session_user(request: Request, db: Session) -> User | None:
    user = session_account(request, db)
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


@router.get("/admin/links")
def admin_links_page(request: Request, db: Session = Depends(get_db)):
    """Link management moved into the links page; keep old bookmarks working."""
    user = session_user(request, db)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    return RedirectResponse("/", status_code=303)
