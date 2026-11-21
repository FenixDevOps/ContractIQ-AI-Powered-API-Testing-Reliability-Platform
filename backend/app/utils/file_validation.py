"""Safe upload format detection."""

import json
from pathlib import PurePath

import yaml


class UploadValidationError(ValueError):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


class OpenApiYamlLoader(yaml.SafeLoader):
    pass


def _construct_timestamp(loader, node):
    return loader.construct_scalar(node)


OpenApiYamlLoader.add_constructor("tag:yaml.org,2002:timestamp", _construct_timestamp)


def _validate_json_compatibility(parsed: object) -> None:
    try:
        json.dumps(parsed, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise UploadValidationError("The specification contains values that cannot be represented as JSON.", 400) from exc


def detect_format(filename: str, content: bytes) -> tuple[str, object]:
    extension = PurePath(filename).suffix.lower()
    if extension not in {".json", ".yaml", ".yml"}:
        raise UploadValidationError("Unsupported file extension; use .json, .yaml, or .yml.", 415)
    if not content:
        raise UploadValidationError("The uploaded file is empty.", 400)
    text = content.decode("utf-8-sig")
    if extension == ".json":
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise UploadValidationError(f"Malformed JSON: {exc.msg}.", 400) from exc
        _validate_json_compatibility(parsed)
        return "JSON", parsed
    try:
        parsed = yaml.load(text, Loader=OpenApiYamlLoader)
    except yaml.YAMLError as exc:
        raise UploadValidationError(f"Invalid YAML: {exc}.", 400) from exc
    _validate_json_compatibility(parsed)
    return "YAML", parsed
