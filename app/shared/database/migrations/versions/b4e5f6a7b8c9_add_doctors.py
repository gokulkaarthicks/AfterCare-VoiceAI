"""add_doctors

Revision ID: b4e5f6a7b8c9
Revises: a3f2c1d4e5b6
Create Date: 2026-03-29 13:00:00.000000

"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "a3f2c1d4e5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DOCTORS = [
    {"id": "doc-001", "name": "Dr. Aris Thorne", "specialty": "General Surgery"},
    {"id": "doc-002", "name": "Dr. Lena Marsh", "specialty": "Internal Medicine"},
    {"id": "doc-003", "name": "Dr. Priya Raman", "specialty": "Neurosurgery"},
]


def _utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=None)


def _gen_slots_for(doctor_id: str, doctor_name: str) -> list[dict]:
    slots = []
    now = datetime.now(timezone.utc)
    days_until_monday = (7 - now.weekday()) % 7 or 7
    start_date = (now + timedelta(days=days_until_monday)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    for week in range(3):
        for day in range(5):  # Mon-Fri
            date = start_date + timedelta(weeks=week, days=day)
            for hour in range(9, 17):  # 9am-5pm
                slot_start = date.replace(hour=hour)
                slot_end = slot_start + timedelta(hours=1)
                slots.append({
                    "id": str(uuid.uuid4()),
                    "doctor_id": doctor_id,
                    "doctor_name": doctor_name,
                    "slot_start": _utc(slot_start),
                    "slot_end": _utc(slot_end),
                    "status": "available",
                    "patient_id": None,
                    "created_at": _utc(now),
                })
    return slots


def upgrade() -> None:
    now = datetime.now(timezone.utc)

    # Create doctors table
    op.create_table(
        "doctors",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("specialty", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # Seed all 3 doctors
    doctors_table = sa.table(
        "doctors",
        sa.column("id", sa.String),
        sa.column("name", sa.String),
        sa.column("specialty", sa.String),
        sa.column("created_at", sa.DateTime),
    )
    op.bulk_insert(doctors_table, [
        {
            "id": d["id"],
            "name": d["name"],
            "specialty": d["specialty"],
            "created_at": _utc(now),
        }
        for d in DOCTORS
    ])

    # Seed schedule slots for doc-002 and doc-003 (doc-001 already done in previous migration)
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
    for doc in DOCTORS[1:]:  # skip doc-001: already seeded
        op.bulk_insert(schedules_table, _gen_slots_for(doc["id"], doc["name"]))


def downgrade() -> None:
    op.drop_table("doctors")
