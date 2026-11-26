"""Deterministic, local-reference-aware OpenAPI compatibility comparison."""

from copy import deepcopy
import re
from uuid import uuid4

from app.services.openapi_parser import SUPPORTED_METHODS

MAX_SCHEMA_DEPTH = 40
SEVERITY_PENALTIES = {"CRITICAL": 30, "HIGH": 15, "MEDIUM": 7, "LOW": 2, "INFO": 0}
PLACEHOLDER = re.compile(r"\{[^{}]+\}")
def _normalized_path(path: str) -> str:
    return PLACEHOLDER.sub("{}", path)


def _path_parameter_position(path: str, name: str) -> int | None:
    names = PLACEHOLDER.findall(path)
    for position, placeholder in enumerate(names):
        if placeholder[1:-1] == name:
            return position
    return None


def _resolve(value, document: dict, active: frozenset[str] = frozenset(), depth: int = 0):
    if depth > MAX_SCHEMA_DEPTH:
        return {"x-contractiq-resolution": "depth-limit"}
    if isinstance(value, list):
        return [_resolve(item, document, active, depth + 1) for item in value]
    if not isinstance(value, dict):
        return deepcopy(value)
    if value.get("x-contractiq-resolution"):
        return deepcopy(value)
    reference = value.get("$ref")
    if reference is not None:
        if not isinstance(reference, str) or not reference.startswith("#/"):
            return {"$ref": reference, "x-contractiq-resolution": "unsupported"}
        if reference in active:
            return {"$ref": reference, "x-contractiq-resolution": "circular"}
        target = document
        try:
            for token in reference[2:].split("/"):
                token = token.replace("~1", "/").replace("~0", "~")
                target = target[token]
        except (KeyError, TypeError):
            return {"$ref": reference, "x-contractiq-resolution": "unresolved"}
        resolved = _resolve(target, document, active | {reference}, depth + 1)
        if not isinstance(resolved, dict):
            return {"$ref": reference, "allOf": [resolved]}
        result = dict(resolved)
        siblings = {key: item for key, item in value.items() if key != "$ref"}
        if siblings:
            result.update(_resolve(siblings, document, active | {reference}, depth + 1))
        return result
    return {
        key: _resolve(item, document, active, depth + 1)
        for key, item in value.items()
    }


def _effective_parameters(path_item: dict, operation: dict, document: dict) -> dict:
    parameters = {}
    for item in (path_item.get("parameters", []) or []) + (operation.get("parameters", []) or []):
        resolved = _resolve(item, document)
        if not isinstance(resolved, dict) or not resolved.get("name") or not resolved.get("in"):
            continue
        location = resolved["in"]
        name = resolved["name"]
        if location == "path":
            position = _path_parameter_position(path_item.get("x-contractiq-path", ""), name)
            if position is not None:
                name = f"#{position}"
        parameters[(location, name)] = resolved
    return parameters


def _operation_map(document: dict) -> dict:
    result = {}
    paths = document.get("paths", {})
    if not isinstance(paths, dict):
        return result
    for path, raw_path_item in paths.items():
        path_item = _resolve(raw_path_item, document)
        if not isinstance(path_item, dict):
            continue
        path_item["x-contractiq-path"] = path
        for method, raw_operation in path_item.items():
            if method.lower() not in SUPPORTED_METHODS:
                continue
            operation = _resolve(raw_operation, document)
            if not isinstance(operation, dict):
                continue
            key = (method.upper(), _normalized_path(path))
            result[key] = {
                "path": path,
                "path_item": path_item,
                "operation": operation,
            }
    return result


class CompatibilityEngine:
    def __init__(self):
        self.changes = []

    def _add(
        self,
        *,
        category: str,
        change_type: str,
        severity: str,
        compatibility: str,
        path: str | None,
        method: str | None,
        explanation: str,
        recommendation: str,
        old_value=None,
        new_value=None,
        property_name: str | None = None,
    ):
        self.changes.append({
            "id": str(uuid4()),
            "category": category,
            "change_type": change_type,
            "severity": severity,
            "compatibility": compatibility,
            "path": path,
            "method": method,
            "property_name": property_name,
            "old_value": old_value,
            "new_value": new_value,
            "explanation": explanation,
            "recommendation": recommendation,
        })

    def _schema(
        self,
        old_schema,
        new_schema,
        old_document: dict,
        new_document: dict,
        mode: str,
        category: str,
        endpoint_path: str,
        method: str,
        schema_path: str,
        depth: int = 0,
    ):
        if depth > MAX_SCHEMA_DEPTH:
            return
        old_schema = _resolve(old_schema or {}, old_document)
        new_schema = _resolve(new_schema or {}, new_document)
        if not isinstance(old_schema, dict) or not isinstance(new_schema, dict):
            return
        if old_schema.get("x-contractiq-resolution") or new_schema.get("x-contractiq-resolution"):
            if old_schema != new_schema:
                self._add(
                    category=category, change_type="REFERENCE_RESOLUTION_CHANGED",
                    severity="INFO", compatibility="INFORMATIONAL",
                    path=endpoint_path, method=method, property_name=schema_path or None,
                    old_value=old_schema.get("$ref"), new_value=new_schema.get("$ref"),
                    explanation="A local schema reference could not be fully resolved; the comparison is limited at this node.",
                    recommendation="Review the referenced component definitions and re-run the comparison.",
                )
            return

        old_type = _schema_type(old_schema)
        new_type = _schema_type(new_schema)
        if old_type != new_type and (old_type is not None or new_type is not None):
            compatibility = _type_change_compatibility(old_type, new_type, mode)
            self._add(
                category=category, change_type="CHANGED_TYPE",
                severity={
                    "BREAKING": "HIGH",
                    "POTENTIALLY_BREAKING": "MEDIUM",
                    "NON_BREAKING": "LOW",
                }[compatibility],
                compatibility=compatibility,
                path=endpoint_path, method=method, property_name=schema_path or None,
                old_value=old_type, new_value=new_type,
                explanation=f"The schema type changed from {old_type} to {new_type}, which can invalidate existing API consumers.",
                recommendation="Keep the existing type or introduce the new type through a versioned contract.",
            )
            return

        old_enum = old_schema.get("enum")
        new_enum = new_schema.get("enum")
        if isinstance(old_enum, list) or isinstance(new_enum, list):
            removed = (
                [item for item in old_enum if item not in new_enum]
                if isinstance(old_enum, list) and isinstance(new_enum, list)
                else (["enum restriction removed"] if isinstance(old_enum, list) else [])
            )
            added = (
                [item for item in new_enum if item not in old_enum]
                if isinstance(old_enum, list) and isinstance(new_enum, list)
                else (["enum restriction added"] if isinstance(new_enum, list) else [])
            )
            if removed or added:
                if isinstance(old_enum, list) and isinstance(new_enum, list):
                    compatibility = (
                        "BREAKING" if mode == "request" and removed else
                        "POTENTIALLY_BREAKING" if mode == "response" and added else
                        "NON_BREAKING"
                    )
                elif isinstance(old_enum, list):
                    compatibility = "POTENTIALLY_BREAKING" if mode == "response" else "NON_BREAKING"
                else:
                    compatibility = "BREAKING" if mode == "request" else "NON_BREAKING"
                self._add(
                    category=category,
                    change_type=("REMOVED_ENUM_VALUES" if removed else "ADDED_ENUM_VALUES"),
                    severity={
                        "BREAKING": "HIGH",
                        "POTENTIALLY_BREAKING": "MEDIUM",
                        "NON_BREAKING": "LOW",
                    }[compatibility],
                    compatibility=compatibility,
                    path=endpoint_path, method=method, property_name=schema_path or None,
                    old_value=old_enum, new_value=new_enum,
                    explanation=(
                        "The accepted request values were restricted; existing clients may send values no longer allowed."
                        if mode == "request" and removed else
                        "Responses may now contain enum values an existing client does not recognize."
                        if mode == "response" and added else
                        "The schema's enum restriction changed."
                    ),
                    recommendation=(
                        "Continue accepting the previous enum values during a compatibility window."
                        if compatibility == "BREAKING" else
                        "Ensure clients handle the updated response enum."
                        if compatibility == "POTENTIALLY_BREAKING" else
                        "No client action is normally required."
                    ),
                )

        old_nullable = _is_nullable(old_schema)
        new_nullable = _is_nullable(new_schema)
        if old_nullable != new_nullable:
            request_break = mode == "request" and old_nullable and not new_nullable
            response_break = mode == "response" and not old_nullable and new_nullable
            breaking = request_break or response_break
            self._add(
                category=category, change_type="CHANGED_NULLABILITY",
                severity="HIGH" if breaking else "LOW",
                compatibility="BREAKING" if breaking else "NON_BREAKING",
                path=endpoint_path, method=method, property_name=schema_path or None,
                old_value=old_nullable, new_value=new_nullable,
                explanation="The schema's nullable contract changed.",
                recommendation=("Keep accepting null values or update clients before deployment."
                                if breaking else "No compatibility action is normally required."),
            )

        for constraint in (
            "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum",
            "minLength", "maxLength", "minItems", "maxItems", "minProperties", "maxProperties",
            "pattern", "multipleOf",
        ):
            old_value = old_schema.get(constraint)
            new_value = new_schema.get(constraint)
            if old_value == new_value:
                continue
            tightened = _constraint_tightened(constraint, old_value, new_value)
            breaking = tightened if mode == "request" else not tightened
            self._add(
                category=category, change_type="CHANGED_CONSTRAINT",
                severity="MEDIUM" if breaking else "LOW",
                compatibility="POTENTIALLY_BREAKING" if breaking else "NON_BREAKING",
                path=endpoint_path, method=method, property_name=schema_path or None,
                old_value={constraint: old_value}, new_value={constraint: new_value},
                explanation=f"The {constraint} constraint changed and may affect accepted {mode} values.",
                recommendation="Review affected consumers and preserve the previous constraint where compatibility is required.",
            )

        if old_schema.get("format") != new_schema.get("format"):
            self._add(
                category=category, change_type="CHANGED_FORMAT",
                severity="MEDIUM", compatibility="POTENTIALLY_BREAKING",
                path=endpoint_path, method=method, property_name=schema_path or None,
                old_value=old_schema.get("format"), new_value=new_schema.get("format"),
                explanation="The schema format changed and consumers may validate or serialize values differently.",
                recommendation="Confirm that existing values and client validators support the new format.",
            )

        old_properties = old_schema.get("properties", {})
        new_properties = new_schema.get("properties", {})
        if isinstance(old_properties, dict) and isinstance(new_properties, dict):
            old_required = set(old_schema.get("required", []) or [])
            new_required = set(new_schema.get("required", []) or [])
            for name in sorted(old_properties.keys() - new_properties.keys()):
                self._add(
                    category=category, change_type="REMOVED_FIELD",
                    severity="HIGH", compatibility="BREAKING",
                    path=endpoint_path, method=method, property_name=_join_property(schema_path, name),
                    old_value={"schema": _schema_summary(old_properties[name]), "required": name in old_required},
                    new_value=None,
                    explanation=("A response field previously provided by the API was removed."
                                 if mode == "response" else "A request field previously accepted by the API was removed."),
                    recommendation="Retain the field until consumers have migrated, or introduce a new API version.",
                )
            for name in sorted(new_properties.keys() - old_properties.keys()):
                required = name in new_required
                if mode == "request" and required:
                    ctype, severity, compatibility = "NEWLY_REQUIRED_FIELD", "HIGH", "BREAKING"
                    explanation = "The request now requires a field that did not exist in the previous contract."
                    recommendation = "Make the field optional or migrate all callers before rollout."
                elif mode == "response" and required:
                    ctype, severity, compatibility = "NEWLY_REQUIRED_FIELD", "MEDIUM", "POTENTIALLY_BREAKING"
                    explanation = "A new required response field can affect strict client-side schema validators."
                    recommendation = "Confirm client validators tolerate newly added response properties."
                elif mode == "response" and old_schema.get("additionalProperties") is False:
                    ctype, severity, compatibility = "ADDED_FIELD", "MEDIUM", "POTENTIALLY_BREAKING"
                    explanation = "A response field was added to an object declared closed by the previous schema."
                    recommendation = "Confirm consumers allow this additional response property."
                else:
                    ctype, severity, compatibility = "ADDED_FIELD", "LOW", "NON_BREAKING"
                    explanation = "An optional field was added to the schema."
                    recommendation = "No client action is normally required."
                self._add(
                    category=category, change_type=ctype, severity=severity, compatibility=compatibility,
                    path=endpoint_path, method=method, property_name=_join_property(schema_path, name),
                    old_value=None, new_value={"schema": _schema_summary(new_properties[name]), "required": required},
                    explanation=explanation, recommendation=recommendation,
                )
            for name in sorted(old_properties.keys() & new_properties.keys()):
                old_is_required = name in old_required
                new_is_required = name in new_required
                if old_is_required != new_is_required:
                    request_break = mode == "request" and not old_is_required and new_is_required
                    response_risk = mode == "response" and old_is_required and not new_is_required
                    self._add(
                        category=category,
                        change_type="NEWLY_REQUIRED_FIELD" if new_is_required else "NO_LONGER_REQUIRED_FIELD",
                        severity="HIGH" if request_break else ("MEDIUM" if response_risk else "LOW"),
                        compatibility=("BREAKING" if request_break else
                                       "POTENTIALLY_BREAKING" if response_risk else "NON_BREAKING"),
                        path=endpoint_path, method=method, property_name=_join_property(schema_path, name),
                        old_value="required" if old_is_required else "optional",
                        new_value="required" if new_is_required else "optional",
                        explanation=("The request field is now required; existing callers may omit it."
                                     if request_break else
                                     "The response may omit a field that was previously guaranteed."
                                     if response_risk else "The field's required status changed without reducing request compatibility."),
                        recommendation=("Make the field optional or update callers before rollout."
                                        if request_break else "Preserve the field in responses or make client handling resilient."),
                    )
                self._schema(
                    old_properties[name], new_properties[name], old_document, new_document, mode,
                    category, endpoint_path, method, _join_property(schema_path, name), depth + 1,
                )

        old_items, new_items = old_schema.get("items"), new_schema.get("items")
        if old_items is not None or new_items is not None:
            if old_items is not None and new_items is not None:
                self._schema(old_items, new_items, old_document, new_document, mode, category,
                             endpoint_path, method, _join_property(schema_path, "[]"), depth + 1)
            elif old_items != new_items:
                self._add(
                    category=category, change_type="CHANGED_ARRAY_ITEMS",
                    severity="HIGH", compatibility="BREAKING",
                    path=endpoint_path, method=method, property_name=schema_path or None,
                    old_value=_schema_summary(old_items), new_value=_schema_summary(new_items),
                    explanation="The array item schema was added or removed.",
                    recommendation="Preserve the existing item contract or publish a versioned API.",
                )

        for composition in ("allOf", "oneOf", "anyOf"):
            old_variants = old_schema.get(composition, [])
            new_variants = new_schema.get(composition, [])
            if old_variants != new_variants:
                self._add(
                    category=category, change_type=f"CHANGED_{composition.upper()}",
                    severity="MEDIUM", compatibility="POTENTIALLY_BREAKING",
                    path=endpoint_path, method=method, property_name=schema_path or None,
                    old_value=_schema_summary(old_variants), new_value=_schema_summary(new_variants),
                    explanation=f"The schema's {composition} alternatives changed.",
                    recommendation="Review each composed schema branch for client and server compatibility.",
                )

        if old_schema.get("additionalProperties") != new_schema.get("additionalProperties"):
            old_value, new_value = old_schema.get("additionalProperties"), new_schema.get("additionalProperties")
            tightened = old_value is not False and new_value is False
            breaking = tightened and mode == "request"
            self._add(
                category=category, change_type="CHANGED_ADDITIONAL_PROPERTIES",
                severity="HIGH" if breaking else "MEDIUM",
                compatibility="BREAKING" if breaking else "POTENTIALLY_BREAKING",
                path=endpoint_path, method=method, property_name=schema_path or None,
                old_value=_schema_summary(old_value), new_value=_schema_summary(new_value),
                explanation="The object schema changed whether undeclared properties are permitted.",
                recommendation="Preserve the old additional-properties behavior or verify consumers tolerate the restriction.",
            )

    def _content(self, old_content, new_content, old_doc, new_doc, mode, category, path, method, owner):
        old_content = old_content if isinstance(old_content, dict) else {}
        new_content = new_content if isinstance(new_content, dict) else {}
        for media_type in sorted(old_content.keys() - new_content.keys()):
            self._add(
                category="CONTENT_TYPE", change_type="REMOVED_CONTENT_TYPE",
                severity="HIGH" if mode == "request" else "MEDIUM",
                compatibility="BREAKING" if mode == "request" else "POTENTIALLY_BREAKING",
                path=path, method=method, property_name=owner,
                old_value=media_type, new_value=None,
                explanation=f"The {mode} content type {media_type} is no longer declared.",
                recommendation="Continue supporting the previous media type or migrate consumers before removal.",
            )
        for media_type in sorted(new_content.keys() - old_content.keys()):
            self._add(
                category="CONTENT_TYPE", change_type="ADDED_CONTENT_TYPE",
                severity="LOW", compatibility="NON_BREAKING",
                path=path, method=method, property_name=owner,
                old_value=None, new_value=media_type,
                explanation=f"The {mode} now supports the additional content type {media_type}.",
                recommendation="No client action is normally required.",
            )
        for media_type in sorted(old_content.keys() & new_content.keys()):
            old_media = _resolve(old_content[media_type], old_doc)
            new_media = _resolve(new_content[media_type], new_doc)
            self._schema(
                old_media.get("schema", {}) if isinstance(old_media, dict) else {},
                new_media.get("schema", {}) if isinstance(new_media, dict) else {},
                old_doc, new_doc, mode, category, path, method, owner,
            )

    def _parameters(self, old_item, new_item, old_doc, new_doc, old_path, new_path, method):
        old_params = _effective_parameters(old_item["path_item"], old_item["operation"], old_doc)
        new_params = _effective_parameters(new_item["path_item"], new_item["operation"], new_doc)
        for key in sorted(old_params.keys() - new_params.keys()):
            parameter = old_params[key]
            self._add(
                category="PARAMETER", change_type="REMOVED_PARAMETER",
                severity="LOW", compatibility="NON_BREAKING",
                path=new_path, method=method, property_name=parameter.get("name"),
                old_value={"in": parameter.get("in"), "required": parameter.get("required", False)},
                new_value=None,
                explanation="A previously accepted parameter is no longer declared.",
                recommendation="Check whether callers rely on the parameter's behavior before removing it.",
            )
        for key in sorted(new_params.keys() - old_params.keys()):
            parameter = new_params[key]
            required = bool(parameter.get("required"))
            self._add(
                category="PARAMETER", change_type="NEWLY_REQUIRED_PARAMETER" if required else "ADDED_PARAMETER",
                severity="HIGH" if required else "LOW",
                compatibility="BREAKING" if required else "NON_BREAKING",
                path=new_path, method=method, property_name=parameter.get("name"),
                old_value=None,
                new_value={"in": parameter.get("in"), "required": required},
                explanation=("A new required parameter must be sent by every caller."
                             if required else "An optional parameter was added."),
                recommendation=("Make the parameter optional or update callers before deployment."
                                if required else "No client action is normally required."),
            )
        for key in sorted(old_params.keys() & new_params.keys()):
            old_param, new_param = old_params[key], new_params[key]
            name = new_param.get("name")
            old_required, new_required = bool(old_param.get("required")), bool(new_param.get("required"))
            if old_required != new_required:
                breaking = not old_required and new_required
                self._add(
                    category="PARAMETER",
                    change_type="NEWLY_REQUIRED_PARAMETER" if breaking else "NO_LONGER_REQUIRED_PARAMETER",
                    severity="HIGH" if breaking else "LOW",
                    compatibility="BREAKING" if breaking else "NON_BREAKING",
                    path=new_path, method=method, property_name=name,
                    old_value="required" if old_required else "optional",
                    new_value="required" if new_required else "optional",
                    explanation=("The parameter is now required; existing callers may omit it."
                                 if breaking else "The parameter is no longer required."),
                    recommendation=("Make the parameter optional or update callers before deployment."
                                    if breaking else "No client action is normally required."),
                )
            self._schema(
                old_param.get("schema", {}), new_param.get("schema", {}), old_doc, new_doc,
                "request", "PARAMETER", new_path, method, name,
            )
        if old_path != new_path:
            self._add(
                category="ENDPOINT", change_type="PATH_PARAMETER_RENAMED",
                severity="INFO", compatibility="INFORMATIONAL",
                path=new_path, method=method, property_name=None,
                old_value=old_path, new_value=new_path,
                explanation="The path parameter name changed, but the normalized route and HTTP method still match.",
                recommendation="Update generated client variable names if your tooling exposes them.",
            )

    def _operation(self, old_item, new_item, old_doc, new_doc, path, method):
        old_op, new_op = old_item["operation"], new_item["operation"]
        self._parameters(old_item, new_item, old_doc, new_doc, old_item["path"], new_item["path"], method)
        if old_op.get("operationId") != new_op.get("operationId"):
            self._add(
                category="ENDPOINT", change_type="CHANGED_OPERATION_ID",
                severity="LOW", compatibility="NON_BREAKING",
                path=path, method=method, property_name="operationId",
                old_value=old_op.get("operationId"), new_value=new_op.get("operationId"),
                explanation="The operation identifier changed; generated SDK method names may change.",
                recommendation="Regenerate clients or preserve the previous operationId when stable SDK names matter.",
            )
        if old_op.get("deprecated") != new_op.get("deprecated") and new_op.get("deprecated"):
            self._add(
                category="ENDPOINT", change_type="ENDPOINT_DEPRECATED",
                severity="MEDIUM", compatibility="POTENTIALLY_BREAKING",
                path=path, method=method, property_name=None,
                old_value=False, new_value=True,
                explanation="The operation is now marked deprecated.",
                recommendation="Plan migration to a supported operation before removal.",
            )
        old_body = _resolve(old_op.get("requestBody", {}), old_doc)
        new_body = _resolve(new_op.get("requestBody", {}), new_doc)
        if bool(old_body) != bool(new_body):
            exists_now = bool(new_body)
            self._add(
                category="REQUEST_BODY", change_type="REQUEST_BODY_ADDED" if exists_now else "REQUEST_BODY_REMOVED",
                severity="MEDIUM", compatibility="POTENTIALLY_BREAKING",
                path=path, method=method, property_name=None,
                old_value=bool(old_body), new_value=bool(new_body),
                explanation="The operation's request body presence changed.",
                recommendation="Keep the prior request-body behavior or verify all consumers are updated.",
            )
        elif old_body and new_body:
            old_required = bool(old_body.get("required"))
            new_required = bool(new_body.get("required"))
            if old_required != new_required:
                breaking = not old_required and new_required
                self._add(
                    category="REQUEST_BODY",
                    change_type="REQUEST_BODY_NEWLY_REQUIRED" if breaking else "REQUEST_BODY_NO_LONGER_REQUIRED",
                    severity="HIGH" if breaking else "LOW",
                    compatibility="BREAKING" if breaking else "NON_BREAKING",
                    path=path, method=method, property_name=None,
                    old_value=old_required, new_value=new_required,
                    explanation=("The request body is now required." if breaking
                                 else "The request body is no longer required."),
                    recommendation=("Make the body optional or update callers before deployment."
                                    if breaking else "No client action is normally required."),
                )
            self._content(old_body.get("content"), new_body.get("content"), old_doc, new_doc,
                          "request", "REQUEST_BODY", path, method, "requestBody")

        old_responses = _resolve(old_op.get("responses", {}), old_doc)
        new_responses = _resolve(new_op.get("responses", {}), new_doc)
        old_responses = old_responses if isinstance(old_responses, dict) else {}
        new_responses = new_responses if isinstance(new_responses, dict) else {}
        for code in sorted(old_responses.keys() - new_responses.keys()):
            self._add(
                category="RESPONSE", change_type="REMOVED_RESPONSE_STATUS",
                severity="HIGH", compatibility="BREAKING",
                path=path, method=method, property_name=str(code),
                old_value=str(code), new_value=None,
                explanation=f"Response status {code} was removed from the contract.",
                recommendation="Continue documenting and supporting this status or migrate clients to an alternative.",
            )
        for code in sorted(new_responses.keys() - old_responses.keys()):
            self._add(
                category="RESPONSE", change_type="ADDED_RESPONSE_STATUS",
                severity="LOW", compatibility="NON_BREAKING",
                path=path, method=method, property_name=str(code),
                old_value=None, new_value=str(code),
                explanation=f"Response status {code} was added.",
                recommendation="Ensure clients handle the additional documented status.",
            )
        for code in sorted(old_responses.keys() & new_responses.keys()):
            old_response = _resolve(old_responses[code], old_doc)
            new_response = _resolve(new_responses[code], new_doc)
            if not isinstance(old_response, dict) or not isinstance(new_response, dict):
                continue
            self._content(old_response.get("content"), new_response.get("content"),
                          old_doc, new_doc, "response", "RESPONSE_SCHEMA", path, method, str(code))
            old_headers = old_response.get("headers", {})
            new_headers = new_response.get("headers", {})
            for header in sorted((old_headers or {}).keys() - (new_headers or {}).keys()):
                self._add(
                    category="RESPONSE", change_type="REMOVED_RESPONSE_HEADER",
                    severity="MEDIUM", compatibility="POTENTIALLY_BREAKING",
                    path=path, method=method, property_name=header,
                    old_value=header, new_value=None,
                    explanation=f"Response header {header} was removed.",
                    recommendation="Continue returning the header if clients may depend on it.",
                )
        old_security = old_op.get("security", old_doc.get("security", [])) or []
        new_security = new_op.get("security", new_doc.get("security", [])) or []
        if old_security != new_security:
            strengthened = bool(new_security) and not bool(old_security)
            self._add(
                category="SECURITY", change_type="SECURITY_REQUIREMENTS_CHANGED",
                severity="HIGH" if strengthened else "MEDIUM",
                compatibility="BREAKING" if strengthened else "POTENTIALLY_BREAKING",
                path=path, method=method, property_name=None,
                old_value=old_security, new_value=new_security,
                explanation="The operation's declared security requirements changed.",
                recommendation="Review authentication and authorization requirements with all API consumers.",
            )

    def compare(self, old_document: dict, new_document: dict) -> dict:
        self.changes = []
        old_ops, new_ops = _operation_map(old_document), _operation_map(new_document)
        old_keys, new_keys = set(old_ops), set(new_ops)
        added = sorted(new_keys - old_keys)
        removed = sorted(old_keys - new_keys)
        common = sorted(old_keys & new_keys)
        modified_count = 0

        for method, normalized in added:
            path = new_ops[(method, normalized)]["path"]
            self._add(
                category="ENDPOINT", change_type="ADDED_ENDPOINT",
                severity="LOW", compatibility="NON_BREAKING",
                path=path, method=method, property_name=None,
                old_value=None, new_value=f"{method} {path}",
                explanation="A new endpoint was added to the API.",
                recommendation="No existing client action is normally required.",
            )
        for method, normalized in removed:
            path = old_ops[(method, normalized)]["path"]
            self._add(
                category="ENDPOINT", change_type="REMOVED_ENDPOINT",
                severity="CRITICAL", compatibility="BREAKING",
                path=path, method=method, property_name=None,
                old_value=f"{method} {path}", new_value=None,
                explanation="An endpoint used by existing clients was removed.",
                recommendation="Restore the endpoint or publish a migration path and versioned replacement.",
            )
        for method, normalized in common:
            change_count = len(self.changes)
            self._operation(old_ops[(method, normalized)], new_ops[(method, normalized)],
                            old_document, new_document, new_ops[(method, normalized)]["path"], method)
            if len(self.changes) > change_count:
                modified_count += 1

        score = max(0, 100 - sum(SEVERITY_PENALTIES[item["severity"]] for item in self.changes))
        counts = {
            "breaking": sum(item["compatibility"] == "BREAKING" for item in self.changes),
            "non_breaking": sum(item["compatibility"] == "NON_BREAKING" for item in self.changes),
            "potentially_breaking": sum(item["compatibility"] == "POTENTIALLY_BREAKING" for item in self.changes),
            "informational": sum(item["compatibility"] == "INFORMATIONAL" for item in self.changes),
        }
        overall_status = (
            "BREAKING" if counts["breaking"] else
            "POTENTIALLY_BREAKING" if counts["potentially_breaking"] else "COMPATIBLE"
        )
        return {
            "changes": self.changes,
            "compatibility_score": score,
            "overall_status": overall_status,
            "counts": counts,
            "endpoint_summary": {
                "total_compared": len(old_keys | new_keys),
                "added": len(added),
                "removed": len(removed),
                "modified": modified_count,
                "unchanged": len(common) - modified_count,
            },
        }


def _schema_type(schema: dict):
    value = schema.get("type")
    if isinstance(value, list):
        types = tuple(sorted(item for item in value if item != "null"))
        return types[0] if len(types) == 1 else types or None
    return value


def _type_change_compatibility(old_type, new_type, mode: str) -> str:
    if old_type == "integer" and new_type == "number":
        return "POTENTIALLY_BREAKING" if mode == "response" else "NON_BREAKING"
    if old_type == "number" and new_type == "integer":
        return "BREAKING" if mode == "request" else "NON_BREAKING"
    if old_type is None:
        return "BREAKING" if mode == "request" else "NON_BREAKING"
    if new_type is None:
        return "NON_BREAKING" if mode == "request" else "POTENTIALLY_BREAKING"
    return "BREAKING"


def _is_nullable(schema: dict) -> bool:
    type_value = schema.get("type")
    return bool(schema.get("nullable")) or (isinstance(type_value, list) and "null" in type_value)


def _constraint_tightened(name, old, new) -> bool:
    if new is None:
        return False
    if old is None:
        return name in {"minimum", "minLength", "minItems", "minProperties", "exclusiveMinimum"}
    if name in {"minimum", "minLength", "minItems", "minProperties", "exclusiveMinimum"}:
        return new > old
    if name in {"maximum", "maxLength", "maxItems", "maxProperties", "exclusiveMaximum"}:
        return new < old
    return old != new


def _join_property(parent: str, child: str) -> str:
    return f"{parent}.{child}" if parent else child


def _schema_summary(value, depth: int = 0):
    if depth > MAX_SCHEMA_DEPTH:
        return {"truncated": True}
    if isinstance(value, list):
        return [_schema_summary(item, depth + 1) for item in value]
    if not isinstance(value, dict):
        return deepcopy(value)
    keys = {
        "$ref", "type", "format", "nullable", "enum", "const", "required",
        "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum",
        "minLength", "maxLength", "minItems", "maxItems", "minProperties",
        "maxProperties", "pattern", "multipleOf", "readOnly", "writeOnly",
        "deprecated", "uniqueItems",
    }
    result = {key: deepcopy(item) for key, item in value.items() if key in keys}
    for key in ("properties", "items", "additionalProperties", "allOf", "oneOf", "anyOf"):
        if key in value:
            result[key] = _schema_summary(value[key], depth + 1)
    return result
