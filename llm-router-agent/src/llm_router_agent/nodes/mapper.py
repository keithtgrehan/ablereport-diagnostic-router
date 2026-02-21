"""Mapper node."""

from __future__ import annotations

from ..json_io import invoke_parse_validate
from ..prompts import mapper_prompt
from ..router import Router
from ..schemas import DependencyList


def dependency_mapping_node(state: dict, router: Router) -> dict:
    """Map task dependencies."""
    tasks = state.get("tasks")
    prompt = mapper_prompt(tasks)
    dependency_list: DependencyList = invoke_parse_validate(
        router,
        "mapper",
        prompt,
        DependencyList,
    )
    return {"dependencies": dependency_list.dependencies}
