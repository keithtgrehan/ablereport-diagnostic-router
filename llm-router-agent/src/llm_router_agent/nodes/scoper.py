"""Scoper node."""

from __future__ import annotations

import uuid

from ..json_io import invoke_parse_validate
from ..prompts import scoper_prompt
from ..router import Router
from ..schemas import TaskList


def scope_decomposition_node(state: dict, router: Router) -> dict:
    """Decompose project description into tasks."""
    team = state.get("team")
    team_skills: list[list[str]] = []
    if team is not None and getattr(team, "team_members", None):
        team_skills = [member.skills for member in team.team_members]

    prompt = scoper_prompt(
        project_description=state.get("project_description", ""),
        team_skills=team_skills,
    )
    tasks: TaskList = invoke_parse_validate(router, "scoper", prompt, TaskList)

    for task in tasks.task:
        if not task.id:
            task.id = str(uuid.uuid4())[:4]

    return {"tasks": tasks}
