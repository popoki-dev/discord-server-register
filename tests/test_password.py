from tests.conftest import PASSWORD, _client, login

NEW = "a-brand-new-password"


def change(c, current=PASSWORD, new=NEW):
    return c.post("/api/auth/password", json={"current_password": current, "new_password": new})


def sign_in(c, password):
    return c.post("/api/auth/login", json={"email": "user@example.com", "password": password})


def test_change_password(user):
    r = change(user)
    assert r.status_code == 200
    assert user.get("/api/auth/me").status_code == 200  # this session stays signed in
    with _client() as c:
        assert sign_in(c, PASSWORD).status_code == 401
        assert sign_in(c, NEW).status_code == 200


def test_change_password_signs_out_other_sessions(user):
    other_device = login("user@example.com")
    change(user)
    assert other_device.get("/api/auth/me").status_code == 401
    other_device.__exit__(None, None, None)


def test_wrong_current_password_is_refused(user):
    r = change(user, current="not-my-password")
    assert r.status_code == 400 and "incorrect" in r.json()["detail"]
    with _client() as c:
        assert sign_in(c, PASSWORD).status_code == 200  # unchanged


def test_new_password_must_differ_and_be_valid(user):
    assert change(user, new=PASSWORD).status_code == 400
    assert change(user, new="short").status_code == 422
    assert change(user, new="x" * 73).status_code == 422


def test_guessing_the_current_password_is_rate_limited(user):
    for _ in range(10):
        assert change(user, current="guess-guess").status_code == 400
    r = change(user)  # even the right password is refused now
    assert r.status_code == 429 and "Retry-After" in r.headers


def test_needs_sign_in_and_finished_setup(client, admin):
    assert change(client).status_code == 401
    admin.post("/api/admin/users", json={"email": "fresh@example.com", "password": PASSWORD})
    client.post("/api/auth/login", json={"email": "fresh@example.com", "password": PASSWORD})
    assert change(client).status_code == 403  # first-time setup comes first


def test_account_page(client, user):
    assert client.get("/account", follow_redirects=False).headers["location"] == "/login"
    page = user.get("/account").text
    assert 'id="password-form"' in page and 'href="/account"' in user.get("/").text
