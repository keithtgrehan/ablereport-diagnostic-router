"""Routing policy and model registry for llm_router_agent."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Callable, Literal

from dotenv import load_dotenv

load_dotenv()

Provider = Literal["ollama", "groq"]


class RouterPolicy:
    """Static routing policy used by workflow nodes."""

    scoper_provider = "groq"
    mapper_provider = "fallback"  # ollama primary, groq fallback
    default_provider = "ollama"


@dataclass(frozen=True)
class NodeRoute:
    """Resolved route for a node."""

    node_name: str
    primary: Provider
    fallback: Provider | None = None


def _normalize_provider(value: str | None) -> Provider:
    normalized = (value or "").strip().lower()
    if normalized == "groq":
        return "groq"
    return "ollama"


def _build_ollama() -> Any:
    try:
        from langchain_ollama import ChatOllama
    except ImportError as exc:
        raise RuntimeError(
            "langchain-ollama is required. Install with: pip install langchain-ollama"
        ) from exc

    kwargs: dict[str, Any] = {
        "model": os.getenv("OLLAMA_MODEL", "llama3.1:8b"),
        "temperature": float(os.getenv("LLM_TEMPERATURE", "0.1")),
    }
    base_url = os.getenv("OLLAMA_BASE_URL")
    if base_url:
        kwargs["base_url"] = base_url
    return ChatOllama(**kwargs)


def _build_groq() -> Any:
    try:
        from langchain_groq import ChatGroq
    except ImportError as exc:
        raise RuntimeError(
            "langchain-groq is required. Install with: pip install langchain-groq"
        ) from exc

    if not os.getenv("GROQ_API_KEY"):
        raise RuntimeError("GROQ_API_KEY is required for Groq routes.")

    return ChatGroq(
        model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        temperature=float(os.getenv("LLM_TEMPERATURE", "0.1")),
    )


def model_registry() -> dict[Provider, Callable[[], Any]]:
    """Return provider builders for lazy model construction."""
    return {"ollama": _build_ollama, "groq": _build_groq}


@lru_cache(maxsize=2)
def _get_provider_llm(provider: Provider) -> Any:
    registry = model_registry()
    return registry[provider]()


def route(node_name: str) -> NodeRoute:
    """Resolve node provider policy."""
    node = (node_name or "").strip().lower()

    if node == "scoper":
        return NodeRoute(node_name="scoper", primary="groq", fallback=None)

    if node == "mapper":
        if RouterPolicy.mapper_provider == "fallback":
            return NodeRoute(node_name="mapper", primary="ollama", fallback="groq")
        provider = _normalize_provider(RouterPolicy.mapper_provider)
        fallback = "groq" if provider == "ollama" else "ollama"
        return NodeRoute(node_name="mapper", primary=provider, fallback=fallback)

    if node in {"scheduler", "allocator", "capacity_audit", "auditor", "optimizer"}:
        return NodeRoute(node_name=node, primary="ollama", fallback="groq")

    default = _normalize_provider(os.getenv("LLM_PROVIDER", RouterPolicy.default_provider))
    fallback: Provider = "groq" if default == "ollama" else "ollama"
    return NodeRoute(node_name=node or "unknown", primary=default, fallback=fallback)


def get_llm(node_name: str, provider: Provider | None = None):
    """
    Get model(s) for a node.

    - `get_llm(node_name)` -> `(primary_llm, fallback_llm|None)`
    - `get_llm(node_name, provider="ollama"|"groq")` -> single llm (compat mode)
    """
    if provider is not None:
        return _get_provider_llm(_normalize_provider(provider))

    resolved = route(node_name)
    primary_llm = _get_provider_llm(resolved.primary)
    fallback_llm = (
        _get_provider_llm(resolved.fallback) if resolved.fallback is not None else None
    )
    return primary_llm, fallback_llm


def get_fallback_llm(node_name: str):
    """Compatibility helper to fetch only fallback model for a node."""
    resolved = route(node_name)
    if resolved.fallback is None:
        return None
    return _get_provider_llm(resolved.fallback)
