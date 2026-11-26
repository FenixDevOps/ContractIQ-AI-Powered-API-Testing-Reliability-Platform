from collections import Counter, defaultdict
from datetime import timedelta
from math import ceil

from sqlalchemy import func

from app.database.models import MonitoringCheck, MonitoringConfiguration
from app.services.monitoring_time import utc_now

WINDOWS = {
    "5m": timedelta(minutes=5),
    "15m": timedelta(minutes=15),
    "1h": timedelta(hours=1),
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
}
MAX_METRIC_ROWS = 20000


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _summary(checks: list[MonitoringCheck]) -> dict:
    latencies = [float(item.latency_ms) for item in checks if item.latency_ms is not None]
    status_codes = Counter(str(item.status_code) for item in checks if item.status_code is not None)
    errors = Counter(item.error_category for item in checks if item.error_category)
    total = len(checks)
    successful = sum(item.success for item in checks)
    return {
        "probe_count": total,
        "successful_probes": successful,
        "failed_probes": total - successful,
        "success_rate": round(successful / total * 100, 2) if total else None,
        "average_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else None,
        "p50_latency_ms": round(_percentile(latencies, 0.50), 2) if latencies else None,
        "p90_latency_ms": round(_percentile(latencies, 0.90), 2) if latencies else None,
        "p95_latency_ms": round(_percentile(latencies, 0.95), 2) if latencies else None,
        "p99_latency_ms": round(_percentile(latencies, 0.99), 2) if latencies else None,
        "min_latency_ms": round(min(latencies), 2) if latencies else None,
        "max_latency_ms": round(max(latencies), 2) if latencies else None,
        "status_code_distribution": dict(status_codes),
        "error_category_distribution": dict(errors),
    }


def aggregate_metrics(
    db,
    *,
    project_id,
    window: str,
    endpoint: str | None = None,
    environment_name: str | None = None,
) -> dict:
    duration = WINDOWS[window]
    now = utc_now()
    start = now - duration
    query = db.query(MonitoringCheck).filter(
        MonitoringCheck.project_id == project_id,
        MonitoringCheck.checked_at >= start,
    )
    if environment_name:
        query = query.join(
            MonitoringConfiguration,
            MonitoringConfiguration.id == MonitoringCheck.monitoring_config_id,
        ).filter(MonitoringConfiguration.environment_name == environment_name)
    if endpoint:
        query = query.filter(MonitoringCheck.endpoint == endpoint)
    total_rows = query.with_entities(func.count(MonitoringCheck.id)).scalar() or 0
    checks = query.order_by(MonitoringCheck.checked_at.desc(), MonitoringCheck.id.desc()).limit(
        MAX_METRIC_ROWS
    ).all()
    checks.reverse()
    grouped: dict[tuple[str, str], list[MonitoringCheck]] = defaultdict(list)
    for item in checks:
        grouped[(item.endpoint, item.method)].append(item)

    bucket_seconds = max(30, ceil(duration.total_seconds() / 40))
    buckets: dict[int, list[MonitoringCheck]] = defaultdict(list)
    for item in checks:
        offset = (item.checked_at - start).total_seconds()
        buckets[int(offset // bucket_seconds)].append(item)
    series = []
    for bucket_id, values in sorted(buckets.items()):
        bucket_start = start + timedelta(seconds=bucket_id * bucket_seconds)
        item_summary = _summary(values)
        series.append({
            "timestamp": bucket_start.isoformat() + "Z",
            "probe_count": item_summary["probe_count"],
            "failed_probes": item_summary["failed_probes"],
            "average_latency_ms": item_summary["average_latency_ms"],
            "p95_latency_ms": item_summary["p95_latency_ms"],
        })

    endpoints = []
    for (path, method), values in sorted(grouped.items()):
        endpoints.append({
            "endpoint": path,
            "method": method,
            **_summary(values),
            "latest_check_at": values[-1].checked_at.isoformat() + "Z",
        })
    endpoints.sort(
        key=lambda item: (
            item["p95_latency_ms"] is not None,
            item["p95_latency_ms"] or -1,
        ),
        reverse=True,
    )
    return {
        "window": window,
        "environment_name": environment_name,
        "from": start.isoformat() + "Z",
        "to": now.isoformat() + "Z",
        "total_checks": total_rows,
        "sampled_checks": len(checks),
        "sample_truncated": total_rows > len(checks),
        "summary": _summary(checks),
        "series": series,
        "endpoints": endpoints,
    }
