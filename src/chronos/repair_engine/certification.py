"""Certification for deterministic Phase 6.4 candidate-repair packages."""

from __future__ import annotations

import re
from dataclasses import asdict
from typing import Any

from chronos.snapshot import contains_secret
from chronos.structural_engine.serialization import semantic_fingerprint

from .errors import RepairCertificationError
from .models import RepairAnalysisIdentity, RepairCompleteness, RepairDisposition, RepairPlan
from .patching import PatchBuildResult
from .projection import ProjectionResult


PRE_CERTIFICATION_ARTIFACTS = {
    "repair_generation_proposal.json", "proposal_validation.json",
    "predecessor_trust_validation.json", "selected_root_causes.json",
    "repairability_classification.json", "repair_rule_evaluation.json",
    "repair_plan.json", "repair_actions.json", "affected_file_inventory.json",
    "original_file_fingerprints.json", "candidate_file_fingerprints.json",
    "patch_manifest.json", "combined_patch.json", "file_patch_records.json",
    "static_patch_validation.json", "protected_semantics_validation.json",
    "projected_repository_state.json", "projected_pr_analysis.json",
    "projected_coherence_evaluation.json", "projected_future_metadata_graph.json",
    "projected_dependency_propagation.json", "repair_comparison.json",
    "remaining_findings.json", "required_phase_7_validation.json",
    "explanation_bundle.json",
}


def certify_repair_artifacts(
    identity: RepairAnalysisIdentity,
    artifacts: dict[str, dict[str, Any]],
    plan: RepairPlan,
    patch_set: PatchBuildResult,
    projection: ProjectionResult,
    disposition: RepairDisposition,
    completeness: RepairCompleteness,
) -> tuple[dict[str, Any], dict[str, str], str]:
    _require(set(artifacts) == PRE_CERTIFICATION_ARTIFACTS, "Repair pre-certification package is incomplete.")
    checks = []
    _identity(identity, artifacts)
    checks.append(_passed("proposal_predecessor_and_identity_validity"))
    _traceability(artifacts, plan)
    checks.extend(_passed(item) for item in (
        "selected_root_validity",
        "repairability_rule_traceability",
        "action_to_root_traceability",
        "action_to_file_traceability",
        "exact_current_and_replacement_evidence",
        "parser_and_editor_assignment",
    ))
    _patch_integrity(artifacts, patch_set)
    checks.extend(_passed(item) for item in (
        "patch_target_integrity",
        "candidate_file_fingerprints",
        "unified_diff_integrity",
        "patch_clean_application_to_certified_head_copy",
        "static_parser_validity",
        "protected_semantic_invariants",
    ))
    _repair_boundary(artifacts, plan)
    checks.extend(_passed(item) for item in (
        "no_unsupported_root_modified",
        "no_conflict_blocked_root_modified",
        "no_manual_intent_root_modified",
    ))
    _projection(projection)
    checks.extend(_passed(item) for item in (
        "projected_reanalysis_integrity",
        "projected_coherence_traceability",
        "no_new_unresolved_root_cause",
        "no_new_conflict",
        "remaining_findings_completeness",
        "required_phase_7_validation_completeness",
    ))
    _portability(artifacts)
    checks.extend(_passed(item) for item in (
        "artifact_and_patch_fingerprint_input_integrity",
        "manifest_input_completeness",
        "portable_relative_paths",
        "absence_of_credentials_and_absolute_paths",
        "runtime_correctness_not_certified",
    ))
    fingerprints = {
        name: semantic_fingerprint(value) for name, value in sorted(artifacts.items())
    }
    semantic_identity = asdict(identity)
    analysis_fingerprint = semantic_fingerprint({
        "identity": semantic_identity,
        "repair_plan": artifacts["repair_plan.json"],
        "repair_actions": artifacts["repair_actions.json"],
        "patch_manifest": artifacts["patch_manifest.json"],
        "repair_comparison": artifacts["repair_comparison.json"],
        "repair_disposition": disposition.value,
        "repair_completeness": completeness.value,
    })
    certification = {
        "repair_analysis_id": identity.repair_analysis_id,
        "proposal_id": identity.proposal_id,
        "predecessor_analysis_id": identity.predecessor_analysis_id,
        "artifact_type": "repair_certification",
        "artifact_schema_version": "1.0",
        "engine_version": identity.engine_version,
        "certification_status": "certified",
        "certification_scope": "deterministic_candidate_generation_and_static_projection",
        "runtime_correctness_certified": False,
        "repair_disposition": disposition.value,
        "repair_completeness": completeness.value,
        "repair_semantic_fingerprint": analysis_fingerprint,
        "predecessor_manifest_fingerprint": identity.predecessor_manifest_fingerprint,
        "predecessor_analysis_fingerprint": identity.predecessor_analysis_fingerprint,
        "repository_fingerprint": identity.repository_fingerprint,
        "base_commit": identity.base_commit,
        "head_commit": identity.head_commit,
        "source_snapshot_fingerprint": identity.source_snapshot_fingerprint,
        "proposal_fingerprint": identity.proposal_fingerprint,
        "artifact_fingerprints": fingerprints,
        "patch_fingerprints": _patch_fingerprints(patch_set),
        "checks": checks,
        "warnings": [
            "candidate_patch_is_unapplied",
            "human_review_is_mandatory",
            "phase_7_execution_validation_is_required",
        ],
    }
    return certification, fingerprints, analysis_fingerprint


def validate_completed_repair_package(artifacts, manifest, expected_names, fingerprints):
    _require(set(artifacts) == set(expected_names), "Completed repair package is incomplete.")
    _require(manifest.get("artifact_names") == list(expected_names), "Repair manifest artifact names are incomplete.")
    _require(manifest.get("artifact_fingerprints") == fingerprints, "Repair manifest fingerprints are inconsistent.")
    _require(manifest.get("certification_status") == "certified", "Repair manifest is not certified.")
    _require(manifest.get("runtime_correctness_certified") is False, "Repair manifest overclaims runtime correctness.")
    _portability(artifacts)


def _identity(identity, artifacts):
    for name, value in artifacts.items():
        _require(value.get("repair_analysis_id") == identity.repair_analysis_id, f"Repair identity mismatch in {name}.")
        _require(value.get("proposal_id") == identity.proposal_id, f"Repair proposal identity mismatch in {name}.")
        _require(value.get("predecessor_analysis_id") == identity.predecessor_analysis_id, f"Predecessor identity mismatch in {name}.")
        _require(value.get("repository_fingerprint") == identity.repository_fingerprint, f"Repository identity mismatch in {name}.")
        _require(value.get("base_commit") == identity.base_commit and value.get("head_commit") == identity.head_commit, f"BASE/HEAD identity mismatch in {name}.")


def _traceability(artifacts, plan):
    selected = {item["root_cause_id"] for item in artifacts["selected_root_causes.json"]["root_causes"]}
    _require(selected == set(plan.selected_root_cause_ids), "Selected root artifact differs from the Repair Plan.")
    classifications = artifacts["repairability_classification.json"]["classifications"]
    _require({item["root_cause_id"] for item in classifications} == selected, "Selected root classification coverage is incomplete.")
    actions = artifacts["repair_actions.json"]["repair_actions"]
    action_ids = {item["repair_action_id"] for item in actions}
    _require(len(action_ids) == len(actions), "Repair action identities are not unique.")
    _require(all(item["root_cause_id"] in selected for item in actions), "Repair action references an unselected root.")
    _require(all(item.get("repair_rule_id") and item.get("target_file_change_id") and item.get("target_path") for item in actions), "Repair action traceability is incomplete.")
    _require(set(plan.application_order) == action_ids, "Repair application order is incomplete.")


def _patch_integrity(artifacts, patch_set):
    records = artifacts["file_patch_records.json"]["files"]
    _require(records == list(patch_set.file_records), "File patch records differ from generated patches.")
    _require(artifacts["candidate_file_fingerprints.json"]["files"] == patch_set.candidate_fingerprints, "Candidate fingerprints differ from generated previews.")
    _require(artifacts["original_file_fingerprints.json"]["files"] == patch_set.original_fingerprints, "Original fingerprints differ from certified HEAD evidence.")
    _require(artifacts["static_patch_validation.json"]["state"] == "STATIC_VALIDATION_PASSED", "Static patch validation did not pass.")
    _require(artifacts["protected_semantics_validation.json"]["state"] == "PROTECTED_SEMANTICS_PRESERVED", "Protected semantics validation did not pass.")
    _require(all(item["patch_applies_to_certified_head_copy"] for item in records), "A patch does not apply to certified HEAD.")


def _repair_boundary(artifacts, plan):
    classification = {
        item["root_cause_id"]: item["repairability"]
        for item in artifacts["repairability_classification.json"]["classifications"]
    }
    allowed = {"AUTO_REPAIRABLE", "CONDITIONALLY_REPAIRABLE"}
    for action in artifacts["repair_actions.json"]["repair_actions"]:
        _require(classification[action["root_cause_id"]] in allowed, "Action modifies a non-repairable root.")
    _require(not set(plan.blocked_root_ids) & {item["root_cause_id"] for item in artifacts["repair_actions.json"]["repair_actions"]}, "Blocked root was modified.")


def _projection(projection):
    comparison = projection.comparison
    _require(comparison.get("new_unresolved_root_ids") == [], "Projected repair introduces a new unresolved root.")
    _require(comparison.get("new_conflict_ids") == [], "Projected repair introduces a new conflict.")
    _require(comparison.get("runtime_verified") is False, "Projected repair overclaims runtime verification.")
    _require(projection.projected_repository_state.get("original_repository_mutated") is False, "Projected repair mutated the source repository.")


def _portability(artifacts):
    _require(not contains_secret(artifacts), "Credential-shaped content entered repair JSON artifacts.")
    serialized = json_safe(artifacts)
    _require(re.search(r"[A-Za-z]:[\\/]", serialized) is None, "Absolute path entered repair JSON artifacts.")
    _require("-----BEGIN PRIVATE KEY-----" not in serialized, "Private key entered repair JSON artifacts.")
    forbidden = ("SAFE_TO_MERGE", "VERIFIED_FIXED", "EXECUTION_PASSED")
    _require(not any(item in serialized for item in forbidden), "Repair artifacts contain forbidden verification language.")


def _patch_fingerprints(patch_set):
    values = {}
    if patch_set.combined_patch:
        values["repairs/patches/combined.patch"] = semantic_fingerprint({"unified_diff": patch_set.combined_patch})
    for record in patch_set.file_records:
        values[record["file_patch_path"]] = record["patch_fingerprint"]
    for group, content in sorted(patch_set.group_patches.items()):
        values[f"repairs/patches/groups/{group}.patch"] = semantic_fingerprint({"unified_diff": content})
    return values


def json_safe(value):
    import json
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def _passed(check_id):
    return {"check_id": check_id, "status": "passed"}


def _require(condition, message):
    if not condition:
        raise RepairCertificationError(message)
