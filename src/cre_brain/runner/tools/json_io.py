"""Bounded JSON without duplicate keys, nonfinite numbers or recursive payloads."""

import json
import math
from typing import Any

MAX_BYTES = 131072
MAX_DEPTH = 20


def canonical(value: object) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    )
    if len(encoded.encode()) > MAX_BYTES:
        raise ValueError("Tool JSON exceeds size limit")
    return encoded


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _constant(value: str) -> None:
    raise ValueError("Nonfinite JSON number")


def _bound(value: object, depth: int = 0) -> None:
    if depth > MAX_DEPTH:
        raise ValueError("JSON nesting exceeds limit")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Nonfinite JSON number")
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str):
                raise ValueError("JSON object requires string keys")
            _bound(child, depth + 1)
    elif isinstance(value, list):
        for child in value:
            _bound(child, depth + 1)


def parse(raw: str) -> dict[str, Any]:
    if len(raw.encode()) > MAX_BYTES:
        raise ValueError("Tool JSON exceeds size limit")
    value = json.loads(raw, object_pairs_hook=_pairs, parse_constant=_constant)
    _bound(value)
    if not isinstance(value, dict):
        raise ValueError("Tool arguments must be an object")
    return value
