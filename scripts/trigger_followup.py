"""Trigger a follow-up call for a patient right now.

Usage:

    uv run python scripts/trigger_followup.py <patient_id>
"""

from __future__ import annotations

import asyncio
import sys

import httpx

from app.shared.core.service_urls import db_service_url, scheduler_url

SCHEDULER = scheduler_url()
DB_SERVICE = db_service_url()


async def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/trigger_followup.py <patient_id>")
        print("\nFind patient ids with:")
        print(f"  curl {DB_SERVICE}/patients")
        sys.exit(1)

    patient_id = sys.argv[1]

    async with httpx.AsyncClient(timeout=30.0) as client:
        print(f"Looking up patient {patient_id}...")
        patient_response = await client.get(f"{DB_SERVICE}/patients/{patient_id}")
        if patient_response.status_code != 200:
            print(f"Patient not found: {patient_response.status_code}")
            sys.exit(1)

        patient = patient_response.json()
        print(f"Patient: {patient['name']} ({patient['phone']})")
        print(f"Risk:    {patient.get('risk_level', 'unknown')}")

        print("\nTriggering the AI voice follow-up call...")
        trigger_response = await client.post(f"{SCHEDULER}/trigger/{patient_id}")

    if trigger_response.status_code != 200:
        print(f"[ERROR] {trigger_response.status_code}: {trigger_response.text}")
        return

    print(f"[OK] {trigger_response.json()}")
    print(f"\nOutbound call initiated to {patient['phone']}.")
    print("The Follow-up Agent asks the condition-specific questions and")
    print("interprets each spoken answer; the Triage Agent then decides the next step.")


if __name__ == "__main__":
    asyncio.run(main())
