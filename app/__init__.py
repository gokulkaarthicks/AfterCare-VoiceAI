"""`app`: AfterCare's single top-level package.

Serving FastAPI apps:            `app.api.triage`, `app.api.followup`,
                                 `app.api.db`, `app.api.scheduler`
Agent logic (the only two LLM agents): `app.agents.triage`, `app.agents.followup`
Shared plumbing:                 `app.shared.*`
"""
