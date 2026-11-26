"""Persist compatibility comparisons and detected changes."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20261126_003"
down_revision = "20261121_002"
branch_labels = None
depends_on = None

JSON_DOCUMENT = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "compatibility_comparisons",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("old_specification_id", sa.Uuid(), nullable=False),
        sa.Column("new_specification_id", sa.Uuid(), nullable=False),
        sa.Column("compatibility_score", sa.Integer(), nullable=False),
        sa.Column("overall_status", sa.String(length=30), nullable=False),
        sa.Column("total_changes", sa.Integer(), nullable=False),
        sa.Column("breaking_changes", sa.Integer(), nullable=False),
        sa.Column("non_breaking_changes", sa.Integer(), nullable=False),
        sa.Column("potentially_breaking_changes", sa.Integer(), nullable=False),
        sa.Column("informational_changes", sa.Integer(), nullable=False),
        sa.Column("comparison_metadata", JSON_DOCUMENT, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["old_specification_id"], ["api_specifications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["new_specification_id"], ["api_specifications.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_compatibility_comparisons_project_id", "compatibility_comparisons", ["project_id"])
    op.create_index("ix_compatibility_comparisons_old_specification_id", "compatibility_comparisons", ["old_specification_id"])
    op.create_index("ix_compatibility_comparisons_new_specification_id", "compatibility_comparisons", ["new_specification_id"])
    op.create_table(
        "compatibility_changes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("comparison_id", sa.Uuid(), nullable=False),
        sa.Column("category", sa.String(length=30), nullable=False),
        sa.Column("change_type", sa.String(length=60), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("compatibility", sa.String(length=30), nullable=False),
        sa.Column("path", sa.String(length=2048), nullable=True),
        sa.Column("method", sa.String(length=10), nullable=True),
        sa.Column("property_name", sa.String(length=512), nullable=True),
        sa.Column("old_value", JSON_DOCUMENT, nullable=True),
        sa.Column("new_value", JSON_DOCUMENT, nullable=True),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("recommendation", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["comparison_id"], ["compatibility_comparisons.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_compatibility_changes_comparison_id", "compatibility_changes", ["comparison_id"])
    op.create_index("ix_compatibility_changes_category", "compatibility_changes", ["category"])
    op.create_index("ix_compatibility_changes_severity", "compatibility_changes", ["severity"])
    op.create_index("ix_compatibility_changes_compatibility", "compatibility_changes", ["compatibility"])
    op.create_index("ix_compatibility_changes_path", "compatibility_changes", ["path"])


def downgrade() -> None:
    op.drop_index("ix_compatibility_changes_path", table_name="compatibility_changes")
    op.drop_index("ix_compatibility_changes_compatibility", table_name="compatibility_changes")
    op.drop_index("ix_compatibility_changes_severity", table_name="compatibility_changes")
    op.drop_index("ix_compatibility_changes_category", table_name="compatibility_changes")
    op.drop_index("ix_compatibility_changes_comparison_id", table_name="compatibility_changes")
    op.drop_table("compatibility_changes")
    op.drop_index("ix_compatibility_comparisons_new_specification_id", table_name="compatibility_comparisons")
    op.drop_index("ix_compatibility_comparisons_old_specification_id", table_name="compatibility_comparisons")
    op.drop_index("ix_compatibility_comparisons_project_id", table_name="compatibility_comparisons")
    op.drop_table("compatibility_comparisons")
