from datetime import datetime, timedelta, timezone

from app.database import SessionLocal
from app.models import Link


def add_link(client, invite):
    assert client.post("/api/links/check", json={"invite": invite}).status_code == 200
    r = client.post("/api/links", json={"category": "Gaming", "invite": invite, "description": "d", "source": "s"})
    assert r.status_code == 201
    return r.json()["id"]


def set_created_at(link_id, when):
    with SessionLocal() as db:
        db.get(Link, link_id).created_at = when
        db.commit()


def ids(admin, **params):
    return [link["id"] for link in admin.get("/api/admin/links", params=params).json()]


def test_admin_links_require_admin(client, user):
    for path in ("/api/admin/links", "/api/admin/submitters"):
        assert client.get(path).status_code == 401
        assert user.get(path).status_code == 403
    assert user.delete("/api/admin/links/1").status_code == 403


def test_admin_list_shows_server_and_submitter_details(user, admin):
    add_link(user, "alpha")
    [link] = admin.get("/api/admin/links").json()
    assert link["guild_id"] == "111111111111111111"
    assert link["icon_url"].startswith("https://cdn.discordapp.com/icons/111111111111111111/")
    assert link["invite_url"] == "https://discord.gg/alpha"
    assert link["category"] == "Gaming"
    assert link["submitter"]["full_name"] == "Uma User"
    assert link["submitter"]["email"] == "user@example.com"
    assert link["deleted_at"] is None


def test_submitter_stays_hidden_from_regular_users(user, other_user):
    add_link(user, "alpha")
    text = other_user.get("/api/links").text
    assert "Uma User" not in text and "user@example.com" not in text


def test_filter_by_submitter(user, other_user, admin):
    a = add_link(user, "alpha")
    b = add_link(other_user, "beta")
    submitters = admin.get("/api/admin/submitters").json()
    by_email = {s["email"]: s["id"] for s in submitters}
    assert set(by_email) == {"user@example.com", "other@example.com"}  # admin has no links
    assert ids(admin, submitter_id=by_email["user@example.com"]) == [a]
    assert ids(admin, submitter_id=by_email["other@example.com"]) == [b]
    assert sorted(ids(admin)) == sorted([a, b])


def test_filter_by_date(user, admin):
    old = add_link(user, "alpha")
    new = add_link(user, "beta")
    set_created_at(old, datetime(2026, 1, 15, 12, tzinfo=timezone.utc))
    set_created_at(new, datetime(2026, 3, 10, 12, tzinfo=timezone.utc))
    assert ids(admin, date_from="2026-02-01T00:00:00Z") == [new]
    assert ids(admin, date_to="2026-02-01T00:00:00Z") == [old]
    assert ids(admin, date_from="2026-01-15T00:00:00Z", date_to="2026-01-16T00:00:00Z") == [old]
    assert ids(admin, date_from="2026-04-01T00:00:00Z") == []
    assert admin.get("/api/admin/links", params={"date_from": "not-a-date"}).status_code == 422


def test_filters_combine(user, other_user, admin):
    a = add_link(user, "alpha")
    add_link(other_user, "beta")
    set_created_at(a, datetime.now(timezone.utc) - timedelta(days=10))
    uid = next(s["id"] for s in admin.get("/api/admin/submitters").json() if s["email"] == "user@example.com")
    recent = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    assert ids(admin, submitter_id=uid, date_from=recent) == []
    assert ids(admin, submitter_id=uid) == [a]


def test_delete_is_soft_and_listed_with_include_deleted(user, admin):
    link_id = add_link(user, "alpha")
    assert admin.delete(f"/api/admin/links/{link_id}").status_code == 204
    assert ids(admin) == []
    [deleted] = admin.get("/api/admin/links", params={"include_deleted": "true"}).json()
    assert deleted["id"] == link_id and deleted["deleted_at"] is not None
    assert admin.delete(f"/api/admin/links/{link_id}").status_code == 404  # already deleted
    assert admin.delete("/api/admin/links/999999").status_code == 404
