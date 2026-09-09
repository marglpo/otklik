from fastapi import FastAPI

from app.core.config import Settings
from app.main import create_app


def test_application_creation(test_settings: Settings) -> None:
    app = create_app(test_settings)
    paths = set(app.openapi()["paths"])

    assert isinstance(app, FastAPI)
    assert app.title == "Otklik API"
    assert "/health" in paths
    assert "/api/v1/health/ready" in paths
    assert "/api/v1/meta" in paths
