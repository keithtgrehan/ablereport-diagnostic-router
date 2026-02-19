"""Optimizer node: emits one concrete risk-reduction suggestion."""

from __future__ import annotations

from typing import Any

from pydantic import AliasChoices, BaseModel, Field

from .. import router
from ..json_io import parse_validate_loop
from ..prompts import optimizer_prompt
from ..schemas import AgentState


class OptimizerOutput(BaseModel):
    insight: str = Field(
        ...,
        validation_alias=AliasChoices(
            "insight",
            "recommendation",
            "suggestion",
            "action",
            "text",
        ),
    )


def _resolve_llms(node_name: str):
    resolved = router.get_llm(node_name)
    if isinstance(resolved, tuple):
        return resolved
    return resolved, None


def node(state: AgentState) -> dict:
    prompt = optimizer_prompt(state)
    primary_llm, fallback_llm = _resolve_llms("optimizer")

    try:
        response: OptimizerOutput = parse_validate_loop(
            llm=primary_llm,
            prompt=prompt,
            model_cls=OptimizerOutput,
            max_retries=1,
        )
        return {"insights": state.get("insights", []) + [response.insight]}
    except RuntimeError:
        if fallback_llm is None:
            raise
        response = parse_validate_loop(
            llm=fallback_llm,
            prompt=prompt,
            model_cls=OptimizerOutput,
            max_retries=1,
        )
        return {"insights": state.get("insights", []) + [response.insight]}


# Backward-compatible export name.
optimization_insight_node = node
