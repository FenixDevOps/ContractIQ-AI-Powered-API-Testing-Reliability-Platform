import json


def _import_spec(client, project_id, version, paths):
    document = {
        "openapi": "3.1.0",
        "info": {"title": "Orders API", "version": version},
        "paths": paths,
    }
    response = client.post(
        f"/api/v1/projects/{project_id}/specifications/import",
        files={"file": (f"orders-{version}.json", json.dumps(document).encode(), "application/json")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_comparison_history_detail_filters_json_export_and_delete(isolated_client):
    project = isolated_client.post("/api/v1/projects", json={"name": "Orders"}).json()
    before = _import_spec(isolated_client, project["id"], "1.0", {
        "/orders": {"get": {"responses": {"200": {"description": "OK"}}}}
    })
    after = _import_spec(isolated_client, project["id"], "2.0", {
        "/orders": {"get": {"responses": {"200": {"description": "OK"}}}},
        "/payments": {"get": {"responses": {"200": {"description": "OK"}}}},
    })

    created = isolated_client.post("/api/v1/compatibility/compare", json={
        "old_specification_id": before["id"],
        "new_specification_id": after["id"],
    })

    assert created.status_code == 201, created.text
    comparison = created.json()
    assert comparison["total_changes"] == 1
    assert comparison["non_breaking_changes"] == 1
    comparison_id = comparison["id"]

    history = isolated_client.get(f"/api/v1/projects/{project['id']}/compatibility?page=1&page_size=5")
    assert history.status_code == 200
    assert history.json()["total"] == 1
    assert history.json()["summary"]["comparisons"] == 1

    details = isolated_client.get(f"/api/v1/compatibility/{comparison_id}")
    assert details.status_code == 200
    assert details.json()["changes"][0]["change_type"] == "ADDED_ENDPOINT"

    filtered = isolated_client.get(
        f"/api/v1/compatibility/{comparison_id}/changes?category=ENDPOINT&compatibility=NON_BREAKING"
    )
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1
    invalid_filter = isolated_client.get(
        f"/api/v1/compatibility/{comparison_id}/changes?severity=urgent"
    )
    assert invalid_filter.status_code == 422

    summary = isolated_client.get(f"/api/v1/compatibility/{comparison_id}/summary")
    assert summary.json()["endpoint_summary"]["added"] == 1

    report = isolated_client.get(f"/api/v1/compatibility/{comparison_id}/report/json")
    assert report.status_code == 200
    assert report.headers["content-disposition"].startswith("attachment;")
    assert report.json()["project_name"] == "Orders"
    assert report.json()["changes"][0]["change_type"] == "ADDED_ENDPOINT"

    deleted = isolated_client.delete(f"/api/v1/compatibility/{comparison_id}")
    assert deleted.status_code == 204
    assert isolated_client.get(f"/api/v1/compatibility/{comparison_id}").status_code == 404


def test_comparison_rejects_mixed_projects_same_spec_and_self_comparison(isolated_client):
    first_project = isolated_client.post("/api/v1/projects", json={"name": "First"}).json()
    second_project = isolated_client.post("/api/v1/projects", json={"name": "Second"}).json()
    document = {"/items": {"get": {"responses": {"200": {"description": "OK"}}}}}
    first = _import_spec(isolated_client, first_project["id"], "1.0", document)
    other_project = _import_spec(isolated_client, second_project["id"], "1.0", document)

    self_comparison = isolated_client.post("/api/v1/compatibility/compare", json={
        "old_specification_id": first["id"], "new_specification_id": first["id"],
    })
    assert self_comparison.status_code == 422

    mixed = isolated_client.post("/api/v1/compatibility/compare", json={
        "old_specification_id": first["id"], "new_specification_id": other_project["id"],
    })
    assert mixed.status_code == 400

    missing = isolated_client.post("/api/v1/compatibility/compare", json={
        "old_specification_id": first["id"], "new_specification_id": "00000000-0000-0000-0000-000000000001",
    })
    assert missing.status_code == 404
