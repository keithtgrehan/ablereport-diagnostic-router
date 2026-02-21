"""LangGraph builder for the PM assistant pipeline."""

from __future__ import annotations

from typing import Any

from .nodes.allocator import resource_allocation_node
from .nodes.auditor import risk_audit_node
from .nodes.capacity_audit import capacity_audit_node
from .nodes.mapper import dependency_mapping_node
from .nodes.optimizer import optimization_insight_node
from .nodes.scheduler import smart_scheduler_node
from .nodes.scoper import scope_decomposition_node
from .router import ModelRegistry, Router, RouterPolicy


def _default_router() -> Router:
    registry = ModelRegistry()
    policy = RouterPolicy(default_provider=registry.llm_provider)
    return Router(registry=registry, policy=policy)


def build_graph(router: Router | None = None):
    """Build and compile the project-planning graph."""
    try:
        from langgraph.graph import END, StateGraph
    except ImportError as exc:
        raise RuntimeError(
            "langgraph is required to build the workflow. Install with: pip install langgraph"
        ) from exc

    active_router = router if router is not None else _default_router()

    def _merge(node_fn):
        def _wrapped(state: dict[str, Any]) -> dict[str, Any]:
            out = node_fn(state, active_router)
            if not isinstance(out, dict):
                raise TypeError(
                    f"Node {node_fn.__name__} must return dict, got {type(out).__name__}"
                )
            return {**state, **out}

        return _wrapped

    def routing_logic(state: dict[str, Any]):
        scores = state.get("project_risk_score_iterations", [])
        last_score = scores[-1] if scores else 999
        if state.get("iteration_number", 0) >= state.get("max_iteration", 1) or last_score < 15:
            return END
        return "optimizer"

    workflow = StateGraph(dict)

    workflow.add_node("scoper", _merge(scope_decomposition_node))
    workflow.add_node("mapper", _merge(dependency_mapping_node))
    workflow.add_node("scheduler", _merge(smart_scheduler_node))
    workflow.add_node("allocator", _merge(resource_allocation_node))
    workflow.add_node("capacity_audit", _merge(capacity_audit_node))
    workflow.add_node("auditor", _merge(risk_audit_node))
    workflow.add_node("optimizer", _merge(optimization_insight_node))

    workflow.set_entry_point("scoper")
    workflow.add_edge("scoper", "mapper")
    workflow.add_edge("mapper", "scheduler")
    workflow.add_edge("scheduler", "allocator")
    workflow.add_edge("allocator", "capacity_audit")
    workflow.add_edge("capacity_audit", "auditor")
    workflow.add_conditional_edges("auditor", routing_logic)
    workflow.add_edge("optimizer", "scheduler")

    return workflow.compile()
