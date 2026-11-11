"""All API times are UTC ("Z"), taken from the database server's clock."""

from datetime import datetime, timedelta, timezone

from app.database import engine
from app.schemas import _utc_iso
from sqlalchemy import text


def test_utc_iso_normalises_any_offset():
    tokyo = timezone(timedelta(hours=9))
    assert _utc_iso(datetime(2026, 1, 1, 9, 0, tzinfo=tokyo)) == "2026-01-01T00:00:00Z"
    assert _utc_iso(datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)) == "2026-01-01T00:00:00Z"
    assert _utc_iso(datetime(2026, 1, 1, 0, 0)) == "2026-01-01T00:00:00Z"  # naive is treated as UTC


def test_database_sessions_run_in_utc():
    with engine.connect() as conn:
        assert conn.scalar(text("SHOW TIME ZONE")) == "UTC"


def test_api_times_are_utc_and_from_the_server_clock(user, admin):
    before = datetime.now(timezone.utc) - timedelta(minutes=1)
    assert user.post("/api/links/check", json={"invite": "temp"}).json()["expires_at"] == "2030-01-01T00:00:00Z"
    user.post("/api/links/check", json={"invite": "alpha"})
    link = user.post("/api/links", json={"invite": "alpha", "source": "s"}).json()
    assert link["register_time"].endswith("Z")
    registered = datetime.fromisoformat(link["register_time"].replace("Z", "+00:00"))
    assert before <= registered <= datetime.now(timezone.utc) + timedelta(minutes=1)
    [account] = [u for u in admin.get("/api/admin/users").json() if u["email"] == "user@example.com"]
    assert account["created_at"].endswith("Z")


def test_date_filters_accept_any_offset(user, admin):
    user.post("/api/links/check", json={"invite": "alpha"})
    link = user.post("/api/links", json={"invite": "alpha", "source": "s"}).json()
    registered = datetime.fromisoformat(link["register_time"].replace("Z", "+00:00"))
    tokyo = timezone(timedelta(hours=9))
    just_after = (registered + timedelta(seconds=1)).astimezone(tokyo).isoformat()
    assert [l["id"] for l in admin.get("/api/links", params={"date_to": just_after}).json()] == [link["id"]]
    assert admin.get("/api/links", params={"date_from": just_after}).json() == []
