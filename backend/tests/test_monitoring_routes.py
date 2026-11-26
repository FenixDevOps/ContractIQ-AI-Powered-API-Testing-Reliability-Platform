import json

import pytest
from starlette.websockets import WebSocketDisconnect

from app.services.target_security import ValidatedTarget


def _import_spec(client, project_id, paths, security=None):
    document = {
        "openapi": "3.1.0",
        "info": {"title": "Public API", "version": "1.0"},
        "paths": paths,
    }
    if security is not None:
        document["security"] = security
    response = client.post(
        f"/api/v1/projects/{project_id}/specifications/import",
        files={"file": ("public-api.json", json.dumps(document).encode(), "application/json")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_monitoring_routes_require_authenticated_project_membership(auth_client):
    login = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "test-owner-password-123"},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    project = auth_client.post(
        "/api/v1/projects",
        headers=headers,
        json={"name": "Monitored"},
    ).json()
    url = f"/api/v1/projects/{project['id']}/monitoring/configurations"
    assert auth_client.get(url).status_code == 401
    response = auth_client.get(url, headers=headers)
    assert response.status_code == 200
    assert response.json() == []

    outsider = auth_client.post(
        "/api/v1/auth/register",
        json={"full_name": "Outsider", "email": "outsider@example.com", "password": "outsider-password-123"},
    )
    assert outsider.status_code == 201
    outsider_headers = {"Authorization": f"Bearer {outsider.json()['access_token']}"}
    assert auth_client.get(url, headers=outsider_headers).status_code == 404


def test_configuration_accepts_only_safe_public_endpoints_and_can_start_pause(
    isolated_client, monkeypatch
):
    project = isolated_client.post("/api/v1/projects", json={"name": "Monitored"}).json()
    headers = {}
    specification = _import_spec(isolated_client, project["id"], {
        "/health": {"get": {"responses": {"200": {"description": "OK"}}}},
        "/change": {"post": {"responses": {"200": {"description": "OK"}}}},
    })
    endpoints = isolated_client.get(
        f"/api/v1/specifications/{specification['id']}/endpoints"
    ).json()
    get_endpoint = next(item for item in endpoints if item["method"] == "GET")
    post_endpoint = next(item for item in endpoints if item["method"] == "POST")

    import app.routes.monitoring as monitoring_routes

    monkeypatch.setattr(
        monitoring_routes,
        "resolve_target_url",
        lambda value: ValidatedTarget(
            url="https://api.example.test",
            hostname="api.example.test",
            port=443,
            addresses=("93.184.216.34",),
        ),
    )
    payload = {
        "specification_id": specification["id"],
        "name": "public health",
        "environment_name": "staging",
        "base_url": "https://api.example.test",
        "endpoint_ids": [get_endpoint["id"]],
        "interval_seconds": 60,
        "timeout_seconds": 5,
    }
    created = isolated_client.post(
        f"/api/v1/projects/{project['id']}/monitoring/configurations",
        headers=headers,
        json=payload,
    )
    assert created.status_code == 201, created.text
    configuration = created.json()
    assert configuration["enabled"] is False
    assert configuration["endpoint_ids"] == [get_endpoint["id"]]
    assert "lease_owner" not in configuration

    started = isolated_client.post(
        f"/api/v1/projects/{project['id']}/monitoring/configurations/{configuration['id']}/start",
        headers=headers,
    )
    assert started.status_code == 200
    assert started.json()["enabled"] is True
    paused = isolated_client.post(
        f"/api/v1/projects/{project['id']}/monitoring/configurations/{configuration['id']}/pause",
        headers=headers,
    )
    assert paused.status_code == 200
    assert paused.json()["enabled"] is False

    unsafe = isolated_client.post(
        f"/api/v1/projects/{project['id']}/monitoring/configurations",
        headers=headers,
        json={**payload, "name": "unsafe method", "endpoint_ids": [post_endpoint["id"]]},
    )
    assert unsafe.status_code == 422
    metrics = isolated_client.get(
        f"/api/v1/projects/{project['id']}/monitoring/metrics?window=1h",
        headers=headers,
    )
    assert metrics.status_code == 200
    assert metrics.json()["total_checks"] == 0


def test_monitoring_configuration_rejects_global_authentication(isolated_client, monkeypatch):
    project = isolated_client.post("/api/v1/projects", json={"name": "Private"}).json()
    headers = {}
    specification = _import_spec(
        isolated_client,
        project["id"],
        {"/health": {"get": {"responses": {"200": {"description": "OK"}}}}},
        security=[{"apiKey": []}],
    )
    endpoint = isolated_client.get(
        f"/api/v1/specifications/{specification['id']}/endpoints"
    ).json()[0]
    import app.routes.monitoring as monitoring_routes

    monkeypatch.setattr(
        monitoring_routes,
        "resolve_target_url",
        lambda value: ValidatedTarget(
            url="https://api.example.test",
            hostname="api.example.test",
            port=443,
            addresses=("93.184.216.34",),
        ),
    )
    response = isolated_client.post(
        f"/api/v1/projects/{project['id']}/monitoring/configurations",
        headers=headers,
        json={
            "specification_id": specification["id"],
            "name": "private api",
            "environment_name": "staging",
            "base_url": "https://api.example.test",
            "endpoint_ids": [endpoint["id"]],
        },
    )
    assert response.status_code == 422
    assert "global authentication" in response.json()["detail"]


def test_live_websocket_requires_access_token_and_project_membership(auth_client):
    login = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "test-owner-password-123"},
    )
    token = login.json()["access_token"]
    project = auth_client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Live"},
    ).json()
    url = f"/ws/v1/projects/{project['id']}/monitoring/live"
    with auth_client.websocket_connect(
        url,
        subprotocols=["contractiq.monitoring.v1", f"bearer.{token}"],
    ) as websocket:
        assert websocket.accepted_subprotocol == "contractiq.monitoring.v1"
        websocket.send_text("PING")
        assert websocket.receive_json()["event"] == "PONG"


def test_live_websocket_reports_expired_access_token(auth_client):
    login = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "test-owner-password-123"},
    )
    token = login.json()["access_token"]
    project = auth_client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Expired live session"},
    ).json()
    with auth_client.websocket_connect(
        f"/ws/v1/projects/{project['id']}/monitoring/live",
        subprotocols=["contractiq.monitoring.v1", "bearer.invalid-token"],
    ) as websocket:
        with pytest.raises(WebSocketDisconnect) as disconnected:
            websocket.receive_text()
        assert disconnected.value.code == 4401
