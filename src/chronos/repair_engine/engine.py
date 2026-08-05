"""Public Phase 6.4 evidence-backed coordinated repair pipeline."""

from __future__ import annotations

import json
import shutil
import tempfile
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from chronos.snapshot import CurrentMetadataSnapshot, load_snapshot
from chronos.structural_engine.serialization import pretty_json, semantic_fingerprint

from .certification import certify_repair_artifacts, validate_completed_repair_package
from .editors import EditorRegistry
from .errors import RepairOutputError, RepairProposalError
from .models import (
    REPAIR_ENGINE_VERSION,
    RepairAnalysisIdentity,
    RepairGenerationProposal,
    RepairGenerationResult,
)
from .patching import build_patch_set
from .planning import build_repair_plan
from .projection import no_action_projection, project_repaired_preview
from .proposals import parse_repair_proposal, repair_proposal_to_dict
from .rules import RepairRuleRegistry
from .trust import load_trusted_predecessor


REPAIR_ARTIFACT_FILENAMES = (
    "repair_generation_proposal.json",
    "proposal_validation.json",
    "predecessor_trust_validation.json",
    "selected_root_causes.json",
    "repairability_classification.json",
    "repair_rule_evaluation.json",
    "repair_plan.json",
    "repair_actions.json",
    "affected_file_inventory.json",
    "original_file_fingerprints.json",
    "candidate_file_fingerprints.json",
    "patch_manifest.json",
    "combined_patch.json",
    "file_patch_records.json",
    "static_patch_validation.json",
    "protected_semantics_validation.json",
    "projected_repository_state.json",
    "projected_pr_analysis.json",
    "projected_coherence_evaluation.json",
    "projected_future_metadata_graph.json",
    "projected_dependency_propagation.json",
    "repair_comparison.json",
    "remaining_findings.json",
    "required_phase_7_validation.json",
    "explanation_bundle.json",
    "repair_certification.json",
    "manifest.json",
)


def generate_repair(
    predecessor_analysis: str | Path,
    proposal: RepairGenerationProposal | Mapping[str, Any] | str | Path,
    repository_bundle: str | Path,
    output_dir: str | Path,
    *,
    snapshot: CurrentMetadataSnapshot | str | Path | None = None,
    overwrite: bool = False,
) -> RepairGenerationResult:
    repository_root = Path(__file__).resolve().parents[3]
    parsed = _load_proposal(proposal)
    loaded_snapshot = _load_snapshot(snapshot, repository_root)
    predecessor = load_trusted_predecessor(
        predecessor_analysis, repository_bundle, parsed, loaded_snapshot
    )
    destination = _validate_output(
        Path(output_dir), repository_root, predecessor.root, predecessor.bundle_root,
        overwrite=overwrite,
    )
    proposal_fingerprint = semantic_fingerprint(
        repair_proposal_to_dict(parsed, semantic=True)
    )
    identity = RepairAnalysisIdentity(
        repair_analysis_id=parsed.repair_analysis_id,
        proposal_id=parsed.proposal_id,
        predecessor_analysis_id=parsed.predecessor_analysis_id,
        predecessor_manifest_fingerprint=predecessor.manifest_fingerprint,
        predecessor_analysis_fingerprint=predecessor.manifest[
            "analysis_semantic_fingerprint"
        ],
        repository_fingerprint=predecessor.identity.repository_fingerprint,
        base_commit=predecessor.identity.base_commit,
        head_commit=predecessor.identity.head_commit,
        source_snapshot_id=predecessor.identity.source_snapshot_id,
        source_snapshot_fingerprint=predecessor.identity.source_snapshot_fingerprint,
        proposal_fingerprint=proposal_fingerprint,
        scenario_id=parsed.scenario_id,
    )
    rule_registry = RepairRuleRegistry()
    editor_registry = EditorRegistry()
    plan, completeness, disposition = build_repair_plan(
        predecessor, parsed, rule_registry
    )
    patch_set = build_patch_set(predecessor, plan, editor_registry)

    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(
        tempfile.mkdtemp(prefix=f".{destination.name}-repair-", dir=destination.parent)
    )
    try:
        projection_workspace = stage / "_projected_static_analysis"
        if plan.repair_actions:
            projection_workspace.mkdir()
            projection = project_repaired_preview(
                predecessor, plan, patch_set, loaded_snapshot, projection_workspace
            )
        else:
            projection = no_action_projection(predecessor, plan)
        artifacts = _artifacts(
            identity, parsed, predecessor, plan, completeness, disposition,
            patch_set, projection, rule_registry, editor_registry,
        )
        certification, fingerprints, repair_fingerprint = certify_repair_artifacts(
            identity, artifacts, plan, patch_set, projection, disposition, completeness
        )
        artifacts["repair_certification.json"] = certification
        fingerprints = {
            **fingerprints,
            "repair_certification.json": semantic_fingerprint(certification),
        }
        manifest = _manifest(
            identity, predecessor, plan, completeness, disposition, patch_set,
            projection, fingerprints, repair_fingerprint, certification,
        )
        artifacts["manifest.json"] = manifest
        validate_completed_repair_package(
            artifacts, manifest, REPAIR_ARTIFACT_FILENAMES, fingerprints
        )
        if projection_workspace.exists():
            shutil.rmtree(projection_workspace)
        _write_package(stage, artifacts, patch_set, plan)
        if destination.exists():
            shutil.rmtree(destination)
        stage.replace(destination)
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    patch_paths = tuple(
        path for path in sorted((destination / "repairs" / "patches").rglob("*.patch"))
    )
    candidate_paths = tuple(
        path for path in sorted((destination / "repairs" / "repaired_files").rglob("*"))
        if path.is_file()
    )
    return RepairGenerationResult(
        identity=identity,
        certification_status="certified",
        repair_disposition=disposition,
        completeness=completeness,
        repair_actions=tuple(artifacts["repair_actions.json"]["repair_actions"]),
        affected_files=plan.affected_files,
        projected_closed_roots=projection.projected_closed_root_ids,
        remaining_findings=tuple(
            artifacts["remaining_findings.json"]["remaining_predecessor_roots"]
        ),
        projected_coherence=projection.projected_coherence_state,
        semantic_fingerprint=repair_fingerprint,
        patch_manifest=patch_set.patch_manifest,
        artifact_manifest=manifest,
        patch_paths=patch_paths,
        candidate_file_paths=candidate_paths,
        output_dir=destination,
        artifact_paths=tuple(destination / name for name in REPAIR_ARTIFACT_FILENAMES),
        artifacts=artifacts,
    )


def _artifacts(identity, proposal, predecessor, plan, completeness, disposition, patch_set, projection, rules, editors):
    header = lambda artifact_type: _header(identity, artifact_type)
    classifications = [_jsonable(item) for item in plan.classifications]
    action_by_id = {
        item["repair_action_id"]: item for item in patch_set.action_records
    }
    actions = [
        {**_jsonable(item), "generation": action_by_id[item.repair_action_id]}
        for item in plan.repair_actions
    ]
    roots_by_id = {
        item["root_cause_id"]: item
        for item in predecessor.artifacts["technical_impact_analysis.json"]["root_causes"]
    }
    selected_roots = [roots_by_id[item] for item in plan.selected_root_cause_ids]
    inventory_by_id = {
        item["file_change_id"]: item
        for item in predecessor.artifacts["changed_file_inventory.json"]["files"]
    }
    action_ids_by_file: dict[str, list[str]] = {}
    for action in plan.repair_actions:
        action_ids_by_file.setdefault(action.target_file_change_id, []).append(
            action.repair_action_id
        )
    affected_inventory = [
        {**inventory_by_id[file_id], "repair_action_ids": sorted(action_ids)}
        for file_id, action_ids in sorted(action_ids_by_file.items())
    ]
    rule_ids = {item.repairability_rule_id for item in plan.classifications}
    rules_by_id = {item["repair_rule_id"]: item for item in rules.artifact_records()}
    explanation = _explanations(plan, patch_set, projection, disposition)
    required_phase7 = [
        {
            "validation_id": value,
            "state": "REQUIRED_NOT_EXECUTED",
            "phase": "7",
        }
        for value in plan.required_phase_7_validations
    ]
    artifacts = {
        "repair_generation_proposal.json": {
            **header("repair_generation_proposal"),
            "proposal": repair_proposal_to_dict(proposal),
        },
        "proposal_validation.json": {
            **header("repair_proposal_validation"),
            "state": "valid",
            "checks": [
                "strict_unknown_property_rejection",
                "operation_and_mode",
                "predecessor_manifest_identity",
                "repository_base_head_identity",
                "no_command_prompt_or_execution_options",
            ],
        },
        "predecessor_trust_validation.json": {
            **header("predecessor_trust_validation"),
            "state": "trusted",
            "predecessor_manifest_fingerprint": predecessor.manifest_fingerprint,
            "predecessor_analysis_fingerprint": predecessor.manifest["analysis_semantic_fingerprint"],
            "checks": list(predecessor.trust_checks),
        },
        "selected_root_causes.json": {
            **header("selected_root_causes"),
            "repair_mode": proposal.repair_mode.value,
            "root_causes": selected_roots,
        },
        "repairability_classification.json": {
            **header("repairability_classification"),
            "classifications": classifications,
            "counts": _counts(classifications, "repairability"),
        },
        "repair_rule_evaluation.json": {
            **header("repair_rule_evaluation"),
            "evaluated_rules": [rules_by_id[item] for item in sorted(rule_ids) if item in rules_by_id],
            "classification_rule_ids": sorted(rule_ids),
            "editor_registry": editors.records(),
        },
        "repair_plan.json": {
            **header("repair_plan"),
            "plan": _jsonable(plan),
            "plan_created_before_candidate_edits": True,
        },
        "repair_actions.json": {
            **header("repair_actions"),
            "repair_actions": actions,
            "application_order": list(plan.application_order),
        },
        "affected_file_inventory.json": {
            **header("affected_file_inventory"),
            "files": affected_inventory,
        },
        "original_file_fingerprints.json": {
            **header("original_file_fingerprints"),
            "files": patch_set.original_fingerprints,
        },
        "candidate_file_fingerprints.json": {
            **header("candidate_file_fingerprints"),
            "files": patch_set.candidate_fingerprints,
        },
        "patch_manifest.json": {**header("patch_manifest"), **patch_set.patch_manifest},
        "combined_patch.json": {
            **header("combined_patch"),
            "patch_path": patch_set.patch_manifest["combined_patch_path"],
            "patch_fingerprint": patch_set.patch_manifest["combined_patch_fingerprint"],
            "patch_hunk_count": patch_set.patch_manifest["patch_hunk_count"],
            "raw_patch_content_in_json": False,
        },
        "file_patch_records.json": {
            **header("file_patch_records"),
            "files": list(patch_set.file_records),
        },
        "static_patch_validation.json": {**header("static_patch_validation"), **patch_set.static_validation},
        "protected_semantics_validation.json": {**header("protected_semantics_validation"), **patch_set.protected_validation},
        "projected_repository_state.json": {**header("projected_repository_state"), **projection.projected_repository_state},
        "projected_pr_analysis.json": {**header("projected_pr_analysis"), **projection.projected_analysis},
        "projected_coherence_evaluation.json": {**projection.projected_coherence, **header("projected_coherence_evaluation")},
        "projected_future_metadata_graph.json": {**projection.projected_graph, **header("projected_future_metadata_graph")},
        "projected_dependency_propagation.json": {**projection.projected_propagation, **header("projected_dependency_propagation")},
        "repair_comparison.json": {**header("repair_comparison"), **projection.comparison},
        "remaining_findings.json": {**header("remaining_findings"), **projection.remaining_findings},
        "required_phase_7_validation.json": {
            **header("required_phase_7_validation"),
            "validations": required_phase7,
            "execution_performed_in_phase_6_4": False,
        },
        "explanation_bundle.json": {**header("repair_explanation_bundle"), **explanation},
    }
    return artifacts


def _manifest(identity, predecessor, plan, completeness, disposition, patch_set, projection, fingerprints, repair_fingerprint, certification):
    classifications = [_jsonable(item) for item in plan.classifications]
    return {
        **_header(identity, "repair_manifest"),
        "repair_semantic_fingerprint": repair_fingerprint,
        "artifact_names": list(REPAIR_ARTIFACT_FILENAMES),
        "artifact_fingerprints": fingerprints,
        "patch_fingerprints": certification["patch_fingerprints"],
        "certification_status": "certified",
        "runtime_correctness_certified": False,
        "selected_root_count": len(plan.selected_root_cause_ids),
        "repairability_counts": _counts(classifications, "repairability"),
        "repair_action_count": len(plan.repair_actions),
        "affected_file_count": len(plan.affected_files),
        "patch_hunk_count": patch_set.patch_manifest["patch_hunk_count"],
        "projected_closed_root_count": len(projection.projected_closed_root_ids),
        "remaining_root_count": len(projection.remaining_findings["remaining_predecessor_roots"]),
        "new_root_count": len(projection.comparison["new_unresolved_root_ids"]),
        "original_coherence": predecessor.artifacts["coherence_evaluation.json"]["state"],
        "projected_coherence": projection.projected_coherence_state,
        "repair_completeness": completeness.value,
        "repair_disposition": disposition.value,
        "human_review_required": True,
        "warnings": list(plan.warnings),
    }


def _write_package(stage, artifacts, patch_set, plan):
    for name in REPAIR_ARTIFACT_FILENAMES:
        (stage / name).write_text(pretty_json(artifacts[name]), encoding="utf-8")
    repairs = stage / "repairs"
    patches = repairs / "patches"
    files_root = patches / "files"
    groups_root = patches / "groups"
    repaired_root = repairs / "repaired_files"
    for path in (files_root, groups_root, repaired_root):
        path.mkdir(parents=True, exist_ok=True)
    if patch_set.combined_patch:
        (patches / "combined.patch").write_text(patch_set.combined_patch, encoding="utf-8")
    for record in patch_set.file_records:
        relative = record["target_path"]
        patch_target = files_root / Path(*f"{relative}.patch".split("/"))
        patch_target.parent.mkdir(parents=True, exist_ok=True)
        file_patch = _file_patch(patch_set.combined_patch, relative)
        patch_target.write_text(file_patch, encoding="utf-8")
        candidate_target = repaired_root / Path(*relative.split("/"))
        candidate_target.parent.mkdir(parents=True, exist_ok=True)
        candidate_target.write_text(patch_set.candidate_contents[relative], encoding="utf-8")
    for group_id, content in patch_set.group_patches.items():
        (groups_root / f"{group_id}.patch").write_text(content, encoding="utf-8")
    (repairs / "repair_actions.json").write_text(
        pretty_json(artifacts["repair_actions.json"]), encoding="utf-8"
    )
    (repairs / "repair_plan.json").write_text(
        pretty_json(artifacts["repair_plan.json"]), encoding="utf-8"
    )


def _validate_output(output, repository_root, predecessor, bundle, *, overwrite):
    destination = output.resolve()
    root = repository_root.resolve()
    try:
        relative = destination.relative_to(root)
    except ValueError as exc:
        raise RepairOutputError("Repair output must remain inside the CHRONOS repository.") from exc
    if destination in {root, predecessor.resolve(), bundle.resolve(), Path.home().resolve()}:
        raise RepairOutputError("Repair output target is protected.")
    if not relative.parts or relative.parts[0].lower() in {
        "artifacts", "src", "tests", "examples", "frontend", ".git"
    }:
        raise RepairOutputError("Repair output cannot target frozen, source, test, example, frontend, or VCS trees.")
    for protected in (predecessor.resolve(), bundle.resolve()):
        try:
            protected.relative_to(destination)
        except ValueError:
            pass
        else:
            raise RepairOutputError("Repair output cannot contain predecessor or bundle evidence.")
    if destination.exists():
        if not overwrite:
            raise RepairOutputError("Repair output already exists; explicit overwrite is required.")
        if destination.is_symlink() or not destination.is_dir():
            raise RepairOutputError("Existing repair output is not a regular directory.")
        allowed = set(REPAIR_ARTIFACT_FILENAMES) | {"repairs"}
        if {item.name for item in destination.iterdir()} != allowed:
            raise RepairOutputError("Refusing to overwrite a non-repair-package directory.")
    return destination


def _load_proposal(value):
    if isinstance(value, RepairGenerationProposal):
        return value
    if isinstance(value, (str, Path)):
        try:
            raw = json.loads(Path(value).read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise RepairProposalError("Unable to load repair proposal JSON.") from exc
        return parse_repair_proposal(raw)
    return parse_repair_proposal(value)


def _load_snapshot(value, repository_root):
    if isinstance(value, CurrentMetadataSnapshot):
        return value
    path = Path(value) if value is not None else repository_root / "artifacts" / "current_metadata_snapshot.json"
    return load_snapshot(path)


def _header(identity, artifact_type):
    value = {
        "repair_analysis_id": identity.repair_analysis_id,
        "proposal_id": identity.proposal_id,
        "predecessor_analysis_id": identity.predecessor_analysis_id,
        "artifact_type": artifact_type,
        "artifact_schema_version": "1.0",
        "engine_version": identity.engine_version,
        "operation": "GENERATE_REPAIR",
        "predecessor_manifest_fingerprint": identity.predecessor_manifest_fingerprint,
        "predecessor_analysis_fingerprint": identity.predecessor_analysis_fingerprint,
        "repository_fingerprint": identity.repository_fingerprint,
        "base_commit": identity.base_commit,
        "head_commit": identity.head_commit,
        "source_snapshot_id": identity.source_snapshot_id,
        "source_snapshot_fingerprint": identity.source_snapshot_fingerprint,
        "proposal_fingerprint": identity.proposal_fingerprint,
    }
    if identity.scenario_id:
        value["scenario_id"] = identity.scenario_id
    return value


def _jsonable(value):
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _counts(values, key):
    result = {}
    for item in values:
        result[item[key]] = result.get(item[key], 0) + 1
    return {item: result[item] for item in sorted(result)}


def _explanations(plan, patch_set, projection, disposition):
    action_by_id = {item.repair_action_id: item for item in plan.repair_actions}
    return {
        "package_explanation": {
            "why": "Generate only parser-backed candidate edits for certified repository inconsistencies.",
            "repair_disposition": disposition.value,
            "what_was_not_changed": "Semantic business intent, dynamic constructs, unsupported roots, and source repository contents.",
            "remaining": projection.remaining_findings,
            "required_validation": list(plan.required_phase_7_validations),
        },
        "logical_group_explanations": [
            {
                "logical_change_group_id": group,
                "repair_action_ids": [item.repair_action_id for item in plan.repair_actions if item.logical_change_group_id == group],
                "application_order": [item for item in plan.application_order if action_by_id[item].logical_change_group_id == group],
            }
            for group in sorted({item.logical_change_group_id for item in plan.repair_actions if item.logical_change_group_id})
        ],
        "repair_action_explanations": [
            {
                "repair_action_id": item.repair_action_id,
                "root_cause_id": item.root_cause_id,
                "why_selected": item.human_explanation,
                "replacement_evidence": item.intended_future_evidence,
                "protected_semantics": list(item.static_validation_requirements),
                "remaining_validation": list(item.remaining_evidence_requirements),
            }
            for item in plan.repair_actions
        ],
        "file_explanations": [
            {
                "target_path": record["target_path"],
                "repair_action_ids": record["repair_action_ids"],
                "candidate_preview_path": record["candidate_preview_path"],
            }
            for record in patch_set.file_records
        ],
        "diff_hunk_explanations": [
            {
                "target_path": record["target_path"],
                "patch_hunk_count": record["patch_hunk_count"],
                "patch_fingerprint": record["patch_fingerprint"],
                "reason": "Every hunk is generated from one or more certified repair actions.",
            }
            for record in patch_set.file_records
        ],
        "remaining_root_explanations": projection.remaining_findings,
        "projected_post_repair_explanation": {
            "state": "STATIC_PROJECTED",
            "coherence": projection.projected_coherence_state,
            "runtime_verified": False,
        },
    }


def _file_patch(combined, path):
    marker = f"--- a/{path}\n"
    start = combined.find(marker)
    if start < 0:
        raise RepairOutputError("Combined patch lacks a declared file patch.")
    next_start = combined.find("--- a/", start + len(marker))
    return combined[start:] if next_start < 0 else combined[start:next_start]
