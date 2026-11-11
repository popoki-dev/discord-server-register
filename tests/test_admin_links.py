from datetime import datetime, timedelta, timezone

from app.database import SessionLocal
from app.models import Link


def add_link(client, invite):
    assert client.post("/api/links/check", json={"invite": invite}).status_code == 200
    r = client.post("/api/links", json={"invite": invite, "source": "s"})
    assert r.status_code == 201
    return r.json()["id"]


def set_register_time(link_id, when):
    with SessionLocal() as db:
        db.get(Link, link_id).register_time = when
        db.commit()


def ids(admin, **params):
    return [link["id"] for link in admin.get("/api/links", params=params).json()]


def test_admin_links_require_admin(client, user):
    for path in ("/api/admin/submitters",):
        assert client.get(path).status_code == 401
        assert user.get(path).status_code == 403
    assert user.delete("/api/admin/links/1").status_code == 403
    assert user.post("/api/admin/links/1/joined").status_code == 403
    assert user.delete("/api/admin/links/1/joined").status_code == 403
    assert user.post("/api/admin/links/1/restore").status_code == 403


def test_admin_list_shows_server_and_submitter_details(user, admin):
    add_link(user, "alpha")
    [link] = admin.get("/api/links").json()
    assert link["guild_id"] == "111111111111111111"
    assert link["icon_url"].startswith("https://cdn.discordapp.com/icons/111111111111111111/")
    assert link["invite_url"] == "https://discord.gg/alpha"
    assert link["name"] == "Alpha Server"
    assert (link["member_count"], link["online_count"]) == (1234, 56)
    assert link["register_account"]["full_name"] == "Uma User"
    assert link["register_account"]["email"] == "user@example.com"
    assert link["joined"] is False
    assert link["removed"] is False


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
    set_register_time(old, datetime(2026, 1, 15, 12, tzinfo=timezone.utc))
    set_register_time(new, datetime(2026, 3, 10, 12, tzinfo=timezone.utc))
    assert ids(admin, date_from="2026-02-01T00:00:00Z") == [new]
    assert ids(admin, date_to="2026-02-01T00:00:00Z") == [old]
    assert ids(admin, date_from="2026-01-15T00:00:00Z", date_to="2026-01-16T00:00:00Z") == [old]
    assert ids(admin, date_from="2026-04-01T00:00:00Z") == []
    assert admin.get("/api/links", params={"date_from": "not-a-date"}).status_code == 422


def test_filters_combine(user, other_user, admin):
    a = add_link(user, "alpha")
    add_link(other_user, "beta")
    set_register_time(a, datetime.now(timezone.utc) - timedelta(days=10))
    uid = next(s["id"] for s in admin.get("/api/admin/submitters").json() if s["email"] == "user@example.com")
    recent = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    assert ids(admin, submitter_id=uid, date_from=recent) == []
    assert ids(admin, submitter_id=uid) == [a]


def test_delete_is_soft_and_listed_with_deletion_filter(user, admin):
    link_id = add_link(user, "alpha")
    assert admin.delete(f"/api/admin/links/{link_id}").status_code == 204
    assert ids(admin) == []
    [removed] = admin.get("/api/links", params={"deletion": "deleted"}).json()
    assert removed["id"] == link_id and removed["removed"] is True
    assert ids(admin, deletion="all") == [link_id]
    assert admin.delete(f"/api/admin/links/{link_id}").status_code == 404  # already deleted
    assert admin.delete("/api/admin/links/999999").status_code == 404


def test_mark_joined(user, admin):
    link_id = add_link(user, "alpha")
    r = admin.post(f"/api/admin/links/{link_id}/joined")
    assert r.status_code == 200
    assert r.json()["joined"] is True
    assert admin.post(f"/api/admin/links/{link_id}/joined").json()["joined"] is True  # stays joined
    r = admin.delete(f"/api/admin/links/{link_id}/joined")  # unjoin
    assert r.status_code == 200 and r.json()["joined"] is False
    assert admin.post(f"/api/admin/links/{link_id}/joined").json()["joined"] is True
    [link] = admin.get("/api/links").json()
    assert link["joined"] is True
    with SessionLocal() as db:
        assert db.get(Link, link_id).joined is True


def test_mark_joined_unknown_or_removed_link(user, admin):
    assert admin.post("/api/admin/links/999999/joined").status_code == 404
    link_id = add_link(user, "alpha")
    admin.delete(f"/api/admin/links/{link_id}")
    assert admin.post(f"/api/admin/links/{link_id}/joined").status_code == 404
    assert admin.delete(f"/api/admin/links/{link_id}/joined").status_code == 404


def test_admin_search(user, admin):
    a = add_link(user, "alpha")
    add_link(user, "beta")
    assert ids(admin, q="alpha") == [a]
    assert ids(admin, q="%") == []


def test_filter_by_joined_status(user, admin):
    a = add_link(user, "alpha")
    b = add_link(user, "beta")
    admin.post(f"/api/admin/links/{a}/joined")
    assert ids(admin, joined="joined") == [a]
    assert ids(admin, joined="unjoined") == [b]
    assert sorted(ids(admin, joined="all")) == sorted([a, b])
    assert admin.get("/api/links", params={"joined": "maybe"}).status_code == 422


def test_filter_by_deletion_status(user, admin):
    kept = add_link(user, "alpha")
    gone = add_link(user, "beta")
    admin.delete(f"/api/admin/links/{gone}")
    assert ids(admin) == [kept]  # not deleted by default
    assert ids(admin, deletion="active") == [kept]
    assert ids(admin, deletion="deleted") == [gone]
    assert sorted(ids(admin, deletion="all")) == sorted([kept, gone])
    assert admin.get("/api/links", params={"deletion": "nope"}).status_code == 422


def test_search_matches_name_or_description_only(user, admin):
    a = add_link(user, "alpha")  # description "Alpha desc", source "s"
    add_link(user, "beta")
    assert ids(admin, q="alpha server") == [a]
    assert ids(admin, q="DESC") == [a]
    assert ids(admin, q="zzz") == []


def test_all_filters_combine(user, other_user, admin):
    a = add_link(user, "alpha")
    add_link(other_user, "beta")
    admin.post(f"/api/admin/links/{a}/joined")
    uid = next(s["id"] for s in admin.get("/api/admin/submitters").json() if s["email"] == "user@example.com")
    today = datetime.now(timezone.utc)
    params = dict(q="alpha", submitter_id=uid, joined="joined", deletion="active",
                  date_from=(today - timedelta(days=1)).isoformat(), date_to=(today + timedelta(days=1)).isoformat())
    assert ids(admin, **params) == [a]
    assert ids(admin, **{**params, "joined": "unjoined"}) == []
    admin.delete(f"/api/admin/links/{a}")
    assert ids(admin, **params) == []
    assert ids(admin, **{**params, "deletion": "deleted"}) == [a]


def test_restore_deleted_link(user, admin):
    link_id = add_link(user, "alpha")
    admin.post(f"/api/admin/links/{link_id}/joined")
    admin.delete(f"/api/admin/links/{link_id}")
    r = admin.post(f"/api/admin/links/{link_id}/restore")
    assert r.status_code == 200
    body = r.json()
    assert body["removed"] is False
    assert body["joined"] is True  # other fields are untouched
    assert body["register_account"]["email"] == "user@example.com"
    assert ids(admin) == [link_id]
    assert [l["id"] for l in user.get("/api/links").json()] == [link_id]  # back in the submitter's list
    assert ids(admin, deletion="deleted") == []


def test_restore_requires_a_deleted_link(user, admin):
    link_id = add_link(user, "alpha")
    assert admin.post(f"/api/admin/links/{link_id}/restore").status_code == 404  # not deleted
    assert admin.post("/api/admin/links/999999/restore").status_code == 404


def test_restored_server_is_still_a_duplicate(user, other_user, admin):
    link_id = add_link(user, "alpha")
    admin.delete(f"/api/admin/links/{link_id}")
    admin.post(f"/api/admin/links/{link_id}/restore")
    r = other_user.post("/api/links/check", json={"invite": "alpha-other"})
    assert r.json()["already_registered"] is True and r.json()["removed"] is False
