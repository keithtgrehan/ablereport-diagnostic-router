"""Capacity audit node: detects team overload collisions."""

from __future__ import annotations

from ..schemas import AgentState


def node(state: AgentState) -> dict:
    overloads: list[str] = []
    workload_by_member_day: dict[tuple[str, int], int] = {}

    schedule_obj = state.get("schedule")
    allocations_obj = state.get("task_allocations")

    if schedule_obj is None or allocations_obj is None:
        return {"insights": state.get("insights", []) + ["Capacity audit skipped: missing schedule or allocations"]}

    schedule_lookup: dict[str, object] = {}
    for item in schedule_obj.schedule:
        schedule_lookup[item.task.task_name] = item
        if item.task.id:
            schedule_lookup[item.task.id] = item

    for allocation in allocations_obj.task_allocations:
        task_key = allocation.task.id or allocation.task.task_name
        scheduled = schedule_lookup.get(task_key) or schedule_lookup.get(
            allocation.task.task_name
        )
        if not scheduled:
            continue

        member_name = allocation.team_member.name
        start_day = max(0, scheduled.start_day)
        end_day = max(start_day + 1, scheduled.end_day)

        for day in range(start_day, end_day):
            key = (member_name, day)
            workload_by_member_day[key] = workload_by_member_day.get(key, 0) + 1
            if workload_by_member_day[key] > 1:
                overloads.append(f"{member_name} overloaded on day {day}")

    insight = (
        f"Capacity issues detected: {overloads[:5]}"
        if overloads
        else "No capacity issues detected"
    )
    return {"insights": state.get("insights", []) + [insight]}


# Backward-compatible export name.
capacity_audit_node = node
