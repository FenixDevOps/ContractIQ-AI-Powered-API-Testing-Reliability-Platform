"""Add test cases, runs, and results without altering Stage 2 records."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy import inspect
from sqlalchemy.exc import NoInspectionAvailable

revision = "20261121_002"
down_revision = "20261121_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    try:
        if "test_cases" in inspect(op.get_bind()).get_table_names():
            return
    except NoInspectionAvailable:
        pass
    op.create_table(
        "test_cases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("specification_id", sa.Uuid(), nullable=False),
        sa.Column("endpoint_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("priority", sa.String(20), nullable=False),
        sa.Column("http_method", sa.String(10), nullable=False),
        sa.Column("endpoint_path", sa.String(2048), nullable=False),
        sa.Column("request_configuration", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=False),
        sa.Column("expected_status_codes", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=False),
        sa.Column("expected_response_schema", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("is_generated", sa.Boolean(), nullable=False),
        sa.Column("generation_key", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["specification_id"], ["api_specifications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["endpoint_id"], ["api_endpoints.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("specification_id", "generation_key", name="uq_test_case_generation_key"),
    )
    op.create_index("ix_test_cases_specification_id", "test_cases", ["specification_id"])
    op.create_index("ix_test_cases_endpoint_id", "test_cases", ["endpoint_id"])
    op.create_table(
        "test_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("specification_id", sa.Uuid(), nullable=False),
        sa.Column("environment_name", sa.String(100), nullable=False),
        sa.Column("base_url", sa.String(2048), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("total_tests", sa.Integer(), nullable=False),
        sa.Column("passed_tests", sa.Integer(), nullable=False),
        sa.Column("failed_tests", sa.Integer(), nullable=False),
        sa.Column("skipped_tests", sa.Integer(), nullable=False),
        sa.Column("error_tests", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("duration_ms", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["specification_id"], ["api_specifications.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_test_runs_specification_id", "test_runs", ["specification_id"])
    op.create_table(
        "test_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("test_run_id", sa.Uuid(), nullable=False),
        sa.Column("test_case_id", sa.Uuid(), nullable=True),
        sa.Column("test_case_snapshot", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("actual_status_code", sa.Integer(), nullable=True),
        sa.Column("expected_status_codes", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=False),
        sa.Column("response_time_ms", sa.Float(), nullable=True),
        sa.Column("request_details", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=False),
        sa.Column("response_details", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=False),
        sa.Column("validation_errors", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("executed_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["test_run_id"], ["test_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["test_case_id"], ["test_cases.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_test_results_test_run_id", "test_results", ["test_run_id"])
    op.create_index("ix_test_results_test_case_id", "test_results", ["test_case_id"])


def downgrade() -> None:
    op.drop_index("ix_test_results_test_case_id", table_name="test_results")
    op.drop_index("ix_test_results_test_run_id", table_name="test_results")
    op.drop_table("test_results")
    op.drop_index("ix_test_runs_specification_id", table_name="test_runs")
    op.drop_table("test_runs")
    op.drop_index("ix_test_cases_endpoint_id", table_name="test_cases")
    op.drop_index("ix_test_cases_specification_id", table_name="test_cases")
    op.drop_table("test_cases")
