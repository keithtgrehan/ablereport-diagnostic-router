"""CLI entrypoint for Offline Audio Transcriber & Summarizer (OATS)."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from .asr.whisper_fw import transcribe_offline
from .config import OATSConfig
from .io_audio.load import load_audio_metadata
from .llm.ollama_client import OllamaClient
from .llm.prompts import build_action_extraction_prompt
from .reporting.writer import write_run_bundle
from .rules.extract_actions import extract_actions_from_segments
from .rules.quality import clean_and_segment
from .schemas import ActionExtraction, RunBundle, SentimentSignal


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser."""
    parser = argparse.ArgumentParser(description="Offline Audio Transcriber & Summarizer")
    parser.add_argument("--audio", required=True, help="Path to local audio file")
    parser.add_argument(
        "--mode",
        default="deterministic",
        choices=["deterministic", "validated_llm", "llm_optional"],
        help="Pipeline mode",
    )
    parser.add_argument("--runs-root", default="runs", help="Run bundle output root")
    parser.add_argument("--asr-model", default="base", help="Local Whisper model name")
    parser.add_argument("--language", default=None, help="Optional ASR language override")
    parser.add_argument(
        "--segment-words",
        type=int,
        default=45,
        help="Max words per deterministic segment",
    )
    parser.add_argument(
        "--transcript-override",
        default=None,
        help="Optional .txt transcript path to bypass ASR",
    )
    parser.add_argument(
        "--ollama-base-url",
        default=None,
        help="Ollama base URL (default from OLLAMA_BASE_URL or http://localhost:11434)",
    )
    parser.add_argument(
        "--ollama-model",
        default=None,
        help="Ollama model (default from OLLAMA_MODEL or llama3.1:8b)",
    )
    parser.add_argument(
        "--llm-timeout",
        type=float,
        default=90.0,
        help="Ollama timeout in seconds",
    )
    parser.add_argument(
        "--include-sentiment",
        action="store_true",
        help="Include lightweight deterministic sentiment signal",
    )
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command line arguments."""
    return build_parser().parse_args(argv)


def _extract_json_text(raw: str) -> str:
    """Extract first JSON object from mixed text responses."""
    text = raw.strip()
    text = text.replace("```json", "").replace("```JSON", "").replace("```", "").strip()

    if text.startswith("{") and text.endswith("}"):
        return text

    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < 0 or end <= start:
        raise ValueError("LLM output does not contain a JSON object.")
    return text[start : end + 1]


def _validate_llm_extraction(raw: str) -> ActionExtraction:
    """Strictly validate LLM JSON with Pydantic."""
    json_text = _extract_json_text(raw)
    return ActionExtraction.model_validate_json(json_text)


def _deterministic_sentiment(text: str) -> SentimentSignal:
    """Simple local sentiment signal based on keyword balance."""
    tokens = [token.strip(".,!?;:\"'()[]{}") for token in text.lower().split()]
    positive = {
        "great",
        "good",
        "excellent",
        "happy",
        "resolved",
        "clear",
        "success",
        "done",
        "improved",
    }
    negative = {
        "bad",
        "issue",
        "problem",
        "blocked",
        "delay",
        "failed",
        "risk",
        "concern",
        "error",
    }

    pos_hits = sum(1 for token in tokens if token in positive)
    neg_hits = sum(1 for token in tokens if token in negative)
    total = max(1, pos_hits + neg_hits)
    score = (pos_hits - neg_hits) / total

    if score > 0.2:
        label = "positive"
    elif score < -0.2:
        label = "negative"
    else:
        label = "neutral"

    return SentimentSignal(label=label, score=round(score, 3))


def _default_summary(clean_text: str, action_count: int) -> str:
    if not clean_text:
        return "Empty transcript."
    if action_count == 0:
        return "Transcript processed with no explicit action items detected."
    return f"Transcript processed successfully with {action_count} action item(s)."


def _build_config(args: argparse.Namespace) -> OATSConfig:
    return OATSConfig(
        audio_path=Path(args.audio),
        mode=args.mode,
        runs_root=Path(args.runs_root),
        asr_model=args.asr_model,
        language=args.language,
        max_segment_words=args.segment_words,
        transcript_override=Path(args.transcript_override)
        if args.transcript_override
        else None,
        ollama_base_url=args.ollama_base_url
        or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        ollama_model=args.ollama_model or os.getenv("OLLAMA_MODEL", "llama3.1:8b"),
        llm_timeout_seconds=args.llm_timeout,
        include_sentiment=bool(args.include_sentiment),
    )


def run_pipeline(config: OATSConfig) -> tuple[RunBundle, Path]:
    """Run full OATS pipeline for one audio input."""
    audio_meta = load_audio_metadata(config.audio_path)
    asr_result = transcribe_offline(
        audio_meta.path,
        model=config.asr_model,
        language=config.language,
        transcript_override=config.transcript_override,
    )

    clean_text, segments = clean_and_segment(
        asr_result.transcript,
        max_words=config.max_segment_words,
    )
    deterministic_actions = extract_actions_from_segments(segments)
    deterministic_payload = ActionExtraction(
        summary=_default_summary(clean_text, len(deterministic_actions)),
        action_items=deterministic_actions,
    )

    final_payload = deterministic_payload
    warnings: list[str] = []

    if config.mode in {"validated_llm", "llm_optional"}:
        prompt = build_action_extraction_prompt(segments)
        llm_client = OllamaClient(
            base_url=config.ollama_base_url,
            model=config.ollama_model,
            timeout_seconds=config.llm_timeout_seconds,
        )
        try:
            llm_raw = llm_client.generate(prompt)
            final_payload = _validate_llm_extraction(llm_raw)
        except (RuntimeError, ValidationError, ValueError, json.JSONDecodeError) as exc:
            if config.mode == "validated_llm":
                raise RuntimeError(
                    "validated_llm mode failed strict schema validation"
                ) from exc
            warnings.append(
                "LLM extraction failed strict validation; using deterministic extraction. "
                f"reason: {exc}"
            )

    sentiment = _deterministic_sentiment(clean_text) if config.include_sentiment else None

    bundle = RunBundle(
        created_at=datetime.now(timezone.utc),
        mode=config.mode,
        audio=audio_meta,
        asr=asr_result,
        transcript_clean=clean_text,
        segments=segments,
        deterministic_actions=deterministic_actions,
        extracted=final_payload,
        sentiment=sentiment,
        warnings=warnings,
    )

    run_dir = write_run_bundle(bundle, runs_root=config.runs_root)
    return bundle, run_dir


def main(argv: list[str] | None = None) -> int:
    """CLI main."""
    args = parse_args(argv)
    config = _build_config(args)
    bundle, run_dir = run_pipeline(config)

    output = {
        "status": "ok",
        "mode": bundle.mode,
        "run_dir": str(run_dir),
        "actions": len(bundle.extracted.action_items),
        "warnings": bundle.warnings,
    }
    print(json.dumps(output, indent=2))
    return 0
