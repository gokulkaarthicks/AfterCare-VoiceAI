"""Check that TWILIO_WEBHOOK_BASE_URL serves TwiML from the public internet.

Usage (repo root, with .env present):

    uv run python scripts/check_twilio_tunnel.py

Exits 0 only when the smoke endpoint returns XML TwiML rather than an ngrok
warning page.
"""

from __future__ import annotations

import asyncio
import sys

import httpx

from app.agents.followup.sessions import ngrok_free_skip_warning_params
from app.shared.core.config import get_settings

SMOKE_PATH = "/webhooks/voice/twiml-smoke"


def _is_twiml(status_code: int, body: str) -> bool:
    return status_code == 200 and "<?xml" in body and "<Response>" in body


async def main() -> None:
    base = get_settings().twilio_webhook_base_url.strip().rstrip("/")
    plain_url = f"{base}{SMOKE_PATH}"
    skip_params = ngrok_free_skip_warning_params(base)
    skip_url = f"{plain_url}?ngrok-skip-browser-warning=1" if skip_params else plain_url

    print(f"Checking: {plain_url[:80]}{'…' if len(plain_url) > 80 else ''}")

    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        # Twilio sends no special headers, so the plain request is the real test.
        plain = await client.get(plain_url)
        skip = await client.get(skip_url)

    plain_body = (plain.text or "")[:500]
    skip_body = (skip.text or "")[:500]

    if _is_twiml(plain.status_code, plain_body):
        print("[PASS] Plain GET returns TwiML: Twilio can reach the webhooks.")
        sys.exit(0)

    if _is_twiml(skip.status_code, skip_body):
        print(
            "[WARN] Plain GET is not TwiML, but the ngrok skip-param URL is.\n"
            "       The app already appends that param to TwiML URLs it generates."
        )
        print(f"       status={plain.status_code} snippet={plain_body[:120]!r}")
        sys.exit(0)

    print(f"[FAIL] Expected TwiML XML. status={plain.status_code}")
    print(f"       body snippet: {plain_body[:200]!r}")
    if plain_body != skip_body:
        print(f"       (with skip param) status={skip.status_code} snippet={skip_body[:120]!r}")
    sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
