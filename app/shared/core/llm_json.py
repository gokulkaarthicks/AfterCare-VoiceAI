"""Tolerant extraction of JSON objects and arrays from raw LLM output.

Chat models occasionally wrap JSON in markdown fences or add a sentence of
preamble. These helpers recover the first valid JSON value so callers never
have to repeat the cleanup logic.
"""

from __future__ import annotations

import json
from typing import Any

_FENCE = "```"


def _strip_code_fence(text: str) -> str:
    """Remove a leading ```json fence and its trailing closing fence, if present."""
    cleaned = text.strip()
    if not cleaned.startswith(_FENCE):
        return cleaned

    newline = cleaned.find("\n")
    cleaned = cleaned[newline + 1 :] if newline != -1 else cleaned[len(_FENCE) :]
    if cleaned.rstrip().endswith(_FENCE):
        cleaned = cleaned.rstrip()[: -len(_FENCE)]
    cleaned = cleaned.strip()
    if cleaned.lower().startswith("json"):
        cleaned = cleaned[4:].lstrip()
    return cleaned


def load_json_object(text: str) -> dict[str, Any]:
    """Parse the first JSON object found in `text`.

    Raises:
        ValueError: when no JSON object is present.
        json.JSONDecodeError: when the object is truncated or malformed.
    """
    cleaned = _strip_code_fence(text or "")
    if not cleaned:
        raise ValueError("empty LLM response")

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"no JSON object in LLM response: {cleaned[:200]!r}")

    parsed = json.loads(cleaned[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("LLM response is not a JSON object")
    return parsed


def load_json_value(text: str) -> Any:
    """Parse a JSON object *or* array from `text` (models vary in what they return)."""
    cleaned = _strip_code_fence(text or "")
    if not cleaned:
        raise ValueError("empty LLM response")

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        object_start, object_end = cleaned.find("{"), cleaned.rfind("}")
        array_start, array_end = cleaned.find("["), cleaned.rfind("]")
        as_object = object_start != -1 and object_end > object_start
        as_array = array_start != -1 and array_end > array_start
        if as_array and (not as_object or array_start < object_start):
            return json.loads(cleaned[array_start : array_end + 1])
        if as_object:
            return json.loads(cleaned[object_start : object_end + 1])
        raise


def message_text(content: Any) -> str:
    """Flatten LangChain message content (plain string or content-block list)."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks: list[str] = []
        for block in content:
            if isinstance(block, str):
                chunks.append(block)
                continue
            text = block.get("text") if isinstance(block, dict) else getattr(block, "text", None)
            if isinstance(text, str):
                chunks.append(text)
        return "\n".join(chunks)
    return str(content)
