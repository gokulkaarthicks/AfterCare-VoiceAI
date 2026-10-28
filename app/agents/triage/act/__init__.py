"""The triage tool-calling subagent: the only part of the Triage Agent with side effects.

The deterministic pipeline only *thinks*. Everything that changes state (chart
writes, alerts, scheduling) is chosen by the model through the tools in
`clinical_tools.py` and executed by `tool_agent.py`.
"""
