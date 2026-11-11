import pytest


@pytest.mark.parametrize("path", ["/", "/admin"])
def test_pages_redirect_anonymous_users_to_login(client, path):
    r = client.get(path, follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/login"


def test_login_page_renders(client):
    r = client.get("/login")
    assert r.status_code == 200
    assert 'id="login-form"' in r.text
    assert 'id="register-form"' not in r.text  # accounts are created by administrators


def test_logged_in_user_is_redirected_away_from_login(user):
    assert user.get("/login", follow_redirects=False).headers["location"] == "/"


def test_regular_user_sees_links_but_not_admin(user):
    r = user.get("/")
    assert r.status_code == 200
    assert 'id="submit-modal"' in r.text
    assert 'href="/admin"' not in r.text
    assert user.get("/admin", follow_redirects=False).headers["location"] == "/"


def test_admin_sees_user_management(admin):
    r = admin.get("/admin")
    assert r.status_code == 200
    assert 'id="users-body"' in r.text
    assert 'href="/admin"' in admin.get("/").text


def test_static_assets_are_served(client):
    for asset in ("/static/style.css", "/static/common.js", "/static/links.js"):
        assert client.get(asset).status_code == 200


def test_old_link_management_url_redirects_to_links_page(client, admin):
    assert client.get("/admin/links", follow_redirects=False).headers["location"] == "/login"
    assert admin.get("/admin/links", follow_redirects=False).headers["location"] == "/"
    assert 'href="/admin/links"' not in admin.get("/").text  # no separate nav entry any more


def test_admin_page_has_add_user_modal(admin):
    page = admin.get("/admin").text
    assert 'id="add-user-btn"' in page and 'id="add-user-form"' in page


def test_new_user_is_sent_to_setup_until_it_is_done(client):
    from tests.conftest import PASSWORD, make_user

    make_user("fresh@example.com", full_name="")
    assert client.post("/api/auth/login", json={"email": "fresh@example.com", "password": PASSWORD}).status_code == 200
    for path in ("/", "/admin", "/login"):
        r = client.get(path, follow_redirects=True)
        assert r.url.path == "/setup" and 'id="setup-form"' in r.text, path
    assert "<nav>" not in client.get("/setup").text  # no links to pages that would bounce back here
    client.post("/api/auth/setup", json={"full_name": "Fresh Person", "password": "my-own-password"})
    assert client.get("/setup", follow_redirects=False).headers["location"] == "/"
    assert client.get("/").status_code == 200


def test_setup_page_needs_sign_in(client):
    assert client.get("/setup", follow_redirects=False).headers["location"] == "/login"


def test_one_links_page_with_admin_only_extras(user, admin):
    page = user.get("/").text
    assert 'id="filters"' in page and 'name="deletion"' in page
    assert 'name="submitter_id"' not in page and ">Actions</th>" not in page and ">Submitter</th>" not in page
    assert 'name="joined"' not in page and ">Status</th>" not in page
    assert 'data-admin="false"' in page
    page = admin.get("/").text
    assert 'name="submitter_id"' in page and ">Actions</th>" in page and ">Submitter</th>" in page
    assert 'name="joined"' in page and ">Status</th>" in page
    assert 'data-admin="true"' in page


def test_static_urls_carry_a_content_hash(user):
    import re

    page = user.get("/").text
    urls = re.findall(r'(?:src|href)="(/static/[^"]+)"', page)
    assert {u.split("?")[0] for u in urls} >= {"/static/common.js", "/static/links.js", "/static/link_actions.js", "/static/style.css"}
    assert all(re.search(r"\?v=[0-9a-f]{12}$", u) for u in urls), urls
    for u in urls:
        assert user.get(u).status_code == 200


def test_static_url_changes_when_the_file_changes(tmp_path, monkeypatch):
    import os

    from app.routers import pages

    monkeypatch.setattr(pages, "STATIC_DIR", tmp_path)
    (tmp_path / "x.js").write_text("one")
    first = pages.static_url("x.js")
    (tmp_path / "x.js").write_text("two")
    os.utime(tmp_path / "x.js", ns=(1, 1))  # force a different mtime
    assert pages.static_url("x.js") != first
    assert pages.static_url("missing.js") == "/static/missing.js"
