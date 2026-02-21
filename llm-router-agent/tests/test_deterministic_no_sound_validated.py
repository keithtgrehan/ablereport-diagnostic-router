import json

import pytest

from llm_router_agent.deterministic import diagnose_no_sound_validated


class _FakeRouter:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls: list[tuple[str, str]] = []

    def invoke(self, node_name: str, prompt: str) -> str:
        self.calls.append((node_name, prompt))
        if not self._responses:
            raise RuntimeError("No fake responses remaining.")
        next_response = self._responses.pop(0)
        if isinstance(next_response, Exception):
            raise next_response
        return str(next_response)


def _ai_key() -> dict:
    return {
        "project": {"audio_engine_enabled": False, "transport_running": True},
        "master_track": {"muted": False, "volume_db": -12.0},
        "tracks": [{"clips_present": False}],
    }


def _valid_report() -> dict:
    return {
        "intent": "no_sound",
        "diagnosis": "Audio engine is disabled.",
        "root_cause_category": "audio_engine_disabled",
        "confidence": "high",
        "evidence": [
            {
                "path": "$.project.audio_engine_enabled",
                "value": False,
                "explanation": "Audio engine is off.",
            }
        ],
        "checks_run": ["audio_engine_enabled"],
        "fix_steps": ["Enable audio engine."],
    }


def test_require_llm_returns_validated_report_on_first_try():
    router = _FakeRouter([json.dumps(_valid_report())])

    out = diagnose_no_sound_validated(_ai_key(), require_llm=True, router=router)

    assert out["intent"] == "no_sound"
    assert out["root_cause_category"] == "audio_engine_disabled"
    assert len(router.calls) == 1


def test_require_llm_retries_once_with_strict_prompt():
    invalid = '{"intent":"no_sound","diagnosis":"bad"}'
    valid = json.dumps(_valid_report())
    router = _FakeRouter([invalid, valid])

    out = diagnose_no_sound_validated(_ai_key(), require_llm=True, router=router)

    assert out["root_cause_category"] == "audio_engine_disabled"
    assert len(router.calls) == 2
    assert "STRICT VALIDATION RETRY." in router.calls[1][1]


def test_require_llm_falls_back_to_deterministic_with_note():
    invalid = '{"intent":"no_sound","diagnosis":"still bad"}'
    router = _FakeRouter([invalid, invalid])

    out = diagnose_no_sound_validated(_ai_key(), require_llm=True, router=router)

    assert out["intent"] == "no_sound"
    assert "LLM failed validation" in out.get("notes", "")
    assert all("LLM failed validation" not in step for step in out["fix_steps"])
    assert out["root_cause_category"] == "audio_engine_disabled"
    assert len(router.calls) == 2


def test_no_llm_and_require_llm_conflict():
    with pytest.raises(ValueError):
        diagnose_no_sound_validated(_ai_key(), no_llm=True, require_llm=True)


def test_deterministic_run_has_no_notes():
    out = diagnose_no_sound_validated(_ai_key(), no_llm=True)
    assert out.get("notes") is None
