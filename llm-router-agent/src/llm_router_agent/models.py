"""Pydantic contracts for diagnostic outputs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class EvidenceItem(BaseModel):
    """Single evidence entry supporting the diagnosis."""

    model_config = ConfigDict(extra="forbid")

    path: str
    value: Any
    explanation: str


class DiagnosticReport(BaseModel):
    """Standardized diagnostic report payload."""

    model_config = ConfigDict(extra="forbid")

    intent: str
    diagnosis: str
    root_cause_category: str
    confidence: str
    evidence: list[EvidenceItem]
    checks_run: list[str]
    fix_steps: list[str]
    notes: str | None = None
