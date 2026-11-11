from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import login


def replay(cookie: str) -> TestClient:
    c = TestClient(app, base_url="https://testserver")
    c.cookies.set("dsr_session", cookie)
    return c


def test_cookie_stops_working_after_logout(user):
    stolen = user.cookies.get("dsr_session")
    assert replay(stolen).get("/api/auth/me").status_code == 200
    assert user.post("/api/auth/logout").status_code == 200
    assert replay(stolen).get("/api/auth/me").status_code == 401
    assert replay(stolen).get("/", follow_redirects=False).headers["location"] == "/login"


def test_logout_signs_out_every_device(user):
    other_device = login("user@example.com")
    assert other_device.get("/api/auth/me").status_code == 200
    user.post("/api/auth/logout")
    assert other_device.get("/api/auth/me").status_code == 401


def test_logging_in_again_after_logout_works(user):
    user.post("/api/auth/logout")
    fresh = login("user@example.com")
    assert fresh.get("/api/auth/me").status_code == 200


def test_logout_without_a_session_is_harmless(client):
    assert client.post("/api/auth/logout").status_code == 200
