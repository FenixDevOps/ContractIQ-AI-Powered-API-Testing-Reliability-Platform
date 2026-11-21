"""Deterministic, conservative test case generation from persisted operations."""

__test__ = False

from copy import deepcopy
from uuid import uuid4

from app.database.models import ApiEndpoint, TestCase


SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def _sample(schema: object) -> tuple[object, bool]:
    if not isinstance(schema, dict):
        return None, False
    for key in ("example", "default"):
        if key in schema:
            return schema[key], True
    enum = schema.get("enum")
    if isinstance(enum, list) and enum:
        return enum[0], True
    schema_type = schema.get("type")
    if schema_type == "object" or "properties" in schema:
        required = schema.get("required", [])
        properties = schema.get("properties", {})
        values = {}
        for name in required:
            value, found = _sample(properties.get(name, {}))
            if not found:
                return None, False
            values[name] = value
        return values, True
    if schema_type == "array":
        item, found = _sample(schema.get("items", {}))
        return ([item] if found else []), found
    return None, False


def _request_values(endpoint: ApiEndpoint) -> tuple[dict, list[str]]:
    config = {"path_params": {}, "query_params": {}, "headers": {}, "cookie_params": {}}
    missing = []
    for parameter in endpoint.parameters or []:
        if not isinstance(parameter, dict):
            continue
        value, found = _sample(parameter.get("schema", {}))
        if "example" in parameter:
            value, found = parameter["example"], True
        if not found and parameter.get("required"):
            missing.append(f"{parameter.get('in')} parameter '{parameter.get('name')}' needs a value")
            continue
        if found and parameter.get("in") in {"path", "query", "header", "cookie"}:
            key = {"path": "path_params", "query": "query_params", "header": "headers", "cookie": "cookie_params"}[parameter["in"]]
            config[key][parameter.get("name")] = value
        elif parameter.get("required"):
            missing.append(f"{parameter.get('in')} parameter '{parameter.get('name')}' needs a value")
    return config, missing


def generate_for_endpoint(specification_id, endpoint: ApiEndpoint) -> list[TestCase]:
    successful = sorted({
        int(code) for code in (endpoint.responses or {})
        if str(code).isdigit() and 200 <= int(code) < 300
    })
    if not successful:
        return []

    request_config, missing = _request_values(endpoint)
    body = endpoint.request_body
    body_media_type = None
    body_sample = None
    body_sample_available = False
    if endpoint.method in {"POST", "PUT", "PATCH"} and isinstance(body, dict):
        for media_type, media in (body.get("content") or {}).items():
            if not isinstance(media, dict):
                continue
            sample = media.get("example")
            if sample is None:
                examples = media.get("examples") or {}
                if isinstance(examples, dict) and examples:
                    first = next(iter(examples.values()))
                    sample = first.get("value") if isinstance(first, dict) else None
            if sample is None:
                sample, body_sample_available = _sample(media.get("schema", {}))
            else:
                body_sample_available = True
            body_media_type = media_type
            body_sample = sample
            break
        if body_sample_available:
            request_config.update({"body": body_sample, "content_type": body_media_type})
        elif body.get("required"):
            request_config["needs_body_configuration"] = True
            missing.append("required request body needs a usable example or schema values")
    request_config["missing_inputs"] = missing
    generated = []
    schemas = {}
    content_types = set()
    for code, response in (endpoint.responses or {}).items():
        if not str(code).isdigit() or int(code) not in successful or not isinstance(response, dict):
            continue
        for content_type, media in (response.get("content") or {}).items():
            if not isinstance(media, dict):
                continue
            content_types.add(content_type)
            schema = media.get("schema")
            if isinstance(schema, dict) and schema:
                schemas[str(code)] = schema

    def create_case(key: str, suffix: str, category: str, description: str, statuses: list[int], schema=None, extra=None):
        config = dict(request_config)
        if extra:
            config.update(extra)
        generated.append(TestCase(
            id=uuid4(),
            specification_id=specification_id,
            endpoint_id=endpoint.id,
            name=f"{endpoint.method} {endpoint.path} - {suffix}",
            description=description,
            category=category,
            priority="HIGH" if category == "STATUS_CODE" else "MEDIUM",
            http_method=endpoint.method,
            endpoint_path=endpoint.path,
            request_configuration=config,
            expected_status_codes=statuses,
            expected_response_schema=schema,
            is_enabled=True,
            is_generated=True,
            generation_key=f"{endpoint.id}:{key}",
        ))

    create_case("status", "successful status", "STATUS_CODE", "Verify the operation returns a documented successful status.", successful)
    if endpoint.parameters:
        create_case(
            "parameters", "parameters", "REQUIRED_PARAMETER",
            "Send parameter values available from the specification and validate the documented status.",
            successful,
        )
    if schemas:
        chosen_code = sorted(schemas, key=int)[0]
        create_case(
            f"schema-{chosen_code}", "response schema", "RESPONSE_SCHEMA",
            f"Validate the response against the schema documented for HTTP {chosen_code}.",
            [int(chosen_code)], schemas[chosen_code],
        )
    if content_types:
        create_case(
            "content-type", "response content type", "CONTENT_TYPE",
            "Verify the response content type matches a documented successful response.",
            successful, extra={"expected_content_types": sorted(content_types)},
        )

    if body_media_type and isinstance(body, dict) and (body_sample_available or body.get("required")):
        create_case(
            f"request-body-{body_media_type}", "request body", "REQUEST_BODY",
            "Send a representative request body and verify its documented success status.",
            successful,
        )
        first_media = next(iter((body.get("content") or {}).values()), {})
        schema = first_media.get("schema", {}) if isinstance(first_media, dict) else {}
        required_fields = schema.get("required", []) if isinstance(schema, dict) else []
        expected_negative = [
            int(code) for code in (endpoint.responses or {})
            if str(code).isdigit() and 400 <= int(code) < 500
        ]
        if body.get("required") and body_sample_available and isinstance(body_sample, dict) and required_fields and expected_negative:
            invalid_body = deepcopy(body_sample)
            invalid_body.pop(required_fields[0], None)
            create_case(
                f"negative-body-{body_media_type}",
                "missing required body property",
                "NEGATIVE_TEST",
                f"Omit required body property '{required_fields[0]}' and check a documented client-error status.",
                expected_negative,
                extra={"body": invalid_body, "content_type": body_media_type},
            )

    if endpoint.method in SAFE_METHODS:
        for parameter in (endpoint.parameters or []):
            if (
                not isinstance(parameter, dict)
                or not parameter.get("required")
                or parameter.get("in") not in {"query", "header"}
            ):
                continue
            expected_negative = [
                int(code) for code in (endpoint.responses or {})
                if str(code).isdigit() and 400 <= int(code) < 500
            ]
            if expected_negative:
                config = dict(request_config)
                config["omit_parameter"] = {"in": parameter.get("in"), "name": parameter.get("name")}
                omitted_reason = f"{parameter.get('in')} parameter '{parameter.get('name')}' needs a value"
                config["missing_inputs"] = [
                    reason for reason in config.get("missing_inputs", []) if reason != omitted_reason
                ]
                create_case(
                    f"negative-{parameter.get('in')}-{parameter.get('name')}",
                    f"missing required {parameter.get('name')}",
                    "NEGATIVE_TEST",
                    "Omit a required parameter and check a documented client-error status.",
                    expected_negative, extra=config,
                )
    return generated


def generate_test_cases(db, specification_id) -> list[TestCase]:
    endpoints = db.query(ApiEndpoint).filter(ApiEndpoint.specification_id == specification_id).all()
    existing_keys = {
        row[0] for row in db.query(TestCase.generation_key).filter(
            TestCase.specification_id == specification_id, TestCase.is_generated.is_(True)
        ).all()
    }
    created = []
    for endpoint in endpoints:
        for case in generate_for_endpoint(specification_id, endpoint):
            if case.generation_key not in existing_keys:
                db.add(case)
                created.append(case)
                existing_keys.add(case.generation_key)
    db.flush()
    return created
