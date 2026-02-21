"""Prompt builders for PM workflow nodes."""

from __future__ import annotations

import json
from typing import Any

JSON_ONLY_PREFIX = "Return ONLY valid JSON. No markdown. No commentary."


def _dump(value: Any) -> str:
    """Serialize Pydantic/list/dict payloads for prompt context."""
    if value is None:
        return "null"
    if hasattr(value, "model_dump"):
        payload = value.model_dump()
    elif isinstance(value, list):
        payload = [item.model_dump() if hasattr(item, "model_dump") else item for item in value]
    elif isinstance(value, dict):
        payload = {
            key: item.model_dump() if hasattr(item, "model_dump") else item
            for key, item in value.items()
        }
    else:
        return str(value)

    try:
        return json.dumps(payload, ensure_ascii=False)
    except TypeError:
        return str(payload)


def _normalize_team_skills(team_skills: list[list[str]] | list[str]) -> list[list[str]]:
    if not team_skills:
        return []
    first = team_skills[0]
    if isinstance(first, str):
        return [list(str(skill) for skill in team_skills)]  # type: ignore[arg-type]
    return [list(str(skill) for skill in group) for group in team_skills]  # type: ignore[arg-type]


def scoper_prompt(project_description: str, team_skills: list[list[str]] | list[str]) -> str:
    """Prompt for task scoping. Expected wrapper: {'tasks': [...]}."""
    skills = _normalize_team_skills(team_skills)
    return (
        f"{JSON_ONLY_PREFIX}\n"
        f"Project: {project_description}\n"
        f"Team skills: {_dump(skills)}\n"
        "Required keys per task: task_name, task_description, estimated_day, required_skill.\n"
        "Rules: 10-15 tasks; each estimated_day <= 3; do not assign people by name.\n"
        'Output shape: {"tasks":[{"task_name":"Setup Repo","task_description":"Initialize repository and CI","estimated_day":1,"required_skill":"DevOps"}]}'
    )


def mapper_prompt(tasks: Any) -> str:
    """Prompt for dependency mapping. Expected wrapper: {'dependencies': [...]}."""
    return (
        f"{JSON_ONLY_PREFIX}\n"
        f"Tasks: {_dump(tasks)}\n"
        "Required keys: task_id, dependent_on (array of task_id).\n"
        'Output shape: {"dependencies":[{"task_id":"t1","dependent_on":[]},{"task_id":"t2","dependent_on":["t1"]}]}'
    )


def scheduler_prompt(tasks: Any, dependencies: Any, insights: Any) -> str:
    """Prompt for scheduling. Preferred output wrapper: {'items': [...]}."""
    return (
        f"{JSON_ONLY_PREFIX}\n"
        f"Tasks: {_dump(tasks)}\n"
        f"Dependencies: {_dump(dependencies)}\n"
        f"Insights: {_dump(insights)}\n"
        "Required keys per item: task_id, start, end (integers).\n"
        "No nulls; break circular dependencies with best-effort integer schedule.\n"
        'Output shape: {"items":[{"task_id":"t1","start":0,"end":2},{"task_id":"t2","start":2,"end":4}]}'
    )


def allocator_prompt(tasks: Any, team: Any) -> str:
    """Prompt for allocation. Expected wrapper: {'allocs': [...]}."""
    return (
        f"{JSON_ONLY_PREFIX}\n"
        f"Tasks: {_dump(tasks)}\n"
        f"Team: {_dump(team)}\n"
        "Required keys: task_id, member_name.\n"
        "Assign every task to exactly one team member.\n"
        'Output shape: {"allocs":[{"task_id":"t1","member_name":"Alice"},{"task_id":"t2","member_name":"Bob"}]}'
    )


def auditor_prompt(schedule: Any, allocations: Any) -> str:
    """Prompt for risk auditing. Expected wrapper: {'risks': [...]}."""
    return (
        f"{JSON_ONLY_PREFIX}\n"
        f"Schedule: {_dump(schedule)}\n"
        f"Allocations: {_dump(allocations)}\n"
        "Required keys: task_name, score, reason. score must be integer 0..10.\n"
        'Output shape: {"risks":[{"task_name":"Auth API","score":8,"reason":"Complex edge cases"}]}'
    )


def optimizer_prompt(risks: Any) -> str:
    """Prompt for one optimization insight as structured JSON."""
    return (
        f"{JSON_ONLY_PREFIX}\n"
        f"Risks: {_dump(risks)}\n"
        "Required key: insight.\n"
        'Output shape: {"insight":"Move security testing earlier and pair QA on auth tasks."}'
    )
