"""Pydantic v2 schemas and typed workflow state for llm_router_agent."""

from __future__ import annotations

from typing import Annotated, Any, Optional, TypedDict

from pydantic import AliasChoices, BaseModel, BeforeValidator, ConfigDict, Field, model_validator


def force_string(value: Any) -> Optional[str]:
    """Normalize ID-like values to string, preserving null semantics."""
    return str(value) if value is not None else None


def list_to_string(value: Any) -> str:
    """Accept skill values as either a string or list[str] and normalize to one string."""
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value) if value is not None else "General"


def force_int(value: Any) -> int:
    """Coerce numeric-like values to int; return -1 for invalid inputs."""
    if value is None:
        return -1
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1


def coerce_string_list(value: Any) -> list[str]:
    """Normalize list-ish or scalar values into a list[str]."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


StringId = Annotated[Optional[str], BeforeValidator(force_string)]
FlexibleString = Annotated[str, BeforeValidator(list_to_string)]
SafeInt = Annotated[int, BeforeValidator(force_int)]


class SchemaBase(BaseModel):
    """Base schema: ignore unknown fields to tolerate noisy LLM output."""

    model_config = ConfigDict(extra="ignore")


class Task(SchemaBase):
    """Atomic work item produced by scoping and consumed by later nodes."""

    id: StringId = None
    task_name: str = Field(
        ...,
        validation_alias=AliasChoices(
            "title",
            "name",
            "task_name",
            "task",
            "taskName",
            "TaskName",
            "Name",
        ),
    )
    task_description: str = Field(
        default="",
        validation_alias=AliasChoices(
            "description",
            "task_description",
            "desc",
            "taskDescription",
            "Description",
        ),
    )
    estimated_day: int = Field(
        ...,
        validation_alias=AliasChoices(
            "duration_days",
            "estimated_days",
            "estimated_day",
            "duration",
            "time",
            "estimatedDay",
            "EstimatedDay",
        ),
    )
    required_skill: FlexibleString = Field(
        default="General",
        validation_alias=AliasChoices(
            "required_skill",
            "skill",
            "skills",
            "required_skills",
            "requiredSkills",
            "requiredSkill",
            "RequiredSkill",
        ),
    )


class TaskList(SchemaBase):
    """Container for a task list that tolerates common wrapper shapes."""

    task: list[Task] = Field(..., validation_alias=AliasChoices("tasks", "task"))

    @model_validator(mode="before")
    @classmethod
    def wrap_list(cls, data: Any) -> Any:
        """Accept list payloads and wrapper dicts, normalizing to {'task': [...]}."""
        target = data
        if isinstance(data, dict):
            for key in ["tasks", "task", "items", "TaskList", "task_list"]:
                if key in data:
                    target = data[key]
                    break

        if isinstance(target, list):
            return {"task": target}
        return data


class Dependency(SchemaBase):
    """Dependency edge where task_id depends on the listed predecessor IDs."""

    task_id: str = Field(
        ...,
        validation_alias=AliasChoices("task_id", "id", "task", "taskId", "ID", "TaskID"),
    )
    dependent_on: list[str] = Field(
        ...,
        validation_alias=AliasChoices(
            "dependent_on",
            "dependencies",
            "deps",
            "depends_on",
            "dependsOn",
            "Dependencies",
            "DependsOn",
        ),
    )


class DependencyList(SchemaBase):
    """Container for dependency mappings with map-to-list normalization."""

    dependencies: list[Dependency] = Field(
        ..., validation_alias=AliasChoices("dependencies", "deps", "DependencyList")
    )

    @model_validator(mode="before")
    @classmethod
    def wrap_list(cls, data: Any) -> Any:
        """Accept wrapper dicts, raw lists, and {'task': ['dep1']} map formats."""
        target = data
        if isinstance(data, dict):
            for key in [
                "dependencies",
                "deps",
                "items",
                "DependencyList",
                "dependency_list",
            ]:
                if key in data:
                    target = data[key]
                    break

        if isinstance(target, dict):
            return {
                "dependencies": [
                    {"task_id": str(task_id), "dependent_on": coerce_string_list(depends)}
                    for task_id, depends in target.items()
                ]
            }

        if isinstance(target, list):
            return {"dependencies": target}
        return data


class TeamMember(SchemaBase):
    """Single team member record."""

    name: str
    role: str
    skills: list[str]
    seniority: str


class Team(SchemaBase):
    """Team roster used for allocation and planning."""

    team_members: list[TeamMember]


class TaskSchedule(SchemaBase):
    """Scheduled window for one task."""

    task: Task
    start_day: int = Field(..., validation_alias=AliasChoices("start_day", "start"))
    end_day: int = Field(..., validation_alias=AliasChoices("end_day", "end"))


class Schedule(SchemaBase):
    """Container for scheduled tasks."""

    schedule: list[TaskSchedule]


class TaskAllocation(SchemaBase):
    """Assignment of one task to one team member."""

    task: Task
    team_member: TeamMember


class TaskAllocationList(SchemaBase):
    """Container for allocations with resilient dict/list normalization."""

    task_allocations: list[TaskAllocation]

    @model_validator(mode="before")
    @classmethod
    def wrap_list(cls, data: Any) -> Any:
        """
        Accept wrapper dicts and map forms, normalizing to {'task_allocations': [...]}.

        Supported map examples:
        - {"Task A": "Alice"}
        - {"Task A": {"member_name": "Alice", ...}}
        - {"Task A": {"task": {...}, "team_member": {...}}}
        """
        target = data
        if isinstance(data, dict):
            for key in [
                "task_allocations",
                "allocs",
                "allocations",
                "TaskAllocationList",
            ]:
                if key in data:
                    target = data[key]
                    break

        if isinstance(target, dict):
            normalized: list[dict[str, Any]] = []
            for task_key, raw_value in target.items():
                if isinstance(raw_value, dict):
                    item = dict(raw_value)
                else:
                    item = {"member_name": raw_value}

                if "task" not in item:
                    task_id = item.get("task_id") or item.get("id") or str(task_key)
                    task_name = item.get("task_name") or item.get("name") or str(task_key)
                    item["task"] = {
                        "id": str(task_id),
                        "task_name": str(task_name),
                        "task_description": str(item.get("task_description", "")),
                        "estimated_day": item.get("estimated_day", 1),
                        "required_skill": item.get("required_skill", "General"),
                    }

                if "team_member" not in item:
                    member_name = (
                        item.get("member_name")
                        or item.get("assignee")
                        or item.get("allocated_to")
                        or item.get("team_member_name")
                        or "Unknown"
                    )
                    item["team_member"] = {
                        "name": str(member_name),
                        "role": str(item.get("member_role", "Unknown")),
                        "skills": coerce_string_list(item.get("member_skills", [])),
                        "seniority": str(item.get("member_seniority", "Unknown")),
                    }

                normalized.append(item)

            return {"task_allocations": normalized}

        if isinstance(target, list):
            return {"task_allocations": target}
        return data


class Risk(SchemaBase):
    """Risk item produced by the audit step."""

    task_name: str = Field(
        ...,
        validation_alias=AliasChoices(
            "task_name",
            "task",
            "name",
            "taskName",
            "risk_id",
            "id",
            "TaskName",
            "ID",
        ),
    )
    score: SafeInt = Field(
        ..., validation_alias=AliasChoices("score", "risk_score", "riskScore", "Score")
    )
    reason: str = Field(
        ...,
        validation_alias=AliasChoices(
            "reason",
            "description",
            "riskReason",
            "Reason",
            "Description",
        ),
    )


class RiskList(SchemaBase):
    """Container for risk items with flexible wrapper handling."""

    risks: list[Risk]

    @model_validator(mode="before")
    @classmethod
    def wrap_list(cls, data: Any) -> Any:
        """Accept {'risks': [...]}, {'RiskList': [...]}, or raw list payloads."""
        target = data
        if isinstance(data, dict):
            for key in ["risks", "RiskList", "Risks"]:
                if key in data:
                    target = data[key]
                    break

        if isinstance(target, list):
            return {"risks": target}
        return data


class AgentState(TypedDict, total=False):
    """Workflow state shared across LangGraph nodes."""

    project_description: str
    team: Team
    tasks: TaskList
    dependencies: list[Dependency]
    schedule: Schedule
    task_allocations: TaskAllocationList
    risks: RiskList
    iteration_number: int
    max_iteration: int
    insights: list[str]
    project_risk_score_iterations: list[int]
