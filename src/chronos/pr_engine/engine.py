"""Public Phase 6.3 multi-file PR analysis pipeline."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any, Mapping

from chronos.snapshot import CurrentMetadataSnapshot, load_snapshot
from chronos.structural_engine.serialization import pretty_json, semantic_fingerprint

from .analysis import build_pre_certification_artifacts
from .certification import certify_pr_artifacts, validate_completed_package
from .errors import PullRequestCertificationError, PullRequestProposalError, RepositoryIntakeError
from .intake import load_exported_bundle, load_git_range, with_classification
from .models import (
    PR_ENGINE_VERSION,
    CoherenceState,
    IntakeMode,
    PullRequestAnalysisIdentity,
    PullRequestAnalysisProposal,
    PullRequestAnalysisResult,
)
from .proposals import parse_pr_proposal, pr_proposal_to_dict
from .registry import ParserRegistry


PR_ARTIFACT_FILENAMES = (
    "pr_analysis_proposal.json", "proposal_validation.json", "repository_identity.json",
    "changed_file_inventory.json", "file_classification.json", "file_analysis_results.json",
    "structural_change_set.json", "semantic_change_set.json", "pipeline_change_set.json",
    "contract_quality_change_set.json", "entity_resolution.json", "logical_change_groups.json",
    "coherence_evaluation.json", "composite_change_set.json",
    "counterfactual_repository_state.json", "counterfactual_metadata_state.json",
    "future_metadata_graph.json", "dependency_propagation.json", "compatibility_evaluation.json",
    "technical_impact_analysis.json", "business_context_propagation.json",
    "severity_criticality_analysis.json", "impact_synthesis.json", "explanation_bundle.json",
    "analysis_certification.json", "manifest.json",
)


def analyze_pull_request(
    snapshot: CurrentMetadataSnapshot | str | Path,
    proposal: PullRequestAnalysisProposal | Mapping[str, Any] | str | Path,
    output_dir: str | Path,
    *,
    repository: str | Path | None = None,
    bundle: str | Path | None = None,
    base_revision: str | None = None,
    head_revision: str | None = None,
    overwrite: bool = False,
) -> PullRequestAnalysisResult:
    repository_root = Path(__file__).resolve().parents[3]
    parsed = _load_proposal(proposal)
    loaded_snapshot = snapshot if isinstance(snapshot, CurrentMetadataSnapshot) else load_snapshot(snapshot)
    _validate_snapshot(parsed, loaded_snapshot)
    _validate_overrides(parsed, repository, bundle, base_revision, head_revision)
    pr_input = (
        load_git_range(repository, parsed)
        if parsed.intake_mode is IntakeMode.LOCAL_GIT_RANGE
        else load_exported_bundle(bundle, parsed)
    )
    registry = ParserRegistry()
    classifications = {item.record.file_change_id: registry.classify(item) for item in pr_input.files}
    pr_input = with_classification(pr_input, classifications)
    file_results = [
        registry.analyze(
            item, snapshot=loaded_snapshot, proposal=parsed,
            all_payloads=pr_input.files,
        )
        for item in pr_input.files
    ]
    proposal_fingerprint = semantic_fingerprint(pr_proposal_to_dict(parsed, semantic=True))
    identity = PullRequestAnalysisIdentity(
        analysis_id=parsed.analysis_id, proposal_id=parsed.proposal_id,
        operation=parsed.operation, intake_mode=parsed.intake_mode,
        repository_fingerprint=pr_input.repository_identity["repository_fingerprint"],
        base_commit=pr_input.base_commit, head_commit=pr_input.head_commit,
        source_snapshot_id=loaded_snapshot.metadata.snapshot_id,
        source_snapshot_fingerprint=loaded_snapshot.semantic_fingerprint,
        proposal_fingerprint=proposal_fingerprint, engine_version=PR_ENGINE_VERSION,
        scenario_id=parsed.scenario_id, created_at=parsed.created_at,
    )
    artifacts = build_pre_certification_artifacts(
        loaded_snapshot, parsed, identity, pr_input, file_results
    )
    certification, fingerprints, analysis_fingerprint = certify_pr_artifacts(identity, artifacts)
    artifacts["analysis_certification.json"] = certification
    fingerprints = {
        **fingerprints,
        "analysis_certification.json": semantic_fingerprint(certification),
    }
    manifest = _manifest(
        identity, pr_input, artifacts, certification, fingerprints, analysis_fingerprint
    )
    artifacts["manifest.json"] = manifest
    validate_completed_package(artifacts, manifest, PR_ARTIFACT_FILENAMES, fingerprints)
    destination = _export(
        Path(output_dir), artifacts, repository_root=repository_root, overwrite=overwrite
    )
    synthesis = artifacts["impact_synthesis.json"]
    coherence = CoherenceState(artifacts["coherence_evaluation.json"]["state"])
    roots = tuple(artifacts["technical_impact_analysis.json"]["root_causes"])
    conflicts = tuple(artifacts["coherence_evaluation.json"]["conflicts"])
    findings = tuple(artifacts["technical_impact_analysis.json"]["findings"])
    return PullRequestAnalysisResult(
        identity=identity, repository_identity=pr_input.repository_identity,
        certification_status="certified", disposition=synthesis["decision"]["disposition"],
        decision_certainty=synthesis["decision"]["certainty"], coherence_state=coherence,
        semantic_fingerprint=analysis_fingerprint,
        changed_file_summary=artifacts["changed_file_inventory.json"]["summary"],
        logical_change_groups=tuple(artifacts["logical_change_groups.json"]["groups"]),
        root_causes=roots, conflicts=conflicts, key_findings=findings,
        future_graph_summary=artifacts["dependency_propagation.json"]["metrics"],
        output_dir=destination,
        artifact_paths=tuple(destination / name for name in PR_ARTIFACT_FILENAMES),
        artifacts=artifacts, manifest=manifest,
    )


def analyze_pull_request_bundle(
    snapshot, proposal, bundle, output_dir, *, overwrite=False
):
    return analyze_pull_request(
        snapshot, proposal, output_dir, bundle=bundle, overwrite=overwrite
    )


def _load_proposal(value):
    if isinstance(value, PullRequestAnalysisProposal):
        return value
    if isinstance(value, (str, Path)):
        try:
            raw = json.loads(Path(value).read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise PullRequestProposalError("Unable to load PR proposal JSON.") from exc
        return parse_pr_proposal(raw)
    return parse_pr_proposal(value)


def _validate_snapshot(proposal, snapshot):
    if proposal.source_snapshot_fingerprint != snapshot.semantic_fingerprint:
        raise PullRequestProposalError("PR proposal snapshot fingerprint mismatch.")
    if proposal.source_snapshot_id and proposal.source_snapshot_id != snapshot.metadata.snapshot_id:
        raise PullRequestProposalError("PR proposal snapshot ID mismatch.")


def _validate_overrides(proposal, repository, bundle, base, head):
    if base is not None and base != proposal.base_revision:
        raise PullRequestProposalError("Base override does not match the proposal.")
    if head is not None and head != proposal.head_revision:
        raise PullRequestProposalError("Head override does not match the proposal.")
    if proposal.intake_mode is IntakeMode.LOCAL_GIT_RANGE:
        if repository is None or bundle is not None:
            raise RepositoryIntakeError("Local Git mode requires only repository input.")
    elif bundle is None or repository is not None:
        raise RepositoryIntakeError("Exported bundle mode requires only bundle input.")


def _manifest(identity, pr_input, artifacts, certification, fingerprints, analysis_fingerprint):
    inventory = artifacts["changed_file_inventory.json"]["summary"]
    resolution = artifacts["entity_resolution.json"]["summary"]
    synthesis = artifacts["impact_synthesis.json"]
    graph = artifacts["dependency_propagation.json"]["metrics"]
    return {
        "analysis_id": identity.analysis_id,
        "artifact_type": "pr_analysis_manifest", "artifact_schema_version": "1.0",
        "analysis_semantic_fingerprint": analysis_fingerprint,
        "artifact_names": list(PR_ARTIFACT_FILENAMES),
        "artifact_fingerprints": fingerprints,
        "certification_status": certification["certification_status"],
        "engine_version": identity.engine_version,
        "operation": identity.operation.value, "intake_mode": identity.intake_mode.value,
        "proposal_id": identity.proposal_id, "proposal_fingerprint": identity.proposal_fingerprint,
        "repository_identity": pr_input.repository_identity,
        "base_commit": identity.base_commit, "head_commit": identity.head_commit,
        "source_snapshot_fingerprint": identity.source_snapshot_fingerprint,
        "changed_file_summary": inventory,
        "logical_change_group_count": len(artifacts["logical_change_groups.json"]["groups"]),
        "root_cause_count": len(artifacts["technical_impact_analysis.json"]["root_causes"]),
        "conflict_count": len(artifacts["coherence_evaluation.json"]["conflicts"]),
        "entity_resolution_summary": resolution,
        "future_graph_summary": graph,
        "decision": synthesis["decision"],
        "warnings": synthesis["warnings"],
    }


def _export(output_dir, artifacts, *, repository_root, overwrite):
    destination = output_dir.resolve()
    root = repository_root.resolve()
    golden = (root / "artifacts").resolve()
    try:
        destination.relative_to(root)
    except ValueError as exc:
        raise RepositoryIntakeError("PR output must remain inside the CHRONOS repository.") from exc
    if destination in {root, golden, Path.home().resolve()}:
        raise RepositoryIntakeError("PR output target is protected.")
    if destination.exists():
        if not overwrite:
            raise RepositoryIntakeError("PR output already exists; explicit overwrite is required.")
        if not destination.is_dir() or not set(item.name for item in destination.iterdir()) <= set(PR_ARTIFACT_FILENAMES):
            raise RepositoryIntakeError("Refusing to overwrite a non-PR-analysis directory.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{destination.name}-", dir=destination.parent))
    try:
        for name in PR_ARTIFACT_FILENAMES:
            (stage / name).write_text(pretty_json(artifacts[name]), encoding="utf-8")
        if destination.exists():
            shutil.rmtree(destination)
        stage.replace(destination)
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    return destination
