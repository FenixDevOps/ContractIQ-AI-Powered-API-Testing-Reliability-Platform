from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root_returns_project_information() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["project"] == "ContractIQ"
    assert response.json()["docs"] == "/docs"


def test_health_returns_healthy_status() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_status_returns_application_version() -> None:
    response = client.get("/api/v1/status")

    assert response.status_code == 200
    assert response.json() == {
        "application": "ContractIQ API",
        "status": "operational",
        "version": "0.1.0",
    }


def test_cors_allows_local_vite_frontend() -> None:
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"