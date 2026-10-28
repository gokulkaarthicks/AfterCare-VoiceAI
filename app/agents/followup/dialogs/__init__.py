"""Call dialogue definitions for the Follow-up Agent.

Two phone flows, both driven by Twilio TwiML webhooks held in Redis sessions:

  followup.py: the post-discharge clinical questionnaire, ending with
                           an appointment-consent question that can roll straight
                           into slot selection on the same call.
  appointment_booking.py: a standalone call offering clinician slots.

The Follow-up Agent is one of only two LLM-backed agents in AfterCare; this
package is where its reasoning (speech in, decisions out) lives.
"""
