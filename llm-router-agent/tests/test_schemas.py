from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from oats.schemas import (
    ASRResult,
    ActionExtraction,
    ActionItem,
    AudioMetadata,
    RunBundle,
    Segment,
)


def _build_valid_run_bundle(mode: str = "deterministic") -> RunBundle:
    return RunBundle(
        created_at=datetime(2026, 2, 24, 10, 0, tzinfo=UTC),
        mode=mode,
        audio=AudioMetadata(
            path="/tmp/sample.wav",
            file_name="sample.wav",
            extension=".wav",
            size_bytes=128,
            duration_seconds=1.25,
        ),
        asr=ASRResult(engine="transcript-override", language="en", transcript="hello"),
        transcript_clean="hello",
        segments=[Segment(index=0, text="hello", start_char=0, end_char=5)],
        deterministic_actions=[
            ActionItem(
                task="Send recap",
                owner="Alex",
                due_date="2026-03-01",
                source_segment=0,
                confidence=0.9,
            )
        ],
        extracted=ActionExtraction(
            summary="One action captured",
            action_items=[
                ActionItem(
                    task="Send recap",
                    owner="Alex",
                    due_date="2026-03-01",
                    source_segment=0,
                    confidence=0.9,
                )
            ],
        ),
        warnings=[],
    )


def test_segment_rejects_reversed_offsets():
    with pytest.raises(ValidationError):
        Segment(index=0, text="bad offsets", start_char=20, end_char=10)


def test_action_extraction_rejects_out_of_range_confidence():
    with pytest.raises(ValidationError):
        ActionExtraction(
            summary="invalid confidence",
            action_items=[
                ActionItem(
                    task="Do the thing",
                    owner="Pat",
                    due_date=None,
                    source_segment=0,
                    confidence=1.5,
                )
            ],
        )


@pytest.mark.parametrize("mode", ["deterministic", "validated_llm", "llm_optional"])
def test_run_bundle_accepts_supported_modes(mode: str):
    bundle = _build_valid_run_bundle(mode=mode)
    assert bundle.mode == mode


def test_run_bundle_rejects_unknown_mode():
    with pytest.raises(ValidationError):
        _build_valid_run_bundle(mode="not_a_mode")
