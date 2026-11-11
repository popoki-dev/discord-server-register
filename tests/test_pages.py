import pytest


@pytest.mark.parametrize("path", ["/", "/admin"])
def test_pages_redirect_anonymous_users_to_login(client, path):
    r = client.get(path, follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/login"


def test_login_page_renders(client):
    r = client.get("/login")
    assert r.status_code == 200
    assert 'id="register-form"' in r.text


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


def test_link_management_page_is_admin_only(client, user, admin):
    assert client.get("/admin/links", follow_redirects=False).headers["location"] == "/login"
    assert user.get("/admin/links", follow_redirects=False).headers["location"] == "/"
    r = admin.get("/admin/links")
    assert r.status_code == 200
    assert 'id="filters"' in r.text
    assert 'href="/admin/links"' not in user.get("/").text


def test_register_form_asks_for_full_name(client):
    assert 'name="full_name"' in client.get("/login").text
