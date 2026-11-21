from datetime import datetime
import re
from uuid import UUID

from pydantic import BaseModel, Field, field_serializer

_SENSITIVE_FIELD = re.compile(r"(authorization|cookie|token|secret|password|api[-_]?key)", re.I)


def _redact_configuration(value):
    if isinstance(value, dict):
        return {
            key: (
                {name: "[REDACTED]" for name in item}
                if str(key).lower() == "cookie_params" and isinstance(item, dict)
                else "[REDACTED]" if _SENSITIVE_FIELD.search(str(key))
                else _redact_configuration(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_configuration(item) for item in value]
        if isinstance(value, str):
            value = re.sub(r"(?i)(bearer\s+)[A-Za-z0-9._~+/-]+=*", r"\1[REDACTED]", value)
            return re.sub(
                r"(?i)((?:password|token|secret|api[-_]?key|authorization)\s*[:=]\s*)[^,\s&]+",
                r"\1[REDACTED]",
                value,
            )
    return value


class TestCaseOut(BaseModel):
    id: UUID
    specification_id: UUID
    endpoint_id: UUID
    name: str
    description: str
    category: str
    priority: str
    http_method: str
    endpoint_path: str
    request_configuration: dict
    expected_status_codes: list[int]
    expected_response_schema: dict | None
    is_enabled: bool
    is_generated: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer("request_configuration")
    def serialize_request_configuration(self, value: dict) -> dict:
        return _redact_configuration(value)


class TestCasePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    priority: str | None = Field(default=None, pattern="^(LOW|MEDIUM|HIGH|CRITICAL)$")
    request_configuration: dict | None = None
    is_enabled: bool | None = None


class TestRunRequest(BaseModel):
    base_url: str = Field(min_length=8, max_length=2048)
    environment_name: str = Field(default="testing", min_length=1, max_length=100)
    timeout_seconds: float = Field(default=10, ge=1, le=30)
    include_negative_tests: bool = False
    allow_write_operations: bool = False
    confirm_destructive: bool = False
    default_headers: dict[str, str] = Field(default_factory=dict, max_length=30)


class SelectedTestRunRequest(TestRunRequest):
    test_case_ids: list[UUID] = Field(min_length=1, max_length=100)


class TestRunOut(BaseModel):
    id: UUID
    specification_id: UUID
    environment_name: str
    base_url: str
    status: str
    total_tests: int
    passed_tests: int
    failed_tests: int
    skipped_tests: int
    error_tests: int
    started_at: datetime
    completed_at: datetime | None
    duration_ms: float | None

    model_config = {"from_attributes": True}


class TestResultOut(BaseModel):
    id: UUID
    test_run_id: UUID
    test_case_id: UUID | None
    test_case_snapshot: dict
    status: str
    actual_status_code: int | None
    expected_status_codes: list[int]
    response_time_ms: float | None
    request_details: dict
    response_details: dict
    validation_errors: list
    error_message: str | None
    executed_at: datetime

    model_config = {"from_attributes": True}
