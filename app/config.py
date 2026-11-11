from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Values that must never be used: a session secret anyone can guess lets them sign a cookie for any account.
WEAK_SECRETS = {"change-me", "changeme", "secret", "secret-key", "test-secret-key"}
MIN_SECRET_LENGTH = 32
MIN_ADMIN_PASSWORD_LENGTH = 12


class Settings(BaseSettings):
    """Settings from the environment / .env. There are no built-in credentials: the app refuses to
    start rather than run with a guessable session secret or database password."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    secret_key: str
    admin_email: str | None = None
    admin_name: str = "Administrator"
    admin_password: str | None = None

    @field_validator("secret_key")
    @classmethod
    def strong_secret(cls, v: str) -> str:
        if v.strip().lower() in WEAK_SECRETS or len(v) < MIN_SECRET_LENGTH:
            raise ValueError(
                f"SECRET_KEY must be a random value of at least {MIN_SECRET_LENGTH} characters. Generate one with: "
                'python3 -c "import secrets; print(secrets.token_urlsafe(48))"'
            )
        return v

    @model_validator(mode="after")
    def strong_admin_password(self) -> "Settings":
        if self.admin_email and self.admin_password and len(self.admin_password) < MIN_ADMIN_PASSWORD_LENGTH:
            raise ValueError(f"ADMIN_PASSWORD must be at least {MIN_ADMIN_PASSWORD_LENGTH} characters")
        return self


settings = Settings()
