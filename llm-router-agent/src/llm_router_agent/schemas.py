"""Pydantic v2 schemas and workflow state for llm_router_agent."""

from __future__ import annotations

from typing import Annotated, Any, Optional, TypedDict

from pydantic import AliasChoices, BaseModel, BeforeValidator, ConfigDict, Field, model_validator


def force_string(value: Any) -> Optional[str]:
    """Normalize ID-like values to string when present."""
    return str(value) if value is not None else None


def list_to_string(value: Any) -> str:
    """Normalize required_skill values from list or scalar to a string."""
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value) if value is not None else "General"


def force_int(value: Any) -> int:
    """Coerce integer-like values; fallback to -1 on invalid input."""
    if value is None:
        return -1
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1


def to_str_list(value: Any) -> list[str]:
    """Normalize dependency-like values to list[str]."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


StringId = Annotated[Optional[str], BeforeValidator(force_string)]
FlexibleString = Annotated[str, BeforeValidator(list_to_string)]
SafeInt = Annotated[int, BeforeValidator(force_int)]


class SchemaBase(BaseModel):
    """Base schema: ignore unknown keys from noisy LLM outputs."""

    model_config = ConfigDict(extra="ignore")


class Task(SchemaBase):
    """Single scoped task."""

    id: StringId = None
    task_name: str = Field(
        ...,
        validation_alias=AliasChoices(
            "task_name",
            "title",
            "name",
            "task",
            "taskName",
            "TaskName",
            "Name",
        ),
    )
    task_description: str = Field(
        default="",
        validation_alias=AliasChoices(
            "task_description",
            "description",
            "desc",
            "taskDescription",
            "Description",
        ),
    )
    estimated_day: int = Field(
        ...,
        validation_alias=AliasChoices(
            "estimated_day",
            "estimated_days",
            "duration_days",
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
            "requiredSkill",
            "requiredSkills",
            "RequiredSkill",
        ),
    )


class TeamMember(SchemaBase):
    """Team member profile."""

    name: str
    role: str
    skills: list[str]
    seniority: str


class Team(SchemaBase):
    """Team wrapper."""

    team_members: list[TeamMember]


class TaskList(SchemaBase):
    """Task container that accepts multiple list wrapper variants."""

    task: list[Task] = Field(..., validation_alias=AliasChoices("task", "tasks"))

    @model_validator(mode="before")
    @classmethod
    def wrap_list(cls, data: Any) -> Any:
        """
        Accept:
        - raw list -> {"task": list}
        - {"tasks":[...]} -> {"task":[...]}
        - {"task":[...]} -> unchanged
        """
        target = data
        if isinstance(data, dict):
            for key in ["task", "tasks"]:
                if key in data:
                    target = data[key]
                    break

        if isinstance(target, list):
            return {"task": target}
        return data


class Dependency(SchemaBase):
    """Task dependency edge."""

    task_id: str = Field(
        ...,
        validation_alias=AliasChoices("task_id", "id", "task", "taskId", "ID", "TaskID"),
    )
    dependent_on: Annotated[
        list[str],
        BeforeValidator(to_str_list),
    ] = Field(
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
    """Dependency container with map-to-list conversion support."""

    dependencies: list[Dependency] = Field(
        ..., validation_alias=AliasChoices("dependencies", "deps")
    )

    @model_validator(mode="before")
    @classmethod
    def wrap_list(cls, data: Any) -> Any:
        """
        Accept:
        - raw list
        - {"dependencies":[...]} / {"deps":[...]}
        - {"dependencies":{"A":["B"],"C":[]}} -> list conversion
        """
        target = data
        if isinstance(data, dict):
            if "dependencies" in data:
                target = data["dependencies"]
            elif "deps" in data:
                target = data["deps"]

        if isinstance(target, dict):
            return {
                "dependencies": [
                    {"task_id": str(task_id), "dependent_on": to_str_list(depends)}
                    for task_id, depends in target.items()
                ]
            }
        if isinstance(target, list):
            return {"dependencies": target}
        return data


class TaskSchedule(SchemaBase):
    """Scheduled range for a task."""

    task: Task
    start_day: int = Field(..., validation_alias=AliasChoices("start_day", "start"))
    end_day: int = Field(..., validation_alias=AliasChoices("end_day", "end"))


class Schedule(SchemaBase):
    """Schedule container."""

    schedule: list[TaskSchedule]


class TaskAllocation(SchemaBase):
    """Task allocation entry."""

    task: Task
    team_member: TeamMember

    @model_validator(mode="before")
    @classmethod
    def from_flattened(cls, data: Any) -> Any:
        """Accept flattened {'task_id':..., 'member_name':...} allocation rows."""
        if not isinstance(data, dict):
            return data
        if "task" in data and "team_member" in data:
            return data

        task_id = data.get("task_id") or data.get("id") or data.get("task_name") or "unknown"
        task_name = data.get("task_name") or data.get("task") or str(task_id)
        member_name = (
            data.get("member_name")
            or data.get("assignee")
            or data.get("allocated_to")
            or data.get("team_member_name")
            or "Unknown"
        )

        return {
            "task": {
                "id": str(task_id),
                "task_name": str(task_name),
                "task_description": str(data.get("task_description", "")),
                "estimated_day": data.get("estimated_day", 1),
                "required_skill": data.get("required_skill", "General"),
            },
            "team_member": {
                "name": str(member_name),
                "role": str(data.get("member_role", "Unknown")),
                "skills": to_str_list(data.get("member_skills", [])),
                "seniority": str(data.get("member_seniority", "Unknown")),
            },
        }


class TaskAllocationList(SchemaBase):
    """Task allocation container with robust wrapper/map handling."""

    task_allocations: list[TaskAllocation]

    @model_validator(mode="before")
    @classmethod
    def wrap_list(cls, data: Any) -> Any:
        """
        Accept:
        - raw list
        - {"task_allocations":[...]} / {"allocs":[...]} / {"allocations":[...]}
        - {"Task A":"Alice"} -> [{"task_id":"Task A","member_name":"Alice"}]
        """
        target = data
        if isinstance(data, dict):
            for key in ["task_allocations", "allocs", "allocations"]:
                if key in data:
                    target = data[key]
                    break

        if isinstance(target, dict):
            if all(isinstance(v, str) for v in target.values()):
                return {
                    "task_allocations": [
                        {"task_id": str(task_key), "member_name": str(member_name)}
                        for task_key, member_name in target.items()
                    ]
                }

            normalized: list[dict[str, Any]] = []
            for task_key, value in target.items():
                if isinstance(value, dict):
                    item = dict(value)
                else:
                    item = {"member_name": value}
                item.setdefault("task_id", str(task_key))
                normalized.append(item)
            return {"task_allocations": normalized}

        if isinstance(target, list):
            return {"task_allocations": target}
        return data


class Risk(SchemaBase):
    """Risk entry."""

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
    score: int = Field(
        ...,
        validation_alias=AliasChoices("score", "risk_score", "riskScore", "Score"),
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
    """Simple risk list wrapper."""

    risks: list[Risk]

    @model_validator(mode="before")
    @classmethod
    def wrap_list(cls, data: Any) -> Any:
        target = data
        if isinstance(data, dict):
            if "risks" in data:
                target = data["risks"]
            elif "RiskList" in data:
                target = data["RiskList"]
            elif "Risks" in data:
                target = data["Risks"]
        if isinstance(target, list):
            return {"risks": target}
        return data


class AgentState(TypedDict, total=False):
    """Workflow state shared across nodes."""

    project_description: str
    team: Team
    tasks: TaskList
    dependencies: list[dict[str, Any]]
    schedule: Schedule
    task_allocations: TaskAllocationList
    risks: RiskList
    iteration_number: int
    max_iteration: int
    insights: list[str]
    project_risk_score_iterations: list[int]
