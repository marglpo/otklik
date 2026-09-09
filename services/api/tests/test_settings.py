import base64

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.core.config import AppEnvironment, Settings


def test_settings_load_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "testing")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://db/otklik")
    monkeypatch.setenv("VALKEY_URL", "redis://cache:6379/0")
    monkeypatch.setenv("JWT_SECRET", "test-jwt-value")
    monkeypatch.setenv("TRACK_HMAC_SECRET", "test-track-value")
    monkeypatch.setenv("RATE_LIMIT_HMAC_SECRET", "test-rate-value")
    monkeypatch.setenv("CONTENT_ENCRYPTION_KEY", "test-encryption-value")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")

    settings = Settings(_env_file=None)

    assert settings.app_env is AppEnvironment.TESTING
    assert settings.database_url == "postgresql+asyncpg://db/otklik"
    assert settings.valkey_url == "redis://cache:6379/0"
    assert settings.jwt_secret is not None
    assert settings.jwt_secret.get_secret_value() == "test-jwt-value"
    assert settings.cors_origins == ["http://localhost:3000", "http://127.0.0.1:3000"]


def test_production_rejects_missing_secrets() -> None:
    with pytest.raises(PydanticValidationError, match="Production requires environment variables"):
        Settings(_env_file=None, app_env="production")


def test_production_rejects_wildcard_cors() -> None:
    encryption_key = base64.urlsafe_b64encode(b"k" * 32).decode("ascii")
    with pytest.raises(PydanticValidationError, match="Wildcard CORS origins"):
        Settings(
            _env_file=None,
            app_env="production",
            jwt_secret="jwt",
            track_hmac_secret="track",
            rate_limit_hmac_secret="rate",
            content_encryption_key=encryption_key,
            cors_origins=["*"],
        )


def test_production_rejects_invalid_encryption_key() -> None:
    with pytest.raises(PydanticValidationError, match="exactly 32 bytes"):
        Settings(
            _env_file=None,
            app_env="production",
            jwt_secret="jwt",
            track_hmac_secret="track",
            rate_limit_hmac_secret="rate",
            content_encryption_key=base64.urlsafe_b64encode(b"too-short").decode("ascii"),
        )
