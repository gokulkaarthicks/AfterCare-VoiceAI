"""Scheduler: turns `schedule_event` messages into timed outbound calls.

It is not an LLM agent: the Triage Agent decides *that* a follow-up is needed and
*when*; this service just dials the Follow-up Agent at that moment.
"""

SERVICE_NAME = "scheduler"
SERVICE_PORT = 8004
