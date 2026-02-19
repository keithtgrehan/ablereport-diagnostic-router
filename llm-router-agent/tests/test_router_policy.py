from llm_router_agent.router import route


def test_router_policy_mapping():
    scoper = route("scoper")
    assert scoper.primary == "groq"
    assert scoper.fallback is None

    mapper = route("mapper")
    assert mapper.primary == "ollama"
    assert mapper.fallback == "groq"

    scheduler = route("scheduler")
    assert scheduler.primary == "ollama"
