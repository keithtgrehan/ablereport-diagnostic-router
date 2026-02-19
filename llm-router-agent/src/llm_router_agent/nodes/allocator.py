"""Allocator node: assigns tasks to team members."""

from __future__ import annotations

from typing import Any

from pydantic import AliasChoices, BaseModel, Field, model_validator

from .. import router
from ..json_io import parse_validate_loop
from ..prompts import allocator_prompt
from ..schemas import AgentState, TaskAllocation, TaskAllocationList


def _standardize_to_list(data: Any, key_alias: str = "id") -> list[dict]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        converted = []
        for key, value in data.items():
            if isinstance(value, dict):
                item = {key_alias: key}
                item.update(value)
                converted.append(item)
        return converted
    return []


class SimpleAllocItem(BaseModel):
    task_id: str = Field(..., validation_alias=AliasChoices("task_id", "id", "task_name", "task"))
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
            if isinstance(first_value, list):
                flattened = []
                for member, tasks in target.items():
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
                            flattened.append({"task_id": task_id, "member_name": member})
                if flattened:
                    return {"allocs": flattened}

            if all(isinstance(value, str) for value in target.values()):
                return {
                    "allocs": [
                        {"task_id": key, "member_name": value}
                        for key, value in target.items()
                    ]
                }

            return {"allocs": _standardize_to_list(target, key_alias="task_id")}

        if isinstance(target, list):
            return {"allocs": target}

        return data


def _resolve_llms(node_name: str):
    resolved = router.get_llm(node_name)
    if isinstance(resolved, tuple):
        return resolved
    return resolved, None


def _to_update(state: AgentState, response: SimpleAlloc) -> dict:
    task_by_id = {task.id: task for task in state["tasks"].task if task.id}
    task_by_name = {task.task_name: task for task in state["tasks"].task}
    members = {member.name: member for member in state["team"].team_members}

    final_allocations: list[TaskAllocation] = []
    for allocation in response.allocs:
        task = task_by_id.get(str(allocation.task_id)) or task_by_name.get(
            str(allocation.task_id)
        )
        member = members.get(allocation.member_name)
        if task and member:
            final_allocations.append(TaskAllocation(task=task, team_member=member))

    return {"task_allocations": TaskAllocationList(task_allocations=final_allocations)}


def node(state: AgentState) -> dict:
    primary_llm, fallback_llm = _resolve_llms("allocator")
    prompt = allocator_prompt(state)

    try:
        response: SimpleAlloc = parse_validate_loop(
            llm=primary_llm,
            prompt=prompt,
            model_cls=SimpleAlloc,
            max_retries=1,
        )
        return _to_update(state, response)
    except RuntimeError:
        if fallback_llm is None:
            raise
        response = parse_validate_loop(
            llm=fallback_llm,
            prompt=prompt,
            model_cls=SimpleAlloc,
            max_retries=1,
        )
        return _to_update(state, response)


# Backward-compatible export name.
resource_allocation_node = node
