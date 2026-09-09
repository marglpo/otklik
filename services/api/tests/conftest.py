import pytest

from app.core.config import AppEnvironment, Settings


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        _env_file=None,
        app_env=AppEnvironment.TESTING,
        database_url="postgresql+asyncpg://otklik@localhost:5432/otklik_test",
        valkey_url="redis://localhost:6379/15",
        jwt_secret="j" * 64,
        rate_limit_hmac_secret="r" * 64,
        refresh_token_hmac_secret="f" * 64,
        cors_origins=["http://localhost:3000"],
    )
