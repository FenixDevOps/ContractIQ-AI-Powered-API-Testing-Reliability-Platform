import json

from app.services.target_security import ValidatedTarget


TOKEN = "test-monitoring-token"


def _authorize(monkeypatch, project_id, *, allow=True):
    import app.services.monitoring_access as access

    monkeypatch.setattr(access, "MONITORING_AUTH_TOKEN", TOKEN)
    monkeypatch.setattr(
        access,
        "MONITORING_ALLOWED_PROJECT_IDS",
        {str(project_id)} if allow else set(),
    )
    return {"Authorization": f"Bearer {TOKEN}"}


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


def test_monitoring_routes_require_bearer_and_project_allowlist(isolated_client, monkeypatch):
    project = isolated_client.post("/api/v1/projects", json={"name": "Monitored"}).json()
    url = f"/api/v1/projects/{project['id']}/monitoring/configurations"
    import app.services.monitoring_access as access

    monkeypatch.setattr(access, "MONITORING_AUTH_TOKEN", TOKEN)
    monkeypatch.setattr(access, "MONITORING_ALLOWED_PROJECT_IDS", {project["id"]})
    assert isolated_client.get(url).status_code == 401
    headers = {"Authorization": f"Bearer {TOKEN}"}
    monkeypatch.setattr(access, "MONITORING_ALLOWED_PROJECT_IDS", set())
    assert isolated_client.get(url, headers=headers).status_code == 403
    monkeypatch.setattr(access, "MONITORING_ALLOWED_PROJECT_IDS", {project["id"]})
    response = isolated_client.get(url, headers=headers)
    assert response.status_code == 200
    assert response.json() == []


def test_configuration_accepts_only_safe_public_endpoints_and_can_start_pause(
    isolated_client, monkeypatch
):
    project = isolated_client.post("/api/v1/projects", json={"name": "Monitored"}).json()
    headers = _authorize(monkeypatch, project["id"])
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
    headers = _authorize(monkeypatch, project["id"])
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


def test_live_websocket_requires_token_and_authorized_project(isolated_client, monkeypatch):
    project = isolated_client.post("/api/v1/projects", json={"name": "Live"}).json()
    _authorize(monkeypatch, project["id"])
    url = f"/ws/v1/projects/{project['id']}/monitoring/live"
    with isolated_client.websocket_connect(
        url,
        subprotocols=["contractiq.monitoring.v1", f"bearer.{TOKEN}"],
    ) as websocket:
        assert websocket.accepted_subprotocol == "contractiq.monitoring.v1"
        websocket.send_text("PING")
        assert websocket.receive_json()["event"] == "PONG"
