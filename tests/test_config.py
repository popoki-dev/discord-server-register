import pytest
from pydantic import ValidationError

from app.config import Settings

DB = "postgresql+psycopg2://u:p@localhost/db"
GOOD = "x" * 40


def make(**env):
    return Settings(_env_file=None, **env)


def test_valid_settings():
    s = make(database_url=DB, secret_key=GOOD)
    assert s.secret_key == GOOD


@pytest.mark.parametrize("secret", ["change-me", "CHANGE-ME", "short", "a" * 31])
def test_weak_secret_key_is_refused(secret):
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        make(database_url=DB, secret_key=secret)


def test_missing_secret_or_database_url_is_refused(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError) as e:
        make()
    fields = {err["loc"][0] for err in e.value.errors()}
    assert {"secret_key", "database_url"} <= fields


def test_short_admin_password_is_refused():
    with pytest.raises(ValidationError, match="ADMIN_PASSWORD"):
        make(database_url=DB, secret_key=GOOD, admin_email="a@example.com", admin_password="short-pw")
    make(database_url=DB, secret_key=GOOD, admin_email="a@example.com", admin_password="long-enough-pw")
