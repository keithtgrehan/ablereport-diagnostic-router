"""Scheduler node."""

from __future__ import annotations

from typing import Any

from pydantic import AliasChoices, BaseModel, Field, model_validator

from ..json_io import invoke_parse_validate
from ..prompts import scheduler_prompt
from ..router import Router
from ..schemas import SafeInt, Schedule, TaskSchedule


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


class SimpleSchedItem(BaseModel):
    task_id: str = Field(
        ...,
        validation_alias=AliasChoices("task_id", "id", "task_name", "task"),
    )
    start: SafeInt = Field(..., validation_alias=AliasChoices("start", "start_day"))
    end: SafeInt = Field(..., validation_alias=AliasChoices("end", "end_day"))


class SimpleSched(BaseModel):
    items: list[SimpleSchedItem]

    @model_validator(mode="before")
    @classmethod
    def wrap(cls, data: Any) -> Any:
        target = data
        if isinstance(data, dict):
            for key in ["tasks", "schedule", "items", "timeline", "task_schedules"]:
                if key in data:
                    target = data[key]
                    break

        if isinstance(target, dict):
            return {"items": _standardize_to_list(target, key_alias="task_id")}
        if isinstance(target, list):
            return {"items": target}
        return data


def smart_scheduler_node(state: dict, router: Router) -> dict:
    """Build schedule from tasks/dependencies/insights."""
    prompt = scheduler_prompt(
        state.get("tasks"),
        state.get("dependencies", []),
        state.get("insights", []),
    )
    response: SimpleSched = invoke_parse_validate(router, "scheduler", prompt, SimpleSched)

    tasks_obj = state.get("tasks")
    if tasks_obj is None:
        return {"schedule": Schedule(schedule=[])}

    task_by_id = {task.id: task for task in tasks_obj.task if task.id}
    task_by_name = {task.task_name: task for task in tasks_obj.task}

    final_schedule: list[TaskSchedule] = []
    for item in response.items:
        task = task_by_id.get(str(item.task_id)) or task_by_name.get(str(item.task_id))
        if task is None:
            continue
        start_day = item.start if item.start >= 0 else 0
        end_day = item.end if item.end >= 0 else start_day + 1
        end_day = max(start_day + 1, end_day)
        final_schedule.append(TaskSchedule(task=task, start_day=start_day, end_day=end_day))

    return {"schedule": Schedule(schedule=final_schedule)}
