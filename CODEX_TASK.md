# CODEX TASK: Build reusable "llm-router-agent" package for AbleReport

## Goal
Refactor the existing PM Assistant LangGraph notebook/logic into a reusable Python package:
- Repo: llm-router-agent-for-ablereport
- Library folder: llm-router-agent/
- Provide router policy (Groq/Ollama) + JSON hardening + standardized prompts + LangGraph builder + tests.

## Required target structure
llm-router-agent/
  README.md
  pyproject.toml
  src/llm_router_agent/
    __init__.py
    router.py              # routing policy + model registry
    json_io.py             # extract_json, repair_json, parse+validate loop
    prompts.py             # standardized prompt templates + node specs
    nodes/
      scoper.py
      mapper.py
      scheduler.py
      allocator.py
      capacity_audit.py
      auditor.py
      optimizer.py
    graph.py               # graph builder: build_graph()
    schemas.py             # Pydantic models
  examples/
    pm_assistant_demo.ipynb
  tests/
    test_extract_json.py
    test_router_policy.py
    test_node_contracts.py

## Inputs (source code)
Use existing working code from:
- Notebook: 1_PM_assistant_v2_Llama.ipynb (in the older repo)
- Any modular code already present under modular_pm_agent/src/*
Port the logic, do not rewrite behavior unless needed for packaging.

## Routing policy (must implement)
- Scoper node: ALWAYS Groq
- Mapper node: Ollama first, fallback to Groq if JSON invalid/empty
- Scheduler/Allocator/Capacity/Auditor/Optimizer: Ollama-first; fallback to Groq on JSON failure or node exception

## JSON hardening requirement
All nodes that expect JSON must go through json_io utilities:
- strip code fences
- extract first JSON object/array if mixed output
- json.loads + pydantic model_validate
- 1 repair attempt: "Return ONLY valid JSON" prompt
- if still invalid: fallback model (based on router policy)
- raise clear RuntimeError with last raw output snippet

## Prompts
Create standardized prompt templates in prompts.py:
- shared prefix: "Return ONLY valid JSON. No markdown. No commentary."
- per-node spec: fields required, allowed shapes
- keep prompts short and deterministic

## Library API
- build_graph() in graph.py returns a compiled LangGraph graph
- router.py exposes get_llm(node_name) or route(node_name)
- allow env vars:
  - GROQ_API_KEY, GROQ_MODEL
  - OLLAMA_MODEL, OLLAMA_BASE_URL (optional)
  - LLM_PROVIDER default "ollama" but router overrides per node policy

## Demo notebook
examples/pm_assistant_demo.ipynb should:
- create team + project
- run build_graph() and invoke
- print tasks/deps/schedule/allocations/risks
- run self-review (optional toggle RUN_DEEP_REVIEW=False by default)

## Tests (must pass)
- test_extract_json.py: mixed text, fenced json, embedded json extraction
- test_router_policy.py: node->provider mapping is correct
- test_node_contracts.py: node functions accept state and return dict updates with expected keys

## Acceptance criteria
- `pip install -e llm-router-agent` works
- `pytest` passes
- demo notebook runs end-to-end with Ollama installed; Groq required only for Scoper (and fallback)
- no secrets committed
