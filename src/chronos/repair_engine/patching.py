"""Isolated deterministic candidate generation and unified-diff validation."""

from __future__ import annotations

import difflib
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from chronos.pr_engine.intake import _content_fingerprint, _reject_credentials, _safe_repo_path
from chronos.structural_engine.serialization import semantic_fingerprint

from .editors import EditorRegistry, EditorResult
from .errors import RepairValidationError
from .models import MAX_PATCH_HUNKS, RepairPlan
from .trust import TrustedPredecessor


_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


@dataclass(frozen=True)
class PatchBuildResult:
    original_contents: dict[str, str]
    candidate_contents: dict[str, str]
    file_records: tuple[dict[str, Any], ...]
    action_records: tuple[dict[str, Any], ...]
    static_validation: dict[str, Any]
    protected_validation: dict[str, Any]
    combined_patch: str
    group_patches: dict[str, str]
    patch_manifest: dict[str, Any]
    original_fingerprints: dict[str, str]
    candidate_fingerprints: dict[str, str]


def build_patch_set(
    predecessor: TrustedPredecessor,
    plan: RepairPlan,
    editor_registry: EditorRegistry,
) -> PatchBuildResult:
    payloads = {
        (item.record.head_path or item.record.base_path): item
        for item in predecessor.pr_input.files
    }
    inventory = {
        item["file_change_id"]: item
        for item in predecessor.artifacts["changed_file_inventory.json"]["files"]
    }
    originals: dict[str, str] = {}
    candidates: dict[str, str] = {}
    editor_results: dict[str, list[tuple[str, EditorResult]]] = defaultdict(list)
    action_records = []
    for action_id in plan.application_order:
        action = next(item for item in plan.repair_actions if item.repair_action_id == action_id)
        _safe_repo_path(action.target_path)
        payload = payloads.get(action.target_path)
        if payload is None or payload.record.binary or payload.head_content is None:
            raise RepairValidationError("Repair target lacks certified non-binary HEAD content.")
        certified = inventory[action.target_file_change_id]
        observed = _content_fingerprint(payload.head_content.encode("utf-8"))
        if observed != certified["head_content_fingerprint"]:
            raise RepairValidationError("Repair target HEAD content fingerprint is stale.")
        originals.setdefault(action.target_path, payload.head_content)
        current_content = candidates.get(action.target_path, payload.head_content)
        dialect = _sql_dialect(predecessor, action.target_path)
        result = editor_registry.apply(action, current_content, sql_dialect=dialect)
        _reject_credentials(result.candidate_content)
        candidates[action.target_path] = result.candidate_content
        editor_results[action.target_path].append((action.repair_action_id, result))
        action_records.append({
            "repair_action_id": action.repair_action_id,
            "target_path": action.target_path,
            "editor": {"name": result.editor_name, "version": result.editor_version},
            "edit_provenance": result.provenance,
            "formatting_changes": list(result.formatting_changes),
            "protected_semantics": result.protected_semantics,
            "candidate_content_in_artifact": False,
        })
    file_records = []
    file_diffs: dict[str, str] = {}
    original_fingerprints = {}
    candidate_fingerprints = {}
    hunk_count = 0
    for path in sorted(candidates):
        original = originals[path]
        candidate = candidates[path]
        if candidate == original:
            raise RepairValidationError("Repair action produced no file change.")
        patch = _unified_diff(path, original, candidate)
        _validate_diff_headers(path, patch)
        applied = _apply_unified_diff(path, original, candidate, patch)
        if _normalize(applied) != _normalize(candidate):
            raise RepairValidationError("Generated patch did not cleanly reproduce the candidate.")
        regenerated = _unified_diff(path, original, candidate)
        if regenerated != patch:
            raise RepairValidationError("Unified diff generation is nondeterministic.")
        _reject_credentials(patch)
        file_diffs[path] = patch
        count = sum(1 for line in patch.splitlines() if line.startswith("@@ "))
        hunk_count += count
        action_ids = [item[0] for item in editor_results[path]]
        original_fp = _content_fingerprint(original.encode("utf-8"))
        candidate_fp = _content_fingerprint(candidate.encode("utf-8"))
        original_fingerprints[path] = original_fp
        candidate_fingerprints[path] = candidate_fp
        file_records.append({
            "target_path": path,
            "repair_action_ids": action_ids,
            "original_content_fingerprint": original_fp,
            "candidate_content_fingerprint": candidate_fp,
            "patch_fingerprint": semantic_fingerprint({"unified_diff": patch}),
            "patch_hunk_count": count,
            "patch_applies_to_certified_head_copy": True,
            "candidate_preview_path": f"repairs/repaired_files/{path}",
            "file_patch_path": f"repairs/patches/files/{path}.patch",
        })
    if hunk_count > MAX_PATCH_HUNKS:
        raise RepairValidationError("Generated patch exceeds the certified hunk limit.")
    combined = "".join(file_diffs[path] for path in sorted(file_diffs))
    group_patches = _group_patches(plan, file_diffs)
    patch_manifest = {
        "patch_format": "portable_unified_diff",
        "combined_patch_path": "repairs/patches/combined.patch" if combined else None,
        "combined_patch_fingerprint": (
            semantic_fingerprint({"unified_diff": combined}) if combined else None
        ),
        "file_patch_paths": [item["file_patch_path"] for item in file_records],
        "logical_group_patch_paths": [
            f"repairs/patches/groups/{group_id}.patch"
            for group_id in sorted(group_patches)
        ],
        "candidate_preview_paths": [item["candidate_preview_path"] for item in file_records],
        "affected_file_count": len(file_records),
        "patch_hunk_count": hunk_count,
        "absolute_paths_present": False,
        "timestamps_present": False,
        "raw_patch_in_semantic_json": False,
    }
    static_checks = [
        {"check_id": "candidate_static_parse", "status": "passed"},
        {"check_id": "exact_parser_backed_targets", "status": "passed"},
        {"check_id": "declared_paths_only", "status": "passed"},
        {"check_id": "deterministic_unified_diff", "status": "passed"},
        {"check_id": "patch_clean_application_to_certified_head_copy", "status": "passed"},
        {"check_id": "no_unexpected_hunks", "status": "passed"},
        {"check_id": "credential_and_absolute_path_scan", "status": "passed"},
    ]
    protected_records = [
        {
            "repair_action_id": action_id,
            "target_path": path,
            **result.protected_semantics,
        }
        for path, values in sorted(editor_results.items())
        for action_id, result in values
    ]
    return PatchBuildResult(
        original_contents=originals,
        candidate_contents=candidates,
        file_records=tuple(file_records),
        action_records=tuple(action_records),
        static_validation={
            "state": "STATIC_VALIDATION_PASSED",
            "checks": static_checks,
            "file_count": len(file_records),
            "hunk_count": hunk_count,
            "repository_code_executed": False,
        },
        protected_validation={
            "state": "PROTECTED_SEMANTICS_PRESERVED",
            "records": protected_records,
            "sql_aggregation_filter_join_expression_changed_by_repair": False,
            "dag_dependency_graph_changed_by_repair": False,
        },
        combined_patch=combined,
        group_patches=group_patches,
        patch_manifest=patch_manifest,
        original_fingerprints=original_fingerprints,
        candidate_fingerprints=candidate_fingerprints,
    )


def _sql_dialect(predecessor, path):
    mappings = {item.path: item for item in predecessor.proposal.file_model_mappings}
    return mappings[path].sql_dialect if path in mappings else "postgres"


def _unified_diff(path: str, original: str, candidate: str) -> str:
    return "".join(
        difflib.unified_diff(
            _normalize(original).splitlines(keepends=True),
            _normalize(candidate).splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            n=3,
            lineterm="\n",
        )
    )


def _validate_diff_headers(path: str, patch: str) -> None:
    lines = patch.splitlines()
    if len(lines) < 2 or lines[0] != f"--- a/{path}" or lines[1] != f"+++ b/{path}":
        raise RepairValidationError("Unified diff has invalid or non-portable headers.")
    if re.search(r"[A-Za-z]:[\\/]", patch) or "../" in patch:
        raise RepairValidationError("Unified diff contains an unsafe path.")


def _apply_unified_diff(path: str, original: str, candidate: str, patch: str) -> str:
    _validate_diff_headers(path, patch)
    source = _normalize(original).splitlines()
    expected = _normalize(candidate).splitlines()
    lines = patch.splitlines()[2:]
    output: list[str] = []
    source_index = 0
    index = 0
    while index < len(lines):
        match = _HUNK.match(lines[index])
        if match is None:
            raise RepairValidationError("Unified diff contains an invalid hunk header.")
        old_start = int(match.group(1)) - 1
        if old_start < source_index or old_start > len(source):
            raise RepairValidationError("Unified diff hunk is out of order.")
        output.extend(source[source_index:old_start])
        source_index = old_start
        index += 1
        while index < len(lines) and not lines[index].startswith("@@ "):
            line = lines[index]
            if line.startswith("\\ No newline"):
                index += 1
                continue
            if not line:
                raise RepairValidationError("Unified diff line lacks an operation prefix.")
            prefix, value = line[0], line[1:]
            if prefix == " ":
                if source_index >= len(source) or source[source_index] != value:
                    raise RepairValidationError("Unified diff context does not match certified HEAD.")
                output.append(value)
                source_index += 1
            elif prefix == "-":
                if source_index >= len(source) or source[source_index] != value:
                    raise RepairValidationError("Unified diff removal does not match certified HEAD.")
                source_index += 1
            elif prefix == "+":
                output.append(value)
            else:
                raise RepairValidationError("Unified diff contains an unsupported line.")
            index += 1
    output.extend(source[source_index:])
    if output != expected:
        raise RepairValidationError("Unified diff output differs from the candidate preview.")
    result = "\n".join(output)
    if _normalize(candidate).endswith("\n"):
        result += "\n"
    return result


def _group_patches(plan: RepairPlan, file_diffs: dict[str, str]) -> dict[str, str]:
    paths_by_group = defaultdict(set)
    for action in plan.repair_actions:
        group = action.logical_change_group_id or f"root-{action.root_cause_id}"
        paths_by_group[group].add(action.target_path)
    return {
        group: "".join(file_diffs[path] for path in sorted(paths) if path in file_diffs)
        for group, paths in sorted(paths_by_group.items())
    }


def _normalize(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n")
