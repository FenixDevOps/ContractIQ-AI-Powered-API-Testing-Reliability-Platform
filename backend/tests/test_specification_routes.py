def test_project_and_specification_import_flow(isolated_client):
    client = isolated_client
    project_response = client.post("/api/v1/projects", json={"name": "Payments", "description": "Payment API"})
    assert project_response.status_code == 201
    project_id = project_response.json()["id"]

    spec = b'''{
      "openapi": "3.0.3",
      "info": {"title": "Payments API", "version": "1.0.0"},
      "paths": {
        "/payments": {
          "get": {
            "summary": "List payments",
            "responses": {"200": {"description": "OK"}}
          }
        }
      }
    }'''
    import_response = client.post(
        f"/api/v1/projects/{project_id}/specifications/import",
        files={"file": ("payments.json", spec, "application/json")},
    )
    assert import_response.status_code == 201
    imported = import_response.json()
    assert imported["endpoint_count"] == 1
    assert imported["version_number"] == 1

    duplicate = client.post(
        f"/api/v1/projects/{project_id}/specifications/import",
        files={"file": ("payments-copy.json", spec, "application/json")},
    )
    assert duplicate.status_code == 409

    endpoints = client.get(f"/api/v1/specifications/{imported['id']}/endpoints")
    assert endpoints.status_code == 200
    assert endpoints.json()[0]["path"] == "/payments"


def test_yaml_import_keeps_date_examples_json_compatible(isolated_client):
    project = isolated_client.post("/api/v1/projects", json={"name": "YAML API"}).json()
    yaml_spec = b"""openapi: 3.0.3
info:
  title: YAML API
  version: '1.0'
paths:
  /reports:
    get:
      responses:
        '200':
          description: OK
          content:
            application/json:
              example:
                date: 2026-11-21
"""
    response = isolated_client.post(
        f"/api/v1/projects/{project['id']}/specifications/import",
        files={"file": ("reports.yaml", yaml_spec, "application/yaml")},
    )
    assert response.status_code == 201
    spec_id = response.json()["id"]
    raw = isolated_client.get(f"/api/v1/specifications/{spec_id}/raw").json()
    assert raw["paths"]["/reports"]["get"]["responses"]["200"]["content"]["application/json"]["example"]["date"] == "2026-11-21"


def test_specification_versions_and_comparison(isolated_client):
    project = isolated_client.post("/api/v1/projects", json={"name": "Versioned API"}).json()
    initial_spec = {
        "openapi": "3.1.0",
        "info": {"title": "Versioned API", "version": "1"},
        "paths": {"/users": {"get": {"responses": {"200": {"description": "OK"}}}}},
    }
    newer_spec = {
        "openapi": "3.1.0",
        "info": {"title": "Versioned API", "version": "2"},
        "paths": {
            "/users": {"get": {"responses": {"200": {"description": "OK"}}}},
            "/groups": {"get": {"responses": {"200": {"description": "OK"}}}},
        },
    }
    first = isolated_client.post(
        f"/api/v1/projects/{project['id']}/specifications/import",
        files={"file": ("api.json", __import__("json").dumps(initial_spec).encode(), "application/json")},
    ).json()
    second_response = isolated_client.post(
        f"/api/v1/projects/{project['id']}/specifications/import",
        files={"file": ("api-v2.json", __import__("json").dumps(newer_spec).encode(), "application/json")},
    )
    assert second_response.status_code == 201
    second = second_response.json()
    assert second["version_number"] == 2
    versions = isolated_client.get(f"/api/v1/specifications/{first['id']}/versions")
    assert [item["version_number"] for item in versions.json()] == [2, 1]
    comparison = isolated_client.get(
        f"/api/v1/specifications/{first['id']}/compare/{second['id']}"
    ).json()
    assert comparison["change_count"] == 1
    assert comparison["changes"][0]["key"] == "GET /groups"
