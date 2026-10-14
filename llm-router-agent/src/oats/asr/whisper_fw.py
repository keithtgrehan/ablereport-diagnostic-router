"""Offline ASR adapters with Whisper-family fallbacks."""

from __future__ import annotations

from pathlib import Path

from ..schemas import ASRResult


def _transcript_from_sidecar(audio_path: Path) -> ASRResult | None:
    sidecar = audio_path.with_suffix(".txt")
    if not sidecar.exists():
        return None

    text = sidecar.read_text(encoding="utf-8").strip()
    if not text:
        return None

    return ASRResult(engine="sidecar-text", language=None, transcript=text)


def transcribe_offline(
    audio_path: str | Path,
    *,
    model: str = "base",
    language: str | None = None,
    transcript_override: str | Path | None = None,
) -> ASRResult:
    """Transcribe locally using faster-whisper/openai-whisper or a text sidecar."""
    path = Path(audio_path).expanduser().resolve()

    if transcript_override is not None:
        text = Path(transcript_override).expanduser().read_text(encoding="utf-8").strip()
        if not text:
            raise ValueError("Transcript override file is empty.")
        return ASRResult(engine="transcript-override", language=language, transcript=text)

    sidecar_result = _transcript_from_sidecar(path)
    if sidecar_result is not None:
        return sidecar_result

    try:
        from faster_whisper import WhisperModel  # type: ignore[import-not-found]

        whisper_model = WhisperModel(model, device="cpu", compute_type="int8")
        segments, info = whisper_model.transcribe(str(path), language=language)
        lines = [segment.text.strip() for segment in segments if segment.text.strip()]
        transcript = " ".join(lines).strip()
        if not transcript:
            raise RuntimeError("faster-whisper returned an empty transcript.")
        return ASRResult(
            engine=f"faster-whisper:{model}",
            language=getattr(info, "language", language),
            transcript=transcript,
        )
    except ImportError:
        pass

    try:
        import whisper  # type: ignore[import-not-found]

        whisper_model = whisper.load_model(model)
        result = whisper_model.transcribe(str(path), language=language, fp16=False)
        transcript = str(result.get("text", "")).strip()
        if not transcript:
            raise RuntimeError("openai-whisper returned an empty transcript.")
        detected_language = result.get("language")
        return ASRResult(
            engine=f"openai-whisper:{model}",
            language=str(detected_language) if detected_language else language,
            transcript=transcript,
        )
    except ImportError as exc:
        raise RuntimeError(
            "No offline Whisper backend found. Install faster-whisper or openai-whisper, "
            "or provide --transcript-override / a same-name .txt sidecar transcript."
        ) from exc
