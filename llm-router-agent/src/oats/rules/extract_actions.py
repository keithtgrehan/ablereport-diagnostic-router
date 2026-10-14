"""Deterministic regex heuristics for action extraction."""

from __future__ import annotations

import re
from typing import Iterable

from ..schemas import ActionItem, Segment

_MARKER_RE = re.compile(
    r"(?i)\b(todo|action item|next step|follow up|follow-up|owner:)\b"
)
_MODAL_RE = re.compile(
    r"(?i)\b(?:i|we|you|[A-Z][a-z]+)\s+"
    r"(?:will|should|must|need to|needs to|can)\s+(.+?)"
    r"(?:[.!?]|$)"
)
_OWNER_RE = re.compile(
    r"(?i)^\s*(?P<owner>[A-Z][a-z]+)\s+"
    r"(?:will|should|must|needs to|can|to)\b"
)
_DUE_RE = re.compile(
    r"(?i)\b(?:by|before|on)\s+"
    r"(?P<due>(?:\d{4}-\d{2}-\d{2}|tomorrow|next week|monday|tuesday|wednesday|"
    r"thursday|friday|saturday|sunday|"
    r"jan(?:uary)?\s+\d{1,2}(?:,\s*\d{4})?|"
    r"feb(?:ruary)?\s+\d{1,2}(?:,\s*\d{4})?|"
    r"mar(?:ch)?\s+\d{1,2}(?:,\s*\d{4})?|"
    r"apr(?:il)?\s+\d{1,2}(?:,\s*\d{4})?|"
    r"may\s+\d{1,2}(?:,\s*\d{4})?|"
    r"jun(?:e)?\s+\d{1,2}(?:,\s*\d{4})?|"
    r"jul(?:y)?\s+\d{1,2}(?:,\s*\d{4})?|"
    r"aug(?:ust)?\s+\d{1,2}(?:,\s*\d{4})?|"
    r"sep(?:t(?:ember)?)?\s+\d{1,2}(?:,\s*\d{4})?|"
    r"oct(?:ober)?\s+\d{1,2}(?:,\s*\d{4})?|"
    r"nov(?:ember)?\s+\d{1,2}(?:,\s*\d{4})?|"
    r"dec(?:ember)?\s+\d{1,2}(?:,\s*\d{4})?))\b"
)


def _normalize_task(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip(" .;:-")


def _extract_from_clause(clause: str, segment_index: int) -> ActionItem | None:
    cleaned = _normalize_task(clause)
    if not cleaned:
        return None

    marker_hit = _MARKER_RE.search(cleaned)
    modal_hit = _MODAL_RE.search(cleaned)
    if marker_hit is None and modal_hit is None:
        return None

    task_text = cleaned
    if marker_hit:
        task_text = _MARKER_RE.sub("", task_text, count=1)
        task_text = task_text.lstrip(" :-")
    if modal_hit:
        task_text = modal_hit.group(1).strip()

    task_text = _normalize_task(task_text)
    if len(task_text) < 3:
        return None

    owner_match = _OWNER_RE.search(cleaned)
    due_match = _DUE_RE.search(cleaned)
    confidence = 0.9 if marker_hit else 0.75

    return ActionItem(
        task=task_text,
        owner=owner_match.group("owner") if owner_match else None,
        due_date=due_match.group("due") if due_match else None,
        source_segment=segment_index,
        confidence=confidence,
    )


def extract_actions_from_segments(segments: Iterable[Segment]) -> list[ActionItem]:
    """Extract action items from transcript segments using regex heuristics."""
    results: list[ActionItem] = []
    seen: set[str] = set()

    for segment in segments:
        clauses = [part.strip() for part in re.split(r"[\n;]", segment.text)]
        for clause in clauses:
            candidate = _extract_from_clause(clause, segment.index)
            if candidate is None:
                continue

            dedupe_key = candidate.task.lower()
            if dedupe_key in seen:
                continue

            seen.add(dedupe_key)
            results.append(candidate)

    return results
