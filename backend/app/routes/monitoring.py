import asyncio
import hashlib
import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import ALLOWED_ORIGINS
from app.database.connection import get_db
from app.database.models import (
    AnomalyDetection,
    ApiEndpoint,
    ApiSpecification,
    MonitoringAlert,
    MonitoringCheck,
    MonitoringConfiguration,
    Project,
    User,
)
from app.schemas.monitoring import (
    AlertOut,
    AlertUpdate,
    AnomalyOut,
    MonitoringCheckOut,
    MonitoringConfigurationCreate,
    MonitoringConfigurationOut,
    MonitoringConfigurationUpdate,
)
from app.services.anomaly_detection import get_model_status, train_project_model
from app.services.authentication import AuthenticationError, authenticate_access_token, get_current_user
from app.services.authorization import READ_ROLES, WRITE_ROLES, project_membership
from app.services.monitoring_events import event_hub
from app.services.monitoring_metrics import aggregate_metrics
from app.services.monitoring_runner import validate_monitorable_endpoints
from app.services.target_security import TargetValidationError, resolve_target_url
from app.services.monitoring_time import utc_now

router = APIRouter(tags=["monitoring"])
logger = logging.getLogger(__name__)
WEBSOCKET_SUBPROTOCOL = "contractiq.monitoring.v1"


def _authorized_project(
    project_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Project:
    project, _ = project_membership(db, user, project_id, READ_ROLES)
    return project


def _editable_project(
    project_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Project:
    project, _ = project_membership(db, user, project_id, WRITE_ROLES)
    if project.is_archived:
        raise HTTPException(status.HTTP_409_CONFLICT, "Restore this project before changing monitoring settings.")
    return project


def _configuration(db: Session, project_id: UUID, configuration_id: UUID) -> MonitoringConfiguration:
    configuration = db.get(MonitoringConfiguration, configuration_id)
    if not configuration or configuration.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Monitoring configuration not found.")
    return configuration


def _serialize_configuration(item: MonitoringConfiguration) -> dict:
    return MonitoringConfigurationOut.model_validate(item).model_dump(mode="json")


def _serialize_check(item: MonitoringCheck) -> dict:
    return MonitoringCheckOut.model_validate(item).model_dump(mode="json")


def _serialize_alert(item: MonitoringAlert) -> dict:
    return AlertOut.model_validate(item).model_dump(mode="json")


def _serialize_anomaly(item: AnomalyDetection) -> dict:
    return AnomalyOut.model_validate(item).model_dump(mode="json")


def _configuration_key(configuration: MonitoringConfiguration) -> str:
    identity = "|".join((
        str(configuration.project_id),
        str(configuration.specification_id),
        configuration.base_url,
        configuration.environment_name.strip().lower(),
        ",".join(sorted(str(item) for item in configuration.endpoint_ids)),
        str(configuration.interval_seconds),
        str(configuration.timeout_seconds),
    ))
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _commit_or_raise(db: Session, message: str, context: str) -> None:
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Could not %s.", context)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, message) from exc


@router.post(
    "/api/v1/projects/{project_id}/monitoring/configurations",
    status_code=status.HTTP_201_CREATED,
    response_model=MonitoringConfigurationOut,
)
def create_configuration(
    payload: MonitoringConfigurationCreate,
    project: Project = Depends(_editable_project),
    db: Session = Depends(get_db),
) -> dict:
    specification = db.get(ApiSpecification, payload.specification_id)
    if not specification or specification.project_id != project.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Specification not found for this project.")
    if len(set(payload.endpoint_ids)) != len(payload.endpoint_ids):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Endpoint IDs must be unique.")
    endpoints = db.query(ApiEndpoint).filter(
        ApiEndpoint.specification_id == specification.id,
        ApiEndpoint.id.in_(payload.endpoint_ids),
    ).all()
    if len(endpoints) != len(payload.endpoint_ids):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "All endpoints must belong to the selected specification.")
    try:
        target = resolve_target_url(str(payload.base_url))
        validate_monitorable_endpoints(specification, endpoints)
    except TargetValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc

    configuration = MonitoringConfiguration(
        project_id=project.id,
        specification_id=specification.id,
        name=payload.name.strip(),
        environment_name=payload.environment_name.strip(),
        base_url=target.url,
        endpoint_ids=[str(item) for item in payload.endpoint_ids],
        configuration_key="",
        enabled=False,
        interval_seconds=payload.interval_seconds,
        timeout_seconds=payload.timeout_seconds,
    )
    configuration.configuration_key = _configuration_key(configuration)
    existing = db.query(MonitoringConfiguration).filter(
        MonitoringConfiguration.configuration_key == configuration.configuration_key
    ).first()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "An identical monitoring configuration already exists.")

    db.add(configuration)
    try:
        db.commit()
        db.refresh(configuration)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "An identical monitoring configuration already exists.") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Could not save monitoring configuration.")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "The monitoring configuration could not be saved.") from exc
    return _serialize_configuration(configuration)


@router.get(
    "/api/v1/projects/{project_id}/monitoring/configurations",
    response_model=list[MonitoringConfigurationOut],
)
def list_configurations(
    project: Project = Depends(_authorized_project),
    db: Session = Depends(get_db),
) -> list[dict]:
    items = db.query(MonitoringConfiguration).filter(
        MonitoringConfiguration.project_id == project.id
    ).order_by(MonitoringConfiguration.created_at.desc()).all()
    return [_serialize_configuration(item) for item in items]


@router.patch(
    "/api/v1/projects/{project_id}/monitoring/configurations/{configuration_id}",
    response_model=MonitoringConfigurationOut,
)
def update_configuration(
    payload: MonitoringConfigurationUpdate,
    configuration_id: UUID,
    project: Project = Depends(_editable_project),
    db: Session = Depends(get_db),
) -> dict:
    configuration = _configuration(db, project.id, configuration_id)
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        if value is not None:
            setattr(configuration, field, value.strip() if field == "name" else value)
    if updates:
        configuration.configuration_key = _configuration_key(configuration)
        configuration.next_check_at = utc_now() if configuration.enabled else None
    _commit_or_raise(
        db,
        "The monitoring configuration could not be updated.",
        f"update monitoring configuration {configuration_id}",
    )
    db.refresh(configuration)
    return _serialize_configuration(configuration)


@router.post(
    "/api/v1/projects/{project_id}/monitoring/configurations/{configuration_id}/start",
    response_model=MonitoringConfigurationOut,
)
def start_configuration(
    configuration_id: UUID,
    project: Project = Depends(_editable_project),
    db: Session = Depends(get_db),
) -> dict:
    configuration = _configuration(db, project.id, configuration_id)
    configuration.enabled = True
    configuration.next_check_at = utc_now()
    _commit_or_raise(
        db,
        "The monitoring configuration could not be started.",
        f"start monitoring configuration {configuration_id}",
    )
    db.refresh(configuration)
    return _serialize_configuration(configuration)


@router.post(
    "/api/v1/projects/{project_id}/monitoring/configurations/{configuration_id}/pause",
    response_model=MonitoringConfigurationOut,
)
def pause_configuration(
    configuration_id: UUID,
    project: Project = Depends(_editable_project),
    db: Session = Depends(get_db),
) -> dict:
    configuration = _configuration(db, project.id, configuration_id)
    configuration.enabled = False
    configuration.next_check_at = None
    _commit_or_raise(
        db,
        "The monitoring configuration could not be paused.",
        f"pause monitoring configuration {configuration_id}",
    )
    db.refresh(configuration)
    return _serialize_configuration(configuration)


@router.delete(
    "/api/v1/projects/{project_id}/monitoring/configurations/{configuration_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_configuration(
    configuration_id: UUID,
    project: Project = Depends(_editable_project),
    db: Session = Depends(get_db),
):
    configuration = _configuration(db, project.id, configuration_id)
    if configuration.lease_until and configuration.lease_until > utc_now():
        raise HTTPException(status.HTTP_409_CONFLICT, "Pause the configuration and wait for its active check to finish before deleting it.")
    db.delete(configuration)
    _commit_or_raise(
        db,
        "The monitoring configuration could not be deleted.",
        f"delete monitoring configuration {configuration_id}",
    )


@router.get("/api/v1/projects/{project_id}/monitoring/overview")
def monitoring_overview(
    window: str = Query("1h", pattern=r"^(5m|15m|1h|24h|7d)$"),
    environment_name: str | None = Query(None, max_length=100),
    project: Project = Depends(_authorized_project),
    db: Session = Depends(get_db),
) -> dict:
    config_count = db.query(func.count(MonitoringConfiguration.id)).filter(
        MonitoringConfiguration.project_id == project.id
    ).scalar() or 0
    enabled_count = db.query(func.count(MonitoringConfiguration.id)).filter(
        MonitoringConfiguration.project_id == project.id,
        MonitoringConfiguration.enabled.is_(True),
    ).scalar() or 0
    active_alerts = db.query(func.count(MonitoringAlert.id)).filter(
        MonitoringAlert.project_id == project.id,
        MonitoringAlert.status != "RESOLVED",
    ).scalar() or 0
    unread_alerts = db.query(func.count(MonitoringAlert.id)).filter(
        MonitoringAlert.project_id == project.id,
        MonitoringAlert.read_at.is_(None),
        MonitoringAlert.status != "RESOLVED",
    ).scalar() or 0
    latest = db.query(MonitoringCheck).filter(
        MonitoringCheck.project_id == project.id
    ).order_by(MonitoringCheck.checked_at.desc()).first()
    return {
        "project_id": str(project.id),
        "window": window,
        "monitoring_configurations": config_count,
        "enabled_configurations": enabled_count,
        "active_alerts": active_alerts,
        "unread_alerts": unread_alerts,
        "latest_check": _serialize_check(latest) if latest else None,
        "metrics": aggregate_metrics(
            db,
            project_id=project.id,
            window=window,
            environment_name=environment_name,
        ),
        "environment_name": environment_name,
        "model": get_model_status(db, project.id),
    }


@router.get("/api/v1/projects/{project_id}/monitoring/metrics")
def monitoring_metrics(
    window: str = Query("1h", pattern=r"^(5m|15m|1h|24h|7d)$"),
    endpoint: str | None = Query(None, max_length=2048),
    environment_name: str | None = Query(None, max_length=100),
    project: Project = Depends(_authorized_project),
    db: Session = Depends(get_db),
) -> dict:
    return aggregate_metrics(
        db,
        project_id=project.id,
        window=window,
        endpoint=endpoint,
        environment_name=environment_name,
    )


@router.get("/api/v1/projects/{project_id}/monitoring/checks")
def monitoring_checks(
    success: bool | None = None,
    endpoint: str | None = Query(None, max_length=2048),
    error_category: str | None = Query(None, max_length=30),
    environment_name: str | None = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    project: Project = Depends(_authorized_project),
    db: Session = Depends(get_db),
) -> dict:
    query = db.query(MonitoringCheck).filter(MonitoringCheck.project_id == project.id)
    if environment_name:
        query = query.join(
            MonitoringConfiguration,
            MonitoringConfiguration.id == MonitoringCheck.monitoring_config_id,
        ).filter(MonitoringConfiguration.environment_name == environment_name)
    if success is not None:
        query = query.filter(MonitoringCheck.success.is_(success))
    if endpoint:
        query = query.filter(MonitoringCheck.endpoint == endpoint)
    if error_category:
        query = query.filter(MonitoringCheck.error_category == error_category.upper())
    total = query.count()
    items = query.order_by(MonitoringCheck.checked_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()
    return {
        "items": [_serialize_check(item) for item in items],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


@router.get("/api/v1/projects/{project_id}/monitoring/errors")
def monitoring_errors(
    error_category: str | None = Query(None, max_length=30),
    endpoint: str | None = Query(None, max_length=2048),
    environment_name: str | None = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    project: Project = Depends(_authorized_project),
    db: Session = Depends(get_db),
) -> dict:
    query = db.query(MonitoringCheck).filter(
        MonitoringCheck.project_id == project.id,
        MonitoringCheck.success.is_(False),
    )
    if environment_name:
        query = query.join(
            MonitoringConfiguration,
            MonitoringConfiguration.id == MonitoringCheck.monitoring_config_id,
        ).filter(MonitoringConfiguration.environment_name == environment_name)
    if error_category:
        query = query.filter(MonitoringCheck.error_category == error_category.upper())
    if endpoint:
        query = query.filter(MonitoringCheck.endpoint == endpoint)
    total = query.count()
    items = query.order_by(MonitoringCheck.checked_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()
    return {
        "items": [_serialize_check(item) for item in items],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


@router.get("/api/v1/projects/{project_id}/monitoring/anomalies")
def list_anomalies(
    acknowledged: bool | None = None,
    severity: str | None = Query(None, pattern=r"(?i)^(CRITICAL|HIGH|MEDIUM|LOW)$"),
    anomaly_type: str | None = Query(None, max_length=40),
    endpoint: str | None = Query(None, max_length=2048),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    project: Project = Depends(_authorized_project),
    db: Session = Depends(get_db),
) -> dict:
    query = db.query(AnomalyDetection).filter(AnomalyDetection.project_id == project.id)
    if acknowledged is not None:
        query = query.filter(AnomalyDetection.acknowledged.is_(acknowledged))
    if severity:
        query = query.filter(AnomalyDetection.severity == severity.upper())
    if anomaly_type:
        query = query.filter(AnomalyDetection.anomaly_type == anomaly_type.upper())
    if endpoint:
        query = query.filter(AnomalyDetection.endpoint == endpoint)
    total = query.count()
    items = query.order_by(AnomalyDetection.detected_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()
    return {
        "items": [_serialize_anomaly(item) for item in items],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


@router.post("/api/v1/projects/{project_id}/monitoring/anomalies/train")
def train_anomaly_model(
    project: Project = Depends(_editable_project),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return train_project_model(db, project.id)
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Could not train anomaly model for project %s.", project.id)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "The anomaly model could not be trained.") from exc
    except (ValueError, TypeError) as exc:
        db.rollback()
        logger.exception("Anomaly model training failed for project %s.", project.id)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "The anomaly model training failed; see backend logs.") from exc


@router.get("/api/v1/projects/{project_id}/monitoring/anomalies/model")
def anomaly_model_status(
    project: Project = Depends(_authorized_project),
    db: Session = Depends(get_db),
) -> dict:
    return get_model_status(db, project.id)


@router.patch("/api/v1/projects/{project_id}/monitoring/anomalies/{anomaly_id}/acknowledge")
def acknowledge_anomaly(
    anomaly_id: UUID,
    project: Project = Depends(_editable_project),
    db: Session = Depends(get_db),
) -> dict:
    anomaly = db.get(AnomalyDetection, anomaly_id)
    if not anomaly or anomaly.project_id != project.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Anomaly not found.")
    anomaly.acknowledged = True
    _commit_or_raise(db, "The anomaly could not be acknowledged.", f"acknowledge anomaly {anomaly_id}")
    db.refresh(anomaly)
    return _serialize_anomaly(anomaly)


@router.get("/api/v1/projects/{project_id}/monitoring/alerts")
def list_alerts(
    status_filter: str | None = Query(None, alias="status", pattern=r"(?i)^(OPEN|ACKNOWLEDGED|RESOLVED)$"),
    severity: str | None = Query(None, pattern=r"(?i)^(CRITICAL|HIGH|MEDIUM|LOW)$"),
    unread: bool | None = None,
    endpoint: str | None = Query(None, max_length=2048),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    project: Project = Depends(_authorized_project),
    db: Session = Depends(get_db),
) -> dict:
    query = db.query(MonitoringAlert).filter(MonitoringAlert.project_id == project.id)
    if status_filter:
        query = query.filter(MonitoringAlert.status == status_filter.upper())
    if severity:
        query = query.filter(MonitoringAlert.severity == severity.upper())
    if unread is True:
        query = query.filter(MonitoringAlert.read_at.is_(None))
    elif unread is False:
        query = query.filter(MonitoringAlert.read_at.is_not(None))
    if endpoint:
        query = query.filter(MonitoringAlert.endpoint == endpoint)
    total = query.count()
    items = query.order_by(MonitoringAlert.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()
    unread_count = db.query(func.count(MonitoringAlert.id)).filter(
        MonitoringAlert.project_id == project.id,
        MonitoringAlert.read_at.is_(None),
        MonitoringAlert.status != "RESOLVED",
    ).scalar() or 0
    return {
        "items": [_serialize_alert(item) for item in items],
        "page": page,
        "page_size": page_size,
        "total": total,
        "unread_count": unread_count,
    }


@router.patch("/api/v1/projects/{project_id}/monitoring/alerts/{alert_id}")
def update_alert(
    payload: AlertUpdate,
    alert_id: UUID,
    project: Project = Depends(_editable_project),
    db: Session = Depends(get_db),
) -> dict:
    alert = db.get(MonitoringAlert, alert_id)
    if not alert or alert.project_id != project.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alert not found.")
    now = utc_now()
    if payload.action == "read":
        alert.read_at = alert.read_at or now
    elif payload.action == "acknowledge":
        alert.status = "ACKNOWLEDGED"
        alert.acknowledged_at = alert.acknowledged_at or now
        alert.read_at = alert.read_at or now
    elif payload.action == "resolve":
        alert.status = "RESOLVED"
        alert.resolved_at = alert.resolved_at or now
        alert.read_at = alert.read_at or now
    _commit_or_raise(db, "The alert could not be updated.", f"update alert {alert_id}")
    db.refresh(alert)
    return _serialize_alert(alert)


@router.websocket("/ws/v1/projects/{project_id}/monitoring/live")
async def monitoring_live(
    websocket: WebSocket,
    project_id: UUID,
    db: Session = Depends(get_db),
) -> None:
    offered = [
        item.strip()
        for item in websocket.headers.get("sec-websocket-protocol", "").split(",")
        if item.strip()
    ]
    token_protocol = next((item for item in offered if item.startswith("bearer.")), None)
    origin = websocket.headers.get("origin")
    if origin and origin not in ALLOWED_ORIGINS:
        subprotocol = WEBSOCKET_SUBPROTOCOL if WEBSOCKET_SUBPROTOCOL in offered else None
        await websocket.accept(subprotocol=subprotocol)
        await websocket.close(code=4403, reason="WebSocket origin is not allowed.")
        return
    if WEBSOCKET_SUBPROTOCOL not in offered or not token_protocol:
        await websocket.accept()
        await websocket.close(code=4401, reason="Monitoring authentication failed.")
        return
    await websocket.accept(subprotocol=WEBSOCKET_SUBPROTOCOL)
    try:
        user = authenticate_access_token(token_protocol[len("bearer."):], db)
        project_membership(db, user, project_id, READ_ROLES)
    except AuthenticationError:
        await websocket.close(code=4401, reason="Monitoring authentication failed.")
        return
    except HTTPException as exc:
        await websocket.close(
            code=4404 if exc.status_code == status.HTTP_404_NOT_FOUND else 4403,
            reason="Project access denied.",
        )
        return
    finally:
        db.close()

    await event_hub.connect(project_id, websocket)
    try:
        while True:
            try:
                message = await asyncio.wait_for(websocket.receive_text(), timeout=25)
            except asyncio.TimeoutError:
                await websocket.send_json({
                    "event": "HEARTBEAT",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                continue
            if message == "PING":
                await websocket.send_json({"event": "PONG"})
    except WebSocketDisconnect:
        pass
    finally:
        event_hub.disconnect(project_id, websocket)
