from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import get_db
from app.main import app


client = TestClient(app, raise_server_exceptions=False)


class HealthySession:
    def execute(self, _statement: Any) -> None:
        return None


class UnavailableSession:
    def execute(self, _statement: Any) -> None:
        raise SQLAlchemyError("PostgreSQL no disponible durante la prueba")


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> Generator[None, None, None]:
    yield
    app.dependency_overrides.clear()


def test_health_check() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_check_when_database_is_available() -> None:
    app.dependency_overrides[get_db] = lambda: HealthySession()

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "environment": "development",
        "services": {"api": "ok", "database": "ok"},
    }


def test_readiness_check_when_database_is_unavailable() -> None:
    app.dependency_overrides[get_db] = lambda: UnavailableSession()

    response = client.get("/api/v1/health")

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "database_unavailable",
            "message": "La API está disponible, pero no puede conectarse a PostgreSQL.",
            "details": {"api": "ok", "database": "unavailable"},
        }
    }


def test_not_found_uses_the_common_error_contract() -> None:
    response = client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "http_error",
            "message": "Not Found",
            "details": "Not Found",
        }
    }
