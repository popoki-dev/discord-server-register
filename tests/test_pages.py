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


def test_old_link_management_url_redirects_to_links_page(client, admin):
    assert client.get("/admin/links", follow_redirects=False).headers["location"] == "/login"
    assert admin.get("/admin/links", follow_redirects=False).headers["location"] == "/"
    assert 'href="/admin/links"' not in admin.get("/").text  # no separate nav entry any more


def test_register_form_asks_for_full_name(client):
    assert 'name="full_name"' in client.get("/login").text


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
