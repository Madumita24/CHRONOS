"""Deterministic serialization for Phase 3.5 explanation bundles."""

from __future__ import annotations

import hashlib
import json
import types
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Union, get_args, get_origin, get_type_hints

from chronos.snapshot.serialization import contains_secret

from .errors import ExplanationSerializationError
from .models import ExplanationBundle


_VOLATILE = {"created_at", "semantic_fingerprint"}


def explanation_to_dict(
    bundle: ExplanationBundle,
    *,
    include_volatile: bool,
) -> dict[str, Any]:
    value = _primitive(bundle, include_volatile)
    if not isinstance(value, dict):
        raise ExplanationSerializationError("Explanation root must be an object.")
    return value


def explanation_to_json(
    bundle: ExplanationBundle,
    *,
    include_volatile: bool,
) -> str:
    return json.dumps(
        explanation_to_dict(bundle, include_volatile=include_volatile),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def explanation_semantic_fingerprint(bundle: ExplanationBundle) -> str:
    payload = explanation_to_json(
        bundle,
        include_volatile=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def explanation_from_json(value: str) -> ExplanationBundle:
    try:
        raw = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ExplanationSerializationError(
            "Explanation JSON is invalid."
        ) from exc
    if not isinstance(raw, dict):
        raise ExplanationSerializationError(
            "Explanation JSON root must be an object."
        )
    stored = raw.get("semantic_fingerprint")
    try:
        bundle = _decode(ExplanationBundle, raw)
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, ExplanationSerializationError):
            raise
        raise ExplanationSerializationError(
            "Explanation JSON is invalid or does not match schema 1.0."
        ) from exc
    if stored != bundle.semantic_fingerprint:
        raise ExplanationSerializationError("Explanation fingerprint mismatch.")
    if contains_secret(bundle.to_dict()):
        raise ExplanationSerializationError(
            "Explanation contains credential-shaped content."
        )
    return bundle


def export_explanation_bundle(
    bundle: ExplanationBundle,
    path: str | Path,
) -> Path:
    if contains_secret(bundle.to_dict()):
        raise ExplanationSerializationError(
            "Refusing to export credential-shaped explanation content."
        )
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(bundle.to_json() + "\n", encoding="utf-8")
    return target


def load_explanation_bundle(path: str | Path) -> ExplanationBundle:
    return explanation_from_json(Path(path).read_text(encoding="utf-8"))


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
            raise ExplanationSerializationError("Expected JSON array.")
        item_type = args[0] if args else Any
        return tuple(_decode(item_type, item) for item in value)
    if origin in (Union, types.UnionType):
        if value is None and type(None) in args:
            return None
        for kind in args:
            if kind is type(None):
                continue
            try:
                return _decode(kind, value)
            except (TypeError, ValueError, KeyError):
                continue
        raise TypeError(expected)
    if expected is Any:
        return value
    if isinstance(expected, type) and issubclass(expected, Enum):
        return expected(value)
    if isinstance(expected, type) and is_dataclass(expected):
        if not isinstance(value, dict):
            raise ExplanationSerializationError(
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
        raise ExplanationSerializationError(
            f"Expected {expected.__name__}, observed {type(value).__name__}."
        )
    return value
