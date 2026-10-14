"""Deterministic transcript cleaning and segmentation."""

from __future__ import annotations

import re

from ..schemas import Segment

_TIMECODE_RE = re.compile(r"\[?(?:\d{1,2}:)?\d{1,2}:\d{2}\]?")
_MULTI_SPACE_RE = re.compile(r"[ \t]+")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")


def clean_transcript(raw_text: str) -> str:
    """Normalize common ASR artifacts with deterministic rules."""
    text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    text = _TIMECODE_RE.sub(" ", text)
    text = _MULTI_SPACE_RE.sub(" ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def _pack_sentences(sentences: list[str], max_words: int) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    current_words = 0

    for sentence in sentences:
        words = len(sentence.split())
        if current and current_words + words > max_words:
            chunks.append(" ".join(current).strip())
            current = [sentence]
            current_words = words
            continue

        current.append(sentence)
        current_words += words

    if current:
        chunks.append(" ".join(current).strip())

    return [chunk for chunk in chunks if chunk]


def segment_transcript(clean_text: str, max_words: int = 45) -> list[Segment]:
    """Split cleaned transcript into deterministic contiguous segments."""
    if not clean_text.strip():
        return []

    raw_sentences = [part.strip() for part in _SENTENCE_SPLIT_RE.split(clean_text)]
    sentences = [sentence for sentence in raw_sentences if sentence]
    chunks = _pack_sentences(sentences, max_words=max_words)

    segments: list[Segment] = []
    cursor = 0
    for idx, chunk in enumerate(chunks):
        start = clean_text.find(chunk, cursor)
        if start < 0:
            start = cursor
        end = start + len(chunk)
        cursor = end

        segments.append(
            Segment(index=idx, text=chunk, start_char=start, end_char=end)
        )

    return segments


def clean_and_segment(raw_text: str, max_words: int = 45) -> tuple[str, list[Segment]]:
    """Apply deterministic cleaning and segmentation in one step."""
    cleaned = clean_transcript(raw_text)
    segments = segment_transcript(cleaned, max_words=max_words)
    return cleaned, segments
