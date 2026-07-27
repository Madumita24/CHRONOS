"""Deterministic serialization for Phase 2.4 certification results."""

from __future__ import annotations

import hashlib
import json
import types
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Union, get_args, get_origin, get_type_hints

from chronos.snapshot.serialization import contains_secret

from .errors import Phase2CertificationSerializationError
from .models import Phase2CertificationResult


_SEMANTICALLY_VOLATILE = {"certified_at", "semantic_fingerprint"}


def certification_to_dict(
    result: Phase2CertificationResult,
    *,
    include_volatile: bool,
) -> dict[str, Any]:
    value = _to_primitive(result, include_volatile=include_volatile)
    if not isinstance(value, dict):
        raise Phase2CertificationSerializationError(
            "Certification result root must be an object."
        )
    return value


def certification_to_json(
    result: Phase2CertificationResult,
    *,
    include_volatile: bool,
) -> str:
    return json.dumps(
        certification_to_dict(result, include_volatile=include_volatile),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def certification_semantic_fingerprint(
    result: Phase2CertificationResult,
) -> str:
    payload = certification_to_json(
        result,
        include_volatile=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def certification_from_json(value: str) -> Phase2CertificationResult:
    try:
        raw = json.loads(value)
    except json.JSONDecodeError as exc:
        raise Phase2CertificationSerializationError(
            "Certification result JSON is invalid."
        ) from exc
    if not isinstance(raw, dict):
        raise Phase2CertificationSerializationError(
            "Certification result JSON root must be an object."
        )
    stored_fingerprint = raw.get("semantic_fingerprint")
    try:
        result = _decode(Phase2CertificationResult, raw)
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, Phase2CertificationSerializationError):
            raise
        raise Phase2CertificationSerializationError(
            "Certification JSON does not match schema version 1.0."
        ) from exc
    if stored_fingerprint != result.semantic_fingerprint:
        raise Phase2CertificationSerializationError(
            "Certification fingerprint does not match its content."
        )
    if contains_secret(result.to_dict()):
        raise Phase2CertificationSerializationError(
            "Certification result contains credential-shaped content."
        )
    return result


def export_certification(
    result: Phase2CertificationResult,
    path: str | Path,
) -> Path:
    if contains_secret(result.to_dict()):
        raise Phase2CertificationSerializationError(
            "Refusing to export credential-shaped certification content."
        )
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(result.to_json() + "\n", encoding="utf-8")
    return target


def load_certification(path: str | Path) -> Phase2CertificationResult:
    return certification_from_json(Path(path).read_text(encoding="utf-8"))


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
        raise Phase2CertificationSerializationError(
            f"Value does not match expected union: {expected!r}."
        )
    if expected is Any:
        return value
    if isinstance(expected, type) and issubclass(expected, Enum):
        return expected(value)
    if isinstance(expected, type) and is_dataclass(expected):
        if not isinstance(value, dict):
            raise Phase2CertificationSerializationError(
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
        raise Phase2CertificationSerializationError(
            f"Expected {expected.__name__}, observed {type(value).__name__}."
        )
    return value
