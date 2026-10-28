"""Fictional clinician roster used by seeding, login, and scheduling.

All names, phone numbers, and addresses are synthetic. IDs (`doc-001` … `doc-004`)
are stable because appointments and schedule slots reference them; only the
display name and specialty may change.
"""

from __future__ import annotations

from typing import TypedDict


class DemoDoctor(TypedDict):
    id: str
    name: str
    specialty: str
    initials: str


DEMO_DOCTORS: list[DemoDoctor] = [
    {
        "id": "doc-001",
        "name": "Dr. Aris Thorne",
        "specialty": "General Surgery",
        "initials": "AT",
    },
    {
        "id": "doc-002",
        "name": "Dr. Lena Marsh",
        "specialty": "Internal Medicine",
        "initials": "LM",
    },
    {
        "id": "doc-003",
        "name": "Dr. Priya Raman",
        "specialty": "Neurosurgery",
        "initials": "PR",
    },
    {
        "id": "doc-004",
        "name": "Dr. Owen Castellano",
        "specialty": "Cardiology",
        "initials": "OC",
    },
]

DEMO_DOCTORS_BY_ID: dict[str, DemoDoctor] = {doctor["id"]: doctor for doctor in DEMO_DOCTORS}
