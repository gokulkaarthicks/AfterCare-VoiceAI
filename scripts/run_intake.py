"""Submit a discharge summary to the Triage Agent and print the intake result.

Usage (repo root, services running):

    uv run python scripts/run_intake.py
"""

from __future__ import annotations

import asyncio
import sys

import httpx

from app.shared.core.service_urls import triage_agent_url
from app.shared.fixtures.discharge import SAMPLE_INTAKE_REQUEST

CARE_AGENT = triage_agent_url()


async def main() -> None:
    print("=" * 60)
    print("AfterCare · sample discharge intake")
    print("=" * 60)

    async with httpx.AsyncClient(timeout=90.0) as client:
        print("\n[1] Posting discharge summary to the Triage Agent...")
        response = await client.post(f"{CARE_AGENT}/intake", json=SAMPLE_INTAKE_REQUEST)

    if response.status_code != 200:
        print(f"\n[ERROR] {response.status_code}: {response.text}")
        sys.exit(1)

    data = response.json()
    print(f"\n[OK] Patient created: {data['patient_id']}")
    print(f"     Risk level:  {data['risk_level']}")
    print(f"     Decision:    {data['decision']}")
    print(f"     Questions:   {len(data.get('generated_questions', []))}")
    print(f"     Correlation: {data['correlation_id']}")

    if data.get("generated_questions"):
        print("\n     Generated follow-up questions:")
        for question in data["generated_questions"]:
            kind = question.get("question_type", "open")
            print(f"       - [{kind}] {question.get('text', '')}")

    print(f"\n[INFO] Patient ID: {data['patient_id']}")
    print("       Use this id with scripts/trigger_followup.py or the dashboard.")


if __name__ == "__main__":
    asyncio.run(main())
