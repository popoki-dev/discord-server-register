"""Test setup.

Tests run against a separate PostgreSQL database (``<your database>_test`` by default,
or TEST_DATABASE_URL if set) so they never touch real data. Discord is replaced with
an in-process fake, so no network access is needed.
"""

import os

# SECRET_KEY has no built-in default; the tests use their own. DATABASE_URL still comes from .env
# (or the environment) and is pointed at a separate test database below.
os.environ["SECRET_KEY"] = "test-only-secret-key-not-used-anywhere-else-0123456789"

import httpx
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.config import settings

# Point the app at the test database *before* app.database creates its engine.
_test_url = make_url(os.environ.get("TEST_DATABASE_URL") or settings.database_url)
if not os.environ.get("TEST_DATABASE_URL"):
    _test_url = _test_url.set(database=f"{_test_url.database}_test")
settings.database_url = _test_url.render_as_string(hide_password=False)
settings.secret_key = "test-only-secret-key-not-used-anywhere-else-0123456789"
settings.admin_email = "admin@example.com"
settings.admin_password = "admin-password-for-tests"

ADMIN = {"email": settings.admin_email, "password": settings.admin_password}

# Cheap bcrypt work factor for tests only (production uses bcrypt's default of 12).
import bcrypt  # noqa: E402

_real_gensalt = bcrypt.gensalt
bcrypt.gensalt = lambda rounds=4, prefix=b"2b": _real_gensalt(rounds, prefix)
PASSWORD = "secret123"


def _create_test_database() -> None:
    server = create_engine(_test_url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with server.connect() as conn:
        exists = conn.scalar(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": _test_url.database})
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{_test_url.database}"'))
    server.dispose()


_create_test_database()

from fastapi.testclient import TestClient  # noqa: E402

from app import discord  # noqa: E402
from app.database import Base, engine  # noqa: E402
from app.main import app, ensure_admin  # noqa: E402
from app.models import User, UserStatus  # noqa: E402

# ---------------------------------------------------------------- fake Discord

GUILD_A = {"id": "111111111111111111", "name": "Alpha Server", "icon": "abc123", "description": "Alpha desc"}
GROUP_DM = "group-dm"
GUILD_B = {"id": "222222222222222222", "name": "Beta Server", "icon": None, "description": None}


class FakeDiscord:
    """Maps invite codes to canned responses: a guild dict, or an int HTTP status."""

    def __init__(self):
        self.invites: dict[str, object] = {
            "alpha": GUILD_A,
            "alpha-other": GUILD_A,  # second invite code for the same server
            "beta": GUILD_B,
            "temp": {**GUILD_B, "expires": "2030-01-01T00:00:00+00:00"},
            "groupdm": GROUP_DM,
            "ratelimited": 429,
            "broken": 500,
        }
        self.calls = 0

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        code = request.url.path.rsplit("/", 1)[-1]
        entry = self.invites.get(code, 404)
        if isinstance(entry, int):
            return httpx.Response(entry, json={"message": "error"})
        if entry == GROUP_DM:
            return httpx.Response(200, json={"code": code, "type": 1, "channel": {"id": "1"}})
        guild = {k: v for k, v in entry.items() if k != "expires"}
        return httpx.Response(200, json={
            "code": code,
            "guild": guild,
            "approximate_member_count": 1234,
            "approximate_presence_count": 56,
            "expires_at": entry.get("expires"),
        })


@pytest.fixture(autouse=True)
def fake_discord(monkeypatch):
    fake = FakeDiscord()
    real_client = httpx.AsyncClient

    def client_factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(fake.handler)
        return real_client(*args, **kwargs)

    monkeypatch.setattr(discord.httpx, "AsyncClient", client_factory)
    return fake


# ---------------------------------------------------------------- database & clients

@pytest.fixture(scope="session", autouse=True)
def schema():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture(autouse=True)
def clean_db(schema):
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    ensure_admin()
    yield


def _client() -> TestClient:
    # HTTPS, so the Secure session cookie is sent back just as a browser would.
    return TestClient(app, base_url="https://testserver")


@pytest.fixture
def client():
    with _client() as c:
        yield c


@pytest.fixture
def admin():
    with _client() as c:
        assert c.post("/api/auth/login", json=ADMIN).status_code == 200
        yield c


def make_user(email: str, status: UserStatus = UserStatus.approved, full_name: str | None = None) -> None:
    full_name = full_name or email.split("@")[0].title()
    with _client() as c:
        r = c.post("/api/auth/register", json={"email": email, "password": PASSWORD, "full_name": full_name})
        assert r.status_code == 201
    from app.database import SessionLocal

    with SessionLocal() as db:
        db.query(User).filter_by(email=email).update({"status": status})
        db.commit()


def login(email: str) -> TestClient:
    c = _client()
    c.__enter__()
    assert c.post("/api/auth/login", json={"email": email, "password": PASSWORD}).status_code == 200
    return c


@pytest.fixture
def user():
    make_user("user@example.com", full_name="Uma User")
    c = login("user@example.com")
    yield c
    c.__exit__(None, None, None)


@pytest.fixture
def other_user():
    make_user("other@example.com", full_name="Otto Other")
    c = login("other@example.com")
    yield c
    c.__exit__(None, None, None)
