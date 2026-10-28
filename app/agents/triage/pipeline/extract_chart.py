"""Merge parsed note fields with explicit intake demographics."""

from __future__ import annotations

from typing import Any

from app.agents.triage.pipeline.state import TriageState


def extract_chart_data(state: TriageState) -> dict[str, Any]:
    """Build `extracted_data` (demographics, discharge, medications) for the chart.

    Explicit intake fields (name, phone, DOB, email) always win over values the
    model inferred from free text.
    """
    parsed = state.get("parsed_summary", {})
    inferred = parsed.get("demographics") or {}

    demographics = {
        "name": state.get("patient_name") or inferred.get("name") or "Unknown",
        "phone": state.get("patient_phone") or inferred.get("phone") or "",
        "dob": state.get("patient_dob") or inferred.get("dob"),
        "email": state.get("patient_email") or inferred.get("email"),
    }

    discharge = {
        "diagnosis": parsed.get("diagnosis", "Unknown"),
        "procedures": parsed.get("procedures"),
        "discharge_date": parsed.get("discharge_date"),
        "instructions": parsed.get("instructions"),
        "raw_text": state.get("raw_text", ""),
    }

    medications = parsed.get("medications") or []
    normalised_medications = [
        {
            "name": med.get("name") or "Unknown",
            "dosage": med.get("dosage") or "Unknown",
            "frequency": med.get("frequency") or "Unknown",
        }
        for med in medications
        if isinstance(med, dict)
    ]

    return {
        "extracted_data": {
            "demographics": demographics,
            "discharge": discharge,
            "medications": normalised_medications,
        }
    }
