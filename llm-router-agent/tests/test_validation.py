from llm_router_agent.validation import validate_report


def test_validate_report_passes_for_matching_evidence():
    ai_key = {
        "project": {"audio_engine_enabled": False, "transport_running": True},
        "master_track": {"muted": False, "volume_db": -12.0},
        "tracks": [{"clips_present": False}, {"clips_present": False}],
    }
    report = {
        "intent": "no_sound",
        "diagnosis": "Audio engine is disabled.",
        "root_cause_category": "audio_engine_disabled",
        "confidence": "high",
        "evidence": [
            {
                "path": "$.project.audio_engine_enabled",
                "value": False,
                "explanation": "Engine is disabled.",
            },
            {
                "path": "$.tracks[*].clips_present",
                "value": False,
                "explanation": "All tracks have no clips.",
            },
        ],
        "checks_run": ["audio_engine_enabled", "transport_running"],
        "fix_steps": ["Enable the audio engine."],
    }

    valid, errors = validate_report(report, ai_key)
    assert valid is True
    assert errors == []


def test_validate_report_fails_for_invalid_json():
    valid, errors = validate_report("{bad", {"project": {}})
    assert valid is False
    assert any("report_json is not valid JSON" in error for error in errors)


def test_validate_report_fails_for_schema_errors():
    report = {
        "intent": "no_sound",
        "diagnosis": "Missing fields example",
    }
    valid, errors = validate_report(report, {"project": {}})
    assert valid is False
    assert any("schema error" in error for error in errors)


def test_validate_report_fails_for_path_and_value_mismatch():
    ai_key = {"project": {"audio_engine_enabled": False}}
    report = {
        "intent": "no_sound",
        "diagnosis": "Mismatch example",
        "root_cause_category": "audio_engine_disabled",
        "confidence": "high",
        "evidence": [
            {
                "path": "$.project.transport_running",
                "value": True,
                "explanation": "Path missing.",
            },
            {
                "path": "$.project.audio_engine_enabled",
                "value": True,
                "explanation": "Wrong value.",
            },
        ],
        "checks_run": ["audio_engine_enabled"],
        "fix_steps": ["Enable audio engine."],
    }

    valid, errors = validate_report(report, ai_key)
    assert valid is False
    assert any("path does not exist in AI Key" in error for error in errors)
    assert any("value mismatch" in error for error in errors)
