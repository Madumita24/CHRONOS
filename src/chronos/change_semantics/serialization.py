"""Deterministic serialization for Phase 2.3 semantic contracts."""

from __future__ import annotations

import hashlib
import json
import types
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Union, get_args, get_origin, get_type_hints

from chronos.snapshot.serialization import contains_secret

from .errors import ChangeSemanticContractSerializationError
from .models import ChangeSemanticContract


_SEMANTICALLY_VOLATILE = {"created_at", "semantic_fingerprint"}


def contract_to_dict(
    contract: ChangeSemanticContract,
    *,
    include_volatile: bool,
) -> dict[str, Any]:
    value = _to_primitive(contract, include_volatile=include_volatile)
    if not isinstance(value, dict):
        raise ChangeSemanticContractSerializationError(
            "Semantic contract root must be an object."
        )
    return value


def contract_to_json(
    contract: ChangeSemanticContract,
    *,
    include_volatile: bool,
) -> str:
    return json.dumps(
        contract_to_dict(contract, include_volatile=include_volatile),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def contract_semantic_fingerprint(
    contract: ChangeSemanticContract,
) -> str:
    payload = contract_to_json(
        contract,
        include_volatile=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def contract_from_json(value: str) -> ChangeSemanticContract:
    try:
        raw = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ChangeSemanticContractSerializationError(
            "Semantic contract JSON is invalid."
        ) from exc
    if not isinstance(raw, dict):
        raise ChangeSemanticContractSerializationError(
            "Semantic contract JSON root must be an object."
        )
    stored_fingerprint = raw.get("semantic_fingerprint")
    try:
        contract = _decode(ChangeSemanticContract, raw)
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, ChangeSemanticContractSerializationError):
            raise
        raise ChangeSemanticContractSerializationError(
            "Semantic contract JSON does not match schema version 1.0."
        ) from exc
    if stored_fingerprint != contract.semantic_fingerprint:
        raise ChangeSemanticContractSerializationError(
            "Semantic contract fingerprint does not match its content."
        )
    if contains_secret(contract.to_dict()):
        raise ChangeSemanticContractSerializationError(
            "Semantic contract contains credential-shaped content."
        )
    return contract


def export_contract(
    contract: ChangeSemanticContract,
    path: str | Path,
) -> Path:
    if contains_secret(contract.to_dict()):
        raise ChangeSemanticContractSerializationError(
            "Refusing to export a contract containing credential-shaped data."
        )
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(contract.to_json() + "\n", encoding="utf-8")
    return target


def load_contract(path: str | Path) -> ChangeSemanticContract:
    return contract_from_json(Path(path).read_text(encoding="utf-8"))


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
        raise ChangeSemanticContractSerializationError(
            f"Value does not match expected union: {expected!r}."
        )
    if expected is Any:
        return value
    if isinstance(expected, type) and issubclass(expected, Enum):
        return expected(value)
    if isinstance(expected, type) and is_dataclass(expected):
        if not isinstance(value, dict):
            raise ChangeSemanticContractSerializationError(
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
        raise ChangeSemanticContractSerializationError(
            f"Expected {expected.__name__}, observed {type(value).__name__}."
        )
    return value
