"""Auditor node."""

from __future__ import annotations

from typing import Any

from pydantic import AliasChoices, BaseModel, Field, model_validator

from ..json_io import invoke_parse_validate
from ..prompts import auditor_prompt
from ..router import Router
from ..schemas import Risk, RiskList, SafeInt


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


def repair_risk_item(item: Any) -> Any:
    """Patch common missing fields from weak risk outputs."""
    if not isinstance(item, dict):
        return item

    if "task_name" not in item:
        if "id" in item:
            item["task_name"] = str(item["id"])
        elif "risk_id" in item:
            item["task_name"] = str(item["risk_id"])
        elif "task_id" in item:
            item["task_name"] = str(item["task_id"])

    if "score" not in item and "impact" in item:
        impact_map = {"high": 8, "medium": 5, "low": 2}
        item["score"] = impact_map.get(str(item["impact"]).lower(), 5)

    if "score" not in item:
        item["score"] = 5

    if "reason" not in item:
        item["reason"] = item.get("description") or item.get("justification") or "No reason"

    return item


class SimpleRisk(BaseModel):
    task_name: str = Field(
        ...,
        validation_alias=AliasChoices(
            "task_name",
            "task",
            "name",
            "risk_id",
            "id",
            "Task Name",
            "Task",
            "ID",
        ),
    )
    score: SafeInt = Field(
        ...,
        validation_alias=AliasChoices("score", "risk_score", "Risk Score"),
    )
    reason: str = Field(
        ...,
        validation_alias=AliasChoices(
            "reason",
            "description",
            "justification",
            "Reason",
            "explanation",
            "Description",
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def patch(cls, data: Any) -> Any:
        return repair_risk_item(data)


class SimpleRiskList(BaseModel):
    risks: list[SimpleRisk]

    @model_validator(mode="before")
    @classmethod
    def wrap(cls, data: Any) -> Any:
        target = data
        if isinstance(data, dict):
            for key in [
                "risks",
                "issues",
                "threats",
                "audit",
                "High-Risk Tasks",
                "tasks",
                "Risk Breakdown",
                "recommendations",
            ]:
                if key in data:
                    target = data[key]
                    break

        if isinstance(target, dict):
            return {"risks": _standardize_to_list(target, key_alias="task_name")}
        if isinstance(target, list):
            return {"risks": target}
        return data


def risk_audit_node(state: dict, router: Router) -> dict:
    """Audit plan risk and update risk history + iteration count."""
    prompt = auditor_prompt(state.get("schedule"), state.get("task_allocations"))
    response: SimpleRiskList = invoke_parse_validate(router, "auditor", prompt, SimpleRiskList)

    final_risks = [
        Risk(task_name=r.task_name, score=r.score, reason=r.reason) for r in response.risks
    ]
    risk_list = RiskList(risks=final_risks)
    project_score = sum(r.score for r in final_risks)

    return {
        "risks": risk_list,
        "project_risk_score_iterations": state.get("project_risk_score_iterations", [])
        + [project_score],
        "iteration_number": state.get("iteration_number", 0) + 1,
    }
