"""Basic structural comparison for imported specification versions."""


def endpoint_key(endpoint) -> str:
    return f"{endpoint.method.upper()} {endpoint.path}"


def compare_specifications(before, after) -> dict:
    before_map = {endpoint_key(item): item for item in before}
    after_map = {endpoint_key(item): item for item in after}
    changes = []

    for key in sorted(after_map.keys() - before_map.keys()):
        endpoint = after_map[key]
        changes.append({
            "classification": "ADDED",
            "kind": "endpoint",
            "key": key,
            "after": {"summary": endpoint.summary, "responses": endpoint.responses},
        })
    for key in sorted(before_map.keys() - after_map.keys()):
        endpoint = before_map[key]
        changes.append({
            "classification": "REMOVED",
            "kind": "endpoint",
            "key": key,
            "before": {"summary": endpoint.summary, "responses": endpoint.responses},
            "potentially_breaking": True,
        })

    for key in sorted(before_map.keys() & after_map.keys()):
        old = before_map[key]
        new = after_map[key]
        modifications = []
        old_params = {f"{item.get('in')}:{item.get('name')}": item for item in (old.parameters or []) if isinstance(item, dict)}
        new_params = {f"{item.get('in')}:{item.get('name')}": item for item in (new.parameters or []) if isinstance(item, dict)}

        for parameter_key in sorted(new_params.keys() - old_params.keys()):
            parameter = new_params[parameter_key]
            modifications.append({
                "kind": "added_parameter",
                "classification": "POTENTIALLY_BREAKING" if parameter.get("required") else "ADDED",
                "name": parameter.get("name"),
                "after": parameter,
            })
        for parameter_key in sorted(old_params.keys() - new_params.keys()):
            modifications.append({
                "kind": "removed_parameter",
                "classification": "REMOVED",
                "name": old_params[parameter_key].get("name"),
                "before": old_params[parameter_key],
            })
        for parameter_key in sorted(old_params.keys() & new_params.keys()):
            old_parameter = old_params[parameter_key]
            new_parameter = new_params[parameter_key]
            if old_parameter.get("schema") != new_parameter.get("schema"):
                modifications.append({
                    "kind": "changed_parameter_type",
                    "classification": "POTENTIALLY_BREAKING",
                    "name": new_parameter.get("name"),
                    "before": old_parameter,
                    "after": new_parameter,
                })
            elif not old_parameter.get("required") and new_parameter.get("required"):
                modifications.append({
                    "kind": "newly_required_parameter",
                    "classification": "POTENTIALLY_BREAKING",
                    "name": new_parameter.get("name"),
                    "before": old_parameter,
                    "after": new_parameter,
                })

        old_codes = set((old.responses or {}).keys())
        new_codes = set((new.responses or {}).keys())
        for code in sorted(old_codes - new_codes):
            modifications.append({"kind": "removed_response_code", "classification": "POTENTIALLY_BREAKING", "code": code})
        if (old.request_body or {}) != (new.request_body or {}):
            modifications.append({
                "kind": "changed_request_body",
                "classification": "MODIFIED",
                "before": old.request_body,
                "after": new.request_body,
            })
        if (old.responses or {}) != (new.responses or {}):
            modified_response = {
                "kind": "changed_response_schema",
                "classification": "MODIFIED",
                "before": old.responses,
                "after": new.responses,
            }
            modifications.append(modified_response)

        if modifications:
            changes.append({
                "classification": "MODIFIED",
                "kind": "endpoint",
                "key": key,
                "modifications": modifications,
                "potentially_breaking": any(
                    item["classification"] == "POTENTIALLY_BREAKING" for item in modifications
                ),
            })

    return {
        "classification": "comparison",
        "limitations": [
            "This is a structural comparison, not a complete compatibility or runtime analysis.",
            "External reference resolution is not supported.",
        ],
        "change_count": len(changes),
        "changes": changes,
    }
