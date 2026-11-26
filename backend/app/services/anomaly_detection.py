import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import mean, median, pstdev

from sklearn.ensemble import IsolationForest
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sqlalchemy import func

from app.config import (
    ANOMALY_CONTAMINATION,
    ANOMALY_MIN_TRAINING_SAMPLES,
    ANOMALY_RETRAIN_NEW_SAMPLES,
)
from app.database.models import AnomalyDetection, AnomalyModel, MonitoringCheck
from app.services.monitoring_alerts import create_anomaly_alert
from app.services.monitoring_time import utc_now

logger = logging.getLogger(__name__)
MODEL_VERSION = "isolation-forest-v1"
MAX_TRAINING_CHECKS = 5000
MAX_ENDPOINT_HISTORY = 100
FEATURE_NAMES = (
    "latency_ms",
    "latency_ratio",
    "p95_latency_ratio",
    "error_rate",
    "probe_count_5m",
    "failure_count_5m",
    "timeout_count_5m",
    "latency_coefficient_of_variation",
)


@dataclass
class CachedModel:
    estimator: object
    training_samples: int
    training_data_end_at: datetime


_MODEL_CACHE: dict[str, CachedModel] = {}
_MODEL_LOCK = threading.RLock()


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _features(check: MonitoringCheck, history: list[MonitoringCheck]) -> tuple[list[float], dict]:
    prior = [
        item for item in history
        if (
            item.endpoint == check.endpoint
            and item.method == check.method
            and item.monitoring_config_id == check.monitoring_config_id
            and item.checked_at < check.checked_at
        )
    ][-MAX_ENDPOINT_HISTORY:]
    prior_latencies = [float(item.latency_ms) for item in prior if item.latency_ms is not None]
    current_latency = float(check.latency_ms or 0)
    baseline = mean(prior_latencies) if prior_latencies else None
    baseline_p95 = _percentile(prior_latencies, 0.95)
    recent_start = check.checked_at - timedelta(minutes=5)
    recent = [item for item in prior if item.checked_at >= recent_start]
    recent_with_current = recent + [check]
    failure_count = sum(not item.success for item in recent_with_current)
    timeout_count = sum(item.error_category == "TIMEOUT" for item in recent_with_current)
    recent_latencies = [
        float(item.latency_ms) for item in recent_with_current if item.latency_ms is not None
    ]
    recent_mean = mean(recent_latencies) if recent_latencies else 0.0
    coefficient = (
        pstdev(recent_latencies) / recent_mean
        if len(recent_latencies) > 1 and recent_mean > 0
        else 0.0
    )
    error_rate = failure_count / len(recent_with_current) if recent_with_current else 0.0
    latency_ratio = current_latency / max(baseline or current_latency or 1.0, 1.0)
    p95_ratio = current_latency / max(baseline_p95 or baseline or current_latency or 1.0, 1.0)
    values = [
        current_latency,
        latency_ratio,
        p95_ratio,
        error_rate,
        float(len(recent_with_current)),
        float(failure_count),
        float(timeout_count),
        coefficient,
    ]
    details = {
        "latency_ms": round(current_latency, 2) if check.latency_ms is not None else None,
        "baseline_latency_ms": round(baseline, 2) if baseline is not None else None,
        "latency_ratio": round(latency_ratio, 3) if baseline is not None else None,
        "baseline_p95_latency_ms": round(baseline_p95, 2) if baseline_p95 is not None else None,
        "error_rate_percent": round(error_rate * 100, 2),
        "probe_count_5m": len(recent_with_current),
        "failure_count_5m": failure_count,
        "timeout_count_5m": timeout_count,
        "latency_coefficient_of_variation": round(coefficient, 3),
    }
    return values, details


def _training_rows(db, project_id, *, end_at: datetime | None = None, limit: int = MAX_TRAINING_CHECKS):
    query = db.query(MonitoringCheck).filter(MonitoringCheck.project_id == project_id)
    if end_at is not None:
        query = query.filter(MonitoringCheck.checked_at <= end_at)
    rows = query.order_by(MonitoringCheck.checked_at.desc(), MonitoringCheck.id.desc()).limit(limit).all()
    rows.reverse()
    return rows


def _feature_dataset(rows: list[MonitoringCheck]) -> list[list[float]]:
    history_by_endpoint: dict[tuple[str, str, str], list[MonitoringCheck]] = {}
    dataset = []
    for check in rows:
        key = (str(check.monitoring_config_id), check.endpoint, check.method)
        history = history_by_endpoint.setdefault(key, [])
        feature_values, _ = _features(check, history)
        dataset.append(feature_values)
        history.append(check)
        if len(history) > MAX_ENDPOINT_HISTORY:
            del history[:-MAX_ENDPOINT_HISTORY]
    return dataset


def _fit(dataset: list[list[float]]):
    estimator = make_pipeline(
        StandardScaler(),
        IsolationForest(
            n_estimators=100,
            contamination=ANOMALY_CONTAMINATION,
            random_state=42,
            max_samples=min(256, len(dataset)),
        ),
    )
    estimator.fit(dataset)
    return estimator


def _model_record(db, project_id) -> AnomalyModel | None:
    return db.query(AnomalyModel).filter(AnomalyModel.project_id == project_id).first()


def train_project_model(db, project_id) -> dict:
    with _MODEL_LOCK:
        rows = _training_rows(db, project_id)
        record = _model_record(db, project_id)
        parameters = {
            "algorithm": "IsolationForest",
            "contamination": ANOMALY_CONTAMINATION,
            "n_estimators": 100,
            "random_state": 42,
            "feature_names": list(FEATURE_NAMES),
            "score_note": "Isolation scores are not probabilities.",
        }
        if len(rows) < ANOMALY_MIN_TRAINING_SAMPLES:
            if record is None:
                record = AnomalyModel(
                    project_id=project_id,
                    model_version=MODEL_VERSION,
                    model_parameters=parameters,
                    training_samples=len(rows),
                    model_status="WARMING_UP",
                )
                db.add(record)
            else:
                record.model_version = MODEL_VERSION
                record.model_parameters = parameters
                record.training_samples = len(rows)
                record.model_status = "WARMING_UP"
                record.trained_at = None
                record.training_data_end_at = None
            db.commit()
            db.refresh(record)
            _MODEL_CACHE.pop(str(project_id), None)
            return _model_status(record, available_samples=len(rows))

        dataset = _feature_dataset(rows)
        estimator = _fit(dataset)
        now = utc_now()
        if record is None:
            record = AnomalyModel(
                project_id=project_id,
                model_version=MODEL_VERSION,
                model_parameters=parameters,
                training_samples=len(rows),
                model_status="READY",
                trained_at=now,
                training_data_end_at=rows[-1].checked_at,
            )
            db.add(record)
        else:
            record.model_version = MODEL_VERSION
            record.model_parameters = parameters
            record.training_samples = len(rows)
            record.model_status = "READY"
            record.trained_at = now
            record.training_data_end_at = rows[-1].checked_at
        db.commit()
        db.refresh(record)
        _MODEL_CACHE[str(project_id)] = CachedModel(estimator, len(rows), rows[-1].checked_at)
        return _model_status(record, available_samples=len(rows))


def _model_status(record: AnomalyModel | None, *, available_samples: int) -> dict:
    is_ready = record is not None and record.model_status == "READY"
    return {
        "model_status": record.model_status if record else "WARMING_UP",
        "model_version": record.model_version if record else MODEL_VERSION,
        "training_samples": record.training_samples if record else 0,
        "available_samples": available_samples,
        "minimum_training_samples": ANOMALY_MIN_TRAINING_SAMPLES,
        "trained_at": record.trained_at if record else None,
        "training_data_end_at": record.training_data_end_at if record else None,
        "detection_method": "ISOLATION_FOREST" if is_ready else "RULE_BASED",
        "score_note": "Isolation Forest scores are uncalibrated and are not probabilities.",
        "message": (
            "Isolation Forest is trained and available."
            if is_ready
            else "Rule-based detection is active until enough real monitoring checks are collected."
        ),
    }


def get_model_status(db, project_id) -> dict:
    record = _model_record(db, project_id)
    samples = db.query(func.count(MonitoringCheck.id)).filter(
        MonitoringCheck.project_id == project_id
    ).scalar() or 0
    return _model_status(record, available_samples=samples)


def _model_for_prediction(db, project_id):
    key = str(project_id)
    with _MODEL_LOCK:
        cached = _MODEL_CACHE.get(key)
        if cached is not None:
            new_samples = db.query(func.count(MonitoringCheck.id)).filter(
                MonitoringCheck.project_id == project_id,
                MonitoringCheck.checked_at > cached.training_data_end_at,
            ).scalar() or 0
            if new_samples >= ANOMALY_RETRAIN_NEW_SAMPLES:
                train_project_model(db, project_id)
            return _MODEL_CACHE.get(key)

        record = _model_record(db, project_id)
        if record is not None and record.model_status == "READY" and record.training_data_end_at:
            rows = _training_rows(
                db,
                project_id,
                end_at=record.training_data_end_at,
                limit=record.training_samples,
            )
            if len(rows) >= ANOMALY_MIN_TRAINING_SAMPLES:
                estimator = _fit(_feature_dataset(rows))
                cached = CachedModel(estimator, len(rows), rows[-1].checked_at)
                _MODEL_CACHE[key] = cached
                return cached
        samples = db.query(func.count(MonitoringCheck.id)).filter(
            MonitoringCheck.project_id == project_id
        ).scalar() or 0
        if samples >= ANOMALY_MIN_TRAINING_SAMPLES:
            train_project_model(db, project_id)
            return _MODEL_CACHE.get(key)
        return None


def _probe_volume_spike(check: MonitoringCheck, history: list[MonitoringCheck]) -> tuple[bool, float | None]:
    epoch = datetime(1970, 1, 1)

    def bucket(timestamp: datetime) -> int:
        return int((timestamp - epoch).total_seconds() // 300)

    current_bucket = bucket(check.checked_at)
    counts = [0] * 6
    for item in history:
        offset = current_bucket - bucket(item.checked_at)
        if 1 <= offset <= 6:
            counts[offset - 1] += 1
    baseline = median(counts) if counts else 0
    current_count = 1 + sum(
        bucket(item.checked_at) == current_bucket for item in history
    )
    return current_count >= 5 and baseline >= 1 and current_count > baseline * 2, baseline or None


def _classify(details: dict, probe_spike: bool) -> tuple[str | None, str]:
    latency = details["latency_ms"]
    baseline = details["baseline_latency_ms"]
    ratio = details["latency_ratio"]
    if latency is not None and (
        latency >= 3000 or (ratio is not None and ratio >= 2.5 and latency >= 1000)
    ):
        return "HIGH_LATENCY", (
            f"Observed latency was {latency:.1f} ms"
            + (f", {ratio:.1f}x the recent {baseline:.1f} ms baseline." if ratio and baseline else ".")
        )
    if details["probe_count_5m"] >= 5 and details["error_rate_percent"] >= 40:
        return "ERROR_RATE_SPIKE", (
            f"{details['error_rate_percent']:.1f}% of the last "
            f"{details['probe_count_5m']} monitoring probes failed in five minutes."
        )
    if probe_spike:
        return "PROBE_VOLUME_SPIKE", (
            "The number of monitoring probes in the current five-minute bucket is more than twice "
            "the recent baseline. This is probe volume, not observed client traffic."
        )
    return None, ""


def _severity(details: dict) -> str:
    if details["error_rate_percent"] >= 70:
        return "CRITICAL"
    if details["latency_ratio"] is not None and details["latency_ratio"] >= 4:
        return "HIGH"
    return "MEDIUM"


def detect_for_check(db, check: MonitoringCheck) -> AnomalyDetection | None:
    history = db.query(MonitoringCheck).filter(
        MonitoringCheck.project_id == check.project_id,
        MonitoringCheck.monitoring_config_id == check.monitoring_config_id,
        MonitoringCheck.endpoint == check.endpoint,
        MonitoringCheck.method == check.method,
        MonitoringCheck.checked_at < check.checked_at,
    ).order_by(MonitoringCheck.checked_at.desc()).limit(MAX_ENDPOINT_HISTORY).all()
    history.reverse()
    feature_values, details = _features(check, history)
    probe_spike, probe_baseline = _probe_volume_spike(check, history)
    model = _model_for_prediction(db, check.project_id)
    anomaly_score = 0.0
    is_outlier = False
    if model is not None:
        anomaly_score = float(-model.estimator.decision_function([feature_values])[0])
        is_outlier = int(model.estimator.predict([feature_values])[0]) == -1

    anomaly_type, explanation = _classify(details, probe_spike)
    if is_outlier and anomaly_type is None:
        anomaly_type = "UNUSUAL_BEHAVIOR"
        explanation = (
            "The measured latency, recent failure ratio, probe count, and latency variability jointly "
            "differ from the model's training observations."
        )
    elif anomaly_type is not None and model is None:
        anomaly_score = max(
            0.0,
            (details["latency_ratio"] or 0.0) - 1.0,
            details["error_rate_percent"] / 100,
            (details["probe_count_5m"] / max(probe_baseline or 1.0, 1.0)) - 1.0 if probe_spike else 0.0,
        )
    if anomaly_type is None:
        return None

    duplicate = db.query(AnomalyDetection).filter(
        AnomalyDetection.project_id == check.project_id,
        AnomalyDetection.monitoring_config_id == check.monitoring_config_id,
        AnomalyDetection.endpoint == check.endpoint,
        AnomalyDetection.method == check.method,
        AnomalyDetection.anomaly_type == anomaly_type,
        AnomalyDetection.detected_at >= utc_now() - timedelta(minutes=5),
    ).first()
    if duplicate:
        return duplicate

    detection_method = "ISOLATION_FOREST" if model is not None and is_outlier else "RULE_BASED"
    if model is not None:
        details["model_score_interpretation"] = (
            "Positive values indicate greater isolation from training samples; this is not a probability."
        )
    else:
        details["rule_score_interpretation"] = "Rule-based severity indicator; this is not a probability."
    details["probe_volume_baseline_per_5m"] = round(probe_baseline, 2) if probe_baseline is not None else None
    anomaly = AnomalyDetection(
        project_id=check.project_id,
        monitoring_config_id=check.monitoring_config_id,
        endpoint=check.endpoint,
        method=check.method,
        anomaly_score=round(anomaly_score, 6),
        detection_method=detection_method,
        severity=_severity(details),
        anomaly_type=anomaly_type,
        metrics=details,
        explanation=explanation,
        recommendation=(
            "Compare recent checks with the target service's deployment and dependency health. "
            "Review the documented response contract before changing client behavior."
        ),
        detected_at=utc_now(),
    )
    db.add(anomaly)
    db.commit()
    db.refresh(anomaly)
    create_anomaly_alert(db, anomaly)
    return anomaly
