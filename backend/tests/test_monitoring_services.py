import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.connection import Base
from app.database.models import (
    ApiEndpoint,
    ApiSpecification,
    MonitoringCheck,
    MonitoringConfiguration,
    MonitoringAlert,
    Project,
)
from app.services.monitoring_metrics import aggregate_metrics
from app.services.target_security import ValidatedTarget


@pytest.fixture
def monitoring_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    db = session_factory()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def _records(db):
    project = Project(name="Monitoring tests")
    db.add(project)
    db.flush()
    specification = ApiSpecification(
        project_id=project.id,
        title="Public API",
        description=None,
        openapi_version="3.1.0",
        api_version="1.0",
        original_filename="public.json",
        file_format="json",
        version_number=1,
        raw_specification={"openapi": "3.1.0"},
        content_hash=uuid.uuid4().hex,
    )
    db.add(specification)
    db.flush()
    configuration = MonitoringConfiguration(
        project_id=project.id,
        specification_id=specification.id,
        name="health",
        environment_name="test",
        base_url="https://api.example.test",
        endpoint_ids=[],
        configuration_key=uuid.uuid4().hex,
        enabled=False,
        interval_seconds=60,
        timeout_seconds=5,
    )
    db.add(configuration)
    db.flush()
    return project, specification, configuration


def test_monitoring_executor_validates_contract_without_persisting_response_body(monkeypatch):
    import app.services.monitoring_runner as runner

    project_id = uuid.uuid4()
    configuration = MonitoringConfiguration(
        id=uuid.uuid4(),
        project_id=project_id,
        specification_id=uuid.uuid4(),
        name="health",
        environment_name="test",
        base_url="https://api.example.test",
        endpoint_ids=[],
        configuration_key=uuid.uuid4().hex,
        enabled=False,
        interval_seconds=60,
        timeout_seconds=5,
    )
    specification = ApiSpecification(
        id=configuration.specification_id,
        project_id=project_id,
        title="Public API",
        description=None,
        openapi_version="3.1.0",
        api_version="1.0",
        original_filename="public.json",
        file_format="json",
        version_number=1,
        raw_specification={"openapi": "3.1.0"},
        content_hash=uuid.uuid4().hex,
    )
    endpoint = ApiEndpoint(
        id=uuid.uuid4(),
        specification_id=specification.id,
        path="/health",
        method="GET",
        operation_id=None,
        summary=None,
        description=None,
        tags=[],
        parameters=[],
        request_body=None,
        responses={
            "200": {
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "required": ["status"],
                            "properties": {"status": {"type": "string"}},
                        }
                    }
                }
            }
        },
        deprecated=False,
        security=[],
    )
    target = ValidatedTarget(
        url="https://api.example.test",
        hostname="api.example.test",
        port=443,
        addresses=("93.184.216.34",),
    )
    client = httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            headers={"content-type": "application/json"},
            json={"status": "ok", "secret": "not stored"},
        )
    ))
    try:
        check = runner._check_endpoint(
            config=configuration,
            specification=specification,
            endpoint=endpoint,
            path="/health",
            query={},
            target=target,
            client=client,
        )
    finally:
        client.close()
    assert check.success is True
    assert check.status_code == 200
    assert check.latency_ms is not None
    assert not hasattr(check, "response_body")

    large_client = httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, content=b"x" * 100)
    ))
    monkeypatch.setattr(runner, "MONITORING_MAX_RESPONSE_BYTES", 16)
    try:
        oversized = runner._check_endpoint(
            config=configuration,
            specification=specification,
            endpoint=endpoint,
            path="/health",
            query={},
            target=target,
            client=large_client,
        )
    finally:
        large_client.close()
    assert oversized.success is False
    assert oversized.error_category == "RESPONSE_TOO_LARGE"
    assert "body" not in oversized.error_message.lower()


def test_metrics_are_calculated_from_saved_monitoring_checks(monitoring_db):
    project, _, configuration = _records(monitoring_db)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    checks = [
        MonitoringCheck(
            monitoring_config_id=configuration.id,
            project_id=project.id,
            endpoint="/health",
            method="GET",
            status_code=200,
            latency_ms=100,
            success=True,
            checked_at=now - timedelta(minutes=2),
        ),
        MonitoringCheck(
            monitoring_config_id=configuration.id,
            project_id=project.id,
            endpoint="/health",
            method="GET",
            status_code=200,
            latency_ms=200,
            success=True,
            checked_at=now - timedelta(minutes=1),
        ),
        MonitoringCheck(
            monitoring_config_id=configuration.id,
            project_id=project.id,
            endpoint="/health",
            method="GET",
            status_code=503,
            latency_ms=400,
            success=False,
            error_category="HTTP_ERROR",
            error_message="Target returned HTTP 503.",
            checked_at=now,
        ),
    ]
    monitoring_db.add_all(checks)
    monitoring_db.commit()

    metrics = aggregate_metrics(monitoring_db, project_id=project.id, window="5m")
    assert metrics["total_checks"] == 3
    assert metrics["summary"]["probe_count"] == 3
    assert metrics["summary"]["failed_probes"] == 1
    assert metrics["summary"]["success_rate"] == pytest.approx(66.67)
    assert metrics["summary"]["average_latency_ms"] == pytest.approx(233.33, rel=0.01)
    assert metrics["summary"]["status_code_distribution"] == {"200": 2, "503": 1}
    assert metrics["endpoints"][0]["endpoint"] == "/health"


def test_isolation_forest_training_and_anomaly_alert_persistence(monitoring_db, monkeypatch):
    import app.services.anomaly_detection as detection

    monkeypatch.setattr(detection, "ANOMALY_MIN_TRAINING_SAMPLES", 20)
    monkeypatch.setattr(detection, "ANOMALY_RETRAIN_NEW_SAMPLES", 50)
    project, _, configuration = _records(monitoring_db)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    baseline_checks = [
        MonitoringCheck(
            monitoring_config_id=configuration.id,
            project_id=project.id,
            endpoint="/health",
            method="GET",
            status_code=200,
            latency_ms=100 + index % 3,
            success=True,
            checked_at=now - timedelta(minutes=30 - index),
        )
        for index in range(25)
    ]
    monitoring_db.add_all(baseline_checks)
    monitoring_db.commit()

    trained = detection.train_project_model(monitoring_db, project.id)
    assert trained["model_status"] == "READY"
    assert trained["training_samples"] == 25
    assert "not probabilities" in trained["score_note"]

    outlier = MonitoringCheck(
        monitoring_config_id=configuration.id,
        project_id=project.id,
        endpoint="/health",
        method="GET",
        status_code=200,
        latency_ms=5000,
        success=True,
        checked_at=now + timedelta(seconds=1),
    )
    monitoring_db.add(outlier)
    monitoring_db.commit()
    anomaly = detection.detect_for_check(monitoring_db, outlier)

    assert anomaly is not None
    assert anomaly.anomaly_type == "HIGH_LATENCY"
    assert anomaly.metrics["latency_ratio"] > 2
    alert = monitoring_db.query(MonitoringAlert).filter(
        MonitoringAlert.anomaly_id == anomaly.id
    ).one()
    assert alert.status == "OPEN"
    assert alert.metrics["latency_ms"] == 5000


def test_scheduler_claims_once_and_persists_a_mocked_monitoring_cycle(monitoring_db, monkeypatch):
    import app.services.monitoring_runner as runner

    project, specification, configuration = _records(monitoring_db)
    endpoint = ApiEndpoint(
        specification_id=specification.id,
        path="/health",
        method="GET",
        operation_id=None,
        summary=None,
        description=None,
        tags=[],
        parameters=[],
        request_body=None,
        responses={"200": {"description": "OK"}},
        deprecated=False,
        security=[],
    )
    monitoring_db.add(endpoint)
    monitoring_db.flush()
    configuration.endpoint_ids = [str(endpoint.id)]
    configuration.enabled = True
    configuration.next_check_at = None
    configuration.lease_owner = None
    configuration.lease_until = None
    monitoring_db.commit()

    session_factory = sessionmaker(
        bind=monitoring_db.get_bind(),
        autoflush=False,
        expire_on_commit=False,
    )
    monkeypatch.setattr(runner, "SessionLocal", session_factory)
    first_claim = runner.claim_due_configurations()
    assert len(first_claim) == 1
    assert runner.claim_due_configurations() == []

    target = ValidatedTarget(
        url="https://api.example.test",
        hostname="api.example.test",
        port=443,
        addresses=("93.184.216.34",),
    )
    monkeypatch.setattr(runner, "resolve_target_url", lambda value: target)
    monkeypatch.setattr(
        runner,
        "_build_client",
        lambda config, validated_target: httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json={"status": "ok"})
            )
        ),
    )
    config_id, owner = first_claim[0]
    runner.run_monitoring_cycle(config_id, owner)

    saved = monitoring_db.query(MonitoringCheck).filter(
        MonitoringCheck.monitoring_config_id == configuration.id
    ).one()
    assert saved.success is True
    assert saved.status_code == 200
    updated = monitoring_db.get(MonitoringConfiguration, configuration.id)
    monitoring_db.refresh(updated)
    assert updated.lease_owner is None
    assert updated.last_success_at is not None
