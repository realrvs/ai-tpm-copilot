"""initial schema

Revision ID: f4e5d9f9ebc0
Revises: 
Create Date: 2026-11-14 10:52:30.090114

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f4e5d9f9ebc0"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the reports table with all required columns and indexes."""
    op.create_table(
        "reports",
        sa.Column("report_id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("repo", sa.String(length=255), nullable=False),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("token_usage", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pii_redacted_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("markdown", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("error", sa.Text(), nullable=True),
    )
    op.create_index(op.f("ix_reports_report_id"), "reports", ["report_id"], unique=False)
    op.create_index(op.f("ix_reports_repo"), "reports", ["repo"], unique=False)
    op.create_index(op.f("ix_reports_generated_at"), "reports", ["generated_at"], unique=False)


def downgrade() -> None:
    """Drop the reports table."""
    op.drop_index(op.f("ix_reports_generated_at"), table_name="reports")
    op.drop_index(op.f("ix_reports_repo"), table_name="reports")
    op.drop_index(op.f("ix_reports_report_id"), table_name="reports")
    op.drop_table("reports")
