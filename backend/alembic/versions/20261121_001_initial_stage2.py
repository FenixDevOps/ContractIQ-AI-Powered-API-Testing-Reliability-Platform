"""Create Stage 2 projects and specification tables."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.exc import NoInspectionAvailable

revision = "20261121_001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    try:
        if "projects" in inspect(op.get_bind()).get_table_names():
            return
    except NoInspectionAvailable:
        pass
    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "api_specifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("openapi_version", sa.String(length=20), nullable=False),
        sa.Column("api_version", sa.String(length=100), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("file_format", sa.String(length=10), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("raw_specification", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("imported_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "version_number", name="uq_project_spec_version"),
    )
    op.create_index("ix_api_specifications_project_id", "api_specifications", ["project_id"])
    op.create_index("ix_api_specifications_content_hash", "api_specifications", ["content_hash"])
    op.create_table(
        "api_endpoints",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("specification_id", sa.Uuid(), nullable=False),
        sa.Column("path", sa.String(length=2048), nullable=False),
        sa.Column("method", sa.String(length=10), nullable=False),
        sa.Column("operation_id", sa.String(length=255), nullable=True),
        sa.Column("summary", sa.String(length=500), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("request_body", sa.JSON(), nullable=True),
        sa.Column("responses", sa.JSON(), nullable=False),
        sa.Column("deprecated", sa.Boolean(), nullable=False),
        sa.Column("security", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["specification_id"], ["api_specifications.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("specification_id", "path", "method", name="uq_spec_endpoint"),
    )
    op.create_index("ix_api_endpoints_specification_id", "api_endpoints", ["specification_id"])


def downgrade() -> None:
    op.drop_index("ix_api_endpoints_specification_id", table_name="api_endpoints")
    op.drop_table("api_endpoints")
    op.drop_index("ix_api_specifications_content_hash", table_name="api_specifications")
    op.drop_index("ix_api_specifications_project_id", table_name="api_specifications")
    op.drop_table("api_specifications")
    op.drop_table("projects")
