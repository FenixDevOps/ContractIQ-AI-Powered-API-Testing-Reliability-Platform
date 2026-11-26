from app.services.compatibility_engine import CompatibilityEngine


def spec(paths, components=None):
    document = {
        "openapi": "3.1.0",
        "info": {"title": "Users API", "version": "1.0"},
        "paths": paths,
    }
    if components:
        document["components"] = components
    return document


def test_normalized_path_parameter_rename_is_not_endpoint_removal():
    before = spec({
        "/users/{id}": {
            "get": {
                "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                "responses": {"200": {"description": "OK"}},
            }
        }
    })
    after = spec({
        "/users/{user_id}": {
            "get": {
                "parameters": [{"name": "user_id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                "responses": {"200": {"description": "OK"}},
            }
        }
    })

    result = CompatibilityEngine().compare(before, after)

    assert result["endpoint_summary"] == {
        "total_compared": 1, "added": 0, "removed": 0, "modified": 1, "unchanged": 0
    }
    assert [change["change_type"] for change in result["changes"]] == ["PATH_PARAMETER_RENAMED"]
    assert result["changes"][0]["compatibility"] == "INFORMATIONAL"


def test_new_required_request_field_and_incompatible_type_are_breaking():
    before = spec({
        "/users": {"post": {
            "requestBody": {"content": {"application/json": {"schema": {
                "type": "object",
                "properties": {"age": {"type": "integer"}, "email": {"type": "string"}},
            }}}},
            "responses": {"200": {"description": "OK"}},
        }}
    })
    after = spec({
        "/users": {"post": {
            "requestBody": {"required": True, "content": {"application/json": {"schema": {
                "type": "object",
                "required": ["email"],
                "properties": {"age": {"type": "string"}, "email": {"type": "string"}},
            }}}},
            "responses": {"200": {"description": "OK"}},
        }}
    })

    result = CompatibilityEngine().compare(before, after)
    types = {change["change_type"] for change in result["changes"]}

    assert "REQUEST_BODY_NEWLY_REQUIRED" in types
    assert "NEWLY_REQUIRED_FIELD" in types
    assert "CHANGED_TYPE" in types
    assert result["counts"]["breaking"] >= 3
    assert result["compatibility_score"] < 100


def test_nested_local_references_and_cycles_are_compared_without_recursion_failure():
    before = spec(
        {"/users": {"get": {"responses": {"200": {"description": "OK", "content": {
            "application/json": {"schema": {"$ref": "#/components/schemas/User"}}
        }}}}}},
        {"schemas": {
            "User": {"type": "object", "properties": {"profile": {"$ref": "#/components/schemas/Profile"}}},
            "Profile": {"type": "object", "properties": {
                "user": {"$ref": "#/components/schemas/User"},
                "name": {"type": "string"},
            }},
        }},
    )
    after = spec(
        {"/users": {"get": {"responses": {"200": {"description": "OK", "content": {
            "application/json": {"schema": {"$ref": "#/components/schemas/User"}}
        }}}}}},
        {"schemas": {
            "User": {"type": "object", "properties": {"profile": {"$ref": "#/components/schemas/Profile"}}},
            "Profile": {"type": "object", "properties": {
                "user": {"$ref": "#/components/schemas/User"},
                "name": {"type": "string"},
                "displayName": {"type": "string"},
            }},
        }},
    )

    result = CompatibilityEngine().compare(before, after)

    assert any(change["property_name"] == "200.profile.displayName" for change in result["changes"])
    assert result["changes"][0]["compatibility"] in {
        "NON_BREAKING", "POTENTIALLY_BREAKING", "INFORMATIONAL"
    }


def test_response_removal_is_breaking_and_added_endpoint_is_non_breaking():
    before = spec({
        "/users": {"get": {"responses": {"200": {"description": "OK", "content": {
            "application/json": {"schema": {"type": "object", "properties": {"email": {"type": "string"}}}}
        }}, "404": {"description": "Missing"}}}}
    })
    after = spec({
        "/users": {"get": {"responses": {"200": {"description": "OK", "content": {
            "application/json": {"schema": {"type": "object"}}
        }}}}},
        "/groups": {"get": {"responses": {"200": {"description": "OK"}}}},
    })

    result = CompatibilityEngine().compare(before, after)
    by_type = {change["change_type"]: change for change in result["changes"]}

    assert by_type["REMOVED_FIELD"]["compatibility"] == "BREAKING"
    assert by_type["REMOVED_RESPONSE_STATUS"]["compatibility"] == "BREAKING"
    assert by_type["ADDED_ENDPOINT"]["compatibility"] == "NON_BREAKING"


def test_request_enum_restriction_and_response_enum_expansion_have_directional_rules():
    before = spec({
        "/orders": {"post": {
            "requestBody": {"content": {"application/json": {"schema": {
                "type": "string", "enum": ["new", "paid"]
            }}}},
            "responses": {"200": {"description": "OK", "content": {"application/json": {
                "schema": {"type": "string", "enum": ["new", "paid"]}
            }}}},
        }}
    })
    after = spec({
        "/orders": {"post": {
            "requestBody": {"content": {"application/json": {"schema": {
                "type": "string", "enum": ["new"]
            }}}},
            "responses": {"200": {"description": "OK", "content": {"application/json": {
                "schema": {"type": "string", "enum": ["new", "paid", "refunded"]}
            }}}},
        }}
    })

    result = CompatibilityEngine().compare(before, after)
    removed = next(item for item in result["changes"] if item["change_type"] == "REMOVED_ENUM_VALUES")
    added = next(item for item in result["changes"] if item["change_type"] == "ADDED_ENUM_VALUES")

    assert removed["compatibility"] == "BREAKING"
    assert added["compatibility"] == "POTENTIALLY_BREAKING"


def test_optional_query_parameter_becoming_required_and_content_type_removal():
    before = spec({
        "/items": {"get": {
            "parameters": [{"name": "limit", "in": "query", "schema": {"type": "integer"}}],
            "responses": {"200": {"description": "OK", "content": {
                "application/json": {"schema": {"type": "object"}}
            }}},
        }}
    })
    after = spec({
        "/items": {"get": {
            "parameters": [{"name": "limit", "in": "query", "required": True, "schema": {"type": "integer"}}],
            "responses": {"200": {"description": "OK", "content": {
                "application/xml": {"schema": {"type": "object"}}
            }}},
        }}
    })

    result = CompatibilityEngine().compare(before, after)
    by_type = {change["change_type"]: change for change in result["changes"]}

    assert by_type["NEWLY_REQUIRED_PARAMETER"]["compatibility"] == "BREAKING"
    assert by_type["REMOVED_CONTENT_TYPE"]["compatibility"] == "POTENTIALLY_BREAKING"
    assert by_type["ADDED_CONTENT_TYPE"]["compatibility"] == "NON_BREAKING"


def test_numeric_widening_uses_request_and_response_direction():
    before = spec({
        "/items": {"post": {
            "requestBody": {"content": {"application/json": {"schema": {"type": "integer"}}}},
            "responses": {"200": {"description": "OK", "content": {
                "application/json": {"schema": {"type": "integer"}}
            }}},
        }}
    })
    after = spec({
        "/items": {"post": {
            "requestBody": {"content": {"application/json": {"schema": {"type": "number"}}}},
            "responses": {"200": {"description": "OK", "content": {
                "application/json": {"schema": {"type": "number"}}
            }}},
        }}
    })

    result = CompatibilityEngine().compare(before, after)
    request_change = next(item for item in result["changes"] if item["category"] == "REQUEST_BODY")
    response_change = next(item for item in result["changes"] if item["category"] == "RESPONSE_SCHEMA")

    assert request_change["compatibility"] == "NON_BREAKING"
    assert response_change["compatibility"] == "POTENTIALLY_BREAKING"


def test_openapi_31_null_union_is_classified_as_nullability_not_type_change():
    before = spec({
        "/items": {"get": {"responses": {"200": {"description": "OK", "content": {
            "application/json": {"schema": {"type": "string"}}
        }}}}}
    })
    after = spec({
        "/items": {"get": {"responses": {"200": {"description": "OK", "content": {
            "application/json": {"schema": {"type": ["string", "null"]}}
        }}}}}
    })

    changes = CompatibilityEngine().compare(before, after)["changes"]

    assert [item["change_type"] for item in changes] == ["CHANGED_NULLABILITY"]
    assert changes[0]["compatibility"] == "BREAKING"


def test_trailing_slash_is_not_normalized_away_and_missing_references_are_bounded():
    before = spec({
        "/items": {"get": {"responses": {"200": {"description": "OK", "content": {
            "application/json": {"schema": {"$ref": "#/components/schemas/Missing"}}
        }}}}}
    })
    after = spec({
        "/items/": {"get": {"responses": {"200": {"description": "OK", "content": {
            "application/json": {"schema": {"$ref": "#/components/schemas/Missing"}}
        }}}}}
    })

    result = CompatibilityEngine().compare(before, after)
    same = CompatibilityEngine().compare(before, before)

    assert result["endpoint_summary"]["added"] == 1
    assert result["endpoint_summary"]["removed"] == 1
    assert same["changes"] == []
