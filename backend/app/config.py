"""Application settings, read from environment variables / .env (never hard-coded)."""
from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "development"          # development | production
    secret_key: str                            # REQUIRED, >= 32 chars. Generate: python -c "import secrets;print(secrets.token_urlsafe(48))"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30
    refresh_token_days: int = 7

    database_path: Path = BASE_DIR / "data" / "app.db"
    model_path: Path = BASE_DIR / "artifacts" / "model.pkl"
    metadata_path: Path = BASE_DIR / "artifacts" / "model_metadata.json"

    # Optional first admin, created at start-up ONLY when the users table is empty.
    admin_username: str | None = None
    admin_password: str | None = None

    allow_registration: bool = False           # private API: users are created by an admin
    enable_docs: bool = True                   # set false in production to hide /docs
    enforce_https: bool = False                # true behind a TLS proxy: redirect + HSTS
    allowed_hosts: List[str] = ["*"]           # production: ["api.example.com"]
    cors_origins: List[str] = []               # native mobile apps do not need CORS; only for web clients

    login_max_attempts: int = 5
    login_lockout_minutes: int = 15
    log_level: str = "INFO"

    @field_validator("secret_key")
    @classmethod
    def _strong_secret(cls, v: str) -> str:
        if len(v) < 32 or v.lower().startswith(("change", "your", "secret")):
            raise ValueError("SECRET_KEY must be a random string of at least 32 characters")
        return v

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
