from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, text
from starlette.middleware.sessions import SessionMiddleware

from app import models  # noqa: F401  (registers tables on Base.metadata)
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.migrations import upgrade
from app.models import User, UserStatus
from app.routers import admin, auth, links, pages
from app.security import hash_password


def ensure_admin() -> None:
    """Create the bootstrap admin from ADMIN_EMAIL/ADMIN_PASSWORD if it doesn't exist."""
    if not (settings.admin_email and settings.admin_password):
        return
    email = settings.admin_email.strip().lower()
    with SessionLocal() as db:
        existing = db.scalar(select(User).where(User.email == email))
        if existing:
            if not existing.full_name:  # accounts created before full names existed
                existing.full_name = settings.admin_name
                db.commit()
            return
        db.add(
            User(
                email=email,
                full_name=settings.admin_name,
                password_hash=hash_password(settings.admin_password),
                status=UserStatus.approved,
                is_admin=True,
            )
        )
        db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    upgrade(engine)
    ensure_admin()
    yield


app = FastAPI(title="Discord Server Register", lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    session_cookie="dsr_session",
    max_age=60 * 60 * 24 * 7,
    same_site="lax",
)
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(links.router)
app.include_router(pages.router)
app.mount("/static", StaticFiles(directory=Path(__file__).resolve().parent / "static"), name="static")


@app.get("/health")
def health() -> dict:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok"}
