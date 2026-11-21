"""Structural OpenAPI validation."""

from openapi_spec_validator import validate
from openapi_spec_validator.exceptions import OpenAPIError
from openapi_spec_validator.validation.exceptions import OpenAPIValidationError
from referencing.exceptions import Unresolvable

from app.services.openapi_parser import OpenApiParseError, parse_openapi


def _validate_local_references(value: object) -> None:
    if isinstance(value, dict):
        reference = value.get("$ref")
        if reference is not None and (not isinstance(reference, str) or not reference.startswith("#/")):
            raise OpenApiParseError("Only local '#/...' OpenAPI references are supported.")
        for item in value.values():
            _validate_local_references(item)
    elif isinstance(value, list):
        for item in value:
            _validate_local_references(item)


def validate_document(document: object) -> dict:
    if not isinstance(document, dict):
        raise OpenApiParseError("The specification document must be a JSON or YAML object.")
    parsed = parse_openapi(document)
    _validate_local_references(document)
    try:
        validate(document)
    except (OpenAPIError, OpenAPIValidationError, Unresolvable) as exc:
        raise OpenApiParseError(f"Invalid OpenAPI document: {exc}") from exc
    return parsed
