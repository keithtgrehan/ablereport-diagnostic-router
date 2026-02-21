from llm_router_agent.nodes.allocator import resource_allocation_node
from llm_router_agent.nodes.auditor import risk_audit_node
from llm_router_agent.nodes.mapper import dependency_mapping_node
from llm_router_agent.nodes.scheduler import smart_scheduler_node
from llm_router_agent.nodes.scoper import scope_decomposition_node
from llm_router_agent.schemas import (
    Dependency,
    RiskList,
    Schedule,
    TaskAllocationList,
    TaskList,
    Team,
    TeamMember,
)


class FakeRouter:
    def __init__(self, payloads: dict[str, str]) -> None:
        self.payloads = payloads

    def invoke(self, node_name: str, _prompt: str) -> str:
        return self.payloads[node_name]

    def invoke_fallback(self, node_name: str, _prompt: str) -> str:
        return self.payloads[node_name]

    def repair(self, _node_name: str, raw_text: str, _schema_name: str, **_kwargs) -> str:
        return raw_text


def test_node_contracts_with_fake_router():
    payloads = {
        "scoper": (
            "{"
            '"tasks": ['
            '{"task_name":"Define API","task_description":"Define endpoints","estimated_day":1,"required_skill":"Python"},'
            '{"id":"t2","task_name":"Build UI","task_description":"Create frontend","estimated_day":2,"required_skill":"React"}'
            "]}"
        ),
        "mapper": (
            '{"dependencies": ['
            '{"task_id": "Define API", "dependent_on": []},'
            '{"task_id": "t2", "dependent_on": ["Define API"]}'
            "]}"
        ),
        "scheduler": (
            '{"items": ['
            '{"task_id": "Define API", "start": 0, "end": 1},'
            '{"task_id": "t2", "start": 1, "end": 3}'
            "]}"
        ),
        "allocator": (
            '{"allocs": ['
            '{"task_id": "Define API", "member_name": "Alice"},'
            '{"task_id": "t2", "member_name": "Bob"}'
            "]}"
        ),
        "auditor": (
            '{"risks": ['
            '{"task_name":"Define API","score":3,"reason":"Low complexity"},'
            '{"task_name":"Build UI","score":6,"reason":"UI uncertainty"}'
            "]}"
        ),
    }
    router = FakeRouter(payloads)

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

    scoper_updates = scope_decomposition_node(state, router)
    assert "tasks" in scoper_updates
    assert isinstance(scoper_updates["tasks"], TaskList)
    assert len(scoper_updates["tasks"].task) == 2
    assert scoper_updates["tasks"].task[0].id is not None
    assert len(scoper_updates["tasks"].task[0].id) == 4
    assert scoper_updates["tasks"].task[1].id == "t2"
    state.update(scoper_updates)

    mapper_updates = dependency_mapping_node(state, router)
    assert "dependencies" in mapper_updates
    assert isinstance(mapper_updates["dependencies"], list)
    assert all(isinstance(dep, Dependency) for dep in mapper_updates["dependencies"])
    state.update(mapper_updates)

    scheduler_updates = smart_scheduler_node(state, router)
    assert "schedule" in scheduler_updates
    assert isinstance(scheduler_updates["schedule"], Schedule)
    state.update(scheduler_updates)

    allocator_updates = resource_allocation_node(state, router)
    assert "task_allocations" in allocator_updates
    assert isinstance(allocator_updates["task_allocations"], TaskAllocationList)
    state.update(allocator_updates)

    auditor_updates = risk_audit_node(state, router)
    assert "risks" in auditor_updates
    assert isinstance(auditor_updates["risks"], RiskList)
    assert auditor_updates["iteration_number"] == 1
    assert auditor_updates["project_risk_score_iterations"] == [9]
