from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.config import (
    MONITORING_MAX_ENDPOINTS,
    MONITORING_MAX_INTERVAL_SECONDS,
    MONITORING_MAX_TIMEOUT_SECONDS,
    MONITORING_MIN_INTERVAL_SECONDS,
)


class MonitoringConfigurationCreate(BaseModel):
    specification_id: UUID
    name: str = Field(min_length=1, max_length=120)
    environment_name: str = Field(min_length=1, max_length=100)
    base_url: HttpUrl
    endpoint_ids: list[UUID] = Field(min_length=1, max_length=MONITORING_MAX_ENDPOINTS)
    interval_seconds: int = Field(
        default=60,
        ge=MONITORING_MIN_INTERVAL_SECONDS,
        le=MONITORING_MAX_INTERVAL_SECONDS,
    )
    timeout_seconds: float = Field(default=10, gt=0, le=MONITORING_MAX_TIMEOUT_SECONDS)


class MonitoringConfigurationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    interval_seconds: int | None = Field(
        default=None,
        ge=MONITORING_MIN_INTERVAL_SECONDS,
        le=MONITORING_MAX_INTERVAL_SECONDS,
    )
    timeout_seconds: float | None = Field(default=None, gt=0, le=MONITORING_MAX_TIMEOUT_SECONDS)


class MonitoringConfigurationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    specification_id: UUID
    name: str
    environment_name: str
    base_url: str
    endpoint_ids: list[UUID]
    enabled: bool
    interval_seconds: int
    timeout_seconds: float
    last_run_at: datetime | None
    last_success_at: datetime | None
    next_check_at: datetime | None
    created_at: datetime


class MonitoringCheckOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    monitoring_config_id: UUID
    endpoint: str
    method: str
    status_code: int | None
    latency_ms: float | None
    success: bool
    error_category: str | None
    error_message: str | None
    checked_at: datetime


class AnomalyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    endpoint: str
    method: str
    anomaly_score: float
    detection_method: str
    severity: str
    anomaly_type: str
    metrics: dict
    explanation: str
    recommendation: str
    detected_at: datetime
    acknowledged: bool


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    anomaly_id: UUID | None
    monitoring_config_id: UUID | None
    endpoint: str | None
    alert_type: str
    severity: str
    title: str
    message: str
    status: str
    metrics: dict
    recommendation: str
    created_at: datetime
    read_at: datetime | None
    acknowledged_at: datetime | None
    resolved_at: datetime | None


class AlertUpdate(BaseModel):
    action: str = Field(pattern=r"^(read|acknowledge|resolve)$")
