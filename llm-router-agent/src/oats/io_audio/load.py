"""Local audio file loading utilities."""

from __future__ import annotations

import subprocess
from pathlib import Path

from ..schemas import AudioMetadata

SUPPORTED_AUDIO_EXTENSIONS = {
    ".wav",
    ".mp3",
    ".m4a",
    ".aac",
    ".flac",
    ".ogg",
    ".opus",
    ".webm",
    ".mp4",
}


def _probe_duration_seconds(audio_path: Path) -> float | None:
    """Best-effort duration probe using ffprobe when available."""
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(audio_path),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except (FileNotFoundError, subprocess.SubprocessError):
        return None

    raw = proc.stdout.strip()
    if not raw:
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    return round(value, 3)


def load_audio_metadata(audio_path: str | Path) -> AudioMetadata:
    """Validate and load audio file metadata."""
    path = Path(audio_path).expanduser().resolve()

    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {path}")
    if not path.is_file():
        raise ValueError(f"Audio path is not a file: {path}")
    if path.suffix.lower() not in SUPPORTED_AUDIO_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_AUDIO_EXTENSIONS))
        raise ValueError(
            f"Unsupported audio extension '{path.suffix}'. Supported: {supported}"
        )

    stat = path.stat()
    return AudioMetadata(
        path=str(path),
        file_name=path.name,
        extension=path.suffix.lower(),
        size_bytes=stat.st_size,
        duration_seconds=_probe_duration_seconds(path),
    )
