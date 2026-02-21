"""Routing policy, model registry, and router execution helpers."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Literal

from dotenv import load_dotenv

load_dotenv()

Provider = Literal["ollama", "groq"]
NodeName = Literal[
    "scoper",
    "mapper",
    "scheduler",
    "allocator",
    "capacity_audit",
    "auditor",
    "optimizer",
]

NODE_NAMES: tuple[NodeName, ...] = (
    "scoper",
    "mapper",
    "scheduler",
    "allocator",
    "capacity_audit",
    "auditor",
    "optimizer",
)


@dataclass(frozen=True)
class NodeRoute:
    """Compatibility route object exposed by module-level route()."""

    node_name: str
    primary: Provider
    allow_fallback: bool
    fallback: Provider | None


class ModelRegistry:
    """Build and cache LLM instances from environment configuration."""

    def __init__(self) -> None:
        self.llm_provider: Provider = self._normalize_provider(
            os.getenv("LLM_PROVIDER", "ollama")
        )
        self.ollama_model = os.getenv("OLLAMA_MODEL", "llama3.1")
        self.ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.groq_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        self.groq_api_key = os.getenv("GROQ_API_KEY", "")

        self._ollama_llm: Any | None = None
        self._groq_llm: Any | None = None

    @staticmethod
    def _normalize_provider(value: str | None) -> Provider:
        return "groq" if (value or "").strip().lower() == "groq" else "ollama"

    @property
    def ollama_llm(self) -> Any:
        if self._ollama_llm is None:
            try:
                from langchain_ollama import ChatOllama
            except ImportError as exc:
                raise RuntimeError(
                    "langchain-ollama is required. Install with: pip install langchain-ollama"
                ) from exc

            self._ollama_llm = ChatOllama(
                model=self.ollama_model,
                base_url=self.ollama_base_url,
                temperature=0.1,
                streaming=False,
                request_timeout=60,
            )
        return self._ollama_llm

    @property
    def groq_llm(self) -> Any:
        if self._groq_llm is None:
            if not self.groq_api_key:
                raise RuntimeError("GROQ_API_KEY is required for Groq usage.")
            try:
                from langchain_groq import ChatGroq
            except ImportError as exc:
                raise RuntimeError(
                    "langchain-groq is required. Install with: pip install langchain-groq"
                ) from exc

            self._groq_llm = ChatGroq(model=self.groq_model, temperature=0.1)
        return self._groq_llm

    def get(self, provider: Provider) -> Any:
        if provider == "groq":
            return self.groq_llm
        return self.ollama_llm


class RouterPolicy:
    """Node-level routing policy rules."""

    NODE_NAMES = list(NODE_NAMES)

    def __init__(self, default_provider: Provider = "ollama") -> None:
        self.default_provider = default_provider

    def route(self, node_name: str) -> dict[str, Any]:
        """Return route config: primary, allow_fallback, fallback."""
        node = (node_name or "").strip().lower()

        if node == "scoper":
            return {
                "primary": "groq",
                "allow_fallback": False,
                "fallback": None,
            }
        if node == "mapper":
            return {
                "primary": "ollama",
                "allow_fallback": True,
                "fallback": "groq",
            }
        if node in {"scheduler", "allocator", "capacity_audit", "auditor", "optimizer"}:
            return {
                "primary": "ollama",
                "allow_fallback": True,
                "fallback": "groq",
            }

        fallback: Provider = "groq" if self.default_provider == "ollama" else "ollama"
        return {
            "primary": self.default_provider,
            "allow_fallback": True,
            "fallback": fallback,
        }


class Router:
    """Router that executes primary/fallback invocations based on policy."""

    def __init__(self, registry: ModelRegistry, policy: RouterPolicy) -> None:
        self.registry = registry
        self.policy = policy

    @staticmethod
    def _to_text(response: Any) -> str:
        if hasattr(response, "content"):
            return str(response.content).strip()
        return str(response).strip()

    def _invoke_provider(self, provider: Provider, prompt: str) -> str:
        llm = self.registry.get(provider)
        text = self._to_text(llm.invoke(prompt))
        if text == "":
            raise RuntimeError(f"{provider}: empty response")
        return text

    def invoke_with_fallback(self, node_name: str, prompt: str) -> tuple[str, Provider]:
        """
        Invoke primary provider and fallback once if needed.

        Returns (raw_text, provider_used).
        """
        route_cfg = self.policy.route(node_name)
        primary: Provider = route_cfg["primary"]
        fallback: Provider | None = route_cfg["fallback"]
        allow_fallback: bool = bool(route_cfg["allow_fallback"])

        try:
            return self._invoke_provider(primary, prompt), primary
        except Exception as primary_error:
            if not allow_fallback or fallback is None:
                raise RuntimeError(f"{node_name}: primary invoke failed: {primary_error}") from primary_error

            try:
                return self._invoke_provider(fallback, prompt), fallback
            except Exception as fallback_error:
                raise RuntimeError(
                    f"{node_name}: primary and fallback failed. "
                    f"primary={primary_error}; fallback={fallback_error}"
                ) from fallback_error

    def invoke(self, node_name: str, prompt: str) -> str:
        """Invoke with policy, returning raw text only."""
        raw, _provider = self.invoke_with_fallback(node_name, prompt)
        return raw

    def invoke_fallback(self, node_name: str, prompt: str) -> str:
        """Force fallback provider invocation for a node."""
        route_cfg = self.policy.route(node_name)
        if not route_cfg["allow_fallback"] or route_cfg["fallback"] is None:
            raise RuntimeError(f"{node_name}: fallback is not allowed")
        fallback: Provider = route_cfg["fallback"]
        return self._invoke_provider(fallback, prompt)

    def repair(self, node_name: str, raw_text: str, schema_name: str) -> str:
        """
        Ask provider to repair malformed output as strict JSON.

        Uses primary first, then fallback if policy allows.
        """
        repair_prompt = (
            "Return ONLY valid JSON. No markdown. No commentary.\n"
            f"Fix output for schema: {schema_name}\n\n"
            "BROKEN_OR_MIXED_OUTPUT:\n"
            f"{raw_text}\n"
        )
        route_cfg = self.policy.route(node_name)
        primary: Provider = route_cfg["primary"]
        fallback: Provider | None = route_cfg["fallback"]
        allow_fallback: bool = bool(route_cfg["allow_fallback"])

        try:
            return self._invoke_provider(primary, repair_prompt)
        except Exception as primary_error:
            if not allow_fallback or fallback is None:
                raise RuntimeError(f"{node_name}: repair failed on primary: {primary_error}") from primary_error
            try:
                return self._invoke_provider(fallback, repair_prompt)
            except Exception as fallback_error:
                raise RuntimeError(
                    f"{node_name}: repair failed on both providers. "
                    f"primary={primary_error}; fallback={fallback_error}"
                ) from fallback_error


@lru_cache(maxsize=1)
def _default_router() -> Router:
    registry = ModelRegistry()
    policy = RouterPolicy(default_provider=registry.llm_provider)
    return Router(registry=registry, policy=policy)


def route(node_name: str) -> NodeRoute:
    """Compatibility route helper used by tests and nodes."""
    cfg = _default_router().policy.route(node_name)
    return NodeRoute(
        node_name=(node_name or "").strip().lower() or "unknown",
        primary=cfg["primary"],
        allow_fallback=bool(cfg["allow_fallback"]),
        fallback=cfg["fallback"],
    )


def get_llm(node_name: str, provider: Provider | None = None):
    """
    Compatibility LLM getter.

    - get_llm(node_name) -> (primary_llm, fallback_llm|None)
    - get_llm(node_name, provider=...) -> single llm
    """
    registry = _default_router().registry
    if provider is not None:
        return registry.get(provider)

    cfg = _default_router().policy.route(node_name)
    primary_llm = registry.get(cfg["primary"])
    fallback_llm = None
    if cfg["allow_fallback"] and cfg["fallback"] is not None:
        fallback_llm = registry.get(cfg["fallback"])
    return primary_llm, fallback_llm


def get_fallback_llm(node_name: str):
    """Compatibility fallback getter."""
    cfg = _default_router().policy.route(node_name)
    if not cfg["allow_fallback"] or cfg["fallback"] is None:
        return None
    return _default_router().registry.get(cfg["fallback"])


def invoke(node_name: str, prompt: str) -> str:
    """Module-level invoke wrapper."""
    return _default_router().invoke(node_name, prompt)


def invoke_fallback(node_name: str, prompt: str) -> str:
    """Module-level fallback invoke wrapper."""
    return _default_router().invoke_fallback(node_name, prompt)


def repair(node_name: str, raw_text: str, schema_name: str, **_kwargs: Any) -> str:
    """Module-level repair wrapper."""
    return _default_router().repair(node_name, raw_text, schema_name)
