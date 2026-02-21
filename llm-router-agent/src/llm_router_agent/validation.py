"""Deterministic validation utilities for diagnostic reports."""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from .models import DiagnosticReport


def _parse_json_input(
    payload: str | dict[str, Any] | list[Any],
    label: str,
    errors: list[str],
) -> Any | None:
    if isinstance(payload, str):
        raw = payload.strip()
        if not raw:
            errors.append(f"{label} is empty.")
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            errors.append(
                f"{label} is not valid JSON: {exc.msg} (line {exc.lineno}, column {exc.colno})."
            )
            return None

    if isinstance(payload, (dict, list)):
        return payload

    errors.append(f"{label} must be a JSON string or a Python dict/list.")
    return None


def _tokenize_json_path(path: str) -> tuple[list[tuple[str, str | int | None]], str | None]:
    if not isinstance(path, str) or path.strip() == "":
        return [], "path must be a non-empty string"
    if not path.startswith("$"):
        return [], "path must start with '$'"

    i = 1
    tokens: list[tuple[str, str | int | None]] = []
    while i < len(path):
        ch = path[i]

        if ch == ".":
            i += 1
            start = i
            while i < len(path) and path[i] not in ".[":
                i += 1
            key = path[start:i]
            if key == "":
                return [], f"empty key segment near index {start}"
            tokens.append(("key", key))
            continue

        if ch == "[":
            end = path.find("]", i)
            if end == -1:
                return [], f"missing closing ']' near index {i}"
            segment = path[i + 1 : end]
            if segment == "*":
                tokens.append(("wildcard", None))
            elif segment.isdigit():
                tokens.append(("index", int(segment)))
            elif (
                len(segment) >= 2
                and segment[0] in {"'", '"'}
                and segment[-1] == segment[0]
            ):
                tokens.append(("key", segment[1:-1]))
            else:
                return [], f"unsupported bracket segment [{segment}]"
            i = end + 1
            continue

        return [], f"unexpected character '{ch}' at index {i}"

    return tokens, None


def _resolve_json_path(data: Any, path: str) -> tuple[list[Any], str | None]:
    tokens, err = _tokenize_json_path(path)
    if err is not None:
        return [], f"invalid JSON path '{path}': {err}"

    nodes: list[Any] = [data]
    for token_type, token_value in tokens:
        next_nodes: list[Any] = []
        for node in nodes:
            if token_type == "key":
                key = str(token_value)
                if isinstance(node, dict) and key in node:
                    next_nodes.append(node[key])
            elif token_type == "index":
                idx = int(token_value)  # guaranteed by tokenizer
                if isinstance(node, list) and 0 <= idx < len(node):
                    next_nodes.append(node[idx])
            elif token_type == "wildcard":
                if isinstance(node, list):
                    next_nodes.extend(node)
                elif isinstance(node, dict):
                    next_nodes.extend(node.values())

        if not next_nodes:
            return [], f"path does not exist in AI Key: {path}"
        nodes = next_nodes

    return nodes, None


def _evidence_matches(path_values: list[Any], expected: Any) -> bool:
    if len(path_values) == 1:
        return path_values[0] == expected
    if isinstance(expected, list):
        return path_values == expected
    return all(value == expected for value in path_values)


def validate_report(
    report_json: str | dict[str, Any] | list[Any],
    ai_key_json: str | dict[str, Any] | list[Any],
) -> tuple[bool, list[str]]:
    """
    Validate a diagnostic report against schema + AI Key evidence consistency.

    Rules:
    - report and AI key must parse as JSON
    - report must conform to DiagnosticReport schema
    - each evidence.path must resolve inside AI key
    - each evidence.value must match resolved AI key value(s)
    """
    errors: list[str] = []

    report_payload = _parse_json_input(report_json, "report_json", errors)
    ai_key_payload = _parse_json_input(ai_key_json, "ai_key_json", errors)

    if report_payload is None or ai_key_payload is None:
        return False, errors

    if not isinstance(report_payload, dict):
        errors.append("report_json must decode to a JSON object.")
        return False, errors
    if not isinstance(ai_key_payload, dict):
        errors.append("ai_key_json must decode to a JSON object.")
        return False, errors

    try:
        report = DiagnosticReport.model_validate(report_payload)
    except ValidationError as exc:
        for detail in exc.errors():
            loc = ".".join(str(part) for part in detail.get("loc", []))
            msg = detail.get("msg", "validation error")
            errors.append(f"schema error at '{loc}': {msg}")
        return False, errors

    for idx, ev in enumerate(report.evidence):
        values, path_error = _resolve_json_path(ai_key_payload, ev.path)
        if path_error is not None:
            errors.append(f"evidence[{idx}].path: {path_error}")
            continue

        if not _evidence_matches(values, ev.value):
            if len(values) == 1:
                errors.append(
                    f"evidence[{idx}].value mismatch at {ev.path}: "
                    f"expected {ev.value!r}, actual {values[0]!r}"
                )
            else:
                errors.append(
                    f"evidence[{idx}].value mismatch at {ev.path}: "
                    f"expected {ev.value!r}, actual values {values!r}"
                )

    return len(errors) == 0, errors

