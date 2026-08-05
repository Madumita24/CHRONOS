"""Shared deterministic parser helpers."""

from __future__ import annotations

from typing import Any

from chronos.structural_engine.serialization import canonicalize, semantic_fingerprint, stable_id


def delta(
    delta_class: str,
    delta_type: str,
    path: str,
    before: Any,
    after: Any,
    *,
    scope: str,
    references: tuple[str, ...] = (),
    material: bool = True,
    explanation: str,
) -> dict[str, Any]:
    value = {
        "delta_class": delta_class,
        "delta_type": delta_type,
        "scope": scope,
        "path": path,
        "before": canonicalize(before),
        "after": canonicalize(after),
        "references": list(sorted(set(references))),
        "material": material,
        "evidence_class": "CODE_DERIVED_EVIDENCE",
        "explanation": explanation,
    }
    value["delta_id"] = stable_id(
        "pr-delta", delta_class, delta_type, path, semantic_fingerprint(value)
    )
    return value


def file_result(
    payload,
    parser_name: str,
    parser_version: str,
    base: Any,
    head: Any,
    deltas: list[dict[str, Any]],
    *,
    resolved_entities: list[dict[str, Any]] | None = None,
    unresolved_references: list[dict[str, Any]] | None = None,
    evidence: list[dict[str, Any]] | None = None,
    warnings: list[str] | None = None,
    status: str = "ANALYZED",
) -> dict[str, Any]:
    return {
        "file_change_id": payload.record.file_change_id,
        "category": payload.record.category.value,
        "parser": {"name": parser_name, "version": parser_version},
        "base_fingerprint": payload.record.base_content_fingerprint,
        "head_fingerprint": payload.record.head_content_fingerprint,
        "parsed_base": canonicalize(base),
        "parsed_head": canonicalize(head),
        "detected_deltas": sorted(deltas, key=lambda item: item["delta_id"]),
        "resolved_entities": sorted(resolved_entities or [], key=lambda item: str(item)),
        "unresolved_references": sorted(unresolved_references or [], key=lambda item: str(item)),
        "evidence_records": sorted(evidence or [], key=lambda item: str(item)),
        "warnings": sorted(set((warnings or []) + list(payload.record.warnings))),
        "analysis_status": status,
    }
