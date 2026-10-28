"""Follow-up Agent: the patient-facing voice service.

Only two LLM-backed agents exist in AfterCare: the Triage Agent (clinical
reasoning) and this Follow-up Agent (understanding and speaking). This
package owns the phone dialogue, speech interpretation, Redis call sessions,
and outbound dialing. The FastAPI surface lives in `app.api.followup`.

Layout:
  dialogs/                 phone dialogue (follow-up questionnaire, booking, dialing)
  speech/                  LLM speech interpretation + ElevenLabs TTS
  sessions.py              Redis voice/appointment session keys and webhook URLs
  voice.py                 Twilio call creation and TwiML helpers
  db_client.py             HTTP client for the DB service
"""

SERVICE_NAME = "followup_agent"
SERVICE_PORT = 8002
