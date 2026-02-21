"""Optimizer node."""

from __future__ import annotations

from ..prompts import optimizer_prompt
from ..router import Router


def optimization_insight_node(state: dict, router: Router) -> dict:
    """Generate one optimization insight and append it to insights."""
    prompt = optimizer_prompt(state.get("risks"))
    raw = router.invoke("optimizer", prompt)
    insight = str(raw).strip()
    if not insight:
        raise RuntimeError("optimizer: empty response")
    return {"insights": state.get("insights", []) + [insight]}
