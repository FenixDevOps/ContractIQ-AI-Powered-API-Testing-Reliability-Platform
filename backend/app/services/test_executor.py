"""Bounded synchronous HTTPX test execution and result persistence."""

__test__ = False

import json
import re
import time
from datetime import datetime, timezone
from urllib.parse import parse_qsl, quote, unquote, urlencode, urlsplit, urlunsplit

import httpx
from referencing.exceptions import Unresolvable
from jsonschema.exceptions import SchemaError

from app.config import TEST_MAX_CASES_PER_RUN, TEST_MAX_RESPONSE_BYTES
from app.database.models import ApiSpecification, TestCase, TestResult, TestRun
from app.services.response_validator import validate_response
from app.services.target_security import PinnedHTTPTransport, TargetValidationError, resolve_target_url

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
SENSITIVE = re.compile(r"(authorization|cookie|token|secret|password|api[-_]?key)", re.I)
FORBIDDEN_HEADERS = {"host", "content-length", "connection", "transfer-encoding", "proxy-authorization"}


class TestExecutionConfigurationError(ValueError):
    __test__ = False

    pass


def _redact(value):
    if isinstance(value, dict):
        return {key: ("[REDACTED]" if SENSITIVE.search(str(key)) else _redact(item)) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, str):
        value = re.sub(r"(?i)(bearer\s+)[A-Za-z0-9._~+/-]+=*", r"\1[REDACTED]", value)
        return re.sub(
            r"(?i)((?:password|token|secret|api[-_]?key|authorization)\s*[:=]\s*)[^,\s&]+",
            r"\1[REDACTED]",
            value,
        )
    return value


def _safe_url(url: str) -> str:
    parts = urlsplit(url)
    query = [(key, "[REDACTED]" if SENSITIVE.search(key) else value) for key, value in parse_qsl(parts.query, keep_blank_values=True)]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query, doseq=True), ""))


def _response_body(response: httpx.Response):
    data = bytearray()
    truncated = False
    for chunk in response.iter_bytes():
        remaining = TEST_MAX_RESPONSE_BYTES + 1 - len(data)
        if remaining <= 0:
            truncated = True
            break
        data.extend(chunk[:remaining])
        if len(data) > TEST_MAX_RESPONSE_BYTES:
            truncated = True
            break
    raw = bytes(data[:TEST_MAX_RESPONSE_BYTES])
    content_type = response.headers.get("content-type", "")
    if "json" in content_type.lower():
        try:
            body = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            body = raw.decode("utf-8", errors="replace")
    else:
        body = raw.decode("utf-8", errors="replace")
    return body, truncated, bool(raw)


def _request_values(case: TestCase) -> tuple[str, dict, dict, dict, object]:
    config = case.request_configuration or {}
    path_values = config.get("path_params", {})
    if not isinstance(path_values, dict):
        raise TestExecutionConfigurationError("Path parameter configuration must be an object.")
    path = case.endpoint_path
    missing = list(config.get("missing_inputs", []))
    for name in re.findall(r"{([^{}]+)}", path):
        if name not in path_values:
            missing.append(f"path parameter '{name}' needs a value")
        else:
            path = path.replace("{" + name + "}", quote(str(path_values[name]), safe=""))
    if missing or config.get("needs_body_configuration"):
        raise TestExecutionConfigurationError("; ".join(missing) or "Request body needs configuration.")
    if (
        "{" in path or "}" in path or not path.startswith("/") or path.startswith("//")
        or "\\" in path or "?" in path or "#" in path
        or any(part in {".", ".."} for part in unquote(path).split("/"))
    ):
        raise TestExecutionConfigurationError("Endpoint path contains an unresolved or invalid path parameter.")

    query = dict(config.get("query_params", {}))
    headers = dict(config.get("headers", {}))
    cookies = dict(config.get("cookie_params", {}))
    omitted = config.get("omit_parameter")
    if isinstance(omitted, dict):
        location, name = omitted.get("in"), omitted.get("name")
        values = {"path": path_values, "query": query, "header": headers, "cookie": cookies}.get(location)
        if isinstance(values, dict):
            values.pop(name, None)
    body = config.get("body")
    return path, query, headers, cookies, body


def _safe_headers(headers: dict) -> dict:
    if len(headers) > 30:
        raise TestExecutionConfigurationError("No more than 30 request headers may be configured.")
    result = {}
    for name, value in headers.items():
        key = str(name)
        if (
            key.lower() in FORBIDDEN_HEADERS
            or not re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+", key)
        ):
            raise TestExecutionConfigurationError(f"Header '{key}' is not allowed.")
        rendered = str(value)
        if re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", rendered) or len(rendered) > 8192:
            raise TestExecutionConfigurationError(f"Header '{key}' contains invalid characters or is too long.")
        result[key] = rendered
    return result


def _case_snapshot(case: TestCase) -> dict:
    return {
        "id": str(case.id),
        "name": case.name,
        "description": case.description,
        "category": case.category,
        "http_method": case.http_method,
        "endpoint_path": case.endpoint_path,
        "expected_status_codes": case.expected_status_codes or [],
    }


def _result(case: TestCase, *, status: str, message: str | None = None, expected=None) -> TestResult:
    return TestResult(
        test_case_id=case.id,
        test_case_snapshot=_case_snapshot(case),
        status=status,
        expected_status_codes=expected or case.expected_status_codes or [],
        request_details={},
        response_details={},
        validation_errors=[],
        error_message=message,
    )


def _run_case(client: httpx.Client, case: TestCase, base_url: str, extra_headers: dict, timeout: float, specification: ApiSpecification) -> TestResult:
    result = _result(case, status="ERROR")
    try:
        path, query, case_headers, cookies, body = _request_values(case)
        headers = _safe_headers({**extra_headers, **case_headers})
        content_type = (case.request_configuration or {}).get("content_type")
        if body is not None and content_type:
            headers.setdefault("Content-Type", str(content_type))
        if body is not None and len(json.dumps(body, separators=(",", ":")).encode("utf-8")) > TEST_MAX_RESPONSE_BYTES:
            raise TestExecutionConfigurationError("Request body exceeds the configured response-size limit.")

        url = f"{base_url.rstrip('/')}{path}"
        parsed_base = urlsplit(base_url)
        parsed_url = urlsplit(url)
        if parsed_url.scheme != parsed_base.scheme or parsed_url.netloc.lower() != parsed_base.netloc.lower():
            raise TestExecutionConfigurationError("Constructed request URL does not match the approved target origin.")

        safe_headers = {name: ("[REDACTED]" if SENSITIVE.search(name) else value) for name, value in headers.items()}
        safe_path = parsed_url.path
        for name, value in (case.request_configuration or {}).get("path_params", {}).items():
            if SENSITIVE.search(str(name)):
                encoded_value = quote(str(value), safe="")
                if encoded_value:
                    safe_path = safe_path.replace(encoded_value, "[REDACTED]")
        result.request_details = {
            "method": case.http_method,
            "url": _safe_url(urlunsplit((
                parsed_url.scheme,
                parsed_url.netloc,
                safe_path,
                urlencode(query, doseq=True),
                "",
            ))),
            "headers": safe_headers,
            "cookies": {name: "[REDACTED]" for name in cookies},
            "body": _redact(body),
        }
        started = time.perf_counter()
        request_body = {}
        if body is not None:
            if not content_type or "json" in content_type.lower():
                request_body["json"] = body
            elif isinstance(body, str):
                request_body["content"] = body
            elif "application/x-www-form-urlencoded" in content_type.lower() and isinstance(body, dict):
                request_body["data"] = body
            else:
                raise TestExecutionConfigurationError(
                    f"Generated request body encoding is not supported for '{content_type}'."
                )
        with client.stream(
            case.http_method,
            url,
            params=query,
            headers=headers,
            cookies=cookies,
            timeout=timeout,
            follow_redirects=False,
            **request_body,
        ) as response:
            body_value, truncated, body_present = _response_body(response)
            elapsed_ms = (time.perf_counter() - started) * 1000
            headers_value = {
                name: (
                    "[REDACTED]" if SENSITIVE.search(name)
                    else _safe_url(value) if name.lower() == "location"
                    else value
                )
                for name, value in response.headers.items()
            }
            result.actual_status_code = response.status_code
            result.response_time_ms = elapsed_ms
            result.response_details = {
                "headers": headers_value,
                "content_type": response.headers.get("content-type"),
                "body": _redact(body_value),
                "truncated": truncated,
                "redirect_blocked": 300 <= response.status_code < 400,
            }
            config = case.request_configuration or {}
            errors = validate_response(
                expected_status_codes=case.expected_status_codes or [],
                actual_status_code=response.status_code,
                expected_content_types=config.get("expected_content_types"),
                actual_content_type=response.headers.get("content-type"),
                schema=case.expected_response_schema,
                body=body_value,
                body_present=body_present,
                specification=specification.raw_specification or {},
            )
            if truncated:
                errors.append({"code": "RESPONSE_TRUNCATED", "message": "Response exceeded the configured size limit and was truncated."})
            for error in errors:
                if SENSITIVE.search(error.get("path", "")):
                    error["message"] = "A sensitive response field failed schema validation."
            result.validation_errors = errors
            result.status = "FAILED" if errors else "PASSED"
    except TestExecutionConfigurationError as exc:
        result.status = "SKIPPED"
        result.error_message = str(exc)
    except httpx.TimeoutException as exc:
        result.status = "ERROR"
        result.error_message = f"Request timed out ({type(exc).__name__})."
    except httpx.RequestError as exc:
        result.status = "ERROR"
        result.error_message = f"HTTP request failed ({type(exc).__name__})."
    except httpx.InvalidURL:
        result.status = "ERROR"
        result.error_message = "The generated request URL is invalid."
    except (Unresolvable, SchemaError) as exc:
        result.status = "ERROR"
        result.error_message = f"Response schema could not be validated ({type(exc).__name__})."
    except (ValueError, TypeError) as exc:
        result.status = "ERROR"
        result.error_message = str(exc)
    return result


def execute_test_run(
    db,
    *,
    specification: ApiSpecification,
    cases: list[TestCase],
    base_url: str,
    environment_name: str,
    timeout_seconds: float,
    include_negative_tests: bool,
    allow_write_operations: bool,
    confirm_destructive: bool,
    default_headers: dict,
) -> TestRun:
    if not cases:
        raise TestExecutionConfigurationError("No matching enabled test cases are available.")
    if len(cases) > TEST_MAX_CASES_PER_RUN:
        raise TestExecutionConfigurationError(
            f"A run cannot exceed the configured maximum of {TEST_MAX_CASES_PER_RUN} test cases."
        )
    try:
        target = resolve_target_url(base_url)
    except TargetValidationError as exc:
        raise TestExecutionConfigurationError(str(exc)) from exc

    mutating = [case for case in cases if case.http_method.upper() not in SAFE_METHODS]
    normalized_environment = environment_name.strip().lower()
    if (normalized_environment.startswith("prod") or normalized_environment in {"live", "production-live"}) and mutating:
        raise TestExecutionConfigurationError("Production safe mode allows only GET, HEAD, and OPTIONS requests.")
    if mutating and allow_write_operations and not confirm_destructive:
        raise TestExecutionConfigurationError("Write methods require explicit destructive-operation confirmation.")

    run = TestRun(
        specification_id=specification.id,
        environment_name=environment_name,
        base_url=target.url,
        status="RUNNING",
        total_tests=len(cases),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    started = time.perf_counter()
    try:
        with httpx.Client(
            transport=PinnedHTTPTransport(
                target,
                limits=httpx.Limits(max_connections=1, max_keepalive_connections=1),
            ),
            timeout=timeout_seconds,
            follow_redirects=False,
            trust_env=False,
        ) as client:
            results = []
            for case in cases:
                if case.category == "NEGATIVE_TEST" and not include_negative_tests:
                    item = _result(case, status="SKIPPED", message="Negative tests were not enabled.")
                elif case.http_method.upper() not in SAFE_METHODS and not allow_write_operations:
                    item = _result(case, status="SKIPPED", message="Write operation was not explicitly enabled.")
                else:
                    item = _run_case(client, case, target.url, default_headers, timeout_seconds, specification)
                item.test_run_id = run.id
                db.add(item)
                results.append(item)
            db.flush()
        run.passed_tests = sum(item.status == "PASSED" for item in results)
        run.failed_tests = sum(item.status == "FAILED" for item in results)
        run.skipped_tests = sum(item.status == "SKIPPED" for item in results)
        run.error_tests = sum(item.status == "ERROR" for item in results)
        run.status = "COMPLETED"
        run.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        run.duration_ms = (time.perf_counter() - started) * 1000
        db.commit()
        db.refresh(run)
        return run
    except Exception:
        db.rollback()
        run.status = "FAILED"
        run.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        run.duration_ms = (time.perf_counter() - started) * 1000
        db.add(run)
        db.commit()
        raise
