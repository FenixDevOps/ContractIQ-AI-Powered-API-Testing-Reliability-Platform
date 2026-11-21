import pytest

from app.services.openapi_parser import OpenApiParseError, parse_openapi
from app.services.specification_validator import validate_document


def valid_spec():
    return {
        "openapi": "3.1.0",
        "info": {"title": "Users API", "version": "1.0.0", "description": "A user API"},
        "paths": {
            "/users": {
                "get": {
                    "operationId": "listUsers",
                    "parameters": [{"name": "limit", "in": "query", "required": False, "schema": {"type": "integer"}}],
                    "responses": {"200": {"description": "OK", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/UserList"}}}}},
                },
                "post": {
                    "requestBody": {"required": True, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/User"}}}},
                    "responses": {"201": {"description": "Created"}},
                },
            }
        },
        "components": {"schemas": {
            "User": {"type": "object", "properties": {"id": {"type": "string"}, "profile": {"$ref": "#/components/schemas/Profile"}}},
            "Profile": {"type": "object", "properties": {"name": {"type": "string"}}},
            "UserList": {"type": "array", "items": {"$ref": "#/components/schemas/User"}},
        }},
    }


def test_valid_spec_extracts_methods_and_metadata():
    parsed = parse_openapi(valid_spec())
    assert parsed["title"] == "Users API"
    assert len(parsed["endpoints"]) == 2
    assert {item["method"] for item in parsed["endpoints"]} == {"GET", "POST"}
    get = next(item for item in parsed["endpoints"] if item["method"] == "GET")
    assert get["parameters"][0]["name"] == "limit"
    assert get["parameters"][0]["in"] == "query"
    assert get["responses"]["200"]["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/UserList"


def test_nested_schema_reference_is_preserved():
    parsed = parse_openapi(valid_spec())
    post = next(item for item in parsed["endpoints"] if item["method"] == "POST")
    assert post["request_body"]["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/User"


def test_recursive_local_schema_reference_is_preserved_without_expansion_loop():
    document = valid_spec()
    document["components"]["schemas"]["User"]["properties"]["children"] = {
        "type": "array",
        "items": {"$ref": "#/components/schemas/User"},
    }

    parsed = validate_document(document)
    post = next(item for item in parsed["endpoints"] if item["method"] == "POST")
    schema = post["request_body"]["content"]["application/json"]["schema"]
    assert schema["properties"]["children"]["items"] == {"$ref": "#/components/schemas/User"}


def test_unresolved_reference_is_rejected():
    document = valid_spec()
    document["paths"]["/users"]["get"]["responses"]["200"]["content"]["application/json"]["schema"] = {"$ref": "#/components/schemas/Missing"}
    with pytest.raises(OpenApiParseError, match="Unresolved reference"):
        parse_openapi(document)


def test_unsupported_openapi_version_is_rejected():
    document = valid_spec()
    document["openapi"] = "2.0"
    with pytest.raises(OpenApiParseError, match="Unsupported OpenAPI"):
        parse_openapi(document)


def test_document_validation_rejects_invalid_structure_and_external_references():
    document = valid_spec()
    document["info"].pop("version")
    with pytest.raises(OpenApiParseError, match="Invalid OpenAPI document"):
        validate_document(document)

    document = valid_spec()
    document["components"]["schemas"]["User"]["external"] = {"$ref": "https://example.test/schema.json"}
    with pytest.raises(OpenApiParseError, match="Only local"):
        validate_document(document)
