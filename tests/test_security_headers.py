def test_security_headers_on_pages_and_api(client, user):
    for r in (client.get("/login"), user.get("/"), user.get("/api/links"), client.get("/static/common.js")):
        h = r.headers
        csp = h["content-security-policy"]
        assert "default-src 'self'" in csp and "script-src 'self'" in csp and "frame-ancestors 'none'" in csp
        assert "unsafe-inline" not in csp
        assert h["x-frame-options"] == "DENY"
        assert h["x-content-type-options"] == "nosniff"
        assert h["referrer-policy"] == "strict-origin-when-cross-origin"
        assert h["strict-transport-security"].startswith("max-age=")  # the test client uses https


def test_no_hsts_over_plain_http():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app, base_url="http://testserver") as c:
        r = c.get("/login")
    assert "strict-transport-security" not in r.headers
    assert r.headers["x-frame-options"] == "DENY"


def test_session_cookie_is_secure_httponly_lax(client):
    from tests.conftest import ADMIN

    cookie = client.post("/api/auth/login", json=ADMIN).headers["set-cookie"].lower()
    assert "secure" in cookie and "httponly" in cookie and "samesite=lax" in cookie


def test_api_docs_are_disabled(client):
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404
