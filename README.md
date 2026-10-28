# AfterCare - Voice AI

**AI discharge follow-up for hospital care teams.** When a patient goes home,
AfterCare reads the discharge summary, builds a personalised check-in script,
phones the patient, understands their spoken answers, and escalates anything
clinically concerning to the right person, then books a clinician appointment
if one is needed.

> **There are exactly two AI agents in AfterCare:**
>
> | Agent | Role | Folder |
> | --- | --- | --- |
> | **Triage Agent** | Clinical reasoning. Parses the discharge note, scores risk, writes the questionnaire, interprets follow-up answers, and decides what to do next through tool calls. | `app/agents/triage/` + `app/api/triage.py` |
> | **Follow-up Agent** | Voice dialogue. Speaks to the patient over Twilio, understands free-form speech, and runs the booking conversation. | `app/agents/followup/` + `app/api/followup.py` |
>
> Everything else is ordinary software: the DB service persists data, the
> Scheduler times the calls, and RabbitMQ/Redis move messages and call state.
> Neither of those services contains an LLM.

---

## Contents

- [How it works](#how-it-works)
- [The two agents](#the-two-agents)
  - [Triage Agent](#triage-agent)
  - [Follow-up Agent](#follow-up-agent)
- [Event flow](#event-flow)
- [Repository layout](#repository-layout)
- [Running locally](#running-locally)
- [Running with Docker](#running-with-docker)
- [Connecting Twilio](#connecting-twilio)
- [Configuration](#configuration)
- [HTTP API reference](#http-api-reference)
- [Demo scripts](#demo-scripts)
- [Demo data](#demo-data)
- [Testing](#testing)

---

## How it works

```
 Discharge note                  ┌─────────────────┐
 (PDF / text) ──────────────────►│   Triage Agent    │
                                 │  pipeline + act │
                                 └────────┬────────┘
                                          │ patient_state_upsert / alert_event /
                                          │ schedule_event
                                   ┌──────▼──────┐
                                   │  RabbitMQ   │
                                   └──────┬──────┘
              ┌────────────────────────────┼───────────────────────────┐
              │                            │                           │
        ┌─────▼──────┐              ┌──────▼──────┐             ┌──────▼──────┐
        │ DB Service │              │  Scheduler  │             │ Next.js     │
        │  (SQLite)  │              │ APScheduler │             │ dashboard   │
        └─────▲──────┘              └──────┬──────┘             └─────────────┘
              │                            │ initiate-call
              │      ┌─────────────────────▼──────────────────┐
              └──────┤        Follow-up Agent             │◄──── Twilio
                     │  TwiML webhooks · speech · ElevenLabs  │      (voice)
                     └─────────────────────┬──────────────────┘
                                           │ patient_response_event
                                           ▼
                                     back to Triage Agent
```

1. **Intake**: a clinician uploads a discharge summary. The Triage Agent parses
   it, extracts the chart, scores post-discharge risk, and writes two
   condition-specific questions plus an appointment-consent question.
2. **Persist & schedule**: the triage tool loop saves the chart, raises an
   alert when risk is high, and schedules the first check-in call.
3. **Call**: at the scheduled time the Scheduler asks the Follow-up Agent to
   dial the patient. Twilio streams TwiML; the Follow-up Agent speaks each
   question (ElevenLabs, or Polly as a fallback) and interprets the answer.
4. **Interpret**: on the last question the patient is asked whether they want
   an appointment. If yes, booking continues on the same call with real slots.
5. **React**: the answers go back to the Triage Agent, which analyses them and
   decides: stay stable, schedule another call, alert the care team, or book a
   clinician visit.
6. **Dashboard**: the care team sees patients, risk levels, alerts, call
   transcripts, appointments, and a per-patient timeline in the Next.js app.

---

## The two agents

### Triage Agent

`app/agents/triage/` + `app/api/triage.py`: FastAPI on **port 8001**.

**Pipeline** (`pipeline/`): deterministic, temperature-0 LLM calls wrapped in
plain LangGraph nodes. Each node has a safe fallback so a model outage degrades
gracefully instead of losing the intake.

| Node | File | What it produces |
| --- | --- | --- |
| Parse discharge note | `parse_discharge.py` | Diagnosis, procedures, medications, dates, instructions |
| Extract chart | `extract_chart.py` | Merges the parsed note with the demographics the caller supplied |
| Score risk | `score_risk.py` | `low` / `medium` / `high` / `critical` plus risk factors |
| Build questionnaire | `build_questionnaire.py` | Two tailored questions, then the appointment-consent item |
| Analyse responses | `analyse_responses.py` | Per-answer concern levels, red flags, overall concern |

**Triage tool loop** (`act/`): the agentic half. A ReAct loop (reason → call a tool →
observe, up to six turns) decides which *side effects* to perform:

| Tool | Effect |
| --- | --- |
| `save_patient_discharge` | Persist the parsed chart (intake only, exactly once) |
| `create_clinical_alert` | Raise a dashboard alert for the care team |
| `schedule_voice_followup` | Queue another automated check-in |
| `request_appointment` | Ask the Follow-up Agent to book a clinician visit |
| `get_patient_context` | Read the current chart (post-call only, read-only) |

Tools return intent dictionaries; `act/tool_actions.py` converts them into
events and `publisher.py` is the single place that talks to RabbitMQ. If the
model is unavailable or makes no tool calls, a deterministic fallback keeps the
service safe (e.g. always persist the chart and schedule the first call).

**Graphs** (`graph.py`):

```
Intake:   parse_summary → extract_data → risk_evaluation → questionnaire_review → act_intake
Response: analyse_response → act_response
```

### Follow-up Agent

`app/agents/followup/` + `app/api/followup.py`: FastAPI on **port 8002**.

The only service that talks to Twilio. It owns the phone conversation and turns
speech into structured answers; that is its entire LLM surface.

```
calls/
  followup.py             the post-discharge questionnaire call
  appointment_booking.py  the standalone slot-selection call
  booking.py              shared slot offer / confirm / hand-off steps
  outbound.py             dial a patient (and the appointment_booking_request consumer)
speech/
  interpreter.py          answer + slot-choice interpretation
  tts.py                  ElevenLabs streaming audio (TwiML <Play>)
sessions.py               Redis voice/appointment sessions + TwiML URL builder
voice.py                  Twilio call creation, TwiML helpers, spoken formatting
db_client.py              HTTP client for the DB service
main.py                   app + webhook routes
```

**Follow-up dialogue** (`calls/followup.py`):

```
GET  /webhooks/voice/start      greeting + question 1
POST /webhooks/voice/gather     interpret answer → next question, or clarify
GET  /webhooks/voice/complete   fallback when speech was missed
POST /webhooks/voice/status     call-status callbacks (no-answer, busy, failed)
```

* Spoken answers are interpreted with a strict JSON prompt. Anything unclear
  gets up to two clarification attempts before being recorded as unclear.
* The last item is always the appointment-consent question. On "yes" the same
  call continues straight into slot selection, with no second call.
* Twilio aborts webhooks at roughly 15 seconds, so every LLM call runs in a
  worker thread with an 11-second deadline and a heuristic fallback.

**Booking dialogue** (`calls/appointment_booking.py`):

```
GET  /webhooks/voice/appointment/start     read out up to three slots
POST /webhooks/voice/appointment/gather    confirm the chosen slot
```

Slot confirmation is optimistic: the DB service returns `409` if another call
took the slot first, and the agent offers what is left or hands the appointment
to staff.

---

## Event flow

RabbitMQ topic exchange `aftercare`, routing key = event name.

| Event | Published by | Consumed by |
| --- | --- | --- |
| `patient_state_upsert` | Triage Agent | DB Service |
| `alert_event` | Triage Agent | DB Service |
| `schedule_event` | Triage Agent, DB Service (doctor UI) | Scheduler, DB Service |
| `patient_response_event` | Follow-up Agent | Triage Agent, DB Service |
| `appointment_booking_request` | Triage Agent | Follow-up Agent |
| `appointment_confirmed` | DB Service | dashboard clients |
| `patient_record_updated` | DB Service | dashboard clients |

Redis holds the in-flight call state (`voice_session:{id}`,
`appt_session:{id}`) with a TTL (`REDIS_SESSION_TTL_SECONDS`, default one hour),
so stateless Twilio webhooks can resume a conversation.

The DB Service drops duplicates: each event's `correlation_id` is stored in an
`event_store` table, so a redelivery never creates a second chart or alert.

---

## Repository layout

```
AfterCare/
├── app/                       the single top-level package
│   ├── api/                   FastAPI entrypoints, one per service
│   │   ├── triage.py          Triage Agent      :8001
│   │   ├── followup.py        Follow-up Agent   :8002
│   │   ├── db.py              DB Service        :8003
│   │   └── scheduler.py       Scheduler         :8004
│   ├── agents/
│   │   ├── triage/            AGENT 1: clinical reasoning
│   │   │   ├── pipeline/      deterministic analysis nodes
│   │   │   ├── act/           triage tool loop
│   │   │   ├── graph.py       compiled pipelines
│   │   │   └── publisher.py   actions → RabbitMQ
│   │   └── followup/          AGENT 2: voice dialogue
│   │       ├── dialogs/       questionnaire, booking, dialing
│   │       ├── speech/        LLM speech interpretation + TTS
│   │       ├── sessions.py    Redis call sessions
│   │       └── voice.py       Twilio calls + TwiML
│   ├── db/                    persistence (not an agent)
│   │   ├── repositories/      one module per domain
│   │   ├── routers/           HTTP endpoints
│   │   └── seed/              demo patients, doctors, slots
│   ├── events/                RabbitMQ consumers that persist agent decisions
│   ├── scheduler/             timed outbound calls (not an agent)
│   └── shared/                code imported by every service
│       ├── core/              settings, logging, LLM factory, JSON helpers, service URLs
│       ├── database/          SQLAlchemy models, engine, Alembic migrations
│       ├── messaging/         event contracts + RabbitMQ bus
│       ├── cache/             Redis JSON cache for call sessions
│       ├── clinical/          appointment-consent question helper
│       └── fixtures/          fictional patients, doctors, sample discharge note
├── dashboard/                 Next.js 16 clinician dashboard (App Router)
├── scripts/                   demo and maintenance CLI helpers
├── infra/                     Dockerfiles
├── docker-compose.yml
├── alembic.ini
└── pyproject.toml
```

---

## Running locally

Requirements: **Python 3.12+**, **Node 20+**, **RabbitMQ**, **Redis**, and
([uv](https://docs.astral.sh/uv/) is recommended).

```bash
# 1. Dependencies
uv sync
cp .env.example .env          # then set OPENROUTER_API_KEY and Twilio values

# 2. Message broker and cache
docker run -d --name aftercare-rabbit -p 5672:5672 -p 15672:15672 rabbitmq:3-management
docker run -d --name aftercare-redis  -p 6379:6379 redis:7-alpine

# 3. Database (Alembic is the source of truth)
uv run alembic upgrade head

# 4. Services: one terminal each
uv run uvicorn app.api.db:app           --port 8003 --reload
uv run uvicorn app.api.triage:app       --port 8001 --reload
uv run uvicorn app.api.followup:app     --port 8002 --reload
uv run uvicorn app.api.scheduler:app    --port 8004 --reload

# 5. Dashboard
cd frontend && npm install && npm run dev             # http://localhost:3000
```

The DB service seeds the fictional patients and the doctor roster on first
start (set `SKIP_DEMO_SEED=1` to skip). Open `/login`, pick a clinician, and the
dashboard loads.

> **Voice needs a public URL.** Twilio cannot reach `localhost`. Set
> `TWILIO_WEBHOOK_BASE_URL` to an HTTPS tunnel for port 8002 (see
> [Connecting Twilio](#connecting-twilio)).

---

## Running with Docker

```bash
docker compose up --build          # broker, cache, four services, dashboard
```

Only the voice tunnel runs on the host:

```bash
ngrok http 8002                    # copy the https://… URL into .env
docker compose up -d followup_agent
```

Services inside Compose use container DNS names, so the inter-service URL
variables are overridden automatically.

---

## Connecting Twilio

1. Create a voice-capable number in the Twilio console and put its SID, auth
   token, and number in `.env`.
2. Start a tunnel to the Follow-up Agent: `ngrok http 8002`.
3. Set `TWILIO_WEBHOOK_BASE_URL=https://<your-subdomain>.ngrok-free.app` -
   origin only, no path, and restart the Follow-up Agent.
4. Verify the tunnel serves XML rather than an ngrok warning page:

   ```bash
   uv run python scripts/check_twilio_tunnel.py
   ```

The agent appends TwiML URLs itself, including the
`ngrok-skip-browser-warning` parameter on ngrok-free hosts.

SMS is not used anywhere in AfterCare; every patient interaction is a voice call.

---

## Configuration

All settings live in `app/shared/core/config.py` and are read from the environment
(or `.env`). Only two are genuinely required: `OPENROUTER_API_KEY` and the
Twilio credentials.

| Variable | Default | Purpose |
| --- | --- | --- |
| `OPENROUTER_API_KEY` |: | LLM access (required) |
| `OPENROUTER_MODEL` | `deepseek/deepseek-v4-flash` | Model for both agents |
| `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` |: | Twilio credentials (required) |
| `TWILIO_PHONE_NUMBER` |: | Caller ID for outbound calls |
| `TWILIO_WEBHOOK_BASE_URL` | `http://localhost:8002` | Public HTTPS origin of the Follow-up Agent |
| `ELEVENLABS_API_KEY` | empty | Enables ElevenLabs narration; otherwise Polly |
| `RABBITMQ_URL` | `amqp://guest:guest@localhost/` | Event bus |
| `REDIS_URL` | `redis://localhost:6379` | Call session store |
| `REDIS_SESSION_TTL_SECONDS` | `3600` | How long an unfinished call can resume |
| `DATABASE_URL` | `sqlite+aiosqlite:///./aftercare.db` | SQLAlchemy async URL |
| `DEMO_MODE` | `true` | Compress follow-up spacing for demos |
| `DEMO_FOLLOWUP_*` | see config | Demo-mode urgency spacing |

---

## HTTP API reference

| Service | Endpoint | Purpose |
| --- | --- | --- |
| Triage Agent | `POST /intake` | Parse a discharge note end-to-end |
| | `POST /evaluate-response` | Evaluate answers without a live call |
| | `GET /patients/{id}/questions` | Proxy the stored questionnaire |
| Follow-up Agent | `POST /initiate-call` | Start the follow-up call |
| | `GET /active-sessions` | Calls currently in flight |
| | `/webhooks/voice/*` | Twilio TwiML webhooks |
| | `GET /voice/tts` | Streaming ElevenLabs audio |
| DB Service | `GET /patients`, `GET /patients/{id}` | Charts |
| | `GET /patients/{id}/timeline` | Everything that happened to a patient |
| | `GET /patients/{id}/questionnaire` | Current questionnaire |
| | `POST /patients/{id}/schedule-followup` | Clinician-scheduled follow-up |
| | `GET /alerts`, `PATCH /alerts/{id}/acknowledge` | Alert inbox |
| | `GET /appointments`, `POST /appointments`, `PATCH /appointments/{id}` | Appointments |
| | `POST /appointments/confirm` | Book a slot (409 if taken) |
| | `GET /doctors`, `GET /doctors/availability` | Directory and open slots |
| | `GET /followup-jobs`, `PATCH /followup-jobs/by-correlation/{id}` | Call job tracking |
| Scheduler | `GET /jobs` | Pending outbound calls |
| | `POST /trigger/{patient_id}` | Call a patient immediately |

Interactive docs are served at `/docs` on each service.

---

## Demo scripts

Run from the repository root with services up:

```bash
uv run python scripts/demo_flow.py            # full end-to-end walkthrough
uv run python scripts/run_intake.py           # submit the sample discharge note
uv run python scripts/trigger_followup.py <patient_id>
uv run python scripts/seed_demo_db.py         # seed an empty SQLite file
uv run python scripts/check_twilio_tunnel.py  # verify the public tunnel
```

---

## Demo data

Every patient and clinician in this repository is fictional. Names, phone
numbers (`555` exchange), emails (`example.com`), and ward/bed notes are
synthetic, and the fixtures are the single source of truth for seeding, scripts,
and the dashboard:

| Fixture | Used for |
| --- | --- |
| `app/shared/fixtures/patients.py` | Five demo charts: Elena Whitfield, Marcus Delgado, Priya Nandakumar, Samuel Okafor, Hannah Lindqvist |
| `app/shared/fixtures/doctors.py` | Four clinicians: Dr. Aris Thorne, Dr. Lena Marsh, Dr. Priya Raman, Dr. Owen Castellano |
| `app/shared/fixtures/discharge.py` | The cardiac discharge note used by the demo scripts |

---

## Testing

```bash
uv run python -m compileall app scripts   # syntax
uv run alembic upgrade head                           # migration chain
cd dashboard && npm run build && npx tsc --noEmit      # dashboard
```
