"""Persistent ContractIQ entities."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.database.connection import Base

JSON_DOCUMENT = JSON().with_variant(JSONB(), "postgresql")


def uuid_type():
    return Uuid(as_uuid=True)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(uuid_type(), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text())
    created_at: Mapped[datetime] = mapped_column(server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("CURRENT_TIMESTAMP"), onupdate=text("CURRENT_TIMESTAMP"))

    specifications: Mapped[list["ApiSpecification"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


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
