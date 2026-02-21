"""Allocator node."""

from __future__ import annotations

from typing import Any

from pydantic import AliasChoices, BaseModel, Field, model_validator

from ..json_io import invoke_parse_validate
from ..prompts import allocator_prompt
from ..router import Router
from ..schemas import TaskAllocation, TaskAllocationList


def _standardize_to_list(data: Any, key_alias: str = "id") -> list[dict]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        converted: list[dict] = []
        for key, value in data.items():
            if isinstance(value, dict):
                item = {key_alias: key}
                item.update(value)
                converted.append(item)
        return converted
    return []


class SimpleAllocItem(BaseModel):
    task_id: str = Field(
        ...,
        validation_alias=AliasChoices("task_id", "id", "task_name", "task"),
    )
    member_name: str = Field(
        ...,
        validation_alias=AliasChoices(
            "member_name",
            "member",
            "assignee",
            "allocated_to",
            "team_member",
            "assigned_to",
            "team_member_name",
            "person",
            "name",
        ),
    )


class SimpleAlloc(BaseModel):
    allocs: list[SimpleAllocItem]

    @model_validator(mode="before")
    @classmethod
    def wrap(cls, data: Any) -> Any:
        target = data
        if isinstance(data, dict):
            for key in [
                "allocations",
                "allocs",
                "assignments",
                "task_allocation",
                "task_allocations",
                "team",
            ]:
                if key in data:
                    target = data[key]
                    break

        if isinstance(target, dict):
            first_value = next(iter(target.values()), None)

            # {"Alice": [{"task_id": "t1"}, ...]}
            if isinstance(first_value, list):
                flattened: list[dict] = []
                for member_name, tasks in target.items():
                    if not isinstance(tasks, list):
                        continue
                    for task_data in tasks:
                        if not isinstance(task_data, dict):
                            continue
                        task_id = (
                            task_data.get("task_id")
                            or task_data.get("id")
                            or task_data.get("task")
                            or task_data.get("task_name")
                        )
                        if task_id:
                            flattened.append(
                                {"task_id": str(task_id), "member_name": str(member_name)}
                            )
                if flattened:
                    return {"allocs": flattened}

            # {"TaskA": "Alice"}
            if all(isinstance(value, str) for value in target.values()):
                return {
                    "allocs": [
                        {"task_id": str(task_id), "member_name": str(member_name)}
                        for task_id, member_name in target.items()
                    ]
                }

            return {"allocs": _standardize_to_list(target, key_alias="task_id")}

        if isinstance(target, list):
            return {"allocs": target}
        return data


def resource_allocation_node(state: dict, router: Router) -> dict:
    """Allocate tasks to team members."""
    prompt = allocator_prompt(state.get("tasks"), state.get("team"))
    response: SimpleAlloc = invoke_parse_validate(router, "allocator", prompt, SimpleAlloc)

    tasks_obj = state.get("tasks")
    team_obj = state.get("team")
    if tasks_obj is None or team_obj is None:
        return {"task_allocations": TaskAllocationList(task_allocations=[])}

    task_by_id = {task.id: task for task in tasks_obj.task if task.id}
    task_by_name = {task.task_name: task for task in tasks_obj.task}
    members_by_name = {member.name: member for member in team_obj.team_members}

    final_allocations: list[TaskAllocation] = []
    for item in response.allocs:
        task = task_by_id.get(str(item.task_id)) or task_by_name.get(str(item.task_id))
        member = members_by_name.get(item.member_name)
        if task and member:
            final_allocations.append(TaskAllocation(task=task, team_member=member))

    return {"task_allocations": TaskAllocationList(task_allocations=final_allocations)}
