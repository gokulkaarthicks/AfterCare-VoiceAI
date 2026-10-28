"""LLM speech interpretation: the Follow-up Agent's reasoning step.

Two jobs:
  * `interpret_answer`: turn a patient's free-form answer into a normalized
                            value plus clinical flags for the follow-up loop.
  * `interpret_slot_choice`: map a spoken appointment preference onto an
                            offered slot index (or capture a preferred time).

Twilio aborts webhooks at roughly 15 s, so every LLM call runs in a thread with
an 11 s overall deadline; heuristics keep the call alive on timeout or bad JSON.
"""

from __future__ import annotations

import asyncio
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from app.shared.core.llm import build_chat_model
from app.shared.core.llm_json import load_json_object, message_text
from app.shared.core.logging import get_logger

logger = get_logger("followup_agent.interpreter")

LLM_DEADLINE_SECONDS = 11.0
LLM_HTTP_TIMEOUT_SECONDS = 10.0

_CLARIFY_AGAIN = "I didn't catch that. Could you please repeat your answer?"


# --- Answer interpretation ----------------------------------------------------


class InterpretedAnswer(BaseModel):
    """What the patient actually said, in a form the pipeline can use."""

    raw_speech: str
    interpreted_answer: str
    normalized: str = ""
    clinical_flags: list[str] = []
    needs_clarification: bool = False
    clarification_question: str | None = None


ANSWER_SYSTEM_PROMPT = """\
You are interpreting a patient's spoken response during a post-discharge follow-up phone call.

Your job:
1. Understand what the patient said in the context of the question asked.
2. Summarise their answer in clinical language (under 25 words).
3. For yes/no questions return "yes" or "no" in `normalized`, even from natural
   speech ("yeah I guess", "not really", "kind of").
4. For scale questions (e.g. pain 1-10) return the number as a string.
5. For open questions return a one-sentence summary.
6. List clinical red flags mentioned: chest_pain, fever, dizziness,
   shortness_of_breath, missed_medication, swelling, bleeding, fatigue.
7. Set needs_clarification only when the speech is genuinely unintelligible or
   off-topic; partial or hedging answers are still interpretable.
8. Keep clarification_question conversational and under 20 words.

Respond ONLY with JSON:
{
  "raw_speech": "<exact speech as given>",
  "interpreted_answer": "<clinical summary>",
  "normalized": "<yes|no|scale_value|free_text_summary>",
  "clinical_flags": ["snake_case_flag"],
  "needs_clarification": true|false,
  "clarification_question": "<question or null>"
}
"""

# Checked "no" first so "not really" never matches a "yes" prefix.
_NO_PREFIXES = ("no ", "no,", "nope", "nah", "not ")
_YES_PREFIXES = ("yes", "yeah", "yep", "yup")


def _heuristic_yes_no(speech: str) -> str | None:
    text = speech.strip().lower().rstrip(".!,?")
    if not text:
        return None
    if text in ("no", "nope", "nah", "negative") or text.startswith(_NO_PREFIXES):
        return "no"
    if text in ("yes", "yeah", "yep", "yup", "sure", "correct", "affirmative"):
        return "yes"
    if text.startswith(_YES_PREFIXES):
        return "yes"
    return None


def _local_fallback(question_type: str, speech: str) -> InterpretedAnswer | None:
    """Best-effort parse when the model is unavailable: only yes/no is reliable."""
    kind = (question_type or "").lower()
    if "yes" not in kind and kind not in ("boolean", "bool"):
        return None
    answer = _heuristic_yes_no(speech)
    if not answer:
        return None
    return InterpretedAnswer(
        raw_speech=speech,
        interpreted_answer=speech.strip(),
        normalized=answer,
    )


def _request_clarification(speech: str) -> InterpretedAnswer:
    return InterpretedAnswer(
        raw_speech=speech,
        interpreted_answer="No response detected" if not speech.strip() else "",
        needs_clarification=True,
        clarification_question=_CLARIFY_AGAIN,
    )


def _call_model(**kwargs: Any) -> str:
    model = build_chat_model(temperature=0, max_tokens=512, timeout=LLM_HTTP_TIMEOUT_SECONDS)
    model = model.bind(response_format={"type": "json_object"})
    reply = model.invoke(kwargs.pop("messages"))
    return message_text(reply.content).strip()


def _interpret_answer_sync(
    question_text: str,
    question_type: str,
    speech: str,
    diagnosis: str,
) -> InterpretedAnswer:
    prompt = (
        f"Patient diagnosis: {diagnosis}"
        f"\nQuestion asked: {question_text}"
        f"\nQuestion type: {question_type}"
        f"\nPatient's spoken response: {speech}"
    )
    messages = [
        SystemMessage(content=ANSWER_SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ]
    raw = _call_model(messages=messages)
    if not raw:
        fallback = _local_fallback(question_type, speech)
        if fallback:
            return fallback
        raise ValueError("empty LLM response")
    return InterpretedAnswer(**load_json_object(raw))


async def interpret_answer(
    question_text: str,
    question_type: str,
    speech_result: str,
    diagnosis: str,
) -> InterpretedAnswer:
    """Interpret one spoken answer, degrading gracefully so the call can continue."""
    if not (speech_result or "").strip():
        logger.warning("interpret_answer.empty_speech")
        return _request_clarification("")

    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(
                _interpret_answer_sync,
                question_text,
                question_type,
                speech_result,
                diagnosis,
            ),
            timeout=LLM_DEADLINE_SECONDS,
        )
        logger.info(
            "interpret_answer.done",
            normalized=result.normalized,
            clinical_flags=result.clinical_flags,
            needs_clarification=result.needs_clarification,
        )
        return result
    except TimeoutError:
        logger.warning("interpret_answer.timeout", deadline=LLM_DEADLINE_SECONDS)
    except Exception:  # noqa: BLE001 - parse or transport failure
        logger.exception("interpret_answer.failed")

    fallback = _local_fallback(question_type, speech_result)
    return fallback or _request_clarification(speech_result)


# --- Appointment slot choice --------------------------------------------------


class SlotChoice(BaseModel):
    chosen_slot_index: int | None = None
    preferred_time: str | None = None
    needs_clarification: bool = False
    clarification_question: str | None = None


SLOT_SYSTEM_PROMPT = """\
You are helping a patient choose an appointment time over the phone. They were
offered numbered slots and have just spoken their preference.

Respond ONLY with JSON:
{
  "chosen_slot_index": <0-based index of the chosen slot, or null>,
  "preferred_time": "<a different preferred time if no slot chosen, or null>",
  "needs_clarification": true|false,
  "clarification_question": "<short follow-up question or null>"
}

Rules:
- "option 1" / "the first one" / "Monday" (matching slot 1) → chosen_slot_index 0.
- "none of these" / "what about Friday" → chosen_slot_index null, preferred_time set.
- needs_clarification only when the response is genuinely unintelligible.
"""


def _interpret_slot_choice_sync(speech: str, slots: list[dict[str, Any]]) -> SlotChoice:
    offered = "\n".join(
        f"Option {index + 1} (index {index}): {slot['slot_start']} with {slot['doctor_name']}"
        for index, slot in enumerate(slots)
    )
    model = build_chat_model(temperature=0, max_tokens=384, timeout=LLM_HTTP_TIMEOUT_SECONDS)
    model = model.bind(response_format={"type": "json_object"})
    reply = model.invoke(
        [
            SystemMessage(content=SLOT_SYSTEM_PROMPT),
            HumanMessage(
                content=f"Offered slots:\n{offered}\n\nPatient's spoken response: {speech}"
            ),
        ]
    )
    raw = message_text(reply.content).strip()
    if not raw:
        raise ValueError("empty LLM response")
    return SlotChoice(**load_json_object(raw))


async def interpret_slot_choice(
    speech_result: str,
    slots: list[dict[str, Any]],
) -> SlotChoice:
    """Map a spoken slot preference onto the offered options."""
    if not (speech_result or "").strip():
        return SlotChoice(
            needs_clarification=True,
            clarification_question="I didn't catch that. Which option would you prefer?",
        )
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(_interpret_slot_choice_sync, speech_result, slots),
            timeout=LLM_DEADLINE_SECONDS,
        )
        logger.info(
            "interpret_slot_choice.done",
            chosen_slot_index=result.chosen_slot_index,
            preferred_time=result.preferred_time,
            needs_clarification=result.needs_clarification,
        )
        return result
    except TimeoutError:
        logger.warning("interpret_slot_choice.timeout")
        prompt = "Sorry, could you repeat which option you prefer?"
    except Exception:  # noqa: BLE001
        logger.exception("interpret_slot_choice.failed")
        prompt = "Could you please repeat which option works for you?"
    return SlotChoice(needs_clarification=True, clarification_question=prompt)
