"""Canonical serialization and semantic hashing helpers."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any


def canonicalize(value: Any) -> Any:
    if is_dataclass(value):
        value = asdict(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {
            str(key): canonicalize(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (tuple, list)):
        return [canonicalize(item) for item in value]
    if isinstance(value, Path):
        return value.name
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(
        canonicalize(value),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def pretty_json(value: Any) -> str:
    return json.dumps(
        canonicalize(value),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"


def semantic_fingerprint(value: Any) -> str:
    digest = hashlib.sha256(
        canonical_json(_semantic_value(value)).encode("utf-8")
    ).hexdigest()
    return f"sha256:{digest}"


def stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:20]
    return f"{prefix}-{digest}"


def _semantic_value(value: Any) -> Any:
    """Remove explicitly volatile presentation fields before hashing."""
    volatile = {"created_at", "generated_at", "output_dir"}
    if isinstance(value, dict):
        return {
            key: _semantic_value(item)
            for key, item in value.items()
            if key not in volatile
        }
    if isinstance(value, (list, tuple)):
        return [_semantic_value(item) for item in value]
    return value
