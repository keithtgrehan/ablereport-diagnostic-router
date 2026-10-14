"""Minimal Ollama HTTP client for local inference."""

from __future__ import annotations

import json
from dataclasses import dataclass
from urllib import error, request


@dataclass(slots=True)
class OllamaClient:
    """Lightweight client for Ollama /api/generate endpoint."""

    base_url: str
    model: str
    timeout_seconds: float = 90.0

    def generate(self, prompt: str) -> str:
        """Generate non-streaming completion and return text response."""
        url = f"{self.base_url.rstrip('/')}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0},
        }
        data = json.dumps(payload).encode("utf-8")
        req = request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as resp:
                raw = resp.read().decode("utf-8")
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Ollama HTTP {exc.code}: {body}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"Could not reach Ollama at {url}: {exc.reason}") from exc

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Ollama returned non-JSON response") from exc

        response_text = parsed.get("response")
        if not isinstance(response_text, str) or not response_text.strip():
            raise RuntimeError("Ollama response did not contain text in 'response'.")

        return response_text.strip()
