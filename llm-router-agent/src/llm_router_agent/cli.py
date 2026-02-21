"""Minimal CLI for validated no-sound diagnosis."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Callable

from .deterministic import diagnose_no_sound_validated


class _LLMRouter:
    """Router adapter around a single chat model client."""

    def __init__(self, llm: Any) -> None:
        self.llm = llm

    def invoke(self, _node_name: str, prompt: str) -> str:
        response = self.llm.invoke(prompt)
        content = response.content if hasattr(response, "content") else response
        return str(content).strip()


class _OpenAIRouter:
    """Router adapter for OpenAI chat completions."""

    def __init__(self, model: str) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                "openai package is required for --llm-provider openai."
            ) from exc

        self.client = OpenAI()
        self.model = model

    def invoke(self, _node_name: str, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        content = response.choices[0].message.content
        return str(content or "").strip()


def build_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser."""
    parser = argparse.ArgumentParser(description="Validated no-sound diagnostic CLI")
    parser.add_argument("--ai-key", required=True, help="Path to AI Key JSON file")
    parser.add_argument("--no-llm", action="store_true", help="Disable LLM path")
    parser.add_argument(
        "--require-llm",
        action="store_true",
        help="Require validated LLM output (retry once on validation failure)",
    )
    parser.add_argument(
        "--llm-provider",
        default="none",
        choices=["none", "ollama", "groq", "openai"],
        help="LLM provider backend",
    )
    parser.add_argument("--llm-model", default=None, help="LLM model name override")
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse and validate CLI args."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.no_llm and args.require_llm:
        parser.error("--no-llm and --require-llm cannot both be set.")

    if args.llm_provider == "none":
        if args.require_llm:
            parser.error("--llm-provider none cannot be used with --require-llm.")
        args.no_llm = True

    return args


def _load_ai_key(path: str) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text())
    if not isinstance(payload, dict):
        raise ValueError("AI Key file must contain a JSON object.")
    return payload


def _build_provider_router(provider: str, model: str | None):
    if provider == "ollama":
        from langchain_ollama import ChatOllama

        llm = ChatOllama(
            model=model or os.getenv("OLLAMA_MODEL", "llama3.1:latest"),
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            temperature=0.1,
            streaming=False,
            request_timeout=60,
        )
        return _LLMRouter(llm)

    if provider == "groq":
        from langchain_groq import ChatGroq

        llm = ChatGroq(
            model=model or os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            temperature=0.1,
        )
        return _LLMRouter(llm)

    if provider == "openai":
        return _OpenAIRouter(model=model or os.getenv("OPENAI_MODEL", "gpt-4o-mini"))

    raise ValueError(f"Unsupported provider: {provider}")


def run_cli(
    args: argparse.Namespace,
    provider_factory: Callable[[str, str | None], Any] | None = None,
) -> dict[str, Any]:
    """
    Execute CLI logic and return final report JSON object.

    provider_factory exists for tests so provider wiring can be mocked.
    """
    ai_key = _load_ai_key(args.ai_key)
    factory = provider_factory or _build_provider_router

    if args.no_llm:
        return diagnose_no_sound_validated(ai_key, no_llm=True)

    provider_router = factory(args.llm_provider, args.llm_model)
    return diagnose_no_sound_validated(
        ai_key,
        require_llm=args.require_llm,
        router=provider_router,
    )


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    args = parse_args(argv)
    report = run_cli(args)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
