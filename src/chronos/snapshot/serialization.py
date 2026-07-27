"""Deterministic JSON serialization and round-trip loading for Phase 1.6."""

from __future__ import annotations

import hashlib
import json
import re
import types
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Union, get_args, get_origin, get_type_hints

from .models import CurrentMetadataSnapshot


_VOLATILE_FIELDS = {
    "created_at",
    "observed_at",
    "snapshot_id",
    "semantic_fingerprint",
    "validation_result",
}
_SECRET_KEY = re.compile(
    r"(?i)(^|_)(token|password|secret|authorization|api_key)($|_)"
)
_BEARER = re.compile(r"(?i)\bauthorization\s*[:=]\s*bearer\b")


class SnapshotSerializationError(ValueError):
    """A snapshot artifact could not be safely serialized or reloaded."""


def snapshot_to_dict(
    snapshot: CurrentMetadataSnapshot,
    *,
    include_volatile: bool,
) -> dict[str, Any]:
    value = _to_primitive(snapshot, include_volatile=include_volatile)
    if not isinstance(value, dict):
        raise SnapshotSerializationError("Snapshot root must be an object.")
    return value


def snapshot_to_json(
    snapshot: CurrentMetadataSnapshot,
    *,
    include_volatile: bool,
) -> str:
    return json.dumps(
        snapshot_to_dict(snapshot, include_volatile=include_volatile),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def semantic_fingerprint(snapshot: CurrentMetadataSnapshot) -> str:
    """Hash semantic JSON for change detection, not cryptographic security."""

    payload = snapshot_to_json(snapshot, include_volatile=False).encode(
        "utf-8"
    )
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def snapshot_from_json(value: str) -> CurrentMetadataSnapshot:
    try:
        raw = json.loads(value)
    except json.JSONDecodeError as exc:
        raise SnapshotSerializationError("Snapshot JSON is invalid.") from exc
    if not isinstance(raw, dict):
        raise SnapshotSerializationError("Snapshot JSON root must be an object.")
    snapshot = _decode(CurrentMetadataSnapshot, raw)
    if not isinstance(snapshot, CurrentMetadataSnapshot):
        raise SnapshotSerializationError("Snapshot type reconstruction failed.")
    observed = semantic_fingerprint(snapshot)
    if snapshot.semantic_fingerprint != observed:
        raise SnapshotSerializationError(
            "Snapshot semantic fingerprint does not match its content."
        )
    if contains_secret(snapshot_to_dict(snapshot, include_volatile=True)):
        raise SnapshotSerializationError(
            "Snapshot contains a credential-shaped key or value."
        )
    return snapshot


def export_snapshot(
    snapshot: CurrentMetadataSnapshot,
    path: str | Path,
) -> Path:
    target = Path(path)
    if contains_secret(snapshot_to_dict(snapshot, include_volatile=True)):
        raise SnapshotSerializationError(
            "Refusing to export a snapshot containing credential-shaped data."
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(snapshot.to_json() + "\n", encoding="utf-8")
    return target


def load_snapshot(path: str | Path) -> CurrentMetadataSnapshot:
    return snapshot_from_json(Path(path).read_text(encoding="utf-8"))


def contains_secret(value: object) -> bool:
    if isinstance(value, dict):
        attribute_name = value.get("name")
        if (
            isinstance(attribute_name, str)
            and _SECRET_KEY.search(attribute_name) is not None
        ):
            return True
        return any(
            _SECRET_KEY.search(str(key)) is not None
            or contains_secret(item)
            for key, item in value.items()
        )
    if isinstance(value, (tuple, list)):
        return any(contains_secret(item) for item in value)
    return isinstance(value, str) and _BEARER.search(value) is not None


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
            if include_volatile or item.name not in _VOLATILE_FIELDS
        }
    if isinstance(value, tuple):
        return [
            _to_primitive(item, include_volatile=include_volatile)
            for item in value
        ]
    if isinstance(value, list):
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
        raise SnapshotSerializationError(
            f"Value does not match expected union: {expected!r}."
        )
    if expected is Any:
        return value
    if isinstance(expected, type) and issubclass(expected, Enum):
        return expected(value)
    if isinstance(expected, type) and is_dataclass(expected):
        if not isinstance(value, dict):
            raise SnapshotSerializationError(
                f"Expected object for {expected.__name__}."
            )
        hints = get_type_hints(expected)
        return expected(
            **{
                item.name: _decode(hints[item.name], value[item.name])
                for item in fields(expected)
            }
        )
    if expected in (str, int, float, bool):
        if not isinstance(value, expected):
            raise SnapshotSerializationError(
                f"Expected {expected.__name__}, observed {type(value).__name__}."
            )
    return value
