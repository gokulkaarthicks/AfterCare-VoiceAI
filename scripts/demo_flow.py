"""Walk through the whole AfterCare loop with real services running.

1. verify every service is healthy
2. submit a discharge summary (Triage Agent intake)
3. wait for the event bus to persist it
4. confirm the chart, questionnaire, and scheduled job exist
5. trigger the outbound voice follow-up through the Scheduler

Usage (repo root, services + ngrok running):

    uv run python scripts/demo_flow.py
"""

from __future__ import annotations

import asyncio
import sys

import httpx

from app.shared.core.service_urls import (
    triage_agent_url,
    followup_agent_url,
    db_service_url,
    frontend_url,
    scheduler_url,
)
from app.shared.fixtures.discharge import SAMPLE_INTAKE_REQUEST

TRIAGE_AGENT = triage_agent_url()
FOLLOWUP_AGENT = followup_agent_url()
DB_SERVICE = db_service_url()
SCHEDULER = scheduler_url()
FRONTEND = frontend_url()

EVENT_SETTLE_SECONDS = 5


async def check_services() -> bool:
    healthchecks = {
        "Triage Agent": f"{TRIAGE_AGENT}/health",
        "Follow-up Agent": f"{FOLLOWUP_AGENT}/health",
        "DB Service": f"{DB_SERVICE}/health",
        "Scheduler": f"{SCHEDULER}/health",
    }
    ok = True
    async with httpx.AsyncClient(timeout=5.0) as client:
        for name, url in healthchecks.items():
            try:
                response = await client.get(url)
                if response.status_code == 200:
                    print(f"  [OK]   {name}")
                else:
                    print(f"  [WARN] {name} returned {response.status_code}")
                    ok = False
            except Exception:  # noqa: BLE001
                print(f"  [FAIL] {name} not reachable at {url}")
                ok = False
    return ok


async def run_intake(client: httpx.AsyncClient) -> str:
    print("\n[Step 1] Submitting a discharge summary to the Triage Agent...")
    response = await client.post(f"{TRIAGE_AGENT}/intake", json=SAMPLE_INTAKE_REQUEST)
    if response.status_code != 200:
        print(f"  [ERROR] Intake failed: {response.status_code} {response.text}")
        sys.exit(1)

    intake = response.json()
    print(f"  [OK] Patient:     {intake['patient_id']}")
    print(f"       Risk:        {intake['risk_level']}")
    print(f"       Decision:    {intake['decision']}")
    print(f"       Questions:   {len(intake.get('generated_questions', []))}")
    return intake["patient_id"]


async def show_chart(client: httpx.AsyncClient, patient_id: str) -> None:
    print("\n[Step 2] Checking the stored chart...")
    response = await client.get(f"{DB_SERVICE}/patients/{patient_id}")
    if response.status_code != 200:
        print(f"  [WARN] Patient not found yet: {response.status_code}")
        return

    patient = response.json()
    print(f"  [OK] {patient['name']}: {patient['status']}")
    print(f"       Risk: {patient['risk_level']}")
    if patient.get("discharge_summary"):
        print(f"       Diagnosis: {patient['discharge_summary']['diagnosis']}")
    print(f"       Medications: {len(patient.get('medications', []))}")
    if patient.get("questionnaire"):
        print(f"       Questionnaire: {len(patient['questionnaire'].get('questions', []))} questions")


async def show_jobs(client: httpx.AsyncClient) -> None:
    print("\n[Step 3] Checking scheduled follow-ups...")
    response = await client.get(f"{SCHEDULER}/jobs")
    if response.status_code != 200:
        print(f"  [WARN] Could not fetch jobs: {response.status_code}")
        return

    jobs = response.json()
    print(f"  [OK] {len(jobs)} job(s) scheduled")
    for job in jobs:
        print(f"       - {job['name']} @ {job['next_run_time']}")


async def trigger_call(client: httpx.AsyncClient, patient_id: str) -> None:
    print("\n[Step 4] Triggering the voice follow-up call now...")
    response = await client.post(f"{SCHEDULER}/trigger/{patient_id}")
    if response.status_code != 200:
        print(f"  [ERROR] Trigger failed: {response.status_code} {response.text}")
        return

    call = response.json().get("call") or {}
    print(f"  [OK] Call initiated: {call.get('call_sid')}")
    print(f"       voice_session_id: {call.get('voice_session_id')}")
    print("  Twilio is dialing the patient. Ensure ngrok points at :8002 and")
    print("  TWILIO_WEBHOOK_BASE_URL matches its HTTPS URL; otherwise no TwiML loads.")


async def main() -> None:
    print("=" * 60)
    print("AfterCare · end-to-end demo")
    print("=" * 60)

    print("\n[Step 0] Checking services...")
    if not await check_services():
        print("\nStart all services first (see README). Exiting.")
        sys.exit(1)

    async with httpx.AsyncClient(timeout=90.0) as client:
        patient_id = await run_intake(client)
        print(f"\n  Waiting {EVENT_SETTLE_SECONDS}s for event propagation...")
        await asyncio.sleep(EVENT_SETTLE_SECONDS)

        await show_chart(client, patient_id)
        await show_jobs(client)
        await trigger_call(client, patient_id)

    print("\n" + "=" * 60)
    print("Demo flow complete.")
    print(f"  Dashboard: {FRONTEND}")
    print(f"  Patient:   {FRONTEND}/patients/{patient_id}")
    print(f"  Alerts:    {FRONTEND}/alerts")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
