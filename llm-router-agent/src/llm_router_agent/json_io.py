"""JSON extraction, repair, and parse/validate utilities."""

from __future__ import annotations

import json
import os
import re
from typing import Any, TypeVar

from pydantic import BaseModel

ModelT = TypeVar("ModelT", bound=BaseModel)


def _content(response: Any) -> str:
    """Normalize model/router responses to plain text."""
    if hasattr(response, "content"):
        return str(response.content)
    return str(response)


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
        return max(1, value)
    except ValueError:
        return default


def strip_fences(text: str) -> str:
    """Remove markdown code fences from text."""
    stripped = (text or "").strip()
    stripped = stripped.replace("```json", "").replace("```JSON", "").replace("```", "")
    return stripped.strip()


def extract_json_text(text: str) -> str | None:
    """
    Extract first JSON object/array from mixed text.

    Rules:
    - remove fences
    - if text starts with '{' or '[' return trimmed text
    - else find first '{...}' via regex DOTALL; if none, first '[...]'
    """
    candidate = strip_fences(text)
    if not candidate:
        return None

    trimmed = candidate.strip()
    if trimmed.startswith("{") or trimmed.startswith("["):
        return trimmed

    obj_match = re.search(r"\{.*?\}", trimmed, flags=re.DOTALL)
    arr_match = re.search(r"\[.*?\]", trimmed, flags=re.DOTALL)

    if obj_match and arr_match:
        if arr_match.start() < obj_match.start():
            return arr_match.group(0).strip()
        return obj_match.group(0).strip()
    if obj_match:
        return obj_match.group(0).strip()
    if arr_match:
        return arr_match.group(0).strip()

    return None


def extract_json(text: str) -> dict | list | None:
    """Compatibility helper: parse extracted JSON text into dict/list."""
    extracted = extract_json_text(text)
    if extracted is None:
        return None
    try:
        parsed = json.loads(extracted)
    except Exception:
        return None
    if isinstance(parsed, (dict, list)):
        return parsed
    return None


def parse_validate(json_text: str, model_cls: type[ModelT]) -> ModelT:
    """Parse JSON string and validate against a Pydantic model."""
    parsed = json.loads(json_text)
    return model_cls.model_validate(parsed)


def make_repair_prompt(raw: str, model_name: str) -> str:
    """Build strict repair prompt for malformed/mixed model output."""
    return (
        "Return ONLY valid JSON. No markdown. No commentary.\n"
        f"Fix the output so it matches schema: {model_name}.\n\n"
        "BROKEN_OR_MIXED_OUTPUT:\n"
        f"{raw}\n"
    )


def _router_allows_fallback(router: Any, node_name: str) -> bool:
    """Best-effort check for fallback availability on injected router."""
    if hasattr(router, "invoke_fallback"):
        return True

    if hasattr(router, "route"):
        try:
            resolved = router.route(node_name)
            return getattr(resolved, "fallback", None) is not None
        except Exception:
            pass

    if hasattr(router, "get_llm"):
        try:
            models = router.get_llm(node_name)
            if isinstance(models, tuple):
                return models[1] is not None
        except Exception:
            pass

    return False


def _router_invoke(router: Any, node_name: str, prompt: str, *, use_fallback: bool) -> str:
    """Invoke router primary/fallback path and normalize result to text."""
    if use_fallback and hasattr(router, "invoke_fallback"):
        return _content(router.invoke_fallback(node_name, prompt))

    if not use_fallback and hasattr(router, "invoke"):
        return _content(router.invoke(node_name, prompt))

    if hasattr(router, "get_llm"):
        models = router.get_llm(node_name)
        if isinstance(models, tuple):
            primary_llm, fallback_llm = models
        else:
            primary_llm, fallback_llm = models, None

        llm = fallback_llm if use_fallback else primary_llm
        if llm is None:
            raise RuntimeError(f"{node_name}: fallback model is not configured")
        return _content(llm.invoke(prompt))

    raise RuntimeError("Router must expose invoke/get_llm (and optionally invoke_fallback)")


def _router_repair(
    router: Any,
    node_name: str,
    raw: str,
    model_name: str,
    *,
    use_fallback: bool,
) -> str:
    """
    Repair via router call site.

    Priority:
    1) router.repair(...)
    2) router invoke with generated repair prompt
    """
    if hasattr(router, "repair"):
        repair_fn = router.repair
        try:
            return _content(
                repair_fn(
                    node_name,
                    raw,
                    model_name,
                    use_fallback=use_fallback,
                )
            )
        except TypeError:
            try:
                return _content(repair_fn(node_name, raw, model_name))
            except TypeError:
                pass

    prompt = make_repair_prompt(raw, model_name)
    return _router_invoke(router, node_name, prompt, use_fallback=use_fallback)


def _extract_parse_validate(raw: str, model_cls: type[ModelT]) -> ModelT:
    json_text = extract_json_text(raw)
    if json_text is None:
        raise RuntimeError("No JSON object/array found in model output.")
    return parse_validate(json_text, model_cls)


def invoke_parse_validate(
    router: Any,
    node_name: str,
    prompt: str,
    model_cls: type[ModelT],
    max_retries: int | None = None,
    repair_tries: int | None = None,
) -> ModelT:
    """
    Invoke router, parse and validate JSON, repair on failure, and use fallback if available.

    Defaults:
    - max_retries from JSON_MAX_RETRIES (default 4)
    - repair_tries from JSON_REPAIR_TRIES (default 1)
    """
    retries = max_retries if max_retries is not None else _env_int("JSON_MAX_RETRIES", 4)
    repairs = repair_tries if repair_tries is not None else _env_int("JSON_REPAIR_TRIES", 1)
    retries = max(1, int(retries))
    repairs = max(1, int(repairs))

    last_error: Exception | None = None
    last_raw = ""
    has_fallback = _router_allows_fallback(router, node_name)

    for _ in range(retries):
        for use_fallback in (False, True):
            if use_fallback and not has_fallback:
                continue

            raw = ""
            try:
                raw = _router_invoke(router, node_name, prompt, use_fallback=use_fallback)
            except Exception as exc:
                last_error = exc
                continue

            last_raw = raw or last_raw

            try:
                return _extract_parse_validate(raw, model_cls)
            except Exception as exc:
                last_error = exc

            repair_input = raw
            for _ in range(repairs):
                repaired_raw = ""
                try:
                    repaired_raw = _router_repair(
                        router,
                        node_name,
                        repair_input,
                        model_cls.__name__,
                        use_fallback=use_fallback,
                    )
                except Exception as exc:
                    last_error = exc
                    continue

                last_raw = repaired_raw or last_raw
                try:
                    return _extract_parse_validate(repaired_raw, model_cls)
                except Exception as exc:
                    last_error = exc
                    repair_input = repaired_raw

    snippet = (last_raw or "").strip().replace("\n", " ")[:1200]
    raise RuntimeError(
        f"{node_name}: JSON parse/validate failed for {model_cls.__name__}. "
        f"Last error: {last_error}. Last raw output snippet: {snippet}"
    )


class _SingleLLMRouter:
    """Adapter for compatibility calls that pass a direct LLM object."""

    def __init__(self, llm: Any) -> None:
        self.llm = llm

    def invoke(self, _node_name: str, prompt: str) -> str:
        return _content(self.llm.invoke(prompt))

    def repair(self, _node_name: str, raw: str, model_name: str, **_kwargs: Any) -> str:
        prompt = make_repair_prompt(raw, model_name)
        return _content(self.llm.invoke(prompt))


class _PairLLMRouter:
    """Adapter for compatibility helpers using explicit primary/fallback LLMs."""

    def __init__(self, primary_llm: Any, fallback_llm: Any | None) -> None:
        self.primary_llm = primary_llm
        self.fallback_llm = fallback_llm

    def invoke(self, _node_name: str, prompt: str) -> str:
        return _content(self.primary_llm.invoke(prompt))

    def invoke_fallback(self, _node_name: str, prompt: str) -> str:
        if self.fallback_llm is None:
            raise RuntimeError("Fallback model is not configured")
        return _content(self.fallback_llm.invoke(prompt))

    def repair(
        self,
        _node_name: str,
        raw: str,
        model_name: str,
        *,
        use_fallback: bool = False,
    ) -> str:
        llm = self.fallback_llm if use_fallback and self.fallback_llm is not None else self.primary_llm
        prompt = make_repair_prompt(raw, model_name)
        return _content(llm.invoke(prompt))


# Backward-compatible names used by current code/tests.
def strip_code_fences(text: str) -> str:
    return strip_fences(text)


def extract_json_str(text: str) -> str | None:
    return extract_json_text(text)


def parse_and_validate_json(raw_text: str, model_cls: type[ModelT]) -> ModelT:
    extracted = extract_json_text(raw_text)
    if extracted is None:
        raise RuntimeError("No JSON object/array found in model output.")
    return parse_validate(extracted, model_cls)


def repair_json(llm: Any, raw_text: str) -> str:
    prompt = make_repair_prompt(raw_text, "UnknownSchema")
    return _content(llm.invoke(prompt))


def parse_validate_loop(
    llm: Any,
    prompt: str,
    model_cls: type[ModelT],
    max_retries: int | None = None,
    repair_tries: int | None = None,
) -> ModelT:
    adapter = _SingleLLMRouter(llm)
    return invoke_parse_validate(
        adapter,
        node_name="direct",
        prompt=prompt,
        model_cls=model_cls,
        max_retries=max_retries,
        repair_tries=repair_tries,
    )


def invoke_json_with_fallback(
    *,
    prompt: str,
    model_cls: type[ModelT],
    primary_llm: Any,
    fallback_llm: Any | None = None,
    node_name: str,
    repair_attempts: int = 1,
) -> ModelT:
    adapter = _PairLLMRouter(primary_llm=primary_llm, fallback_llm=fallback_llm)
    return invoke_parse_validate(
        adapter,
        node_name=node_name,
        prompt=prompt,
        model_cls=model_cls,
        max_retries=1,
        repair_tries=max(1, int(repair_attempts)),
    )
