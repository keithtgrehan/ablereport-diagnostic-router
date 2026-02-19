"""JSON extraction and validation utilities with retry/repair support."""

from __future__ import annotations

import json
import re
from typing import Any, TypeVar

from pydantic import BaseModel

ModelT = TypeVar("ModelT", bound=BaseModel)


def _content(response: Any) -> str:
    """Normalize LangChain-like responses to plain text."""
    if hasattr(response, "content"):
        return str(response.content)
    return str(response)


def strip_fences(text: str) -> str:
    """Remove markdown code fences from model output."""
    stripped = (text or "").strip()
    stripped = stripped.replace("```json", "").replace("```JSON", "").replace("```", "").strip()
    stripped = re.sub(r"^`{3,}\s*json\s*", "", stripped, flags=re.IGNORECASE).strip()
    stripped = re.sub(r"`{3,}\s*$", "", stripped).strip()
    return stripped


def _extract_balanced_fragment(text: str, start_index: int) -> str | None:
    """Extract the first balanced JSON fragment starting at start_index."""
    open_char = text[start_index]
    close_char = "}" if open_char == "{" else "]"

    depth = 0
    in_string = False
    escaped = False

    for idx in range(start_index, len(text)):
        ch = text[idx]

        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
            continue

        if ch == open_char:
            depth += 1
        elif ch == close_char:
            depth -= 1
            if depth == 0:
                return text[start_index : idx + 1]

    return None


def extract_json_str(text: str) -> str | None:
    """
    Extract the first valid JSON object/array string from mixed model output.

    Returns None when no valid JSON block can be found.
    """
    candidate = strip_fences(text)
    if not candidate:
        return None

    # Fast path: full output is already valid JSON.
    try:
        json.loads(candidate)
        return candidate
    except Exception:
        pass

    # Mixed text path: find first balanced object/array that parses.
    for idx, ch in enumerate(candidate):
        if ch not in ("{", "["):
            continue
        fragment = _extract_balanced_fragment(candidate, idx)
        if not fragment:
            continue
        try:
            json.loads(fragment)
            return fragment
        except Exception:
            continue

    return None


def extract_json(text: str) -> dict | list | None:
    """Extract and parse first valid JSON object/array from text."""
    extracted = extract_json_str(text)
    if extracted is None:
        return None
    try:
        parsed = json.loads(extracted)
    except Exception:
        return None
    if isinstance(parsed, (dict, list)):
        return parsed
    return None


def repair_json(llm: Any, raw_text: str) -> str:
    """Ask the model to repair broken output into strict JSON-only text."""
    prompt = (
        "Return ONLY valid JSON.\n"
        "Fix the content below into valid JSON. No markdown. No commentary.\n\n"
        f"RAW_OUTPUT:\n{raw_text}\n"
    )
    return _content(llm.invoke(prompt))


def parse_validate_loop(
    llm: Any,
    prompt: str,
    model_cls: type[ModelT],
    max_retries: int = 1,
) -> ModelT:
    """
    Invoke model, parse/extract JSON, validate with Pydantic, and retry with repair.

    One repair attempt is performed on each retry cycle.
    """
    retries = max(1, int(max_retries))
    last_error: Exception | None = None
    last_raw = ""

    for _ in range(retries):
        raw = ""
        try:
            raw = _content(llm.invoke(prompt))
        except Exception as exc:
            last_error = exc

        last_raw = raw or last_raw
        parsed = extract_json(raw) if raw and raw.strip() else None

        if parsed is not None:
            try:
                return model_cls.model_validate(parsed)
            except Exception as exc:
                last_error = exc
        else:
            if not raw or not raw.strip():
                last_error = RuntimeError("Empty response from model.")
            else:
                last_error = RuntimeError("No JSON object/array found in model output.")

        repaired_raw = ""
        try:
            repaired_raw = repair_json(llm, raw)
        except Exception as exc:
            last_error = exc
            continue

        last_raw = repaired_raw or last_raw
        repaired_parsed = (
            extract_json(repaired_raw) if repaired_raw and repaired_raw.strip() else None
        )

        if repaired_parsed is not None:
            try:
                return model_cls.model_validate(repaired_parsed)
            except Exception as exc:
                last_error = exc
        else:
            if not repaired_raw or not repaired_raw.strip():
                last_error = RuntimeError("Empty repair response from model.")
            else:
                last_error = RuntimeError("Repair output did not contain valid JSON.")

    snippet = (last_raw or "").strip().replace("\n", " ")[:1200]
    raise RuntimeError(
        f"JSON parse/validate failed for {model_cls.__name__}. "
        f"Last error: {last_error}. Last raw output snippet: {snippet}"
    )


# Backward-compatible helpers used by existing nodes/tests.
def strip_code_fences(text: str) -> str:
    """Compatibility alias for strip_fences."""
    return strip_fences(text)


def parse_and_validate_json(raw_text: str, model_cls: type[ModelT]) -> ModelT:
    """Compatibility helper: parse already-generated raw model output once."""
    parsed = extract_json(raw_text)
    if parsed is None:
        raise RuntimeError("No JSON object/array found in model output.")
    return model_cls.model_validate(parsed)


def invoke_json_with_fallback(
    *,
    prompt: str,
    model_cls: type[ModelT],
    primary_llm: Any,
    fallback_llm: Any | None = None,
    node_name: str,
    repair_attempts: int = 1,
) -> ModelT:
    """Compatibility helper for node routing with primary/fallback providers."""
    last_error: Exception | None = None
    max_retries = max(1, int(repair_attempts) + 1)

    for llm in (primary_llm, fallback_llm):
        if llm is None:
            continue
        try:
            return parse_validate_loop(llm, prompt, model_cls, max_retries=max_retries)
        except Exception as exc:
            last_error = exc

    raise RuntimeError(f"{node_name}: provider chain failed") from last_error
