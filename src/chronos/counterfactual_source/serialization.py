"""Deterministic serialization for Phase 3.1 source-state artifacts."""

from __future__ import annotations

import hashlib
import json
import types
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Union, get_args, get_origin, get_type_hints

from chronos.snapshot.serialization import contains_secret

from .errors import CounterfactualSourceStateSerializationError
from .models import CounterfactualSourceState


_SEMANTICALLY_VOLATILE = {"created_at", "semantic_fingerprint"}


def source_state_to_dict(
    state: CounterfactualSourceState,
    *,
    include_volatile: bool,
) -> dict[str, Any]:
    value = _to_primitive(state, include_volatile=include_volatile)
    if not isinstance(value, dict):
        raise CounterfactualSourceStateSerializationError(
            "Counterfactual source-state root must be an object."
        )
    return value


def source_state_to_json(
    state: CounterfactualSourceState,
    *,
    include_volatile: bool,
) -> str:
    return json.dumps(
        source_state_to_dict(state, include_volatile=include_volatile),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def source_state_semantic_fingerprint(
    state: CounterfactualSourceState,
) -> str:
    payload = source_state_to_json(
        state,
        include_volatile=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def source_state_from_json(value: str) -> CounterfactualSourceState:
    try:
        raw = json.loads(value)
    except json.JSONDecodeError as exc:
        raise CounterfactualSourceStateSerializationError(
            "Counterfactual source-state JSON is invalid."
        ) from exc
    if not isinstance(raw, dict):
        raise CounterfactualSourceStateSerializationError(
            "Counterfactual source-state JSON root must be an object."
        )
    stored_fingerprint = raw.get("semantic_fingerprint")
    try:
        state = _decode(CounterfactualSourceState, raw)
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, CounterfactualSourceStateSerializationError):
            raise
        raise CounterfactualSourceStateSerializationError(
            "Source-state JSON does not match schema version 1.0."
        ) from exc
    if stored_fingerprint != state.semantic_fingerprint:
        raise CounterfactualSourceStateSerializationError(
            "Source-state semantic fingerprint does not match its content."
        )
    if contains_secret(state.to_dict()):
        raise CounterfactualSourceStateSerializationError(
            "Source-state artifact contains credential-shaped content."
        )
    return state


def export_source_state(
    state: CounterfactualSourceState,
    path: str | Path,
) -> Path:
    if contains_secret(state.to_dict()):
        raise CounterfactualSourceStateSerializationError(
            "Refusing to export credential-shaped source-state content."
        )
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(state.to_json() + "\n", encoding="utf-8")
    return target


def load_source_state(path: str | Path) -> CounterfactualSourceState:
    return source_state_from_json(Path(path).read_text(encoding="utf-8"))


def _to_primitive(value: Any, *, include_volatile: bool) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {
            item.name: _to_primitive(
                getattr(value, item.name),
                include_volatile=include_volatile,
            )
            for item in fields(value)
            if include_volatile or item.name not in _SEMANTICALLY_VOLATILE
        }
    if isinstance(value, (tuple, list)):
        return [
            _to_primitive(item, include_volatile=include_volatile)
            for item in value
        ]
    if isinstance(value, dict):
        return {
            str(key): _to_primitive(item, include_volatile=include_volatile)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    return value


def _decode(expected: Any, value: Any) -> Any:
    origin = get_origin(expected)
    args = get_args(expected)
    if origin is tuple:
        item_type = args[0] if args else Any
        return tuple(_decode(item_type, item) for item in value)
    if origin in (Union, types.UnionType):
        if value is None and type(None) in args:
            return None
        for item_type in args:
            if item_type is type(None):
                continue
            try:
                return _decode(item_type, value)
            except (TypeError, ValueError, KeyError):
                continue
        raise CounterfactualSourceStateSerializationError(
            f"Value does not match expected union: {expected!r}."
        )
    if expected is Any:
        return value
    if isinstance(expected, type) and issubclass(expected, Enum):
        return expected(value)
    if isinstance(expected, type) and is_dataclass(expected):
        if not isinstance(value, dict):
            raise CounterfactualSourceStateSerializationError(
                f"Expected object for {expected.__name__}."
            )
        hints = get_type_hints(expected)
        return expected(
            **{
                item.name: _decode(hints[item.name], value[item.name])
                for item in fields(expected)
                if item.init
            }
        )
    if expected in (str, int, float, bool) and not isinstance(value, expected):
        raise CounterfactualSourceStateSerializationError(
            f"Expected {expected.__name__}, observed {type(value).__name__}."
        )
    return value
