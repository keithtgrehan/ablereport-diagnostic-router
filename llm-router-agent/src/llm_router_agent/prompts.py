"""Prompt templates for PM workflow nodes."""

from __future__ import annotations

import json
from typing import Any

JSON_ONLY_PREFIX = "Return ONLY valid JSON. No markdown. No commentary."


def _dump_for_prompt(value: Any) -> str:
    if value is None:
        return "null"
    if hasattr(value, "model_dump"):
        payload = value.model_dump()
    elif isinstance(value, list):
        payload = [
            item.model_dump() if hasattr(item, "model_dump") else item for item in value
        ]
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


def _team_skills(team: Any) -> list[list[str]]:
    if team is None or not getattr(team, "team_members", None):
        return []
    return [member.skills for member in team.team_members]


def scoper_prompt(project_description: str, team: Any) -> str:
    return (
        f"{JSON_ONLY_PREFIX}\n"
        f"Project: {project_description}\n"
        f"Team skills: {_team_skills(team)}\n"
        "Required fields: task_name, task_description, estimated_day, required_skill.\n"
        "Rules: 10-15 tasks, each <=3 days, no person names in output.\n"
        'Example: {"tasks":[{"task_name":"Setup Repo","task_description":"Init repo and CI","estimated_day":1,"required_skill":"DevOps"}]}'
    )


def mapper_prompt(tasks_fmt: str) -> str:
    return (
        f"{JSON_ONLY_PREFIX}\n"
        f"Tasks:\n{tasks_fmt}\n"
        "Required fields: task_id, dependent_on (array of task IDs).\n"
        'Example: {"dependencies":[{"task_id":"t1","dependent_on":[]},{"task_id":"t2","dependent_on":["t1"]}]}'
    )


def scheduler_prompt(state: dict[str, Any]) -> str:
    return (
        f"{JSON_ONLY_PREFIX}\n"
        f"Tasks: {_dump_for_prompt(state.get('tasks'))}\n"
        f"Dependencies: {_dump_for_prompt(state.get('dependencies', []))}\n"
        f"Insights: {_dump_for_prompt(state.get('insights', []))}\n"
        "Required fields: task_id, start, end (integers).\n"
        "Rules: no nulls; if loops exist, break and return best-effort integers.\n"
        'Example: {"items":[{"task_id":"t1","start":0,"end":2},{"task_id":"t2","start":2,"end":4}]}'
    )


def allocator_prompt(state: dict[str, Any]) -> str:
    return (
        f"{JSON_ONLY_PREFIX}\n"
        f"Tasks: {_dump_for_prompt(state.get('tasks'))}\n"
        f"Team: {_dump_for_prompt(state.get('team'))}\n"
        "Required fields: task_id, member_name.\n"
        "Rule: assign every task to one team member.\n"
        'Example: {"allocs":[{"task_id":"t1","member_name":"Alice"},{"task_id":"t2","member_name":"Bob"}]}'
    )


def auditor_prompt(state: dict[str, Any]) -> str:
    return (
        f"{JSON_ONLY_PREFIX}\n"
        f"Schedule: {_dump_for_prompt(state.get('schedule'))}\n"
        f"Allocations: {_dump_for_prompt(state.get('task_allocations'))}\n"
        "Required fields: task_name, score (0-10), reason.\n"
        'Example: {"risks":[{"task_name":"Auth API","score":8,"reason":"Complex edge cases"}]}'
    )


def optimizer_prompt(state: dict[str, Any]) -> str:
    return (
        f"{JSON_ONLY_PREFIX}\n"
        f"Risks: {_dump_for_prompt(state.get('risks'))}\n"
        f"Insights so far: {_dump_for_prompt(state.get('insights', []))}\n"
        "Required field: insight.\n"
        'Example: {"insight":"Move security testing earlier and pair QA on auth tasks."}'
    )


def capacity_audit_exception_prompt(state: dict[str, Any], error: Exception) -> str:
    return (
        "Provide one concise fallback insight for capacity audit failure.\n"
        f"Error: {error}\n"
        f"Schedule: {_dump_for_prompt(state.get('schedule'))}\n"
        f"Allocations: {_dump_for_prompt(state.get('task_allocations'))}\n"
        'Required field: insight. Example: {"insight":"Rebalance Bob tasks on day 3 to Alice."}'
    )
