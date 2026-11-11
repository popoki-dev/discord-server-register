import pytest

from app.discord import InviteError, parse_invite_code

LINK = {"invite": "https://discord.gg/alpha", "source": "example.com"}


def check(client, invite):
    return client.post("/api/links/check", json={"invite": invite})


def submit(client, **overrides):
    return client.post("/api/links", json={**LINK, **overrides})


# ---------------------------------------------------------------- invite parsing

@pytest.mark.parametrize("value, code", [
    ("https://discord.gg/abc123", "abc123"),
    ("discord.gg/abc123/", "abc123"),
    ("https://discord.com/invite/abc-123?event=1", "abc-123"),
    ("https://www.discordapp.com/invite/abc", "abc"),
    ("  abc123  ", "abc123"),
])
def test_parse_invite_code(value, code):
    assert parse_invite_code(value) == code


@pytest.mark.parametrize("value", ["https://evil.com/abc", "discord.gg/", "has space", "https://discord.gg/a/b"])
def test_parse_invite_code_rejects_non_invites(value):
    with pytest.raises(InviteError):
        parse_invite_code(value)


# ---------------------------------------------------------------- check

def test_check_returns_server_info(user):
    r = check(user, "https://discord.gg/alpha")
    assert r.status_code == 200
    body = r.json()
    assert body["guild_id"] == "111111111111111111"
    assert body["name"] == "Alpha Server"
    assert body["member_count"] == 1234
    assert body["online_count"] == 56
    assert body["icon_url"] == "https://cdn.discordapp.com/icons/111111111111111111/abc123.png?size=128"
    assert body["invite_url"] == "https://discord.gg/alpha"
    assert body["already_registered"] is False


def test_check_reports_expiry(user):
    assert check(user, "temp").json()["expires_at"].startswith("2030-01-01")


@pytest.mark.parametrize("invite, status, fragment", [
    ("https://evil.com/x", 400, "doesn't look like"),
    ("unknown-code", 404, "invalid or has expired"),
    ("groupdm", 400, "not for a server"),
    ("ratelimited", 429, "rate limiting"),
    ("broken", 502, "unexpected error"),
])
def test_check_errors(user, invite, status, fragment):
    r = check(user, invite)
    assert r.status_code == status
    assert fragment in r.json()["detail"]


def test_check_requires_approved_login(client):
    assert check(client, "alpha").status_code == 401


# ---------------------------------------------------------------- submit

def test_submit_requires_a_prior_check(user, fake_discord):
    r = submit(user)
    assert r.status_code == 400
    assert "Check" in r.json()["detail"]
    assert fake_discord.calls == 0  # rejected before contacting Discord


def test_submit_stores_everything_check_returned(user):
    shown = check(user, "alpha").json()
    r = submit(user)
    assert r.status_code == 201
    body = r.json()
    assert body["guild_id"] == "111111111111111111"  # from Discord, not the client
    assert "category" not in body

    from app.database import SessionLocal
    from app.models import Link

    with SessionLocal() as db:
        link = db.query(Link).one()
        submitter_email = link.submitter.email
    for field in ("guild_id", "name", "icon_url", "description", "member_count", "online_count", "invite_url"):
        assert getattr(link, field) == shown[field], field
    assert link.expires_at is None
    assert link.description == "Alpha desc"
    assert link.source == "example.com"
    assert link.joined is False
    assert link.removed is False
    assert link.register_time is not None
    assert submitter_email == "user@example.com"


def test_submit_stores_invite_expiry(user):
    check(user, "temp")
    body = submit(user, invite="temp").json()
    assert body["expires_at"].startswith("2030-01-01")
    assert body["description"] is None


def test_category_and_description_are_not_accepted(user):
    check(user, "alpha")
    submit(user, category="Gaming", description="ignored")
    [link] = user.get("/api/links").json()
    assert link["description"] == "Alpha desc"  # Discord's description, not the client's


def test_check_is_per_session_and_single_use(user, other_user):
    check(user, "alpha")
    assert submit(other_user).status_code == 400  # another user's check doesn't count
    assert submit(user).status_code == 201
    assert submit(user).status_code == 400  # check was consumed


def test_check_accepts_any_url_form_of_the_same_code(user):
    check(user, "discord.gg/alpha")
    assert submit(user, invite="https://discord.com/invite/alpha").status_code == 201


def test_duplicate_server_is_detected_on_check(user, other_user):
    check(user, "alpha")
    submit(user)
    r = check(other_user, "alpha-other")  # different invite code, same server
    assert r.json()["already_registered"] is True
    assert submit(other_user, invite="alpha-other").status_code == 400  # never unlocked


def test_duplicate_submitted_after_check_returns_409(user, other_user):
    check(user, "alpha")
    check(other_user, "alpha-other")
    assert submit(other_user, invite="alpha-other").status_code == 201
    r = submit(user)
    assert r.status_code == 409
    assert r.json()["detail"] == "This server has already been registered"


@pytest.mark.parametrize("field, value", [
    ("source", ""),
    ("source", "   "),
    ("source", "x" * 256),
])
def test_submit_validates_fields(user, field, value):
    check(user, "alpha")
    assert submit(user, **{field: value}).status_code == 422


# ---------------------------------------------------------------- list

def test_list_hides_submitter(user, other_user):
    check(user, "alpha")
    submit(user)
    links = other_user.get("/api/links").json()
    assert len(links) == 1
    assert set(links[0]) == {
        "id", "guild_id", "name", "icon_url", "description", "member_count",
        "online_count", "invite_url", "expires_at", "source", "register_time",
    }
    assert "user@example.com" not in other_user.get("/api/links").text


def test_list_search(user):
    check(user, "alpha")
    submit(user)
    check(user, "beta")
    submit(user, invite="beta", source="100% tunes")
    assert len(user.get("/api/links").json()) == 2
    assert [l["name"] for l in user.get("/api/links", params={"q": "alpha"}).json()] == ["Alpha Server"]
    assert [l["name"] for l in user.get("/api/links", params={"q": "desc"}).json()] == ["Alpha Server"]
    assert len(user.get("/api/links", params={"q": "100%"}).json()) == 1
    assert len(user.get("/api/links", params={"q": "%"}).json()) == 1  # % is literal, not a wildcard


# ---------------------------------------------------------------- deleted servers stay blocked

def delete(admin, link_id):
    return admin.delete(f"/api/admin/links/{link_id}")


def test_deleted_link_disappears_from_public_list(user, admin):
    check(user, "alpha")
    link_id = submit(user).json()["id"]
    assert delete(admin, link_id).status_code == 204
    assert user.get("/api/links").json() == []

    from app.database import SessionLocal
    from app.models import Link

    with SessionLocal() as db:
        assert db.get(Link, link_id).removed is True  # row kept, flagged


def test_deleted_server_cannot_be_submitted_again(user, other_user, admin):
    check(user, "alpha")
    delete(admin, submit(user).json()["id"])
    for client, invite in ((user, "alpha"), (other_user, "alpha-other")):  # any invite for that server
        r = check(client, invite)
        assert r.json()["already_registered"] is True
        assert r.json()["removed"] is True
        assert submit(client, invite=invite).status_code == 400  # check never unlocks submit


def test_deleted_server_race_returns_removed_message(user, admin):
    check(user, "beta")
    submit(user, invite="beta")
    check(user, "alpha")  # checked while still allowed...
    with_alpha = admin.post("/api/links/check", json={"invite": "alpha"})
    assert with_alpha.status_code == 200
    admin_id = submit(admin).json()["id"]  # ...then an admin registers and deletes it
    delete(admin, admin_id)
    r = submit(user)
    assert r.status_code == 409
    assert "removed by an administrator" in r.json()["detail"]
