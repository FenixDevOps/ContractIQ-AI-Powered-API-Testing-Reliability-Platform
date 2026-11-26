"""Persistent ContractIQ entities."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.database.connection import Base

JSON_DOCUMENT = JSON().with_variant(JSONB(), "postgresql")


def uuid_type():
    return Uuid(as_uuid=True)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(uuid_type(), primary_key=True, default=uuid.uuid4)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(
        server_default=text("CURRENT_TIMESTAMP"), onupdate=text("CURRENT_TIMESTAMP")
    )

    memberships: Mapped[list["ProjectMembership"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    auth_sessions: Mapped[list["AuthSession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(uuid_type(), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text())
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime())
    created_at: Mapped[datetime] = mapped_column(server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("CURRENT_TIMESTAMP"), onupdate=text("CURRENT_TIMESTAMP"))

    specifications: Mapped[list["ApiSpecification"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    monitoring_configurations: Mapped[list["MonitoringConfiguration"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    memberships: Mapped[list["ProjectMembership"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    activities: Mapped[list["ProjectActivity"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    invitations: Mapped[list["ProjectInvite"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class ProjectMembership(Base):
    __tablename__ = "project_memberships"
    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_project_membership_project_user"),
        Index("ix_project_memberships_user_role", "user_id", "role"),
    )

    id: Mapped[uuid.UUID] = mapped_column(uuid_type(), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        uuid_type(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        uuid_type(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(
        server_default=text("CURRENT_TIMESTAMP"), onupdate=text("CURRENT_TIMESTAMP")
    )

    project: Mapped["Project"] = relationship(back_populates="memberships")
    user: Mapped["User"] = relationship(back_populates="memberships")


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[uuid.UUID] = mapped_column(uuid_type(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        uuid_type(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    refresh_token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    csrf_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("CURRENT_TIMESTAMP"))
    last_used_at: Mapped[datetime] = mapped_column(server_default=text("CURRENT_TIMESTAMP"))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime())

    user: Mapped["User"] = relationship(back_populates="auth_sessions")


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[uuid.UUID] = mapped_column(uuid_type(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        uuid_type(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime())
    created_at: Mapped[datetime] = mapped_column(server_default=text("CURRENT_TIMESTAMP"))


class EmailVerificationToken(Base):
    __tablename__ = "email_verification_tokens"

    id: Mapped[uuid.UUID] = mapped_column(uuid_type(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        uuid_type(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime())
    created_at: Mapped[datetime] = mapped_column(server_default=text("CURRENT_TIMESTAMP"))


class AuthRateLimitBucket(Base):
    __tablename__ = "auth_rate_limit_buckets"

    key_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    window_started_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ProjectInvite(Base):
    __tablename__ = "project_invites"

    id: Mapped[uuid.UUID] = mapped_column(uuid_type(), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        uuid_type(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    invited_by_user_id: Mapped[uuid.UUID] = mapped_column(
        uuid_type(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, index=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime())
    created_at: Mapped[datetime] = mapped_column(server_default=text("CURRENT_TIMESTAMP"))

    project: Mapped["Project"] = relationship(back_populates="invitations")


class ProjectActivity(Base):
    __tablename__ = "project_activities"
    __table_args__ = (Index("ix_project_activities_project_created", "project_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(uuid_type(), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        uuid_type(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        uuid_type(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(40), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(80))
    details: Mapped[dict] = mapped_column(JSON_DOCUMENT, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(server_default=text("CURRENT_TIMESTAMP"))

    project: Mapped["Project"] = relationship(back_populates="activities")
    actor: Mapped["User | None"] = relationship()


class ApiSpecification(Base):
    __tablename__ = "api_specifications"
    __table_args__ = (UniqueConstraint("project_id", "version_number", name="uq_project_spec_version"),)

    id: Mapped[uuid.UUID] = mapped_column(uuid_type(), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(uuid_type(), ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text())
    openapi_version: Mapped[str] = mapped_column(String(20), nullable=False)
    api_version: Mapped[str] = mapped_column(String(100), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_format: Mapped[str] = mapped_column(String(10), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_specification: Mapped[dict] = mapped_column(JSON, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    imported_at: Mapped[datetime] = mapped_column(server_default=text("CURRENT_TIMESTAMP"))
    created_at: Mapped[datetime] = mapped_column(server_default=text("CURRENT_TIMESTAMP"))

    project: Mapped["Project"] = relationship(back_populates="specifications")
    endpoints: Mapped[list["ApiEndpoint"]] = relationship(
        back_populates="specification", cascade="all, delete-orphan"
    )
    compatibility_comparisons_old: Mapped[list["CompatibilityComparison"]] = relationship(
        foreign_keys="CompatibilityComparison.old_specification_id", cascade="all, delete-orphan"
    )
    compatibility_comparisons_new: Mapped[list["CompatibilityComparison"]] = relationship(
        foreign_keys="CompatibilityComparison.new_specification_id", cascade="all, delete-orphan"
    )
    monitoring_configurations: Mapped[list["MonitoringConfiguration"]] = relationship(
        back_populates="specification", cascade="all, delete-orphan"
    )


class ApiEndpoint(Base):
    __tablename__ = "api_endpoints"
    __table_args__ = (UniqueConstraint("specification_id", "path", "method", name="uq_spec_endpoint"),)

    id: Mapped[uuid.UUID] = mapped_column(uuid_type(), primary_key=True, default=uuid.uuid4)
    specification_id: Mapped[uuid.UUID] = mapped_column(
        uuid_type(), ForeignKey("api_specifications.id", ondelete="CASCADE"), index=True
    )
    path: Mapped[str] = mapped_column(String(2048), nullable=False)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    operation_id: Mapped[str | None] = mapped_column(String(255))
    summary: Mapped[str | None] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text())
    tags: Mapped[list] = mapped_column(JSON, default=list)
    parameters: Mapped[list] = mapped_column(JSON, default=list)
    request_body: Mapped[dict | None] = mapped_column(JSON)
    responses: Mapped[dict] = mapped_column(JSON, default=dict)
    deprecated: Mapped[bool] = mapped_column(Boolean, default=False)
    security: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(server_default=text("CURRENT_TIMESTAMP"))

    specification: Mapped["ApiSpecification"] = relationship(back_populates="endpoints")


class TestCase(Base):
    __tablename__ = "test_cases"
    __table_args__ = (UniqueConstraint("specification_id", "generation_key", name="uq_test_case_generation_key"),)

    id: Mapped[uuid.UUID] = mapped_column(uuid_type(), primary_key=True, default=uuid.uuid4)
    specification_id: Mapped[uuid.UUID] = mapped_column(uuid_type(), ForeignKey("api_specifications.id", ondelete="CASCADE"), index=True)
    endpoint_id: Mapped[uuid.UUID] = mapped_column(uuid_type(), ForeignKey("api_endpoints.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text(), nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="MEDIUM")
    http_method: Mapped[str] = mapped_column(String(10), nullable=False)
    endpoint_path: Mapped[str] = mapped_column(String(2048), nullable=False)
    request_configuration: Mapped[dict] = mapped_column(JSON_DOCUMENT, nullable=False, default=dict)
    expected_status_codes: Mapped[list] = mapped_column(JSON_DOCUMENT, nullable=False, default=list)
    expected_response_schema: Mapped[dict | None] = mapped_column(JSON_DOCUMENT)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_generated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    generation_key: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("CURRENT_TIMESTAMP"), onupdate=text("CURRENT_TIMESTAMP"))


class TestRun(Base):
    __tablename__ = "test_runs"

    id: Mapped[uuid.UUID] = mapped_column(uuid_type(), primary_key=True, default=uuid.uuid4)
    specification_id: Mapped[uuid.UUID] = mapped_column(uuid_type(), ForeignKey("api_specifications.id", ondelete="CASCADE"), index=True)
    environment_name: Mapped[str] = mapped_column(String(100), nullable=False)
    base_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    total_tests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    passed_tests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_tests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_tests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_tests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime(), server_default=text("CURRENT_TIMESTAMP"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime())
    duration_ms: Mapped[float | None] = mapped_column(Float())


class TestResult(Base):
    __tablename__ = "test_results"

    id: Mapped[uuid.UUID] = mapped_column(uuid_type(), primary_key=True, default=uuid.uuid4)
    test_run_id: Mapped[uuid.UUID] = mapped_column(uuid_type(), ForeignKey("test_runs.id", ondelete="CASCADE"), index=True)
    test_case_id: Mapped[uuid.UUID | None] = mapped_column(uuid_type(), ForeignKey("test_cases.id", ondelete="SET NULL"), index=True)
    test_case_snapshot: Mapped[dict] = mapped_column(JSON_DOCUMENT, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    actual_status_code: Mapped[int | None] = mapped_column(Integer())
    expected_status_codes: Mapped[list] = mapped_column(JSON_DOCUMENT, nullable=False, default=list)
    response_time_ms: Mapped[float | None] = mapped_column(Float())
    request_details: Mapped[dict] = mapped_column(JSON_DOCUMENT, nullable=False, default=dict)
    response_details: Mapped[dict] = mapped_column(JSON_DOCUMENT, nullable=False, default=dict)
    validation_errors: Mapped[list] = mapped_column(JSON_DOCUMENT, nullable=False, default=list)
    error_message: Mapped[str | None] = mapped_column(Text())
    executed_at: Mapped[datetime] = mapped_column(DateTime(), server_default=text("CURRENT_TIMESTAMP"))


class CompatibilityComparison(Base):
    __tablename__ = "compatibility_comparisons"

    id: Mapped[uuid.UUID] = mapped_column(uuid_type(), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        uuid_type(), ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    old_specification_id: Mapped[uuid.UUID] = mapped_column(
        uuid_type(), ForeignKey("api_specifications.id", ondelete="CASCADE"), index=True
    )
    new_specification_id: Mapped[uuid.UUID] = mapped_column(
        uuid_type(), ForeignKey("api_specifications.id", ondelete="CASCADE"), index=True
    )
    compatibility_score: Mapped[int] = mapped_column(Integer, nullable=False)
    overall_status: Mapped[str] = mapped_column(String(30), nullable=False)
    total_changes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    breaking_changes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    non_breaking_changes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    potentially_breaking_changes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    informational_changes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    comparison_metadata: Mapped[dict] = mapped_column(JSON_DOCUMENT, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(server_default=text("CURRENT_TIMESTAMP"))
    changes: Mapped[list["CompatibilityChange"]] = relationship(
        back_populates="comparison", cascade="all, delete-orphan", order_by="CompatibilityChange.created_at"
    )


class CompatibilityChange(Base):
    __tablename__ = "compatibility_changes"

    id: Mapped[uuid.UUID] = mapped_column(uuid_type(), primary_key=True, default=uuid.uuid4)
    comparison_id: Mapped[uuid.UUID] = mapped_column(
        uuid_type(), ForeignKey("compatibility_comparisons.id", ondelete="CASCADE"), index=True
    )
    category: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    change_type: Mapped[str] = mapped_column(String(60), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    compatibility: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    path: Mapped[str | None] = mapped_column(String(2048), index=True)
    method: Mapped[str | None] = mapped_column(String(10))
    property_name: Mapped[str | None] = mapped_column(String(512))
    old_value: Mapped[dict | list | str | int | float | bool | None] = mapped_column(JSON_DOCUMENT)
    new_value: Mapped[dict | list | str | int | float | bool | None] = mapped_column(JSON_DOCUMENT)
    explanation: Mapped[str] = mapped_column(Text(), nullable=False)
    recommendation: Mapped[str] = mapped_column(Text(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=text("CURRENT_TIMESTAMP"))

    comparison: Mapped["CompatibilityComparison"] = relationship(back_populates="changes")


class MonitoringConfiguration(Base):
    __tablename__ = "monitoring_configs"
    __table_args__ = (
        UniqueConstraint("configuration_key", name="uq_monitoring_configuration_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(uuid_type(), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        uuid_type(), ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    specification_id: Mapped[uuid.UUID] = mapped_column(
        uuid_type(), ForeignKey("api_specifications.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    environment_name: Mapped[str] = mapped_column(String(100), nullable=False)
    base_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    endpoint_ids: Mapped[list] = mapped_column(JSON_DOCUMENT, nullable=False)
    configuration_key: Mapped[str] = mapped_column(String(64), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    timeout_seconds: Mapped[float] = mapped_column(Float(), nullable=False)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime())
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime())
    next_check_at: Mapped[datetime | None] = mapped_column(DateTime(), index=True)
    lease_owner: Mapped[str | None] = mapped_column(String(64))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(), index=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(
        server_default=text("CURRENT_TIMESTAMP"), onupdate=text("CURRENT_TIMESTAMP")
    )

    project: Mapped["Project"] = relationship(back_populates="monitoring_configurations")
    specification: Mapped["ApiSpecification"] = relationship(back_populates="monitoring_configurations")
    checks: Mapped[list["MonitoringCheck"]] = relationship(
        back_populates="configuration", cascade="all, delete-orphan"
    )


class MonitoringCheck(Base):
    __tablename__ = "monitoring_checks"
    __table_args__ = (
        Index("ix_monitoring_checks_project_checked_at", "project_id", "checked_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(uuid_type(), primary_key=True, default=uuid.uuid4)
    monitoring_config_id: Mapped[uuid.UUID] = mapped_column(
        uuid_type(), ForeignKey("monitoring_configs.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        uuid_type(), ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    endpoint: Mapped[str] = mapped_column(String(2048), nullable=False, index=True)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    status_code: Mapped[int | None] = mapped_column(Integer())
    latency_ms: Mapped[float | None] = mapped_column(Float())
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, index=True)
    error_category: Mapped[str | None] = mapped_column(String(30), index=True)
    error_message: Mapped[str | None] = mapped_column(String(500))
    checked_at: Mapped[datetime] = mapped_column(DateTime(), server_default=text("CURRENT_TIMESTAMP"), index=True)

    configuration: Mapped["MonitoringConfiguration"] = relationship(back_populates="checks")


class AnomalyModel(Base):
    __tablename__ = "anomaly_models"
    __table_args__ = (UniqueConstraint("project_id", name="uq_anomaly_model_project_id"),)

    id: Mapped[uuid.UUID] = mapped_column(uuid_type(), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        uuid_type(), ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    model_version: Mapped[str] = mapped_column(String(40), nullable=False)
    model_parameters: Mapped[dict] = mapped_column(JSON_DOCUMENT, nullable=False)
    training_samples: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    model_status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    trained_at: Mapped[datetime | None] = mapped_column(DateTime())
    training_data_end_at: Mapped[datetime | None] = mapped_column(DateTime())
    created_at: Mapped[datetime] = mapped_column(server_default=text("CURRENT_TIMESTAMP"))


class AnomalyDetection(Base):
    __tablename__ = "anomaly_detections"

    id: Mapped[uuid.UUID] = mapped_column(uuid_type(), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        uuid_type(), ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    monitoring_config_id: Mapped[uuid.UUID | None] = mapped_column(
        uuid_type(), ForeignKey("monitoring_configs.id", ondelete="SET NULL"), index=True
    )
    endpoint: Mapped[str] = mapped_column(String(2048), nullable=False, index=True)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    anomaly_score: Mapped[float] = mapped_column(Float(), nullable=False)
    detection_method: Mapped[str] = mapped_column(String(30), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    anomaly_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    metrics: Mapped[dict] = mapped_column(JSON_DOCUMENT, nullable=False)
    explanation: Mapped[str] = mapped_column(Text(), nullable=False)
    recommendation: Mapped[str] = mapped_column(Text(), nullable=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime(), server_default=text("CURRENT_TIMESTAMP"), index=True)
    acknowledged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)


class MonitoringAlert(Base):
    __tablename__ = "monitoring_alerts"
    __table_args__ = (
        UniqueConstraint("deduplication_key", name="uq_monitoring_alert_deduplication_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(uuid_type(), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        uuid_type(), ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    anomaly_id: Mapped[uuid.UUID | None] = mapped_column(
        uuid_type(), ForeignKey("anomaly_detections.id", ondelete="SET NULL"), index=True
    )
    monitoring_config_id: Mapped[uuid.UUID | None] = mapped_column(
        uuid_type(), ForeignKey("monitoring_configs.id", ondelete="SET NULL"), index=True
    )
    endpoint: Mapped[str | None] = mapped_column(String(2048), index=True)
    alert_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text(), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="OPEN", index=True)
    deduplication_key: Mapped[str] = mapped_column(String(255), nullable=False)
    metrics: Mapped[dict] = mapped_column(JSON_DOCUMENT, nullable=False, default=dict)
    recommendation: Mapped[str] = mapped_column(Text(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(), server_default=text("CURRENT_TIMESTAMP"), index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime())
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime())
