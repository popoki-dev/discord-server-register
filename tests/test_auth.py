from app.models import UserStatus
from tests.conftest import ADMIN, PASSWORD, make_user

NEW_PASSWORD = "my-own-password"


def add_user(admin, email="new@example.com", password=PASSWORD):
    return admin.post("/api/admin/users", json={"email": email, "password": password})


def sign_in(client, email="new@example.com", password=PASSWORD):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def setup(client, full_name="New Person", password=NEW_PASSWORD):
    return client.post("/api/auth/setup", json={"full_name": full_name, "password": password})


def test_public_registration_is_gone(client):
    r = client.post("/api/auth/register", json={"email": "x@example.com", "password": PASSWORD, "full_name": "X"})
    assert r.status_code in (404, 405)


def test_admin_adds_an_approved_user_without_a_name(admin):
    r = add_user(admin, "New@Example.com")
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "new@example.com"  # email is normalised
    assert (body["status"], body["full_name"], body["needs_setup"]) == ("approved", "", True)


def test_only_admins_can_add_users(client, user):
    assert add_user(client).status_code == 401
    assert add_user(user).status_code == 403


def test_add_user_rejects_duplicates_and_bad_input(admin):
    assert add_user(admin, "dup@example.com").status_code == 201
    r = add_user(admin, "DUP@example.com")
    assert r.status_code == 409 and "already exists" in r.json()["detail"]
    assert add_user(admin, "not-an-email").status_code == 422
    assert add_user(admin, password="short").status_code == 422
    assert add_user(admin, password="x" * 73).status_code == 422


def test_new_user_signs_in_with_the_admin_password_and_must_set_up_first(admin, client):
    add_user(admin)
    r = sign_in(client)
    assert r.status_code == 200 and r.json()["needs_setup"] is True
    assert client.get("/api/auth/me").json()["needs_setup"] is True
    # Nothing else works until setup is done.
    r = client.get("/api/links")
    assert r.status_code == 403 and "new password" in r.json()["detail"]
    assert client.post("/api/links/check", json={"invite": "alpha"}).status_code == 403


def test_setup_sets_name_and_replaces_password(admin, client):
    add_user(admin)
    sign_in(client)
    r = setup(client, full_name="  Ada   Lovelace ")
    assert r.status_code == 200
    assert (r.json()["full_name"], r.json()["needs_setup"]) == ("Ada Lovelace", False)
    assert client.get("/api/links").status_code == 200  # still signed in, now fully
    client.post("/api/auth/logout")
    assert sign_in(client).status_code == 401  # the admin's password no longer works
    assert sign_in(client, password=NEW_PASSWORD).status_code == 200


def test_setup_signs_out_other_sessions_using_the_first_password(admin, client):
    from tests.conftest import _client

    add_user(admin)
    with _client() as other:
        sign_in(other)
        sign_in(client)
        setup(client)
        assert other.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me").status_code == 200


def test_setup_validates_input(admin, client):
    add_user(admin)
    sign_in(client)
    assert setup(client, full_name="   ").status_code == 422
    assert setup(client, full_name="x" * 101).status_code == 422
    assert setup(client, password="short").status_code == 422
    r = setup(client, password=PASSWORD)
    assert r.status_code == 400 and "new password" in r.json()["detail"]
    assert client.get("/api/auth/me").json()["needs_setup"] is True


def test_setup_works_only_once(admin, client, user):
    # It can't be used as a password change that skips the current password.
    assert setup(user).status_code == 409
    assert setup(client).status_code == 401


def test_pending_user_cannot_log_in(client):
    make_user("pending@example.com", UserStatus.pending)
    r = sign_in(client, "pending@example.com")
    assert r.status_code == 403
    assert "awaiting approval" in r.json()["detail"]


def test_rejected_user_cannot_log_in(client):
    make_user("rejected@example.com", UserStatus.rejected)
    r = sign_in(client, "rejected@example.com")
    assert r.status_code == 403
    assert "rejected" in r.json()["detail"]


def test_status_is_not_revealed_without_correct_password(client):
    make_user("pending@example.com", UserStatus.pending)
    wrong = sign_in(client, "pending@example.com", "wrong-password")
    unknown = sign_in(client, "nobody@example.com", "wrong-password")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_approved_user_can_log_in_and_out(client):
    make_user("ok@example.com")
    assert sign_in(client, "ok@example.com").status_code == 200
    assert client.get("/api/auth/me").json()["email"] == "ok@example.com"
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").status_code == 401


def test_bootstrap_admin_exists(client):
    r = client.post("/api/auth/login", json=ADMIN)
    assert r.status_code == 200
    assert r.json()["is_admin"] is True and r.json()["needs_setup"] is False
