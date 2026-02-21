from llm_router_agent.router import RouterPolicy


def test_router_policy_scoper_is_groq_without_fallback():
    policy = RouterPolicy(default_provider="ollama")
    cfg = policy.route("scoper")
    assert cfg["primary"] == "groq"
    assert cfg["allow_fallback"] is False
    assert cfg["fallback"] is None


def test_router_policy_mapper_is_ollama_with_groq_fallback():
    policy = RouterPolicy(default_provider="ollama")
    cfg = policy.route("mapper")
    assert cfg["primary"] == "ollama"
    assert cfg["allow_fallback"] is True
    assert cfg["fallback"] == "groq"


def test_router_policy_scheduler_and_related_nodes_use_ollama_with_groq_fallback():
    policy = RouterPolicy(default_provider="ollama")
    for node_name in ["scheduler", "allocator", "capacity_audit", "auditor", "optimizer"]:
        cfg = policy.route(node_name)
        assert cfg["primary"] == "ollama"
        assert cfg["allow_fallback"] is True
        assert cfg["fallback"] == "groq"
