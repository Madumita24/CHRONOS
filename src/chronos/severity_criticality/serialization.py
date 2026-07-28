"""Deterministic serialization for Phase 4.3 severity analysis."""

from __future__ import annotations

import hashlib
import json
import types
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Union, get_args, get_origin, get_type_hints

from chronos.snapshot.serialization import contains_secret

from .errors import SeverityCriticalitySerializationError
from .models import SeverityCriticalityAnalysis


_VOLATILE = {"created_at", "semantic_fingerprint"}


def severity_to_dict(
    result: SeverityCriticalityAnalysis,
    *,
    include_volatile: bool,
) -> dict[str, Any]:
    value = _primitive(result, include_volatile)
    if not isinstance(value, dict):
        raise SeverityCriticalitySerializationError(
            "Severity analysis root must be an object."
        )
    return value


def severity_to_json(
    result: SeverityCriticalityAnalysis,
    *,
    include_volatile: bool,
) -> str:
    return json.dumps(
        severity_to_dict(result, include_volatile=include_volatile),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def severity_semantic_fingerprint(
    result: SeverityCriticalityAnalysis,
) -> str:
    payload = severity_to_json(
        result,
        include_volatile=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def severity_from_json(value: str) -> SeverityCriticalityAnalysis:
    try:
        raw = json.loads(value)
    except json.JSONDecodeError as exc:
        raise SeverityCriticalitySerializationError(
            "Severity analysis JSON is invalid."
        ) from exc
    if not isinstance(raw, dict):
        raise SeverityCriticalitySerializationError(
            "Severity analysis JSON root must be an object."
        )
    stored = raw.get("semantic_fingerprint")
    try:
        result = _decode(SeverityCriticalityAnalysis, raw)
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, SeverityCriticalitySerializationError):
            raise
        raise SeverityCriticalitySerializationError(
            "Severity analysis JSON does not match schema 1.0."
        ) from exc
    if stored != result.semantic_fingerprint:
        raise SeverityCriticalitySerializationError(
            "Severity analysis fingerprint mismatch."
        )
    if contains_secret(result.to_dict()):
        raise SeverityCriticalitySerializationError(
            "Severity analysis contains credential-shaped data."
        )
    return result


def export_severity_analysis(
    result: SeverityCriticalityAnalysis,
    path: str | Path,
) -> Path:
    if contains_secret(result.to_dict()):
        raise SeverityCriticalitySerializationError(
            "Refusing to export credential-shaped severity analysis."
        )
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(result.to_json() + "\n", encoding="utf-8")
    return target


def load_severity_analysis(
    path: str | Path,
) -> SeverityCriticalityAnalysis:
    return severity_from_json(Path(path).read_text(encoding="utf-8"))


def _primitive(value: Any, include_volatile: bool) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {
            item.name: _primitive(getattr(value, item.name), include_volatile)
            for item in fields(value)
            if include_volatile or item.name not in _VOLATILE
        }
    if isinstance(value, (tuple, list)):
        return [_primitive(item, include_volatile) for item in value]
    return value


def _decode(expected: Any, value: Any) -> Any:
    origin = get_origin(expected)
    args = get_args(expected)
    if origin is tuple:
        if not isinstance(value, list):
            raise SeverityCriticalitySerializationError(
                "Expected JSON array."
            )
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
        raise SeverityCriticalitySerializationError(
            f"Value does not match expected union: {expected!r}."
        )
    if expected is Any:
        return value
    if isinstance(expected, type) and issubclass(expected, Enum):
        return expected(value)
    if isinstance(expected, type) and is_dataclass(expected):
        if not isinstance(value, dict):
            raise SeverityCriticalitySerializationError(
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
        raise SeverityCriticalitySerializationError(
            f"Expected {expected.__name__}, "
            f"observed {type(value).__name__}."
        )
    return value
