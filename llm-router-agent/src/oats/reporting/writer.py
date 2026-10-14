"""Run bundle writing utilities for OATS."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from ..schemas import RunBundle


def _timestamp_slug(now: datetime | None = None) -> str:
    dt = now or datetime.now()
    return dt.strftime("%Y%m%d_%H%M%S")


def _ensure_unique_run_dir(runs_root: Path, slug: str) -> Path:
    candidate = runs_root / slug
    if not candidate.exists():
        return candidate

    suffix = 1
    while True:
        trial = runs_root / f"{slug}_{suffix}"
        if not trial.exists():
            return trial
        suffix += 1


def _render_report_markdown(bundle: RunBundle, run_dir: Path) -> str:
    lines: list[str] = []
    lines.append("# Offline Audio Transcriber & Summarizer")
    lines.append("")
    lines.append(f"- Run directory: `{run_dir}`")
    lines.append(f"- Mode: `{bundle.mode}`")
    lines.append(f"- Audio: `{bundle.audio.path}`")
    lines.append(f"- ASR engine: `{bundle.asr.engine}`")
    lines.append("")

    lines.append("## Summary")
    lines.append(bundle.extracted.summary or "No summary generated.")
    lines.append("")

    lines.append("## Action Items")
    if not bundle.extracted.action_items:
        lines.append("No action items detected.")
    else:
        for idx, item in enumerate(bundle.extracted.action_items, start=1):
            owner = item.owner or "unassigned"
            due = item.due_date or "unspecified"
            lines.append(
                f"{idx}. {item.task} (owner: {owner}, due: {due}, "
                f"segment: {item.source_segment}, confidence: {item.confidence:.2f})"
            )
    lines.append("")

    if bundle.sentiment is not None:
        lines.append("## Sentiment")
        lines.append(
            f"Label: `{bundle.sentiment.label}`, score: {bundle.sentiment.score:.2f}"
        )
        lines.append("")

    if bundle.warnings:
        lines.append("## Warnings")
        for warning in bundle.warnings:
            lines.append(f"- {warning}")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def write_run_bundle(bundle: RunBundle, runs_root: str | Path = "runs") -> Path:
    """Persist a run bundle under runs/<timestamp>/ and return directory path."""
    root = Path(runs_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)

    run_dir = _ensure_unique_run_dir(root, _timestamp_slug(bundle.created_at))
    run_dir.mkdir(parents=True, exist_ok=False)

    (run_dir / "run.json").write_text(bundle.model_dump_json(indent=2), encoding="utf-8")
    (run_dir / "audio_metadata.json").write_text(
        json.dumps(bundle.audio.model_dump(mode="json"), indent=2), encoding="utf-8"
    )
    (run_dir / "transcript_raw.txt").write_text(bundle.asr.transcript, encoding="utf-8")
    (run_dir / "transcript_clean.txt").write_text(
        bundle.transcript_clean, encoding="utf-8"
    )
    (run_dir / "segments.json").write_text(
        json.dumps([segment.model_dump(mode="json") for segment in bundle.segments], indent=2),
        encoding="utf-8",
    )
    (run_dir / "actions_deterministic.json").write_text(
        json.dumps(
            [item.model_dump(mode="json") for item in bundle.deterministic_actions], indent=2
        ),
        encoding="utf-8",
    )
    (run_dir / "actions_final.json").write_text(
        bundle.extracted.model_dump_json(indent=2), encoding="utf-8"
    )
    (run_dir / "report.md").write_text(
        _render_report_markdown(bundle, run_dir), encoding="utf-8"
    )

    return run_dir
