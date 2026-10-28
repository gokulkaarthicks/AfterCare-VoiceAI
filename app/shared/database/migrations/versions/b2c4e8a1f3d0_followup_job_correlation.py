"""followup_job correlation and completed_at

Revision ID: b2c4e8a1f3d0
Revises: 97ec1ad9d5d8
Create Date: 2026-03-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2c4e8a1f3d0"
down_revision: Union[str, Sequence[str], None] = "97ec1ad9d5d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "followup_jobs",
        sa.Column("correlation_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "followup_jobs",
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_followup_jobs_correlation_id",
        "followup_jobs",
        ["correlation_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_followup_jobs_correlation_id", table_name="followup_jobs")
    op.drop_column("followup_jobs", "completed_at")
    op.drop_column("followup_jobs", "correlation_id")
