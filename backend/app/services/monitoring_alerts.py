import hashlib
import logging
from datetime import timedelta

from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.config import MONITORING_ALERT_COOLDOWN_SECONDS
from app.database.models import AnomalyDetection, MonitoringAlert, MonitoringCheck
from app.services.monitoring_events import alert_event, event_hub
from app.services.monitoring_time import utc_now

logger = logging.getLogger(__name__)


def _create_alert(
    db,
    *,
    project_id,
    monitoring_config_id,
    endpoint: str | None,
    alert_type: str,
    severity: str,
    title: str,
    message: str,
    metrics: dict,
    recommendation: str,
    anomaly_id=None,
) -> tuple[MonitoringAlert, bool]:
    now = utc_now()
    existing = db.query(MonitoringAlert).filter(
        MonitoringAlert.project_id == project_id,
        MonitoringAlert.monitoring_config_id == monitoring_config_id,
        MonitoringAlert.alert_type == alert_type,
        MonitoringAlert.endpoint == endpoint,
        MonitoringAlert.status != "RESOLVED",
        MonitoringAlert.created_at >= now - timedelta(seconds=MONITORING_ALERT_COOLDOWN_SECONDS),
    ).order_by(MonitoringAlert.created_at.desc()).first()
    if existing:
        return existing, False

    bucket = int(now.timestamp() // MONITORING_ALERT_COOLDOWN_SECONDS)
    fingerprint = "|".join((
        str(project_id),
        str(monitoring_config_id or ""),
        endpoint or "",
        alert_type,
        str(bucket),
    ))
    key = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()
    alert = MonitoringAlert(
        project_id=project_id,
        anomaly_id=anomaly_id,
        monitoring_config_id=monitoring_config_id,
        endpoint=endpoint,
        alert_type=alert_type,
        severity=severity,
        title=title,
        message=message,
        status="OPEN",
        deduplication_key=key,
        metrics=metrics,
        recommendation=recommendation,
        created_at=now,
    )
    db.add(alert)
    try:
        db.commit()
        db.refresh(alert)
    except IntegrityError:
        db.rollback()
        existing = db.query(MonitoringAlert).filter(
            MonitoringAlert.deduplication_key == key
        ).first()
        if existing:
            return existing, False
        raise
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Could not persist monitoring alert.")
        raise
    event_hub.publish_from_worker(alert.project_id, alert_event(alert))
    return alert, True


def create_failure_alert(db, check: MonitoringCheck) -> tuple[MonitoringAlert, bool]:
    severity = "HIGH" if check.status_code is not None and check.status_code >= 500 else "MEDIUM"
    category = check.error_category or "HTTP_ERROR"
    return _create_alert(
        db,
        project_id=check.project_id,
        monitoring_config_id=check.monitoring_config_id,
        endpoint=check.endpoint,
        alert_type="MONITORING_FAILURE",
        severity=severity,
        title="Monitored endpoint check failed",
        message=f"{check.method} {check.endpoint} failed ({category}).",
        metrics={
            "status_code": check.status_code,
            "latency_ms": check.latency_ms,
            "error_category": category,
        },
        recommendation="Review target availability, the allowlisted host configuration, and the endpoint response contract.",
    )


def create_anomaly_alert(db, anomaly: AnomalyDetection) -> tuple[MonitoringAlert, bool]:
    return _create_alert(
        db,
        project_id=anomaly.project_id,
        monitoring_config_id=anomaly.monitoring_config_id,
        endpoint=anomaly.endpoint,
        alert_type=anomaly.anomaly_type,
        severity=anomaly.severity,
        title=f"{anomaly.severity.title()} {anomaly.anomaly_type.replace('_', ' ').lower()} detected",
        message=anomaly.explanation,
        metrics=anomaly.metrics,
        recommendation=anomaly.recommendation,
        anomaly_id=anomaly.id,
    )
