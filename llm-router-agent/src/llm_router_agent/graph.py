"""LangGraph builder for the PM assistant pipeline."""

from __future__ import annotations

from .nodes.allocator import resource_allocation_node
from .nodes.auditor import risk_audit_node
from .nodes.capacity_audit import capacity_audit_node
from .nodes.mapper import dependency_mapping_node
from .nodes.optimizer import optimization_insight_node
from .nodes.scheduler import smart_scheduler_node
from .nodes.scoper import scope_decomposition_node
from .schemas import AgentState


def build_graph():
    try:
        from langgraph.checkpoint.memory import MemorySaver
        from langgraph.graph import END, StateGraph
    except ImportError as exc:
        raise RuntimeError(
            "langgraph is required to build the workflow. Install with: pip install langgraph"
        ) from exc

    def routing_logic(state: AgentState):
        scores = state.get("project_risk_score_iterations", [])
        last_score = scores[-1] if scores else 999
        if state.get("iteration_number", 0) >= state.get("max_iteration", 1) or last_score < 15:
            return END
        return "optimizer"

    workflow = StateGraph(AgentState)

    workflow.add_node("scoper", scope_decomposition_node)
    workflow.add_node("mapper", dependency_mapping_node)
    workflow.add_node("scheduler", smart_scheduler_node)
    workflow.add_node("allocator", resource_allocation_node)
    workflow.add_node("capacity_audit", capacity_audit_node)
    workflow.add_node("auditor", risk_audit_node)
    workflow.add_node("optimizer", optimization_insight_node)

    workflow.set_entry_point("scoper")
    workflow.add_edge("scoper", "mapper")
    workflow.add_edge("mapper", "scheduler")
    workflow.add_edge("scheduler", "allocator")
    workflow.add_edge("allocator", "capacity_audit")
    workflow.add_edge("capacity_audit", "auditor")
    workflow.add_conditional_edges("auditor", routing_logic)
    workflow.add_edge("optimizer", "scheduler")

    return workflow.compile(checkpointer=MemorySaver())
