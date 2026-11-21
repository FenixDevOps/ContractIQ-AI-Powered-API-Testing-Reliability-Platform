from uuid import uuid4

import httpx
import pytest

from app.database.models import ApiEndpoint, ApiSpecification, Project, TestCase as DbTestCase, TestResult as DbTestResult
from app.services import test_executor
from app.services.test_executor import TestExecutionConfigurationError
from app.services.response_validator import validate_response
from app.services.target_security import TargetValidationError, ValidatedTarget, validate_target_url
from app.services.test_generator import generate_for_endpoint


def _mock_target(value):
    return ValidatedTarget(
        url=value,
        hostname="api.example.test",
        port=443,
        addresses=("127.0.0.1",),
    )


def test_generator_creates_status_parameter_and_schema_cases():
    endpoint = ApiEndpoint(
        id=uuid4(),
        specification_id=uuid4(),
        path="/users/{user_id}",
        method="GET",
        parameters=[{
            "name": "user_id",
            "in": "path",
            "required": True,
            "schema": {"type": "integer", "example": 12},
        }, {
            "name": "page",
            "in": "query",
            "required": True,
            "schema": {"type": "integer", "example": 1},
        }],
        responses={
            "200": {
                "description": "OK",
                "content": {"application/json": {
                    "schema": {"type": "object", "required": ["id"], "properties": {"id": {"type": "integer"}}},
                }},
            },
            "404": {"description": "Not found"},
    })
    cases = generate_for_endpoint(endpoint.specification_id, endpoint)
    categories = {case.category for case in cases}
    assert {"STATUS_CODE", "REQUIRED_PARAMETER", "RESPONSE_SCHEMA", "CONTENT_TYPE", "NEGATIVE_TEST"} <= categories
    assert all(str(endpoint.id) in case.generation_key for case in cases)


def test_post_generator_uses_documented_body_example_and_gates_negative_body():
    endpoint = ApiEndpoint(
        id=uuid4(),
        specification_id=uuid4(),
        path="/users",
        method="POST",
        parameters=[],
        request_body={
            "required": True,
            "content": {"application/json": {
                "schema": {
                    "type": "object",
                    "required": ["name", "email"],
                    "properties": {"name": {"type": "string"}, "email": {"type": "string"}},
                },
                "example": {"name": "Test User", "email": "test@example.invalid"},
            }},
        },
        responses={"201": {"description": "Created"}, "400": {"description": "Invalid request"}},
    )
    cases = generate_for_endpoint(endpoint.specification_id, endpoint)
    body_case = next(case for case in cases if case.category == "REQUEST_BODY")
    negative = next(case for case in cases if case.category == "NEGATIVE_TEST")
    assert body_case.request_configuration["body"]["email"] == "test@example.invalid"
    assert "name" not in negative.request_configuration["body"]
    assert negative.expected_status_codes == [400]


@pytest.mark.parametrize("method", ["PUT", "PATCH", "DELETE"])
def test_write_method_generation_is_documented_and_nonexecuting(method):
    endpoint = ApiEndpoint(
        id=uuid4(),
        specification_id=uuid4(),
        path="/users/{user_id}",
        method=method,
        parameters=[{
            "name": "user_id",
            "in": "path",
            "required": True,
            "schema": {"type": "integer", "example": 12},
        }],
        request_body={
            "required": True,
            "content": {"application/json": {
                "schema": {"type": "object"},
                "example": {"active": False},
            }},
        } if method != "DELETE" else None,
        responses={"200": {"description": "OK"}},
    )
    cases = generate_for_endpoint(endpoint.specification_id, endpoint)
    assert any(case.category == "STATUS_CODE" and case.http_method == method for case in cases)
    if method != "DELETE":
        body_case = next(case for case in cases if case.category == "REQUEST_BODY")
        assert body_case.request_configuration["body"] == {"active": False}


def test_required_parameter_without_example_is_skipped_when_run(isolated_client, monkeypatch):
    from app.database.connection import get_db
    from app.main import app

    db_generator = app.dependency_overrides[get_db]()
    db = next(db_generator)
    project = Project(name="Test Project")
    db.add(project)
    db.flush()
    spec = ApiSpecification(
        project_id=project.id,
        title="Example",
        openapi_version="3.0.3",
        api_version="1",
        original_filename="x.json",
        file_format="JSON",
        version_number=1,
        raw_specification={"openapi": "3.0.3", "info": {"title": "X"}, "paths": {}},
        content_hash="hash",
    )
    db.add(spec)
    db.flush()
    endpoint = ApiEndpoint(
        specification_id=spec.id,
        path="/users/{id}",
        method="GET",
        parameters=[{"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}],
        responses={"200": {"description": "OK"}},
    )
    db.add(endpoint)
    db.flush()
    case = next(item for item in generate_for_endpoint(spec.id, endpoint) if item.category == "STATUS_CODE")
    db.add(case)
    db.commit()
    monkeypatch.setattr(test_executor, "resolve_target_url", _mock_target)
    try:
        run = test_executor.execute_test_run(
            db,
            specification=spec,
            cases=[case],
            base_url="https://api.example.test",
            environment_name="testing",
            timeout_seconds=2,
            include_negative_tests=False,
            allow_write_operations=False,
            confirm_destructive=False,
            default_headers={},
        )
        result = db.query(DbTestResult).filter(DbTestResult.test_run_id == run.id).one()
        assert run.status == "COMPLETED"
        assert result.status == "SKIPPED"
    finally:
        db_generator.close()


def test_response_validation_reports_status_type_and_content_errors():
    errors = validate_response(
        expected_status_codes=[200],
        actual_status_code=200,
        expected_content_types=["application/json"],
        actual_content_type="text/plain",
        schema={"type": "object", "required": ["id"], "properties": {"id": {"type": "integer"}}},
        body={"id": "wrong"},
        specification={"openapi": "3.1.0", "components": {"schemas": {}}},
    )
    codes = {item["code"] for item in errors}
    assert codes == {"CONTENT_TYPE_MISMATCH", "SCHEMA_MISMATCH"}


def test_response_validation_resolves_nested_refs_and_nullable_openapi_30():
    specification = {
        "openapi": "3.1.0",
        "components": {
            "schemas": {
                "Envelope": {"type": "object", "required": ["user"], "properties": {"user": {"$ref": "#/components/schemas/User"}}},
                "User": {"type": "object", "required": ["id"], "properties": {"id": {"type": "integer"}}},
            }
        },
    }
    valid = validate_response(
        expected_status_codes=[200],
        actual_status_code=200,
        schema={"$ref": "#/components/schemas/Envelope"},
        body={"user": {"id": 8}},
        specification=specification,
    )
    invalid = validate_response(
        expected_status_codes=[200],
        actual_status_code=200,
        schema={"$ref": "#/components/schemas/Envelope"},
        body={"user": {"id": "wrong"}},
        specification=specification,
    )
    assert valid == []
    assert any("integer" in error["message"] for error in invalid)
    nullable = validate_response(
        expected_status_codes=[200],
        actual_status_code=200,
        schema={"type": "string", "nullable": True},
        body=None,
        specification={"openapi": "3.0.3"},
    )
    assert nullable == []


def test_target_requires_allowlisted_hostname_and_rejects_private_dns(monkeypatch):
    import app.services.target_security as security

    monkeypatch.setattr(security, "TEST_ALLOWED_TARGET_HOSTS", {"api.example.test"})
    monkeypatch.setattr(
        security.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(None, None, None, None, ("10.0.0.5", 443))],
    )
    monkeypatch.setattr(security, "TEST_ALLOW_PRIVATE_TARGETS", False)
    with pytest.raises(TargetValidationError, match="Private"):
        validate_target_url("https://api.example.test")
    with pytest.raises(TargetValidationError, match="allowlisted"):
        validate_target_url("https://other.example.test")
    with pytest.raises(TargetValidationError, match="credentials"):
        validate_target_url("https://user:pass@api.example.test")
    with pytest.raises(TargetValidationError, match="metadata"):
        validate_target_url("http://metadata.google.internal")
    monkeypatch.setattr(security, "TEST_ALLOW_PRIVATE_TARGETS", True)
    assert validate_target_url("https://api.example.test/v1") == "https://api.example.test/v1"
    with pytest.raises(TargetValidationError, match="path prefix"):
        validate_target_url("https://api.example.test/v1/../admin")


def test_httpx_transport_pins_the_address_resolved_during_target_validation(monkeypatch):
    import socket
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    import app.services.target_security as security

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"pinned")

        def log_message(self, format, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    monkeypatch.setattr(security, "TEST_ALLOWED_TARGET_HOSTS", {"api.example.test"})
    monkeypatch.setattr(security, "TEST_ALLOWED_TARGET_PORTS", {port})
    monkeypatch.setattr(security, "TEST_ALLOW_PRIVATE_TARGETS", True)
    original_getaddrinfo = security.socket.getaddrinfo
    resolutions = []

    def resolve(host, requested_port, *args, **kwargs):
        if host == "api.example.test":
            resolutions.append(host)
            address = "127.0.0.1" if len(resolutions) == 1 else "10.0.0.8"
            return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (address, requested_port))]
        return original_getaddrinfo(host, requested_port, *args, **kwargs)

    monkeypatch.setattr(security.socket, "getaddrinfo", resolve)
    try:
        target = security.resolve_target_url(f"http://api.example.test:{port}")
        with httpx.Client(
            transport=security.PinnedHTTPTransport(target, limits=httpx.Limits(max_connections=1)),
            timeout=2,
            trust_env=False,
        ) as client:
            response = client.get(target.url)
        assert response.status_code == 200
        assert response.text == "pinned"
        assert resolutions == ["api.example.test"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.mark.parametrize(
    "failure, expected",
    [
        (httpx.ConnectError("connection refused"), "HTTP request failed"),
        (httpx.ReadTimeout("read timed out"), "Request timed out"),
    ],
)
def test_httpx_transport_errors_are_saved_as_test_errors(monkeypatch, failure, expected):
    from app.database.models import ApiSpecification, TestCase as DbTestCase

    specification = ApiSpecification(
        raw_specification={"openapi": "3.1.0", "components": {"schemas": {}}}
    )
    case = DbTestCase(
        id=uuid4(),
        specification_id=uuid4(),
        endpoint_id=uuid4(),
        name="GET /health",
        description="Check status",
        category="STATUS_CODE",
        priority="HIGH",
        http_method="GET",
        endpoint_path="/health",
        request_configuration={},
        expected_status_codes=[200],
        generation_key="network-failure",
    )
    with httpx.Client(transport=httpx.MockTransport(lambda request: (_ for _ in ()).throw(failure))) as client:
        result = test_executor._run_case(
            client,
            case,
            "https://api.example.test",
            {},
            1,
            specification,
        )
    assert result.status == "ERROR"
    assert expected in result.error_message


def test_httpx_execution_persists_mocked_response_without_network(isolated_client, monkeypatch):
    from app.database.connection import get_db
    from app.main import app

    db_generator = app.dependency_overrides[get_db]()
    db = next(db_generator)
    project = Project(name="Mocked")
    db.add(project)
    db.flush()
    specification = ApiSpecification(
        project_id=project.id,
        title="Mock API",
        openapi_version="3.1.0",
        api_version="1",
        original_filename="mock.json",
        file_format="JSON",
        version_number=1,
        raw_specification={"openapi": "3.1.0", "components": {"schemas": {}}},
        content_hash="mockhash",
    )
    db.add(specification)
    db.flush()
    endpoint = ApiEndpoint(specification_id=specification.id, path="/health", method="GET", responses={"200": {"description": "ok"}})
    db.add(endpoint)
    db.flush()
    case = DbTestCase(
        specification_id=specification.id,
        endpoint_id=endpoint.id,
        name="Health status",
        description="Check status",
        category="STATUS_CODE",
        priority="HIGH",
        http_method="GET",
        endpoint_path="/health",
        request_configuration={},
        expected_status_codes=[200],
        is_enabled=True,
        generation_key="health-status",
    )
    db.add(case)
    db.commit()

    monkeypatch.setattr(test_executor, "resolve_target_url", _mock_target)
    original_client = httpx.Client
    def mock_client(**kwargs):
        kwargs["transport"] = httpx.MockTransport(
            lambda request: httpx.Response(200, json={"status": "ok"}, headers={"content-type": "application/json"})
        )
        return original_client(**kwargs)

    monkeypatch.setattr(test_executor.httpx, "Client", mock_client)
    try:
        run = test_executor.execute_test_run(
            db,
            specification=specification,
            cases=[case],
            base_url="https://api.example.test",
            environment_name="testing",
            timeout_seconds=3,
            include_negative_tests=False,
            allow_write_operations=False,
            confirm_destructive=False,
            default_headers={"Authorization": "Bearer very-secret"},
        )
        result = db.query(DbTestResult).filter(DbTestResult.test_run_id == run.id).one()
        assert run.status == "COMPLETED"
        assert run.passed_tests == 1
        assert result.status == "PASSED"
        assert result.request_details["headers"]["Authorization"] == "[REDACTED]"
        assert "very-secret" not in str(result.request_details)
    finally:
        db_generator.close()


def test_sensitive_path_parameters_are_redacted_from_persisted_request_urls(monkeypatch):
    specification = ApiSpecification(
        raw_specification={"openapi": "3.1.0", "components": {"schemas": {}}}
    )
    case = DbTestCase(
        id=uuid4(),
        specification_id=uuid4(),
        endpoint_id=uuid4(),
        name="GET /keys/{api_token}",
        description="Fetch a tokenized resource",
        category="STATUS_CODE",
        priority="HIGH",
        http_method="GET",
        endpoint_path="/keys/{api_token}",
        request_configuration={"path_params": {"api_token": "very-secret"}},
        expected_status_codes=[200],
        generation_key="sensitive-path",
    )
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200))) as client:
        result = test_executor._run_case(
            client,
            case,
            "https://api.example.test",
            {},
            1,
            specification,
        )
    assert result.status == "PASSED"
    assert result.request_details["url"] == "https://api.example.test/keys/[REDACTED]"
    assert "very-secret" not in str(result.request_details)


def test_oversized_http_response_is_truncated_and_fails_validation(monkeypatch):
    specification = ApiSpecification(
        raw_specification={"openapi": "3.1.0", "components": {"schemas": {}}}
    )
    case = DbTestCase(
        id=uuid4(),
        specification_id=uuid4(),
        endpoint_id=uuid4(),
        name="GET /large",
        description="Check response size handling",
        category="STATUS_CODE",
        priority="HIGH",
        http_method="GET",
        endpoint_path="/large",
        request_configuration={},
        expected_status_codes=[200],
        generation_key="large-response",
    )
    monkeypatch.setattr(test_executor, "TEST_MAX_RESPONSE_BYTES", 4)
    with httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b"abcdefgh"))
    ) as client:
        result = test_executor._run_case(
            client,
            case,
            "https://api.example.test",
            {},
            1,
            specification,
        )
    assert result.status == "FAILED"
    assert result.response_details["body"] == "abcd"
    assert result.response_details["truncated"] is True
    assert result.validation_errors[-1]["code"] == "RESPONSE_TRUNCATED"


def test_testing_routes_generate_execute_and_return_persisted_history(isolated_client, monkeypatch):
    project = isolated_client.post("/api/v1/projects", json={"name": "Route test"}).json()
    document = {
        "openapi": "3.1.0",
        "info": {"title": "Mock service", "version": "1"},
        "paths": {"/health": {"get": {"responses": {"200": {
            "description": "OK",
            "content": {"application/json": {"schema": {
                "type": "object",
                "required": ["status"],
                "properties": {"status": {"type": "string"}},
            }}},
        }}}}},
    }
    import_response = isolated_client.post(
        f"/api/v1/projects/{project['id']}/specifications/import",
        files={"file": ("mock.json", __import__("json").dumps(document).encode(), "application/json")},
    )
    assert import_response.status_code == 201
    specification_id = import_response.json()["id"]
    generated = isolated_client.post(f"/api/v1/specifications/{specification_id}/test-cases/generate")
    assert generated.status_code == 200
    assert generated.json()["created_count"] == 3
    repeated = isolated_client.post(f"/api/v1/specifications/{specification_id}/test-cases/generate")
    assert repeated.json()["created_count"] == 0

    monkeypatch.setattr(test_executor, "resolve_target_url", _mock_target)
    original_client = httpx.Client
    def mock_client(**kwargs):
        kwargs["transport"] = httpx.MockTransport(
            lambda request: httpx.Response(200, json={"status": "ok"})
        )
        return original_client(**kwargs)

    monkeypatch.setattr(test_executor.httpx, "Client", mock_client)
    run_response = isolated_client.post(
        f"/api/v1/specifications/{specification_id}/test-runs",
        json={"base_url": "https://api.example.test", "environment_name": "testing"},
    )
    assert run_response.status_code == 201
    run = run_response.json()
    assert run["status"] == "COMPLETED"
    assert run["passed_tests"] == 3
    result_response = isolated_client.get(f"/api/v1/test-runs/{run['id']}/results")
    assert result_response.status_code == 200
    assert len(result_response.json()) == 3
    target_result = result_response.json()[0]
    result_snapshot = target_result["test_case_snapshot"]
    deleted_case_id = target_result["test_case_id"]
    delete_case = isolated_client.delete(f"/api/v1/test-cases/{deleted_case_id}")
    assert delete_case.status_code == 204
    retained_result = isolated_client.get(f"/api/v1/test-results/{target_result['id']}").json()
    assert retained_result["test_case_id"] is None
    assert retained_result["test_case_snapshot"] == result_snapshot
    history = isolated_client.get(f"/api/v1/specifications/{specification_id}/test-runs")
    assert history.json()[0]["id"] == run["id"]
    summary = isolated_client.get(f"/api/v1/specifications/{specification_id}/testing-summary")
    assert summary.json()["test_run_count"] == 1
    assert summary.json()["passed_tests"] == 3


def test_write_operations_require_confirmation_and_are_blocked_in_production(isolated_client, monkeypatch):
    from app.database.connection import get_db
    from app.main import app

    db_generator = app.dependency_overrides[get_db]()
    db = next(db_generator)
    project = Project(name="Write safety")
    db.add(project)
    db.flush()
    specification = ApiSpecification(
        project_id=project.id,
        title="Write API",
        openapi_version="3.1.0",
        api_version="1",
        original_filename="write.json",
        file_format="JSON",
        version_number=1,
        raw_specification={"openapi": "3.1.0", "components": {"schemas": {}}},
        content_hash="writehash",
    )
    db.add(specification)
    db.flush()
    endpoint = ApiEndpoint(specification_id=specification.id, path="/items", method="POST", responses={"201": {"description": "created"}})
    db.add(endpoint)
    db.flush()
    case = DbTestCase(
        specification_id=specification.id,
        endpoint_id=endpoint.id,
        name="Create item",
        description="Create an item",
        category="STATUS_CODE",
        priority="HIGH",
        http_method="POST",
        endpoint_path="/items",
        request_configuration={"body": {"name": "sample"}, "content_type": "application/json"},
        expected_status_codes=[201],
        generation_key="post-write",
    )
    db.add(case)
    db.commit()
    monkeypatch.setattr(test_executor, "resolve_target_url", _mock_target)
    arguments = {
        "db": db,
        "specification": specification,
        "cases": [case],
        "base_url": "https://api.example.test",
        "timeout_seconds": 2,
        "include_negative_tests": False,
        "allow_write_operations": True,
        "default_headers": {},
    }
    try:
        with pytest.raises(TestExecutionConfigurationError, match="confirmation"):
            test_executor.execute_test_run(
                **arguments,
                environment_name="testing",
                confirm_destructive=False,
            )
        with pytest.raises(TestExecutionConfigurationError, match="Production safe mode"):
            test_executor.execute_test_run(
                **arguments,
                environment_name="production",
                confirm_destructive=True,
            )
    finally:
        db_generator.close()
