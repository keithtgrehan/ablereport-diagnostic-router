"""Scoper node: project decomposition (Groq-only)."""

from __future__ import annotations

import uuid

from .. import router
from ..json_io import parse_validate_loop
from ..prompts import scoper_prompt
from ..schemas import AgentState, TaskList


def _resolve_llms(node_name: str):
    resolved = router.get_llm(node_name)
    if isinstance(resolved, tuple):
        return resolved
    return resolved, None


def node(state: AgentState) -> dict:
    primary_llm, _ = _resolve_llms("scoper")
    tasks: TaskList = parse_validate_loop(
        llm=primary_llm,
        prompt=scoper_prompt(
            project_description=state.get("project_description", ""),
            team=state.get("team"),
        ),
        model_cls=TaskList,
        max_retries=1,
    )

    for task in tasks.task:
        if not task.id:
            task.id = str(uuid.uuid4())[:4]

    return {"tasks": tasks}


# Backward-compatible export name.
scope_decomposition_node = node
