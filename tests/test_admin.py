from app.models import UserStatus
from tests.conftest import PASSWORD, make_user


def user_id(admin, email):
    return next(u["id"] for u in admin.get("/api/admin/users").json() if u["email"] == email)


def test_admin_endpoints_require_admin(client, user):
    assert client.get("/api/admin/users").status_code == 401
    assert user.get("/api/admin/users").status_code == 403
    assert user.post("/api/admin/users/1/approve").status_code == 403


def test_list_filters_by_status(admin):
    make_user("p@example.com", UserStatus.pending)
    make_user("r@example.com", UserStatus.rejected)
    pending = admin.get("/api/admin/users", params={"status": "pending"}).json()
    assert [u["email"] for u in pending] == ["p@example.com"]
    assert len(admin.get("/api/admin/users").json()) == 3  # includes the admin
    assert admin.get("/api/admin/users", params={"status": "bogus"}).status_code == 422


def test_approve_lets_user_log_in(admin, client):
    make_user("p@example.com", UserStatus.pending)
    r = admin.post(f"/api/admin/users/{user_id(admin, 'p@example.com')}/approve")
    assert r.status_code == 200
    assert r.json()["status"] == "approved"
    assert r.json()["reviewed_at"] is not None
    assert client.post("/api/auth/login", json={"email": "p@example.com", "password": PASSWORD}).status_code == 200


def test_reject_revokes_an_active_session_immediately(admin, user):
    assert user.get("/api/links").status_code == 200
    admin.post(f"/api/admin/users/{user_id(admin, 'user@example.com')}/reject")
    assert user.get("/api/links").status_code == 403
    assert user.get("/api/auth/me").status_code == 401  # session was cleared


def test_admin_cannot_change_self_or_other_admins(admin):
    me = admin.get("/api/auth/me").json()["id"]
    assert admin.post(f"/api/admin/users/{me}/reject").status_code == 400


def test_unknown_user_is_404(admin):
    assert admin.post("/api/admin/users/999999/approve").status_code == 404
