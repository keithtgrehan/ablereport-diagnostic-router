from llm_router_agent import router
from llm_router_agent.nodes.allocator import resource_allocation_node
from llm_router_agent.nodes.auditor import risk_audit_node
from llm_router_agent.nodes.capacity_audit import capacity_audit_node
from llm_router_agent.nodes.mapper import dependency_mapping_node
from llm_router_agent.nodes.optimizer import optimization_insight_node
from llm_router_agent.nodes.scheduler import smart_scheduler_node
from llm_router_agent.nodes.scoper import scope_decomposition_node
from llm_router_agent.schemas import (
    Schedule,
    Task,
    TaskAllocation,
    TaskAllocationList,
    TaskSchedule,
    Team,
    TeamMember,
)


class _FakeResponse:
    def __init__(self, content: str):
        self.content = content


class _FakeLLM:
    def __init__(self, content: str):
        self._content = content

    def invoke(self, _prompt: str):
        return _FakeResponse(self._content)


def test_node_contracts(monkeypatch):
    payloads = {
        "scoper": (
            "{"
            '"tasks": ['
            '{"id": "t1", "task_name": "Setup Repo", "task_description": "Init repo", "estimated_day": 1, "required_skill": "Python"},'
            '{"id": "t2", "task_name": "Build UI", "task_description": "Create dashboard", "estimated_day": 2, "required_skill": "React"}'
            "]}"
        ),
        "mapper": '{"dependencies": [{"task_id": "t1", "dependent_on": []}, {"task_id": "t2", "dependent_on": ["t1"]}]}',
        "scheduler": '{"items": [{"task_id": "t1", "start": 0, "end": 1}, {"task_id": "t2", "start": 1, "end": 3}]}',
        "allocator": '{"allocs": [{"task_id": "t1", "member_name": "Alice"}, {"task_id": "t2", "member_name": "Bob"}]}',
        "auditor": '{"risks": [{"task_name": "Setup Repo", "score": 3, "reason": "Low complexity"}, {"task_name": "Build UI", "score": 5, "reason": "UI uncertainty"}]}',
        "optimizer": '{"insight":"Move Build UI review one day earlier and add QA pairing."}',
        "capacity_audit": "No capacity issues detected",
    }

    def fake_get_llm(node_name: str, provider=None):
        _ = provider
        return _FakeLLM(payloads[node_name])

    monkeypatch.setattr(router, "get_llm", fake_get_llm)

    state = {
        "project_description": "Create a secure dashboard app",
        "team": Team(
            team_members=[
                TeamMember(name="Alice", role="Lead", skills=["Python"], seniority="Senior"),
                TeamMember(name="Bob", role="Frontend", skills=["React"], seniority="Mid"),
            ]
        ),
        "iteration_number": 0,
        "max_iteration": 2,
        "insights": [],
        "project_risk_score_iterations": [],
    }

    updates = scope_decomposition_node(state)
    assert isinstance(updates, dict)
    assert "tasks" in updates
    state.update(updates)

    updates = dependency_mapping_node(state)
    assert isinstance(updates, dict)
    assert "dependencies" in updates
    state.update(updates)

    updates = smart_scheduler_node(state)
    assert isinstance(updates, dict)
    assert "schedule" in updates
    state.update(updates)

    updates = resource_allocation_node(state)
    assert isinstance(updates, dict)
    assert "task_allocations" in updates
    state.update(updates)

    updates = capacity_audit_node(state)
    assert isinstance(updates, dict)
    assert "insights" in updates
    state.update(updates)

    updates = risk_audit_node(state)
    assert isinstance(updates, dict)
    assert "risks" in updates
    assert "project_risk_score_iterations" in updates
    assert "iteration_number" in updates
    state.update(updates)

    updates = optimization_insight_node(state)
    assert isinstance(updates, dict)
    assert "insights" in updates


def test_capacity_audit_is_deterministic_without_llm(monkeypatch):
    def fail_get_llm(*_args, **_kwargs):
        raise AssertionError("capacity_audit should not call router.get_llm")

    monkeypatch.setattr(router, "get_llm", fail_get_llm)

    member = TeamMember(name="Alice", role="Lead", skills=["Python"], seniority="Senior")
    task = Task(
        id="t1",
        task_name="Setup Repo",
        task_description="Init repo",
        estimated_day=1,
        required_skill="Python",
    )
    state = {
        "insights": [],
        "schedule": Schedule(
            schedule=[
                TaskSchedule(task=task, start_day=0, end_day=2),
                TaskSchedule(task=task, start_day=1, end_day=3),
            ]
        ),
        "task_allocations": TaskAllocationList(
            task_allocations=[
                TaskAllocation(task=task, team_member=member),
                TaskAllocation(task=task, team_member=member),
            ]
        ),
    }

    updates = capacity_audit_node(state)
    assert isinstance(updates, dict)
    assert "insights" in updates
    assert isinstance(updates["insights"], list)
