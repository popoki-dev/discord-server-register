from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/discord_register"
    secret_key: str = "change-me"
    admin_email: str | None = None
    admin_name: str = "Administrator"
    admin_password: str | None = None


settings = Settings()
