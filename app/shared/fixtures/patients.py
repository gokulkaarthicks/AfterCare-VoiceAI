"""Fictional patient charts seeded into an empty database.

Single source of truth for demo patient IDs, demographics, discharge notes,
medications, questionnaires, and appointment stubs. Every name, phone number,
email, and ward is synthetic (555 exchange / example.com). Pass
`existing_patient_id` to `POST /intake` to refresh one of these charts in place
instead of minting a new patient.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.shared.clinical.questionnaire import APPOINTMENT_CONSENT_QUESTION

_APPOINTMENT_BASE = datetime(2026, 4, 5, 14, 30, tzinfo=timezone.utc)

DEMO_PATIENTS: list[dict[str, Any]] = [
    {
        "id": "MRN-10001",
        "name": "Elena Whitfield",
        "dob": "1983-06-12",
        "phone": "+15550102001",
        "email": "elena.whitfield@example.com",
        "status": "Stable",
        "risk_level": "high",
        "discharge_summary": {
            "diagnosis": "Traumatic brain injury (concussion) with brief LOC, now monitoring in ICU",
            "procedures": "CT head without contrast; neuro checks q2h; ICP monitoring per protocol.",
            "discharge_date": "2026-03-27",
            "instructions": "Neuro follow-up in 1 week; avoid contact sports; return for worsening headache, vomiting, or confusion.",
            "raw_text": """DISCHARGE SUMMARY
Patient: Elena Whitfield
DOB: 1983-06-12
Phone: +15550102001

Admission: 2026-03-22  Discharge: 2026-03-27
Primary diagnosis: Traumatic brain injury (concussion) with brief loss of consciousness

Hospital course: Patient struck head during fall; GCS 14 on arrival. Imaging negative for acute bleed.
Neurology consulted; symptoms improved with rest and medication optimization.

Discharge medications:
- Acetaminophen 650 mg PO q6h PRN pain
- Ondansetron 4 mg PO q8h PRN nausea

Follow-up: Neurosurgery clinic in 7 days; return to ED for red flags.
""",
        },
        "medications": [
            {"name": "Acetaminophen", "dosage": "650 mg", "frequency": "q6h PRN"},
            {"name": "Ondansetron", "dosage": "4 mg", "frequency": "q8h PRN"},
        ],
        "questionnaire": {
            "diagnosis_context": "Post-concussion follow-up",
            "questions": [
                {
                    "id": "q1",
                    "text": "Have you had any new or worsening headaches since discharge?",
                    "question_type": "yes_no",
                    "relevance": "high",
                },
                {
                    "id": "q2",
                    "text": "Any nausea, vomiting, or vision changes?",
                    "question_type": "yes_no",
                    "relevance": "high",
                },
            ],
        },
        "appointments": [
            {
                "appointment_type": "Neurosurgery follow-up",
                "scheduled_at": _APPOINTMENT_BASE,
                "status": "scheduled",
                "notes": "Bring medication list; ICU-3 discharge.",
            }
        ],
    },
    {
        "id": "MRN-10002",
        "name": "Marcus Delgado",
        "dob": "1985-11-03",
        "phone": "+15550102002",
        "email": "marcus.delgado@example.com",
        "status": "Discharged",
        "risk_level": "low",
        "discharge_summary": {
            "diagnosis": "Heart failure with reduced ejection fraction (HFrEF), compensated",
            "procedures": "Echocardiogram; diuresis; medication optimization.",
            "discharge_date": "2026-03-25",
            "instructions": "Low-sodium diet; daily weights; cardiology in 2 weeks.",
            "raw_text": """DISCHARGE SUMMARY
Patient: Marcus Delgado
Phone: +15550102002

Primary diagnosis: Heart failure with reduced ejection fraction

Hospital course: Volume overload treated with IV diuresis; EF 35% on echo. Patient educated on fluid restriction.

Discharge medications:
- Furosemide 40 mg daily
- Carvedilol 12.5 mg BID
- Lisinopril 10 mg daily

Follow-up: Cardiology outpatient.
""",
        },
        "medications": [
            {"name": "Furosemide", "dosage": "40 mg", "frequency": "daily"},
            {"name": "Carvedilol", "dosage": "12.5 mg", "frequency": "BID"},
            {"name": "Lisinopril", "dosage": "10 mg", "frequency": "daily"},
        ],
        "questionnaire": {
            "diagnosis_context": "Heart failure symptom check-in",
            "questions": [
                {
                    "id": "q1",
                    "text": "Any increased shortness of breath or swelling in your legs?",
                    "question_type": "yes_no",
                    "relevance": "high",
                },
                {
                    "id": "q2",
                    "text": "Are you taking all prescribed medications as directed?",
                    "question_type": "yes_no",
                    "relevance": "medium",
                },
                {**APPOINTMENT_CONSENT_QUESTION},
            ],
        },
        "appointments": [
            {
                "appointment_type": "Cardiology",
                "scheduled_at": _APPOINTMENT_BASE.replace(day=8),
                "status": "scheduled",
                "notes": "Post-discharge, ward R-18.",
            }
        ],
    },
    {
        "id": "MRN-10003",
        "name": "Priya Nandakumar",
        "dob": "1959-01-20",
        "phone": "+15550102003",
        "email": "priya.nandakumar@example.com",
        "status": "Recovering",
        "risk_level": "medium",
        "discharge_summary": {
            "diagnosis": "Community-acquired pneumonia (CAP), improving on antibiotics",
            "procedures": "Supplemental oxygen wean; IV to oral antibiotic transition.",
            "discharge_date": "2026-03-28",
            "instructions": "Complete antibiotic course; pulmonary follow-up; return if fever or worsening breathing.",
            "raw_text": """DISCHARGE SUMMARY
Patient: Priya Nandakumar
DOB: 1959-01-20
Phone: +15550102003
Email: priya.nandakumar@example.com

Admission: 2026-03-20  Discharge: 2026-03-28
Primary diagnosis: Community-acquired pneumonia (CAP)

Hospital course: Patient admitted with fever, productive cough, and hypoxia. Treated with ceftriaxone and azithromycin with good response. Oxygen weaned to room air.

Discharge medications:
- Amoxicillin-clavulanate 875/125 mg BID to complete 7-day course
- Albuterol inhaler 2 puffs q4-6h PRN wheeze

Follow-up: Primary care in 1 week; pulmonology if symptoms persist.
Attending: Dr. Lena Marsh
""",
        },
        "medications": [
            {
                "name": "Amoxicillin-clavulanate",
                "dosage": "875/125 mg",
                "frequency": "BID",
            },
            {"name": "Albuterol", "dosage": "90 mcg", "frequency": "q4-6h PRN"},
        ],
        "questionnaire": {
            "diagnosis_context": "Post-pneumonia recovery",
            "questions": [
                {
                    "id": "q1",
                    "text": "Are you still having cough or fever?",
                    "question_type": "yes_no",
                    "relevance": "high",
                },
                {
                    "id": "q2",
                    "text": "Can you complete daily activities without getting winded?",
                    "question_type": "yes_no",
                    "relevance": "medium",
                },
                {**APPOINTMENT_CONSENT_QUESTION},
            ],
        },
        "appointments": [
            {
                "appointment_type": "Primary care follow-up",
                "scheduled_at": _APPOINTMENT_BASE.replace(day=12),
                "status": "scheduled",
                "notes": "G-12 / Bed A",
            }
        ],
    },
    {
        "id": "MRN-10004",
        "name": "Samuel Okafor",
        "dob": "1939-04-08",
        "phone": "+15550102004",
        "email": None,
        "status": "Stable",
        "risk_level": "low",
        "discharge_summary": {
            "diagnosis": "Post-operative recovery after elective procedure, stable",
            "procedures": "Wound care; PT evaluation; pain control.",
            "discharge_date": "2026-03-26",
            "instructions": "Wound checks; DVT prophylaxis per protocol; PT home exercises.",
            "raw_text": """DISCHARGE SUMMARY
Patient: Samuel Okafor
Phone: +15550102004

Primary diagnosis: Post-operative recovery: stable

Hospital course: Recovering well from procedure; ambulating with assistance; pain controlled with oral analgesics.

Discharge medications:
- Acetaminophen 650 mg q6h PRN
- Enoxaparin 40 mg SQ daily (per protocol)

Follow-up: Surgical clinic; physical therapy as arranged.
""",
        },
        "medications": [
            {"name": "Acetaminophen", "dosage": "650 mg", "frequency": "q6h PRN"},
            {"name": "Enoxaparin", "dosage": "40 mg", "frequency": "daily SQ"},
        ],
        "questionnaire": {
            "diagnosis_context": "Post-operative wellness",
            "questions": [
                {
                    "id": "q1",
                    "text": "Any increased pain or redness at the surgical site?",
                    "question_type": "yes_no",
                    "relevance": "high",
                },
                {**APPOINTMENT_CONSENT_QUESTION},
            ],
        },
        "appointments": [
            {
                "appointment_type": "Surgical follow-up",
                "scheduled_at": _APPOINTMENT_BASE.replace(day=15),
                "status": "scheduled",
                "notes": "Ward R-14",
            }
        ],
    },
    {
        "id": "MRN-10005",
        "name": "Hannah Lindqvist",
        "dob": "1998-02-14",
        "phone": "+15550102005",
        "email": None,
        "status": "Stable",
        "risk_level": "low",
        "discharge_summary": {
            "diagnosis": "Post-operative recovery, monitored in ICU step-down",
            "procedures": "Continuous monitoring; IV fluids titrated; early mobilization when safe.",
            "discharge_date": "2026-03-29",
            "instructions": "Gradual activity increase; wound care instructions provided; return for fever or drainage.",
            "raw_text": """DISCHARGE SUMMARY
Patient: Hannah Lindqvist
Phone: +15550102005

Primary diagnosis: Post-operative recovery

Hospital course: Patient stable for transfer from ICU-9; vitals trending normal; tolerating diet.

Discharge medications:
- Ibuprofen 400 mg q8h PRN pain
- Omeprazole 20 mg daily

Follow-up: Surgery/primary care as scheduled.
""",
        },
        "medications": [
            {"name": "Ibuprofen", "dosage": "400 mg", "frequency": "q8h PRN"},
            {"name": "Omeprazole", "dosage": "20 mg", "frequency": "daily"},
        ],
        "questionnaire": {
            "diagnosis_context": "Post-operative check-in",
            "questions": [
                {
                    "id": "q1",
                    "text": "Any fever, chills, or wound drainage?",
                    "question_type": "yes_no",
                    "relevance": "high",
                },
                {**APPOINTMENT_CONSENT_QUESTION},
            ],
        },
        "appointments": [
            {
                "appointment_type": "Clinic follow-up",
                "scheduled_at": _APPOINTMENT_BASE.replace(day=18),
                "status": "scheduled",
                "notes": "ICU-9",
            }
        ],
    },
]
