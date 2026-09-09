import json
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class AppEnvironment(StrEnum):
    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


def _default_env_files() -> tuple[Path, ...]:
    working_directory = Path.cwd().resolve()
    if working_directory.name == "api" and working_directory.parent.name == "services":
        repository_env = working_directory.parent.parent / ".env"
        return (repository_env, working_directory / ".env")
    return (working_directory / ".env",)


class Settings(BaseSettings):
    """Environment-backed application settings.

    Secrets are optional while unused in development and testing. Production
    validation requires every declared secret to be supplied by the environment.
    """

    model_config = SettingsConfigDict(
        env_file=_default_env_files(),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Otklik API"
    api_version: str = "v1"
    app_env: AppEnvironment = AppEnvironment.DEVELOPMENT
    log_level: LogLevel = "INFO"

    database_url: str = "postgresql+asyncpg://otklik@localhost:5432/otklik"
    valkey_url: str = "redis://localhost:6379/0"

    jwt_secret: SecretStr | None = None
    track_hmac_secret: SecretStr | None = None
    rate_limit_hmac_secret: SecretStr | None = None
    refresh_token_hmac_secret: SecretStr | None = None
    content_encryption_key: SecretStr | None = None

    jwt_issuer: str = Field(default="otklik-api", min_length=1, max_length=200)
    jwt_audience: str = Field(default="otklik-staff", min_length=1, max_length=200)
    access_token_ttl_minutes: int = Field(default=15, ge=1, le=60)
    refresh_session_ttl_days: int = Field(default=7, ge=1, le=30)
    refresh_cookie_name: str = Field(
        default="otklik_staff_refresh", pattern=r"^[A-Za-z0-9_-]+$"
    )
    login_rate_limit_attempts: int = Field(default=5, ge=1, le=100)
    login_rate_limit_window_seconds: int = Field(default=300, ge=1, le=3600)

    demo_operator_login: str = "demo_operator"
    demo_operator_password: SecretStr | None = None
    demo_expert_login: str = "demo_expert"
    demo_expert_password: SecretStr | None = None
    demo_admin_login: str = "demo_admin"
    demo_admin_password: SecretStr | None = None

    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )
    healthcheck_timeout_seconds: float = Field(default=3.0, gt=0, le=30)

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if not isinstance(value, str):
            return value

        raw_value = value.strip()
        if not raw_value:
            return []
        if raw_value.startswith("["):
            parsed = json.loads(raw_value)
            if not isinstance(parsed, list):
                raise ValueError("CORS_ORIGINS JSON must be an array")
            return parsed
        return [origin.strip() for origin in raw_value.split(",") if origin.strip()]

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        if "*" in self.cors_origins:
            raise ValueError("Wildcard CORS origins are forbidden when credentials are enabled")
        if self.app_env is not AppEnvironment.PRODUCTION:
            return self

        secrets = {
            "JWT_SECRET": self.jwt_secret,
            "TRACK_HMAC_SECRET": self.track_hmac_secret,
            "RATE_LIMIT_HMAC_SECRET": self.rate_limit_hmac_secret,
            "REFRESH_TOKEN_HMAC_SECRET": self.refresh_token_hmac_secret,
            "CONTENT_ENCRYPTION_KEY": self.content_encryption_key,
        }
        missing = [
            name
            for name, value in secrets.items()
            if value is None or not value.get_secret_value().strip()
        ]
        if missing:
            raise ValueError(f"Production requires environment variables: {', '.join(missing)}")
        short_secrets = [
            name
            for name, value in secrets.items()
            if name != "CONTENT_ENCRYPTION_KEY"
            and value is not None
            and len(value.get_secret_value().encode("utf-8")) < 32
        ]
        if short_secrets:
            raise ValueError(
                "Production secrets must be at least 32 bytes: " + ", ".join(short_secrets)
            )
        from app.core.crypto.encryption import decode_content_encryption_key

        encryption_key = self.content_encryption_key
        if encryption_key is not None:
            decode_content_encryption_key(encryption_key.get_secret_value())
        return self

    @property
    def api_prefix(self) -> str:
        return f"/api/{self.api_version}"

    @property
    def refresh_cookie_secure(self) -> bool:
        return self.app_env is AppEnvironment.PRODUCTION


@lru_cache
def get_settings() -> Settings:
    return Settings()
