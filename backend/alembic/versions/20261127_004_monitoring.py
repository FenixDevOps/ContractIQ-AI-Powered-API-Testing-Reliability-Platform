"""Persist API monitoring checks, anomaly detections, and alerts."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20261127_004"
down_revision = "20261126_003"
branch_labels = None
depends_on = None

JSON_DOCUMENT = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "monitoring_configs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("specification_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("environment_name", sa.String(length=100), nullable=False),
        sa.Column("base_url", sa.String(length=2048), nullable=False),
        sa.Column("endpoint_ids", JSON_DOCUMENT, nullable=False),
        sa.Column("configuration_key", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("interval_seconds", sa.Integer(), nullable=False),
        sa.Column("timeout_seconds", sa.Float(), nullable=False),
        sa.Column("last_run_at", sa.DateTime(), nullable=True),
        sa.Column("last_success_at", sa.DateTime(), nullable=True),
        sa.Column("next_check_at", sa.DateTime(), nullable=True),
        sa.Column("lease_owner", sa.String(length=64), nullable=True),
        sa.Column("lease_until", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["specification_id"], ["api_specifications.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("configuration_key", name="uq_monitoring_configuration_key"),
    )
    op.create_index("ix_monitoring_configs_project_id", "monitoring_configs", ["project_id"])
    op.create_index("ix_monitoring_configs_specification_id", "monitoring_configs", ["specification_id"])
    op.create_index("ix_monitoring_configs_enabled", "monitoring_configs", ["enabled"])
    op.create_index("ix_monitoring_configs_next_check_at", "monitoring_configs", ["next_check_at"])
    op.create_index("ix_monitoring_configs_lease_until", "monitoring_configs", ["lease_until"])

    op.create_table(
        "monitoring_checks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("monitoring_config_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("endpoint", sa.String(length=2048), nullable=False),
        sa.Column("method", sa.String(length=10), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("error_category", sa.String(length=30), nullable=True),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("checked_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["monitoring_config_id"], ["monitoring_configs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_monitoring_checks_monitoring_config_id", "monitoring_checks", ["monitoring_config_id"])
    op.create_index("ix_monitoring_checks_project_id", "monitoring_checks", ["project_id"])
    op.create_index("ix_monitoring_checks_endpoint", "monitoring_checks", ["endpoint"])
    op.create_index("ix_monitoring_checks_success", "monitoring_checks", ["success"])
    op.create_index("ix_monitoring_checks_error_category", "monitoring_checks", ["error_category"])
    op.create_index("ix_monitoring_checks_checked_at", "monitoring_checks", ["checked_at"])
    op.create_index(
        "ix_monitoring_checks_project_checked_at", "monitoring_checks", ["project_id", "checked_at"]
    )

    op.create_table(
        "anomaly_models",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("model_version", sa.String(length=40), nullable=False),
        sa.Column("model_parameters", JSON_DOCUMENT, nullable=False),
        sa.Column("training_samples", sa.Integer(), server_default="0", nullable=False),
        sa.Column("model_status", sa.String(length=30), nullable=False),
        sa.Column("trained_at", sa.DateTime(), nullable=True),
        sa.Column("training_data_end_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", name="uq_anomaly_model_project_id"),
    )
    op.create_index("ix_anomaly_models_project_id", "anomaly_models", ["project_id"])
    op.create_index("ix_anomaly_models_model_status", "anomaly_models", ["model_status"])

    op.create_table(
        "anomaly_detections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("monitoring_config_id", sa.Uuid(), nullable=True),
        sa.Column("endpoint", sa.String(length=2048), nullable=False),
        sa.Column("method", sa.String(length=10), nullable=False),
        sa.Column("anomaly_score", sa.Float(), nullable=False),
        sa.Column("detection_method", sa.String(length=30), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("anomaly_type", sa.String(length=40), nullable=False),
        sa.Column("metrics", JSON_DOCUMENT, nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("recommendation", sa.Text(), nullable=False),
        sa.Column("detected_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("acknowledged", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["monitoring_config_id"], ["monitoring_configs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_anomaly_detections_project_id", "anomaly_detections", ["project_id"])
    op.create_index("ix_anomaly_detections_monitoring_config_id", "anomaly_detections", ["monitoring_config_id"])
    op.create_index("ix_anomaly_detections_endpoint", "anomaly_detections", ["endpoint"])
    op.create_index("ix_anomaly_detections_severity", "anomaly_detections", ["severity"])
    op.create_index("ix_anomaly_detections_anomaly_type", "anomaly_detections", ["anomaly_type"])
    op.create_index("ix_anomaly_detections_detected_at", "anomaly_detections", ["detected_at"])
    op.create_index("ix_anomaly_detections_acknowledged", "anomaly_detections", ["acknowledged"])

    op.create_table(
        "monitoring_alerts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("anomaly_id", sa.Uuid(), nullable=True),
        sa.Column("monitoring_config_id", sa.Uuid(), nullable=True),
        sa.Column("endpoint", sa.String(length=2048), nullable=True),
        sa.Column("alert_type", sa.String(length=40), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="OPEN", nullable=False),
        sa.Column("deduplication_key", sa.String(length=255), nullable=False),
        sa.Column("metrics", JSON_DOCUMENT, nullable=False),
        sa.Column("recommendation", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["anomaly_id"], ["anomaly_detections.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["monitoring_config_id"], ["monitoring_configs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("deduplication_key", name="uq_monitoring_alert_deduplication_key"),
    )
    op.create_index("ix_monitoring_alerts_project_id", "monitoring_alerts", ["project_id"])
    op.create_index("ix_monitoring_alerts_anomaly_id", "monitoring_alerts", ["anomaly_id"])
    op.create_index("ix_monitoring_alerts_monitoring_config_id", "monitoring_alerts", ["monitoring_config_id"])
    op.create_index("ix_monitoring_alerts_endpoint", "monitoring_alerts", ["endpoint"])
    op.create_index("ix_monitoring_alerts_alert_type", "monitoring_alerts", ["alert_type"])
    op.create_index("ix_monitoring_alerts_severity", "monitoring_alerts", ["severity"])
    op.create_index("ix_monitoring_alerts_status", "monitoring_alerts", ["status"])
    op.create_index("ix_monitoring_alerts_created_at", "monitoring_alerts", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_monitoring_alerts_created_at", table_name="monitoring_alerts")
    op.drop_index("ix_monitoring_alerts_status", table_name="monitoring_alerts")
    op.drop_index("ix_monitoring_alerts_severity", table_name="monitoring_alerts")
    op.drop_index("ix_monitoring_alerts_alert_type", table_name="monitoring_alerts")
    op.drop_index("ix_monitoring_alerts_endpoint", table_name="monitoring_alerts")
    op.drop_index("ix_monitoring_alerts_monitoring_config_id", table_name="monitoring_alerts")
    op.drop_index("ix_monitoring_alerts_anomaly_id", table_name="monitoring_alerts")
    op.drop_index("ix_monitoring_alerts_project_id", table_name="monitoring_alerts")
    op.drop_table("monitoring_alerts")
    op.drop_index("ix_anomaly_detections_acknowledged", table_name="anomaly_detections")
    op.drop_index("ix_anomaly_detections_detected_at", table_name="anomaly_detections")
    op.drop_index("ix_anomaly_detections_anomaly_type", table_name="anomaly_detections")
    op.drop_index("ix_anomaly_detections_severity", table_name="anomaly_detections")
    op.drop_index("ix_anomaly_detections_endpoint", table_name="anomaly_detections")
    op.drop_index("ix_anomaly_detections_monitoring_config_id", table_name="anomaly_detections")
    op.drop_index("ix_anomaly_detections_project_id", table_name="anomaly_detections")
    op.drop_table("anomaly_detections")
    op.drop_index("ix_anomaly_models_model_status", table_name="anomaly_models")
    op.drop_index("ix_anomaly_models_project_id", table_name="anomaly_models")
    op.drop_table("anomaly_models")
    op.drop_index("ix_monitoring_checks_project_checked_at", table_name="monitoring_checks")
    op.drop_index("ix_monitoring_checks_checked_at", table_name="monitoring_checks")
    op.drop_index("ix_monitoring_checks_error_category", table_name="monitoring_checks")
    op.drop_index("ix_monitoring_checks_success", table_name="monitoring_checks")
    op.drop_index("ix_monitoring_checks_endpoint", table_name="monitoring_checks")
    op.drop_index("ix_monitoring_checks_project_id", table_name="monitoring_checks")
    op.drop_index("ix_monitoring_checks_monitoring_config_id", table_name="monitoring_checks")
    op.drop_table("monitoring_checks")
    op.drop_index("ix_monitoring_configs_lease_until", table_name="monitoring_configs")
    op.drop_index("ix_monitoring_configs_next_check_at", table_name="monitoring_configs")
    op.drop_index("ix_monitoring_configs_enabled", table_name="monitoring_configs")
    op.drop_index("ix_monitoring_configs_specification_id", table_name="monitoring_configs")
    op.drop_index("ix_monitoring_configs_project_id", table_name="monitoring_configs")
    op.drop_table("monitoring_configs")
