import faulthandler
import sys

import pytest

from app.core.config import AppEnvironment, Settings


@pytest.hookimpl(trylast=True)
def pytest_configure() -> None:
    """Suppress misleading handled-exception reports from Windows native extensions."""

    if sys.platform == "win32":
        faulthandler.disable()


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        _env_file=None,
        app_env=AppEnvironment.TESTING,
        database_url="postgresql+asyncpg://otklik@localhost:5432/otklik_test",
        valkey_url="redis://localhost:6379/15",
        cors_origins=["http://localhost:3000"],
    )
