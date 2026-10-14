"""Structured schemas for Offline Audio Transcriber & Summarizer (OATS)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

PipelineMode = Literal["deterministic", "validated_llm", "llm_optional"]


class AudioMetadata(BaseModel):
    """Minimal local audio file metadata."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    path: str
    file_name: str
    extension: str
    size_bytes: int = Field(ge=0)
    duration_seconds: float | None = Field(default=None, ge=0)


class ASRResult(BaseModel):
    """ASR engine output."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    engine: str
    language: str | None = None
    transcript: str = Field(min_length=1)


class Segment(BaseModel):
    """Deterministic transcript segment."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    index: int = Field(ge=0)
    text: str = Field(min_length=1)
    start_char: int = Field(ge=0)
    end_char: int = Field(ge=0)

    @model_validator(mode="after")
    def _validate_offsets(self) -> "Segment":
        if self.end_char < self.start_char:
            raise ValueError("end_char must be >= start_char")
        return self


class ActionItem(BaseModel):
    """Structured action item extracted from transcript."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    task: str = Field(min_length=3, max_length=300)
    owner: str | None = Field(default=None, max_length=120)
    due_date: str | None = Field(default=None, max_length=64)
    source_segment: int = Field(ge=0)
    confidence: float = Field(ge=0.0, le=1.0)


class ActionExtraction(BaseModel):
    """Top-level extraction payload used for deterministic and validated LLM modes."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    summary: str = Field(default="")
    action_items: list[ActionItem] = Field(default_factory=list)


class SentimentSignal(BaseModel):
    """Optional deterministic sentiment signal."""

    model_config = ConfigDict(extra="forbid")

    label: Literal["positive", "neutral", "negative"]
    score: float = Field(ge=-1.0, le=1.0)


class RunBundle(BaseModel):
    """Persisted run artifact payload."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    created_at: datetime
    mode: PipelineMode
    audio: AudioMetadata
    asr: ASRResult
    transcript_clean: str = Field(default="")
    segments: list[Segment] = Field(default_factory=list)
    deterministic_actions: list[ActionItem] = Field(default_factory=list)
    extracted: ActionExtraction
    sentiment: SentimentSignal | None = None
    warnings: list[str] = Field(default_factory=list)
