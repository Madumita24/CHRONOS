"""Deterministic Phase 3 certification serialization."""

from __future__ import annotations

import hashlib
import json
import types
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Union, get_args, get_origin, get_type_hints

from chronos.snapshot.serialization import contains_secret

from .errors import Phase3CertificationSerializationError
from .models import Phase3CertificationResult


_VOLATILE = {"certified_at", "semantic_fingerprint"}


def phase3_certification_to_dict(
    result: Phase3CertificationResult,
    *,
    include_volatile: bool,
) -> dict[str, Any]:
    value = _primitive(result, include_volatile)
    if not isinstance(value, dict):
        raise Phase3CertificationSerializationError(
            "Phase 3 certification root must be an object."
        )
    return value


def phase3_certification_to_json(
    result: Phase3CertificationResult,
    *,
    include_volatile: bool,
) -> str:
    return json.dumps(
        phase3_certification_to_dict(
            result,
            include_volatile=include_volatile,
        ),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def phase3_certification_semantic_fingerprint(
    result: Phase3CertificationResult,
) -> str:
    payload = phase3_certification_to_json(
        result,
        include_volatile=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def phase3_certification_from_json(value: str) -> Phase3CertificationResult:
    try:
        raw = json.loads(value)
    except json.JSONDecodeError as exc:
        raise Phase3CertificationSerializationError(
            "Phase 3 certification JSON is invalid."
        ) from exc
    if not isinstance(raw, dict):
        raise Phase3CertificationSerializationError(
            "Phase 3 certification JSON root must be an object."
        )
    stored = raw.get("semantic_fingerprint")
    try:
        result = _decode(Phase3CertificationResult, raw)
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, Phase3CertificationSerializationError):
            raise
        raise Phase3CertificationSerializationError(
            "Phase 3 certification JSON does not match schema 1.0."
        ) from exc
    if stored != result.semantic_fingerprint:
        raise Phase3CertificationSerializationError(
            "Phase 3 certification fingerprint mismatch."
        )
    if contains_secret(result.to_dict()):
        raise Phase3CertificationSerializationError(
            "Phase 3 certification contains credential-shaped content."
        )
    return result


def export_phase3_certification(
    result: Phase3CertificationResult,
    path: str | Path,
) -> Path:
    if contains_secret(result.to_dict()):
        raise Phase3CertificationSerializationError(
            "Refusing to export credential-shaped certification content."
        )
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(result.to_json() + "\n", encoding="utf-8")
    return target


def load_phase3_certification(path: str | Path) -> Phase3CertificationResult:
    return phase3_certification_from_json(
        Path(path).read_text(encoding="utf-8")
    )


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
            raise Phase3CertificationSerializationError(
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
        raise Phase3CertificationSerializationError(
            f"Value does not match expected union: {expected!r}."
        )
    if expected is Any:
        return value
    if isinstance(expected, type) and issubclass(expected, Enum):
        return expected(value)
    if isinstance(expected, type) and is_dataclass(expected):
        if not isinstance(value, dict):
            raise Phase3CertificationSerializationError(
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
        raise Phase3CertificationSerializationError(
            f"Expected {expected.__name__}, observed {type(value).__name__}."
        )
    return value
