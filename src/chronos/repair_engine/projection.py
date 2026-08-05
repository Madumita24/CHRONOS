"""Deterministic Phase 6.3 reanalysis of isolated repaired previews."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from chronos.pr_engine import analyze_pull_request
from chronos.pr_engine.intake import _bundle_file, _content_fingerprint, _safe_repo_path
from chronos.snapshot import CurrentMetadataSnapshot

from .errors import RepairValidationError
from .models import RepairPlan
from .patching import PatchBuildResult
from .trust import TrustedPredecessor


_ALLOWED_REPAIR_DERIVED_ROOT_TYPES = {
    "PIPELINE_TASK_CHANGED",
    "FIELD_REFERENCE_CHANGED",
    "DATASET_REFERENCE_CHANGED",
    "CONFIGURATION_CHANGED",
    "QUALITY_EXPECTATION_CHANGED",
    "CONTRACT_CHANGE",
    "STRUCTURAL_CHANGE",
}


@dataclass(frozen=True)
class ProjectionResult:
    projected_analysis: dict[str, Any]
    projected_coherence: dict[str, Any]
    projected_graph: dict[str, Any]
    projected_propagation: dict[str, Any]
    projected_repository_state: dict[str, Any]
    comparison: dict[str, Any]
    remaining_findings: dict[str, Any]
    projected_closed_root_ids: tuple[str, ...]
    projected_coherence_state: str
    projected_analysis_fingerprint: str


def project_repaired_preview(
    predecessor: TrustedPredecessor,
    plan: RepairPlan,
    patch_set: PatchBuildResult,
    snapshot: CurrentMetadataSnapshot,
    workspace: Path,
) -> ProjectionResult:
    bundle = workspace / "projected_bundle"
    output = workspace / "projected_phase_6_3"
    _build_projected_bundle(predecessor, patch_set, bundle)
    try:
        result = analyze_pull_request(
            snapshot,
            predecessor.proposal,
            output,
            bundle=bundle,
        )
    except Exception as exc:
        raise RepairValidationError(
            "Projected repaired preview failed deterministic Phase 6.3 reanalysis."
        ) from exc
    original_roots = {
        item["root_cause_id"]: item
        for item in predecessor.artifacts["technical_impact_analysis.json"]["root_causes"]
    }
    projected_roots = {
        item["root_cause_id"]: item
        for item in result.artifacts["technical_impact_analysis.json"]["root_causes"]
    }
    original_conflicts = {
        item["conflict_id"]
        for item in predecessor.artifacts["coherence_evaluation.json"]["conflicts"]
    }
    projected_conflicts = {
        item["conflict_id"]
        for item in result.artifacts["coherence_evaluation.json"]["conflicts"]
    }
    new_conflicts = sorted(projected_conflicts - original_conflicts)
    if new_conflicts:
        raise RepairValidationError("Candidate repair introduces a new conflict.")
    affected_file_ids = {item.target_file_change_id for item in plan.repair_actions}
    new_roots = [
        item for root_id, item in projected_roots.items() if root_id not in original_roots
    ]
    action_derived = []
    unexpected = []
    for root in new_roots:
        if (
            root.get("root_type") in _ALLOWED_REPAIR_DERIVED_ROOT_TYPES
            and set(root.get("contributing_file_ids", [])) <= affected_file_ids
        ):
            action_derived.append(root)
        else:
            unexpected.append(root)
    if unexpected:
        raise RepairValidationError("Candidate repair introduces a new unexplained root cause.")
    targeted = set(plan.selected_root_cause_ids)
    projected_closed = tuple(sorted(targeted - set(projected_roots)))
    unchanged = tuple(sorted(set(original_roots) & set(projected_roots)))
    remaining = [projected_roots[item] for item in sorted(projected_roots) if item in original_roots]
    original_coherence = predecessor.artifacts["coherence_evaluation.json"]["state"]
    raw_projected_coherence = result.artifacts["coherence_evaluation.json"]["state"]
    original_stale = _stale_count(predecessor.artifacts["coherence_evaluation.json"])
    projected_stale = _stale_count(result.artifacts["coherence_evaluation.json"])
    action_group_ids = {
        item.logical_change_group_id for item in plan.repair_actions
        if item.logical_change_group_id
    }
    projected_groups = result.artifacts["logical_change_groups.json"]["groups"]
    action_groups_coherent = all(
        item["coherence_state"] == "COHERENT"
        for item in projected_groups
        if item["logical_change_id"] in action_group_ids
    )
    projected_coherence = (
        "COHERENT"
        if projected_stale == 0
        and not projected_conflicts
        and action_groups_coherent
        else raw_projected_coherence
    )
    comparison = {
        "projection_state": "STATIC_PROJECTED",
        "original_root_ids": sorted(original_roots),
        "targeted_root_ids": sorted(targeted),
        "projected_closed_root_ids": list(projected_closed),
        "unchanged_root_ids": list(unchanged),
        "repair_action_derived_root_ids": sorted(item["root_cause_id"] for item in action_derived),
        "new_unresolved_root_ids": [],
        "original_conflict_ids": sorted(original_conflicts),
        "projected_conflict_ids": sorted(projected_conflicts),
        "new_conflict_ids": [],
        "original_coherence": original_coherence,
        "projected_coherence": projected_coherence,
        "phase_6_3_raw_projected_coherence": raw_projected_coherence,
        "original_stale_reference_count": original_stale,
        "projected_stale_reference_count": projected_stale,
        "original_downstream_exposure": predecessor.artifacts["dependency_propagation.json"]["metrics"],
        "projected_downstream_exposure": result.artifacts["dependency_propagation.json"]["metrics"],
        "unresolved_semantic_questions": [
            item for item in remaining if item.get("root_type") == "SEMANTIC_DEFINITION_CHANGED"
        ],
        "missing_execution_evidence": True,
        "runtime_verified": False,
    }
    projected_analysis = {
        "projection_state": "STATIC_PROJECTED",
        "projected_analysis_id": result.identity.analysis_id,
        "projected_analysis_fingerprint": result.semantic_fingerprint,
        "changed_file_inventory": result.artifacts["changed_file_inventory.json"],
        "file_analysis_results": result.artifacts["file_analysis_results.json"],
        "logical_change_groups": result.artifacts["logical_change_groups.json"],
        "conflicts": result.artifacts["coherence_evaluation.json"]["conflicts"],
        "composite_change_set": result.artifacts["composite_change_set.json"],
        "counterfactual_metadata_state": result.artifacts["counterfactual_metadata_state.json"],
        "technical_impact_analysis": result.artifacts["technical_impact_analysis.json"],
        "impact_synthesis": result.artifacts["impact_synthesis.json"],
        "repair_action_derived_roots_are_not_new_unresolved_defects": [
            item["root_cause_id"] for item in action_derived
        ],
        "repository_code_executed": False,
        "runtime_verified": False,
    }
    remaining_findings = {
        "projection_state": "STATIC_PROJECTED",
        "remaining_predecessor_roots": remaining,
        "manual_decision_root_ids": list(plan.non_repairable_root_ids),
        "blocked_root_ids": list(plan.blocked_root_ids),
        "unresolved_semantic_intent": [
            item for item in remaining if item.get("root_type") == "SEMANTIC_DEFINITION_CHANGED"
        ],
        "execution_evidence_state": "MISSING_PHASE_7_VALIDATION",
    }
    return ProjectionResult(
        projected_analysis=projected_analysis,
        projected_coherence={
            **result.artifacts["coherence_evaluation.json"],
            "projection_state": "STATIC_PROJECTED",
            "state": projected_coherence,
            "phase_6_3_raw_state": raw_projected_coherence,
            "evaluation_scope": "repair_target_identity_coherence",
        },
        projected_graph={
            "projection_state": "STATIC_PROJECTED",
            **result.artifacts["future_metadata_graph.json"],
        },
        projected_propagation={
            "projection_state": "STATIC_PROJECTED",
            **result.artifacts["dependency_propagation.json"],
        },
        projected_repository_state={
            "state": "PROJECTED_POST_REPAIR",
            "candidate_file_fingerprints": patch_set.candidate_fingerprints,
            "expected_aligned_references": [
                {
                    "repair_action_id": item.repair_action_id,
                    "target_path": item.target_path,
                    "current": item.current_evidence.get("value"),
                    "projected": item.intended_future_evidence.get("value"),
                }
                for item in plan.repair_actions
            ],
            "expected_coherence_state": projected_coherence,
            "roots_expected_to_close": list(projected_closed),
            "roots_expected_to_remain": [item["root_cause_id"] for item in remaining],
            "required_phase_7_validation": list(plan.required_phase_7_validations),
            "original_repository_mutated": False,
            "runtime_verified": False,
        },
        comparison=comparison,
        remaining_findings=remaining_findings,
        projected_closed_root_ids=projected_closed,
        projected_coherence_state=projected_coherence,
        projected_analysis_fingerprint=result.semantic_fingerprint,
    )


def no_action_projection(
    predecessor: TrustedPredecessor,
    plan: RepairPlan,
) -> ProjectionResult:
    coherence = predecessor.artifacts["coherence_evaluation.json"]["state"]
    roots = predecessor.artifacts["technical_impact_analysis.json"]["root_causes"]
    conflicts = predecessor.artifacts["coherence_evaluation.json"]["conflicts"]
    comparison = {
        "projection_state": "STATIC_PROJECTED_NO_PATCH",
        "original_root_ids": [item["root_cause_id"] for item in roots],
        "targeted_root_ids": list(plan.selected_root_cause_ids),
        "projected_closed_root_ids": [],
        "unchanged_root_ids": [item["root_cause_id"] for item in roots],
        "repair_action_derived_root_ids": [],
        "new_unresolved_root_ids": [],
        "original_conflict_ids": [item["conflict_id"] for item in conflicts],
        "projected_conflict_ids": [item["conflict_id"] for item in conflicts],
        "new_conflict_ids": [],
        "original_coherence": coherence,
        "projected_coherence": coherence,
        "original_stale_reference_count": _stale_count(predecessor.artifacts["coherence_evaluation.json"]),
        "projected_stale_reference_count": _stale_count(predecessor.artifacts["coherence_evaluation.json"]),
        "missing_execution_evidence": True,
        "runtime_verified": False,
    }
    return ProjectionResult(
        projected_analysis={
            "projection_state": "STATIC_PROJECTED_NO_PATCH",
            "reason": "No supported repair actions were generated.",
            "predecessor_analysis_id": predecessor.identity.analysis_id,
            "repository_code_executed": False,
            "runtime_verified": False,
        },
        projected_coherence={
            "projection_state": "STATIC_PROJECTED_NO_PATCH",
            **predecessor.artifacts["coherence_evaluation.json"],
        },
        projected_graph={
            "projection_state": "STATIC_PROJECTED_NO_PATCH",
            **predecessor.artifacts["future_metadata_graph.json"],
        },
        projected_propagation={
            "projection_state": "STATIC_PROJECTED_NO_PATCH",
            **predecessor.artifacts["dependency_propagation.json"],
        },
        projected_repository_state={
            "state": "PROJECTED_POST_REPAIR_NO_PATCH",
            "candidate_file_fingerprints": {},
            "expected_aligned_references": [],
            "expected_coherence_state": coherence,
            "roots_expected_to_close": [],
            "roots_expected_to_remain": [item["root_cause_id"] for item in roots],
            "required_phase_7_validation": list(plan.required_phase_7_validations),
            "original_repository_mutated": False,
            "runtime_verified": False,
        },
        comparison=comparison,
        remaining_findings={
            "projection_state": "STATIC_PROJECTED_NO_PATCH",
            "remaining_predecessor_roots": roots,
            "manual_decision_root_ids": list(plan.non_repairable_root_ids),
            "blocked_root_ids": list(plan.blocked_root_ids),
            "execution_evidence_state": "MISSING_PHASE_7_VALIDATION",
        },
        projected_closed_root_ids=(),
        projected_coherence_state=coherence,
        projected_analysis_fingerprint=predecessor.manifest["analysis_semantic_fingerprint"],
    )


def _build_projected_bundle(predecessor, patch_set, destination):
    if destination.exists():
        raise RepairValidationError("Projected bundle staging destination already exists.")
    destination.mkdir(parents=True)
    source_manifest = json.loads(
        (predecessor.bundle_root / "bundle.json").read_text(encoding="utf-8")
    )
    for record in source_manifest["files"]:
        for side, key in (("base", "base_path"), ("head", "head_path")):
            path = record.get(key)
            if path is None:
                continue
            _safe_repo_path(path)
            if side == "head" and path in patch_set.candidate_contents:
                content = patch_set.candidate_contents[path].encode("utf-8")
            else:
                content = _bundle_file(predecessor.bundle_root, side, path)
            target = destination / side / Path(*path.split("/"))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            record[f"{side}_fingerprint"] = _content_fingerprint(content)
    (destination / "bundle.json").write_text(
        json.dumps(source_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _stale_count(value):
    return sum(item.get("finding_type") == "STALE_REFERENCE" for item in value["findings"])
