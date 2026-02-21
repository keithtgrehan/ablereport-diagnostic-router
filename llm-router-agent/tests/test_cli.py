import json

import pytest

from llm_router_agent.cli import parse_args, run_cli


class _FakeRouter:
    def __init__(self, response_text: str) -> None:
        self.response_text = response_text
        self.calls = 0

    def invoke(self, _node_name: str, _prompt: str) -> str:
        self.calls += 1
        return self.response_text


def test_cli_arg_parsing_and_run_with_mock_provider(tmp_path):
    ai_key = {
        "project": {"audio_engine_enabled": False, "transport_running": True},
        "master_track": {"muted": False, "volume_db": -12.0},
        "tracks": [{"clips_present": False}],
    }
    ai_key_path = tmp_path / "ai_key.json"
    ai_key_path.write_text(json.dumps(ai_key))

    valid_report = {
        "intent": "no_sound",
        "diagnosis": "Audio engine is disabled.",
        "root_cause_category": "audio_engine_disabled",
        "confidence": "high",
        "evidence": [
            {
                "path": "$.project.audio_engine_enabled",
                "value": False,
                "explanation": "Audio engine disabled.",
            }
        ],
        "checks_run": ["audio_engine_enabled"],
        "fix_steps": ["Enable the audio engine."],
    }

    args = parse_args(
        [
            "--ai-key",
            str(ai_key_path),
            "--require-llm",
            "--llm-provider",
            "ollama",
            "--llm-model",
            "dummy-model",
        ]
    )
    assert args.require_llm is True
    assert args.no_llm is False
    assert args.llm_provider == "ollama"
    assert args.llm_model == "dummy-model"

    seen: dict[str, str | None] = {}

    def provider_factory(provider: str, model: str | None):
        seen["provider"] = provider
        seen["model"] = model
        return _FakeRouter(json.dumps(valid_report))

    report = run_cli(args, provider_factory=provider_factory)
    assert report["intent"] == "no_sound"
    assert report["root_cause_category"] == "audio_engine_disabled"
    assert seen == {"provider": "ollama", "model": "dummy-model"}


def test_cli_conflict_flags_raise():
    with pytest.raises(SystemExit):
        parse_args(
            [
                "--ai-key",
                "fixtures/ai_key/no_sound_audio_engine_off.json",
                "--no-llm",
                "--require-llm",
            ]
        )
