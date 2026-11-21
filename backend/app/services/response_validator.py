"""Status, content-type, and OpenAPI response-schema validation."""

from jsonschema import Draft4Validator, Draft202012Validator, FormatChecker
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT4, DRAFT202012

SPECIFICATION_URI = "https://contractiq.invalid/openapi.json"


def _normalize_schema(value):
    if isinstance(value, list):
        return [_normalize_schema(item) for item in value]
    if not isinstance(value, dict):
        return value
    result = {key: _normalize_schema(item) for key, item in value.items() if key != "nullable"}
    if value.get("nullable") is True:
        if "$ref" in result:
            return {"anyOf": [result, {"type": "null"}]}
        current_type = result.get("type")
        if isinstance(current_type, str):
            result["type"] = [current_type, "null"]
        elif isinstance(current_type, list) and "null" not in current_type:
            result["type"] = [*current_type, "null"]
        elif current_type is None:
            result["anyOf"] = [result, {"type": "null"}]
    return result


def _absolutize_references(value):
    if isinstance(value, list):
        return [_absolutize_references(item) for item in value]
    if not isinstance(value, dict):
        return value
    result = {}
    for key, item in value.items():
        if key == "$ref" and isinstance(item, str) and item.startswith("#/"):
            result[key] = SPECIFICATION_URI + item
        else:
            result[key] = _absolutize_references(item)
    return result


def validate_response(
    *,
    expected_status_codes: list[int],
    actual_status_code: int,
    expected_content_types: list[str] | None = None,
    actual_content_type: str | None = None,
    schema: dict | None = None,
    body=None,
    body_present: bool = True,
    specification: dict | None = None,
) -> list[dict]:
    errors = []
    if expected_status_codes and actual_status_code not in expected_status_codes:
        errors.append({
            "code": "STATUS_MISMATCH",
            "message": f"Expected status {expected_status_codes}; received {actual_status_code}.",
        })
    if expected_content_types:
        actual = (actual_content_type or "").split(";", 1)[0].strip().lower()
        if not any(actual == item.split(";", 1)[0].strip().lower() for item in expected_content_types):
            errors.append({
                "code": "CONTENT_TYPE_MISMATCH",
                "message": f"Expected content type {expected_content_types}; received {actual or 'none'}.",
            })
    if schema:
        if not body_present:
            errors.append({"code": "RESPONSE_BODY_MISSING", "message": "Expected a response body matching the documented schema."})
        else:
            is_openapi_31 = str((specification or {}).get("openapi", "")).startswith("3.1")
            document = _absolutize_references(_normalize_schema(specification or {}))
            normalized_schema = _absolutize_references(_normalize_schema(schema))
            validator_type = Draft202012Validator if is_openapi_31 else Draft4Validator
            jsonschema_dialect = DRAFT202012 if is_openapi_31 else DRAFT4
            registry = Registry().with_resource(
                SPECIFICATION_URI,
                Resource(contents=document, specification=jsonschema_dialect),
            )
            validator = validator_type(
                normalized_schema,
                registry=registry,
                format_checker=FormatChecker(),
            )
            for error in sorted(validator.iter_errors(body), key=lambda item: list(map(str, item.absolute_path))):
                path = ".".join(str(part) for part in error.absolute_path) or "$"
                errors.append({
                    "code": "SCHEMA_MISMATCH",
                    "path": path,
                    "message": error.message,
                })
    return errors
