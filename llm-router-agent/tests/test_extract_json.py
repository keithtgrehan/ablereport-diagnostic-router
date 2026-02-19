from llm_router_agent.json_io import extract_json


def test_extract_json_from_mixed_text_object():
    raw = "Model output: {\"a\": 1, \"b\": [2, 3]} end"
    extracted = extract_json(raw)

    assert extracted is not None
    assert extracted == {"a": 1, "b": [2, 3]}


def test_extract_json_from_fenced_json():
    raw = "```json\n{\"tasks\": [{\"id\": \"t1\"}]}\n```"
    extracted = extract_json(raw)

    assert extracted is not None
    assert extracted == {"tasks": [{"id": "t1"}]}


def test_extract_json_from_embedded_array():
    raw = "prefix text [ {\"x\": 1}, {\"x\": 2} ] suffix"
    extracted = extract_json(raw)

    assert extracted is not None
    assert extracted == [{"x": 1}, {"x": 2}]


def test_extract_json_returns_none_when_no_json():
    raw = "No structured payload in this response."
    assert extract_json(raw) is None
