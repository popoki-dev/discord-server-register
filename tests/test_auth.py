from app.models import UserStatus
from tests.conftest import ADMIN, PASSWORD, make_user


def register(client, email="new@example.com", password=PASSWORD, full_name="New Person"):
    body = {"email": email, "password": password}
    if full_name is not None:
        body["full_name"] = full_name
    return client.post("/api/auth/register", json=body)


def test_register_creates_pending_application(client, admin):
    assert register(client, "New@Example.com").status_code == 201
    users = admin.get("/api/admin/users", params={"status": "pending"}).json()
    assert [u["email"] for u in users] == ["new@example.com"]  # email is normalised
    assert users[0]["full_name"] == "New Person"


def test_register_duplicate_email_is_rejected_case_insensitively(client):
    register(client, "dup@example.com")
    r = register(client, "DUP@example.com")
    assert r.status_code == 409


def test_register_validates_input(client):
    assert register(client, email="not-an-email").status_code == 422
    assert register(client, password="short").status_code == 422
    assert register(client, password="x" * 73).status_code == 422


def test_register_requires_full_name(client, admin):
    assert register(client, full_name=None).status_code == 422
    assert register(client, full_name="   ").status_code == 422
    assert register(client, full_name="x" * 101).status_code == 422
    assert register(client, full_name="  Ada   Lovelace ").status_code == 201
    pending = admin.get("/api/admin/users", params={"status": "pending"}).json()
    assert pending[0]["full_name"] == "Ada Lovelace"  # whitespace normalised


def test_pending_user_cannot_log_in(client):
    make_user("pending@example.com", UserStatus.pending)
    r = client.post("/api/auth/login", json={"email": "pending@example.com", "password": PASSWORD})
    assert r.status_code == 403
    assert "awaiting approval" in r.json()["detail"]


def test_rejected_user_cannot_log_in(client):
    make_user("rejected@example.com", UserStatus.rejected)
    r = client.post("/api/auth/login", json={"email": "rejected@example.com", "password": PASSWORD})
    assert r.status_code == 403
    assert "rejected" in r.json()["detail"]


def test_status_is_not_revealed_without_correct_password(client):
    make_user("pending@example.com", UserStatus.pending)
    wrong = client.post("/api/auth/login", json={"email": "pending@example.com", "password": "wrong-password"})
    unknown = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "wrong-password"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_approved_user_can_log_in_and_out(client):
    make_user("ok@example.com")
    assert client.post("/api/auth/login", json={"email": "ok@example.com", "password": PASSWORD}).status_code == 200
    assert client.get("/api/auth/me").json()["email"] == "ok@example.com"
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").status_code == 401


def test_bootstrap_admin_exists(client):
    r = client.post("/api/auth/login", json=ADMIN)
    assert r.status_code == 200
    assert r.json()["is_admin"] is True
