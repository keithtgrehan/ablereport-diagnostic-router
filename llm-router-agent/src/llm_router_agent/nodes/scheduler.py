"""Scheduler node: builds task schedule from dependencies."""

from __future__ import annotations

from typing import Any

from pydantic import AliasChoices, BaseModel, Field, model_validator

from .. import router
from ..json_io import parse_validate_loop
from ..prompts import scheduler_prompt
from ..schemas import AgentState, SafeInt, Schedule, TaskSchedule


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


class SimpleSchedItem(BaseModel):
    task_id: str = Field(..., validation_alias=AliasChoices("task_id", "id", "task_name", "task"))
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


def _resolve_llms(node_name: str):
    resolved = router.get_llm(node_name)
    if isinstance(resolved, tuple):
        return resolved
    return resolved, None


def _to_update(state: AgentState, response: SimpleSched) -> dict:
    task_by_id = {task.id: task for task in state["tasks"].task if task.id}
    task_by_name = {task.task_name: task for task in state["tasks"].task}

    final_schedule: list[TaskSchedule] = []
    for item in response.items:
        task = task_by_id.get(str(item.task_id)) or task_by_name.get(str(item.task_id))
        if not task:
            continue
        start_day = item.start if item.start >= 0 else 0
        end_day = item.end if item.end >= 0 else start_day + 1
        end_day = max(start_day + 1, end_day)
        final_schedule.append(TaskSchedule(task=task, start_day=start_day, end_day=end_day))

    return {"schedule": Schedule(schedule=final_schedule)}


def node(state: AgentState) -> dict:
    primary_llm, fallback_llm = _resolve_llms("scheduler")
    prompt = scheduler_prompt(state)

    try:
        response: SimpleSched = parse_validate_loop(
            llm=primary_llm,
            prompt=prompt,
            model_cls=SimpleSched,
            max_retries=1,
        )
        return _to_update(state, response)
    except RuntimeError:
        if fallback_llm is None:
            raise
        response = parse_validate_loop(
            llm=fallback_llm,
            prompt=prompt,
            model_cls=SimpleSched,
            max_retries=1,
        )
        return _to_update(state, response)


# Backward-compatible export name.
smart_scheduler_node = node
