"""Prompt builders for local LLM extraction."""

from __future__ import annotations

import json

from ..schemas import ActionExtraction, Segment


def build_action_extraction_prompt(segments: list[Segment]) -> str:
    """Prompt for strict JSON action extraction."""
    schema_json = json.dumps(ActionExtraction.model_json_schema(), indent=2)
    lines = [f"[{segment.index}] {segment.text}" for segment in segments]
    transcript_block = "\n".join(lines)

    return (
        "You are extracting action items from a meeting transcript.\n"
        "Return ONLY valid JSON that conforms exactly to this JSON schema.\n"
        "Do not include markdown, prose, or code fences.\n\n"
        "JSON schema:\n"
        f"{schema_json}\n\n"
        "Rules:\n"
        "- Keep action_items focused and concrete.\n"
        "- If owner is unknown, use null.\n"
        "- If due date is unknown, use null.\n"
        "- source_segment must reference the segment index where evidence appears.\n"
        "- confidence must be between 0 and 1.\n"
        "- If there are no actions, return an empty action_items list and a short summary.\n\n"
        "Transcript segments:\n"
        f"{transcript_block}\n"
    )
