import json
from pathlib import Path

import pytest

from llm_router_agent.deterministic import diagnose_no_sound


FIXTURES = Path("fixtures/ai_key")

CASES = [
    ("no_sound_audio_engine_off.json", "audio_engine_disabled", "$.project.audio_engine_enabled", 1),
    ("no_sound_transport_stopped.json", "transport_stopped", "$.project.transport_running", 2),
    ("no_sound_master_muted.json", "muted_master", "$.master_track.muted", 3),
    ("no_sound_master_volume_silenced.json", "master_level_silenced", "$.master_track.volume_db", 4),
    ("no_sound_no_clips.json", "no_clips", "$.tracks[*].clips_present", 5),
]


@pytest.mark.parametrize("fname, expected_category, expected_path, expected_checks_len", CASES)
def test_deterministic_no_sound_mapping(fname, expected_category, expected_path, expected_checks_len):
    data = json.loads((FIXTURES / fname).read_text())
    report = diagnose_no_sound(data)

    assert report["root_cause_category"] == expected_category
    assert report["confidence"] == "high"
    assert report["evidence"][0]["path"] == expected_path

    # checks_run should be ordered and include up to match
    assert report["checks_run"][0] == "audio_engine_enabled"
    assert report["checks_run"] == report["checks_run"][:]  # list
    assert len(report["checks_run"]) == expected_checks_len

    expected_order = [
        "audio_engine_enabled",
        "transport_running",
        "master_track_muted",
        "master_track_volume_silenced",
        "clips_present_any",
    ]
    assert report["checks_run"] == expected_order[:expected_checks_len]
