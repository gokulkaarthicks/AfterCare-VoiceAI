"""add_doctor_schedule

Revision ID: a3f2c1d4e5b6
Revises: b2c4e8a1f3d0
Create Date: 2026-03-29 12:00:00.000000

"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a3f2c1d4e5b6"
down_revision: Union[str, Sequence[str], None] = "b2c4e8a1f3d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DOCTOR_ID = "doc-001"
DOCTOR_NAME = "Dr. Aris Thorne"


def _utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=None)  # SQLite stores naive datetimes


def _gen_slots() -> list[dict]:
    """Generate Mon-Fri 9am-5pm slots (1-hour each) for the next 3 weeks."""
    slots = []
    now = datetime.now(timezone.utc)
    # Start from the next Monday
    days_until_monday = (7 - now.weekday()) % 7 or 7
    start_date = (now + timedelta(days=days_until_monday)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    for week in range(3):
        for day in range(5):  # Mon-Fri
            date = start_date + timedelta(weeks=week, days=day)
            for hour in range(9, 17):  # 9am-5pm (8 slots per day)
                slot_start = date.replace(hour=hour)
                slot_end = slot_start + timedelta(hours=1)
                slots.append({
                    "id": str(uuid.uuid4()),
                    "doctor_id": DOCTOR_ID,
                    "doctor_name": DOCTOR_NAME,
                    "slot_start": _utc(slot_start),
                    "slot_end": _utc(slot_end),
                    "status": "available",
                    "patient_id": None,
                    "created_at": _utc(now),
                })
    return slots


def upgrade() -> None:
    op.create_table(
        "doctor_schedules",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("doctor_id", sa.String(length=36), nullable=False),
        sa.Column("doctor_name", sa.String(length=255), nullable=False),
        sa.Column("slot_start", sa.DateTime(), nullable=False),
        sa.Column("slot_end", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("patient_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_doctor_schedules_status_slot_start",
        "doctor_schedules",
        ["status", "slot_start"],
    )

    op.add_column("appointments", sa.Column("doctor_id", sa.String(length=36), nullable=True))
    op.add_column("appointments", sa.Column("doctor_name", sa.String(length=255), nullable=True))

    # Seed doctor slots
    schedules_table = sa.table(
        "doctor_schedules",
        sa.column("id", sa.String),
        sa.column("doctor_id", sa.String),
        sa.column("doctor_name", sa.String),
        sa.column("slot_start", sa.DateTime),
        sa.column("slot_end", sa.DateTime),
        sa.column("status", sa.String),
        sa.column("patient_id", sa.String),
        sa.column("created_at", sa.DateTime),
    )
    op.bulk_insert(schedules_table, _gen_slots())


def downgrade() -> None:
    op.drop_index("ix_doctor_schedules_status_slot_start", table_name="doctor_schedules")
    op.drop_table("doctor_schedules")
    op.drop_column("appointments", "doctor_name")
    op.drop_column("appointments", "doctor_id")
