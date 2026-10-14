"""Runtime configuration for OATS pipeline."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .schemas import PipelineMode


class OATSConfig(BaseModel):
    """Validated runtime configuration."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    audio_path: Path
    mode: PipelineMode = "deterministic"
    runs_root: Path = Path("runs")
    asr_model: str = Field(default="base")
    language: str | None = None
    max_segment_words: int = Field(default=45, ge=10, le=200)
    transcript_override: Path | None = None
    ollama_base_url: str = Field(
        default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    )
    ollama_model: str = Field(
        default_factory=lambda: os.getenv("OLLAMA_MODEL", "llama3.1:8b")
    )
    llm_timeout_seconds: float = Field(default=90.0, ge=1.0, le=600.0)
    include_sentiment: bool = False

    @field_validator("audio_path")
    @classmethod
    def _validate_audio_path(cls, value: Path) -> Path:
        candidate = value.expanduser()
        if not candidate.exists():
            raise ValueError(f"audio path does not exist: {candidate}")
        if not candidate.is_file():
            raise ValueError(f"audio path must be a file: {candidate}")
        return candidate

    @field_validator("transcript_override")
    @classmethod
    def _validate_transcript_override(cls, value: Path | None) -> Path | None:
        if value is None:
            return None
        candidate = value.expanduser()
        if not candidate.exists():
            raise ValueError(f"transcript override does not exist: {candidate}")
        if not candidate.is_file():
            raise ValueError(f"transcript override must be a file: {candidate}")
        return candidate
