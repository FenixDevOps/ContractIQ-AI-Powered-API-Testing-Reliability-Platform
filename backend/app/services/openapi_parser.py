"""OpenAPI 3.x parsing and local-reference handling."""

from collections.abc import Iterable
import re


SUPPORTED_METHODS = {"get", "post", "put", "patch", "delete", "head", "options", "trace"}


class OpenApiParseError(ValueError):
    def __init__(self, message: str, status_code: int = 422):
        super().__init__(message)
        self.status_code = status_code


def resolve_local_reference(document: dict, reference: object, active: set[str] | None = None) -> object:
    if not isinstance(reference, str):
        raise OpenApiParseError("OpenAPI references must be strings.")
    if not reference.startswith("#/"):
        raise OpenApiParseError(f"External references are not supported: {reference}.")
    active = set(active or ())
    if reference in active:
        raise OpenApiParseError(f"Circular reference detected: {reference}.")
    value: object = document
    for token in reference[2:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if not isinstance(value, dict) or token not in value:
            raise OpenApiParseError(f"Unresolved reference: {reference}.")
        value = value[token]
    if isinstance(value, dict) and "$ref" in value:
        return resolve_local_reference(document, value["$ref"], active | {reference})
    return value


def extract_schema(document: dict, schema: object, active: set[str] | None = None) -> object:
    if not isinstance(schema, dict):
        return schema
    active = set(active or ())
    if "$ref" in schema:
        ref = schema["$ref"]
        if not isinstance(ref, str):
            raise OpenApiParseError("OpenAPI references must be strings.")
        if ref in active:
            return {"$ref": ref}
        resolved = resolve_local_reference(document, ref, active)
        out = extract_schema(document, resolved, active | {ref}) if isinstance(resolved, dict) else {"$ref": ref}
        out["$ref"] = ref
        return out
    out = dict(schema)
    for key in ("allOf", "oneOf", "anyOf"):
        if isinstance(out.get(key), list):
            out[key] = [extract_schema(document, item, active) for item in out[key]]
    if isinstance(out.get("items"), dict):
        out["items"] = extract_schema(document, out["items"], active)
    if isinstance(out.get("properties"), dict):
        out["properties"] = {name: extract_schema(document, value, active) for name, value in out["properties"].items()}
    return out


def extract_parameters(document: dict, parameters: object) -> list[dict]:
    if not isinstance(parameters, list):
        return []
    result = []
    for parameter in parameters:
        if not isinstance(parameter, dict):
            continue
        if "$ref" in parameter:
            try:
                parameter = resolve_local_reference(document, parameter["$ref"])
            except OpenApiParseError:
                raise
        if not isinstance(parameter, dict):
            continue
        schema = extract_schema(document, parameter.get("schema", {}))
        result.append({
            "name": parameter.get("name"),
            "in": parameter.get("in"),
            "required": bool(parameter.get("required", False)),
            "description": parameter.get("description"),
            "schema": schema,
            "deprecated": bool(parameter.get("deprecated", False)),
            "example": parameter.get("example"),
        })
    return result


def extract_request_body(document: dict, request_body: object) -> dict | None:
    if not isinstance(request_body, dict):
        return None
    if "$ref" in request_body:
        request_body = resolve_local_reference(document, request_body["$ref"])
    content = request_body.get("content", {})
    normalized = {}
    if isinstance(content, dict):
        for media_type, media in content.items():
            media = media if isinstance(media, dict) else {}
            normalized[media_type] = {
                "schema": extract_schema(document, media.get("schema", {})),
                "examples": media.get("examples"),
                "example": media.get("example"),
            }
    return {"required": bool(request_body.get("required", False)), "content": normalized}


def extract_responses(document: dict, responses: object) -> dict:
    if not isinstance(responses, dict):
        return {}
    result = {}
    for status, response in responses.items():
        if not isinstance(response, dict):
            continue
        if "$ref" in response:
            response = resolve_local_reference(document, response["$ref"])
        content = {}
        if isinstance(response.get("content"), dict):
            for media_type, media in response["content"].items():
                media = media if isinstance(media, dict) else {}
                content[media_type] = {
                    "schema": extract_schema(document, media.get("schema", {})),
                    "examples": media.get("examples"),
                    "example": media.get("example"),
                }
        result[str(status)] = {
            "description": response.get("description"),
            "headers": response.get("headers", {}),
            "content": content,
        }
    return result


def parse_openapi(document: dict) -> dict:
    if not isinstance(document, dict):
        raise OpenApiParseError("The specification document must be a JSON or YAML object.")
    openapi_version = document.get("openapi")
    if not isinstance(openapi_version, str):
        raise OpenApiParseError("Missing required 'openapi' version.")
    if not re.fullmatch(r"3\.(?:0|1)\.\d+", openapi_version):
        raise OpenApiParseError(
            f"Unsupported OpenAPI version '{openapi_version}'. ContractIQ supports OpenAPI 3.0.x and 3.1.x.",
            422,
        )
    info = document.get("info")
    if not isinstance(info, dict) or not info.get("title"):
        raise OpenApiParseError("Missing required info.title.")
    if "paths" not in document or not isinstance(document["paths"], dict):
        raise OpenApiParseError("Missing required paths object.")

    endpoints = []
    for path, path_item in document["paths"].items():
        if not isinstance(path_item, dict):
            continue
        path_parameters = path_item.get("parameters", [])
        for method, operation in path_item.items():
            method_lower = method.lower()
            if method_lower not in SUPPORTED_METHODS or not isinstance(operation, dict):
                continue
            merged_parameters = list(path_parameters) + list(operation.get("parameters", []) if isinstance(operation.get("parameters", []), list) else [])
            endpoints.append({
                "path": path,
                "method": method_lower.upper(),
                "operation_id": operation.get("operationId"),
                "summary": operation.get("summary"),
                "description": operation.get("description"),
                "tags": operation.get("tags", []) if isinstance(operation.get("tags", []), list) else [],
                "parameters": extract_parameters(document, merged_parameters),
                "request_body": extract_request_body(document, operation.get("requestBody")),
                "responses": extract_responses(document, operation.get("responses", {})),
                "deprecated": bool(operation.get("deprecated", False)),
                "security": operation.get("security", document.get("security", [])),
            })

    return {
        "openapi_version": openapi_version,
        "title": info["title"],
        "description": info.get("description"),
        "api_version": str(info.get("version", "unspecified")),
        "servers": document.get("servers", []) if isinstance(document.get("servers", []), list) else [],
        "global_tags": document.get("tags", []) if isinstance(document.get("tags", []), list) else [],
        "global_security": document.get("security", []) if isinstance(document.get("security", []), list) else [],
        "endpoints": endpoints,
    }
