"""Mapper node: dependency mapping (Ollama-first with Groq fallback)."""

from __future__ import annotations

from .. import router
from ..json_io import parse_validate_loop
from ..prompts import mapper_prompt
from ..schemas import AgentState, DependencyList


def _resolve_llms(node_name: str):
    resolved = router.get_llm(node_name)
    if isinstance(resolved, tuple):
        return resolved
    return resolved, None


def node(state: AgentState) -> dict:
    primary_llm, fallback_llm = _resolve_llms("mapper")
    tasks_fmt = "\n".join(
        f"ID: {task.id} | Name: {task.task_name}" for task in state["tasks"].task
    )

    try:
        dependencies: DependencyList = parse_validate_loop(
            llm=primary_llm,
            prompt=mapper_prompt(tasks_fmt),
            model_cls=DependencyList,
            max_retries=1,
        )
    except RuntimeError:
        if fallback_llm is None:
            raise
        dependencies = parse_validate_loop(
            llm=fallback_llm,
            prompt=mapper_prompt(tasks_fmt),
            model_cls=DependencyList,
            max_retries=1,
        )

    return {"dependencies": dependencies.dependencies}


# Backward-compatible export name.
dependency_mapping_node = node
