import json
import logging
import re
import threading
import time
from datetime import timedelta
from urllib.parse import quote, unquote, urlsplit
from uuid import UUID, uuid4

import httpx
from jsonschema.exceptions import SchemaError
from referencing.exceptions import Unresolvable
from sqlalchemy import or_
from sqlalchemy.exc import SQLAlchemyError

from app.config import (
    MONITORING_LEASE_SECONDS,
    MONITORING_MAX_RESPONSE_BYTES,
    MONITORING_SCHEDULER_POLL_SECONDS,
)
from app.database.connection import SessionLocal
from app.database.models import ApiEndpoint, ApiSpecification, MonitoringCheck, MonitoringConfiguration
from app.services.anomaly_detection import detect_for_check
from app.services.monitoring_alerts import create_failure_alert
from app.services.monitoring_time import utc_now
from app.services.response_validator import validate_response
from app.services.target_security import (
    PinnedHTTPTransport,
    TargetValidationError,
    resolve_target_url,
)
from app.services.test_executor import SAFE_METHODS, SENSITIVE
from app.services.test_generator import _request_values

logger = logging.getLogger(__name__)
PATH_PARAMETER = re.compile(r"{([^{}]+)}")
MAX_SCHEDULER_JOBS = 8


def _request_parts(endpoint: ApiEndpoint) -> tuple[str, dict]:
    method = endpoint.method.upper()
    if method not in SAFE_METHODS:
        raise ValueError(f"{method} is not permitted for scheduled monitoring.")
    if endpoint.security:
        raise ValueError("Scheduled monitoring supports only public endpoints without authentication requirements.")

    values, missing = _request_values(endpoint)
    if missing:
        raise ValueError("Required endpoint parameters do not have safe examples or defaults.")
    path_values = values.get("path_params", {})
    query_values = values.get("query_params", {})
    for parameter in endpoint.parameters or []:
        if not isinstance(parameter, dict) or not parameter.get("required"):
            continue
        location = parameter.get("in")
        name = str(parameter.get("name", ""))
        if location in {"header", "cookie"}:
            raise ValueError("Scheduled monitoring does not store or send required header or cookie credentials.")
        if location == "path" and SENSITIVE.search(name):
            raise ValueError("Sensitive path parameters are not supported for scheduled monitoring.")
        if location == "query" and SENSITIVE.search(name):
            raise ValueError("Sensitive query parameters are not supported for scheduled monitoring.")
    query = {
        str(key): value for key, value in query_values.items()
        if not SENSITIVE.search(str(key))
    }

    path = endpoint.path
    for name in PATH_PARAMETER.findall(path):
        if name not in path_values:
            raise ValueError("A required path parameter does not have a safe example or default.")
        path = path.replace("{" + name + "}", quote(str(path_values[name]), safe=""))
    if (
        "{" in path or "}" in path or not path.startswith("/") or path.startswith("//")
        or "\\" in path or "?" in path or "#" in path
        or any(part in {".", ".."} for part in unquote(path).split("/"))
    ):
        raise ValueError("Endpoint path contains an unresolved or invalid path parameter.")
    if len(path.encode("utf-8")) > 4096:
        raise ValueError("Rendered endpoint path exceeds the monitoring request limit.")
    query_size = sum(
        len(str(key).encode("utf-8")) + len(str(value).encode("utf-8"))
        for key, value in query.items()
    )
    if query_size > 8192:
        raise ValueError("Endpoint query examples exceed the monitoring request limit.")
    return path, query


def validate_monitorable_endpoints(
    specification: ApiSpecification,
    endpoints: list[ApiEndpoint],
) -> list[tuple[ApiEndpoint, str, dict]]:
    if specification.raw_specification.get("security"):
        raise ValueError("The API specification declares global authentication; authenticated monitoring is not enabled.")
    prepared = []
    for endpoint in endpoints:
        path, query = _request_parts(endpoint)
        prepared.append((endpoint, path, query))
    return prepared


def _read_bounded_response(response: httpx.Response) -> tuple[object, bool, bool]:
    data = bytearray()
    truncated = False
    for chunk in response.iter_bytes():
        remaining = MONITORING_MAX_RESPONSE_BYTES + 1 - len(data)
        if remaining <= 0:
            truncated = True
            break
        data.extend(chunk[:remaining])
        if len(data) > MONITORING_MAX_RESPONSE_BYTES:
            truncated = True
            break
    raw = bytes(data[:MONITORING_MAX_RESPONSE_BYTES])
    content_type = response.headers.get("content-type", "").lower()
    if "json" in content_type:
        try:
            return json.loads(raw.decode("utf-8")), truncated, bool(raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return raw.decode("utf-8", errors="replace"), truncated, bool(raw)
    return raw.decode("utf-8", errors="replace"), truncated, bool(raw)


def _expected_response(endpoint: ApiEndpoint, status_code: int, content_type: str | None):
    documented = endpoint.responses or {}
    success_statuses = sorted(
        int(code) for code in documented
        if str(code).isdigit() and 200 <= int(code) < 300
    )
    response = documented.get(str(status_code), documented.get("default", {}))
    content = response.get("content", {}) if isinstance(response, dict) else {}
    expected_types = list(content) if content else None
    selected_schema = None
    if content:
        normalized_type = (content_type or "").split(";", 1)[0].strip().lower()
        selected_media = next(
            (media for media_type, media in content.items()
             if media_type.split(";", 1)[0].strip().lower() == normalized_type),
            None,
        )
        if selected_media is None and content:
            selected_media = next(iter(content.values()))
        if isinstance(selected_media, dict) and isinstance(selected_media.get("schema"), dict):
            selected_schema = selected_media["schema"]
    return success_statuses, expected_types, selected_schema


def _check_endpoint(
    *,
    config: MonitoringConfiguration,
    specification: ApiSpecification,
    endpoint: ApiEndpoint,
    path: str,
    query: dict,
    target,
    client: httpx.Client | None,
) -> MonitoringCheck:
    now = utc_now()
    if client is None:
        return MonitoringCheck(
            monitoring_config_id=config.id,
            project_id=config.project_id,
            endpoint=endpoint.path,
            method=endpoint.method.upper(),
            success=False,
            error_category="TARGET_REJECTED",
            error_message="Target URL failed the configured outbound safety policy.",
            checked_at=now,
        )

    url = f"{target.url.rstrip('/')}{path}"
    base = urlsplit(target.url)
    parsed = urlsplit(url)
    if parsed.scheme != base.scheme or parsed.netloc.lower() != base.netloc.lower():
        return MonitoringCheck(
            monitoring_config_id=config.id,
            project_id=config.project_id,
            endpoint=endpoint.path,
            method=endpoint.method.upper(),
            success=False,
            error_category="INVALID_ENDPOINT",
            error_message="Constructed endpoint URL did not match the approved target origin.",
            checked_at=now,
        )

    started = time.perf_counter()
    try:
        with client.stream(
            endpoint.method.upper(),
            url,
            params=query,
            timeout=config.timeout_seconds,
            follow_redirects=False,
        ) as response:
            body, truncated, body_present = _read_bounded_response(response)
            latency = (time.perf_counter() - started) * 1000
            status_code = response.status_code
            if truncated:
                return MonitoringCheck(
                    monitoring_config_id=config.id,
                    project_id=config.project_id,
                    endpoint=endpoint.path,
                    method=endpoint.method.upper(),
                    status_code=status_code,
                    latency_ms=latency,
                    success=False,
                    error_category="RESPONSE_TOO_LARGE",
                    error_message="Response exceeded the configured monitoring size limit.",
                    checked_at=now,
                )
            if 300 <= status_code < 400:
                return MonitoringCheck(
                    monitoring_config_id=config.id,
                    project_id=config.project_id,
                    endpoint=endpoint.path,
                    method=endpoint.method.upper(),
                    status_code=status_code,
                    latency_ms=latency,
                    success=False,
                    error_category="REDIRECT",
                    error_message="Redirects are disabled for scheduled monitoring.",
                    checked_at=now,
                )
            if not 200 <= status_code < 300:
                return MonitoringCheck(
                    monitoring_config_id=config.id,
                    project_id=config.project_id,
                    endpoint=endpoint.path,
                    method=endpoint.method.upper(),
                    status_code=status_code,
                    latency_ms=latency,
                    success=False,
                    error_category="HTTP_ERROR",
                    error_message=f"Target returned HTTP {status_code}.",
                    checked_at=now,
                )
            expected_statuses, expected_types, schema = _expected_response(
                endpoint, status_code, response.headers.get("content-type")
            )
            errors = validate_response(
                expected_status_codes=expected_statuses,
                actual_status_code=status_code,
                expected_content_types=expected_types,
                actual_content_type=response.headers.get("content-type"),
                schema=schema,
                body=body,
                body_present=body_present,
                specification=specification.raw_specification or {},
            )
            if errors:
                return MonitoringCheck(
                    monitoring_config_id=config.id,
                    project_id=config.project_id,
                    endpoint=endpoint.path,
                    method=endpoint.method.upper(),
                    status_code=status_code,
                    latency_ms=latency,
                    success=False,
                    error_category="CONTRACT_MISMATCH",
                    error_message="Response did not satisfy the documented successful response contract.",
                    checked_at=now,
                )
            return MonitoringCheck(
                monitoring_config_id=config.id,
                project_id=config.project_id,
                endpoint=endpoint.path,
                method=endpoint.method.upper(),
                status_code=status_code,
                latency_ms=latency,
                success=True,
                checked_at=now,
            )
    except httpx.TimeoutException as exc:
        category, message = "TIMEOUT", f"Request timed out ({type(exc).__name__})."
    except httpx.ConnectError as exc:
        category, message = "NETWORK_ERROR", f"Target connection failed ({type(exc).__name__})."
    except httpx.RequestError as exc:
        category, message = "NETWORK_ERROR", f"HTTP request failed ({type(exc).__name__})."
    except (Unresolvable, SchemaError):
        category, message = "SCHEMA_CONFIGURATION", "The documented response schema could not be validated."
    except (ValueError, TypeError):
        category, message = "INVALID_RESPONSE", "The response could not be safely validated."
    return MonitoringCheck(
        monitoring_config_id=config.id,
        project_id=config.project_id,
        endpoint=endpoint.path,
        method=endpoint.method.upper(),
        latency_ms=(time.perf_counter() - started) * 1000,
        success=False,
        error_category=category,
        error_message=message,
        checked_at=now,
    )


def _build_client(config: MonitoringConfiguration, target):
    return httpx.Client(
        transport=PinnedHTTPTransport(
            target,
            limits=httpx.Limits(max_connections=2, max_keepalive_connections=2),
        ),
        timeout=config.timeout_seconds,
        follow_redirects=False,
        trust_env=False,
    )


def run_monitoring_cycle(
    config_id,
    lease_owner: str,
    stop_event: threading.Event | None = None,
) -> None:
    db = SessionLocal()
    try:
        configuration_uuid = UUID(str(config_id))
    except ValueError:
        db.close()
        logger.error("Skipped monitoring cycle with invalid configuration ID %r.", config_id)
        return
    try:
        config = db.get(MonitoringConfiguration, configuration_uuid)
        if not config or not config.enabled or config.lease_owner != lease_owner:
            return
        specification = db.get(ApiSpecification, config.specification_id)
        endpoint_ids = []
        for endpoint_id in config.endpoint_ids:
            try:
                endpoint_ids.append(UUID(str(endpoint_id)))
            except ValueError:
                logger.error(
                    "Monitoring configuration %s contains an invalid endpoint ID.",
                    config.id,
                )
        endpoints = db.query(ApiEndpoint).filter(
            ApiEndpoint.specification_id == config.specification_id,
            ApiEndpoint.id.in_(endpoint_ids),
        ).all()
        endpoint_map = {str(endpoint.id): endpoint for endpoint in endpoints}
        prepared = []
        for endpoint_id in config.endpoint_ids:
            endpoint = endpoint_map.get(str(endpoint_id))
            if endpoint is None:
                logger.error("Monitoring configuration %s references a missing endpoint.", config.id)
                continue
            try:
                path, query = _request_parts(endpoint)
            except ValueError:
                logger.exception("Could not construct a safe monitoring request for configuration %s.", config.id)
                continue
            prepared.append((endpoint, path, query))
        try:
            target = resolve_target_url(config.base_url)
        except TargetValidationError:
            target = None
            logger.warning("Monitoring target for configuration %s failed outbound policy validation.", config.id)

        checks = []
        client = _build_client(config, target) if target is not None and prepared else None
        try:
            for endpoint, path, query in prepared:
                if stop_event and stop_event.is_set():
                    break
                checks.append(_check_endpoint(
                    config=config,
                    specification=specification,
                    endpoint=endpoint,
                    path=path,
                    query=query,
                    target=target,
                    client=client,
                ))
        finally:
            if client is not None:
                client.close()

        now = utc_now()
        config.last_run_at = now
        config.next_check_at = now + timedelta(seconds=config.interval_seconds)
        config.lease_owner = None
        config.lease_until = None
        if checks and all(check.success for check in checks):
            config.last_success_at = now
        db.add_all(checks)
        db.commit()
        for check in checks:
            try:
                if not check.success:
                    create_failure_alert(db, check)
                anomaly = detect_for_check(db, check)
                if anomaly is not None:
                    logger.info(
                        "Monitoring anomaly persisted: project=%s type=%s method=%s endpoint=%s",
                        config.project_id,
                        anomaly.anomaly_type,
                        anomaly.method,
                        anomaly.endpoint,
                    )
            except SQLAlchemyError:
                db.rollback()
                logger.exception("Could not persist monitoring analysis for check %s.", check.id)
            except Exception:
                db.rollback()
                logger.exception("Monitoring analysis failed for check %s.", check.id)
    except Exception:
        db.rollback()
        logger.exception("Monitoring cycle failed for configuration %s.", config_id)
        config = db.get(MonitoringConfiguration, configuration_uuid)
        if config and config.lease_owner == lease_owner:
            now = utc_now()
            config.last_run_at = now
            config.next_check_at = now + timedelta(seconds=config.interval_seconds)
            config.lease_owner = None
            config.lease_until = None
            try:
                db.commit()
            except SQLAlchemyError:
                db.rollback()
                logger.exception("Could not release monitoring lease for configuration %s.", config_id)
    finally:
        db.close()


def claim_due_configurations(limit: int = MAX_SCHEDULER_JOBS) -> list[tuple[str, str]]:
    db = SessionLocal()
    now = utc_now()
    claimed = []
    try:
        due = db.query(MonitoringConfiguration).filter(
            MonitoringConfiguration.enabled.is_(True),
            or_(MonitoringConfiguration.next_check_at.is_(None), MonitoringConfiguration.next_check_at <= now),
            or_(MonitoringConfiguration.lease_until.is_(None), MonitoringConfiguration.lease_until < now),
        ).order_by(MonitoringConfiguration.next_check_at.asc().nullsfirst()).limit(limit).all()
        for config in due:
            owner = uuid4().hex
            lease_seconds = max(
                MONITORING_LEASE_SECONDS,
                int(config.timeout_seconds * max(len(config.endpoint_ids or []), 1)) + 15,
            )
            changed = db.query(MonitoringConfiguration).filter(
                MonitoringConfiguration.id == config.id,
                MonitoringConfiguration.enabled.is_(True),
                or_(MonitoringConfiguration.lease_until.is_(None), MonitoringConfiguration.lease_until < now),
            ).update(
                {
                    MonitoringConfiguration.lease_owner: owner,
                    MonitoringConfiguration.lease_until: now + timedelta(seconds=lease_seconds),
                },
                synchronize_session=False,
            )
            if changed:
                claimed.append((str(config.id), owner))
        db.commit()
        return claimed
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Could not claim due monitoring configurations.")
        return []
    finally:
        db.close()


class MonitoringScheduler:
    def __init__(self) -> None:
        self._poll_task = None
        self._job_tasks: dict[object, threading.Event] = {}
        self._stopping = False

    async def start(self) -> None:
        import asyncio

        if self._poll_task is not None and not self._poll_task.done():
            return
        self._stopping = False
        event_loop = asyncio.get_running_loop()
        from app.services.monitoring_events import event_hub

        event_hub.set_loop(event_loop)
        self._poll_task = asyncio.create_task(self._poll())

    async def stop(self) -> None:
        import asyncio

        self._stopping = True
        for stop_event in self._job_tasks.values():
            stop_event.set()
        if self._poll_task is not None:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
            self._poll_task = None
        tasks = list(self._job_tasks)
        if tasks:
            try:
                await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=35)
            except asyncio.TimeoutError:
                logger.warning("Some monitoring requests did not finish before application shutdown.")
        self._job_tasks.clear()

    async def _run_job(self, config_id: str, owner: str, stop_event: threading.Event) -> None:
        import asyncio

        try:
            await asyncio.to_thread(run_monitoring_cycle, config_id, owner, stop_event)
        except Exception:
            logger.exception("Monitoring worker crashed for configuration %s.", config_id)

    async def _poll(self) -> None:
        import asyncio

        while not self._stopping:
            available = MAX_SCHEDULER_JOBS - len(self._job_tasks)
            if available > 0:
                claimed = await asyncio.to_thread(claim_due_configurations, available)
                for config_id, owner in claimed:
                    stop_event = threading.Event()
                    task = asyncio.create_task(self._run_job(config_id, owner, stop_event))
                    self._job_tasks[task] = stop_event
                    task.add_done_callback(self._job_tasks.pop)
            await asyncio.sleep(MONITORING_SCHEDULER_POLL_SECONDS)


monitoring_scheduler = MonitoringScheduler()
