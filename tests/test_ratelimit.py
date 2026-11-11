from app import ratelimit
from tests.conftest import ADMIN, PASSWORD, make_user


def bad_login(client, email="user@example.com"):
    return client.post("/api/auth/login", json={"email": email, "password": "wrong-password"})


def test_account_is_locked_after_ten_failed_sign_ins(client):
    make_user("user@example.com")
    for _ in range(10):
        assert bad_login(client).status_code == 401
    r = client.post("/api/auth/login", json={"email": "user@example.com", "password": PASSWORD})
    assert r.status_code == 429  # even the right password is refused while locked
    assert int(r.headers["retry-after"]) > 0
    assert "Too many failed sign-in attempts" in r.json()["detail"]
    assert client.post("/api/auth/login", json=ADMIN).status_code == 200  # other accounts unaffected


def test_unknown_accounts_are_limited_the_same_way(client):
    for _ in range(10):
        assert bad_login(client, "nobody@example.com").status_code == 401
    assert bad_login(client, "nobody@example.com").status_code == 429


def test_one_address_trying_many_accounts_is_limited(client):
    for i in range(30):
        assert bad_login(client, f"guess{i}@example.com").status_code == 401
    assert client.post("/api/auth/login", json=ADMIN).status_code == 429


def test_successful_sign_ins_are_not_counted(client):
    for _ in range(15):
        assert client.post("/api/auth/login", json=ADMIN).status_code == 200


def test_registrations_are_limited_per_address(client):
    for i in range(5):
        r = client.post("/api/auth/register", json={"email": f"new{i}@example.com", "password": PASSWORD, "full_name": "N"})
        assert r.status_code == 201
    r = client.post("/api/auth/register", json={"email": "new9@example.com", "password": PASSWORD, "full_name": "N"})
    assert r.status_code == 429


def test_checks_are_limited_per_user(user, other_user):
    for _ in range(20):
        assert user.post("/api/links/check", json={"invite": "alpha"}).status_code == 200
    assert user.post("/api/links/check", json={"invite": "alpha"}).status_code == 429
    assert other_user.post("/api/links/check", json={"invite": "alpha"}).status_code == 200


def test_limiter_window_expires(monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(ratelimit.time, "monotonic", lambda: clock[0])
    limiter = ratelimit.RateLimiter(limit=2, window_seconds=60)
    assert limiter.hit("k") == 0 and limiter.hit("k") == 0
    assert limiter.hit("k") == 60
    clock[0] += 30
    assert limiter.hit("k") == 30
    clock[0] += 31
    assert limiter.hit("k") == 0
