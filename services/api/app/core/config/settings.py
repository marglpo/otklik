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
    content_encryption_key: SecretStr | None = None

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
        if self.app_env is not AppEnvironment.PRODUCTION:
            return self

        secrets = {
            "JWT_SECRET": self.jwt_secret,
            "TRACK_HMAC_SECRET": self.track_hmac_secret,
            "RATE_LIMIT_HMAC_SECRET": self.rate_limit_hmac_secret,
            "CONTENT_ENCRYPTION_KEY": self.content_encryption_key,
        }
        missing = [
            name
            for name, value in secrets.items()
            if value is None or not value.get_secret_value().strip()
        ]
        if missing:
            raise ValueError(f"Production requires environment variables: {', '.join(missing)}")
        from app.core.crypto.encryption import decode_content_encryption_key

        encryption_key = self.content_encryption_key
        if encryption_key is not None:
            decode_content_encryption_key(encryption_key.get_secret_value())
        if "*" in self.cors_origins:
            raise ValueError("Wildcard CORS origins are forbidden in production")
        return self

    @property
    def api_prefix(self) -> str:
        return f"/api/{self.api_version}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
