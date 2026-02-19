"""Auditor node: risk scoring with JSON hardening and fallback."""

from __future__ import annotations

from typing import Any, List

from pydantic import AliasChoices, BaseModel, Field, model_validator

from .. import router
from ..json_io import parse_validate_loop
from ..prompts import auditor_prompt
from ..schemas import AgentState, Risk, RiskList, SafeInt


def _standardize_to_list(data: Any, key_alias: str = "id") -> List[dict]:
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


def _repair_risk_item(item: Any) -> Any:
    if isinstance(item, dict):
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
    score: SafeInt = Field(..., validation_alias=AliasChoices("score", "risk_score", "Risk Score"))
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
    def repair(cls, data: Any) -> Any:
        return _repair_risk_item(data)


class SimpleRiskList(BaseModel):
    risks: List[SimpleRisk]

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


def _resolve_llms(node_name: str):
    resolved = router.get_llm(node_name)
    if isinstance(resolved, tuple):
        return resolved
    return resolved, None


def _to_update(state: AgentState, response: SimpleRiskList) -> dict:
    final_risks = [
        Risk(task_name=risk.task_name, score=risk.score, reason=risk.reason)
        for risk in response.risks
    ]
    project_score = sum(risk.score for risk in final_risks)
    return {
        "risks": RiskList(risks=final_risks),
        "project_risk_score_iterations": state.get("project_risk_score_iterations", [])
        + [project_score],
        "iteration_number": state.get("iteration_number", 0) + 1,
    }


def node(state: AgentState) -> dict:
    primary_llm, fallback_llm = _resolve_llms("auditor")
    prompt = auditor_prompt(state)

    try:
        response: SimpleRiskList = parse_validate_loop(
            llm=primary_llm,
            prompt=prompt,
            model_cls=SimpleRiskList,
            max_retries=1,
        )
        return _to_update(state, response)
    except RuntimeError:
        if fallback_llm is None:
            raise
        response = parse_validate_loop(
            llm=fallback_llm,
            prompt=prompt,
            model_cls=SimpleRiskList,
            max_retries=1,
        )
        return _to_update(state, response)


# Backward-compatible export name.
risk_audit_node = node
