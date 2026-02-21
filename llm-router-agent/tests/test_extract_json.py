import json

from llm_router_agent.json_io import extract_json_text


def test_extract_json_text_from_fenced_json():
    raw = "```json\n{\"tasks\": [{\"id\": \"t1\"}]}\n```"
    extracted = extract_json_text(raw)
    assert extracted is not None
    assert json.loads(extracted) == {"tasks": [{"id": "t1"}]}


def test_extract_json_text_from_preamble_and_trailing_text():
    raw = "Here is the payload: {\"ok\": true, \"count\": 2} -- done."
    extracted = extract_json_text(raw)
    assert extracted is not None
    assert json.loads(extracted) == {"ok": True, "count": 2}


def test_extract_json_text_from_array_json():
    raw = "prefix [ {\"x\": 1}, {\"x\": 2} ] suffix"
    extracted = extract_json_text(raw)
    assert extracted is not None
    assert json.loads(extracted) == [{"x": 1}, {"x": 2}]


def test_extract_json_text_returns_none_when_no_json():
    raw = "No structured payload in this response."
    assert extract_json_text(raw) is None
