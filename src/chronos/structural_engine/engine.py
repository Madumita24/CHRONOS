"""Public shared pipeline for generalized structural-change analysis."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any, Mapping

from chronos.snapshot import CurrentMetadataSnapshot, load_snapshot

from .artifacts import build_analysis_artifacts
from .certification import certify_artifacts
from .errors import CertificationError, OutputSafetyError, ProposalValidationError
from .models import (
    GENERALIZED_ENGINE_VERSION,
    AnalysisIdentity,
    StructuralAnalysisResult,
)
from .operations import get_adapter
from .proposals import Proposal, parse_proposal, proposal_to_dict
from .resolver import resolve_target
from .serialization import pretty_json, semantic_fingerprint


ARTIFACT_FILENAMES = (
    "proposal.json",
    "proposal_validation.json",
    "change_semantic_contract.json",
    "counterfactual_source_state.json",
    "future_metadata_graph.json",
    "dependency_propagation.json",
    "compatibility_evaluation.json",
    "technical_impact_analysis.json",
    "business_context_propagation.json",
    "severity_criticality_analysis.json",
    "impact_synthesis.json",
    "explanation_bundle.json",
    "analysis_certification.json",
    "manifest.json",
)


def analyze_structural_change(
    proposal: Proposal | Mapping[str, Any] | str | Path,
    snapshot: CurrentMetadataSnapshot | str | Path,
    output_dir: str | Path,
    *,
    overwrite: bool = False,
) -> StructuralAnalysisResult:
    """Analyze one structural proposal and atomically export isolated artifacts."""
    parsed_proposal = _load_proposal(proposal)
    loaded_snapshot = _load_snapshot(snapshot)
    target = resolve_target(loaded_snapshot, parsed_proposal)
    adapter = get_adapter(parsed_proposal)
    adapter.validate(loaded_snapshot, target, parsed_proposal)
    proposal_fingerprint = semantic_fingerprint(
        proposal_to_dict(parsed_proposal, semantic=True)
    )
    identity = AnalysisIdentity(
        analysis_id=parsed_proposal.analysis_id,
        proposal_id=parsed_proposal.proposal_id,
        operation=parsed_proposal.operation,
        dataset_urn=parsed_proposal.dataset_urn,
        current_field_path=parsed_proposal.current_field_path,
        source_snapshot_fingerprint=parsed_proposal.source_snapshot_fingerprint,
        proposal_fingerprint=proposal_fingerprint,
        source_snapshot_id=loaded_snapshot.metadata.snapshot_id,
        engine_version=GENERALIZED_ENGINE_VERSION,
        scenario_id=next(
            (
                item.value
                for item in parsed_proposal.proposal_metadata
                if item.key in {"scenario", "scenario_id", "demonstration_id"}
            ),
            None,
        ),
        created_at=parsed_proposal.created_at,
    )
    artifacts = build_analysis_artifacts(
        loaded_snapshot, parsed_proposal, identity, target, adapter
    )
    artifacts = {
        "proposal.json": _proposal_artifact(identity, parsed_proposal),
        "proposal_validation.json": _proposal_validation_artifact(identity),
        "change_semantic_contract.json": _semantic_contract_artifact(
            identity, parsed_proposal, adapter.projected_field_path(parsed_proposal)
        ),
        **artifacts,
    }
    certification, artifact_fingerprints, analysis_fingerprint = certify_artifacts(
        identity, artifacts
    )
    artifacts["analysis_certification.json"] = certification
    certification_fingerprint = semantic_fingerprint(certification)
    all_fingerprints = dict(artifact_fingerprints)
    all_fingerprints["analysis_certification.json"] = certification_fingerprint
    synthesis = artifacts["impact_synthesis.json"]
    manifest = {
        "analysis_id": identity.analysis_id,
        "analysis_semantic_fingerprint": analysis_fingerprint,
        "artifact_fingerprints": all_fingerprints,
        "artifact_names": list(ARTIFACT_FILENAMES),
        "artifact_schema_version": "1.0",
        "artifact_type": "analysis_manifest",
        "certification_status": certification["certification_status"],
        "current_state": {
            "field_path": identity.current_field_path,
            "snapshot_id": loaded_snapshot.metadata.snapshot_id,
        },
        "dataset_urn": identity.dataset_urn,
        "decision": synthesis["decision"],
        "engine_version": GENERALIZED_ENGINE_VERSION,
        "future_state": artifacts["counterfactual_source_state.json"]["source_change"],
        "operation": identity.operation.value,
        "proposal": proposal_to_dict(parsed_proposal),
        "proposal_fingerprint": identity.proposal_fingerprint,
        "proposal_id": identity.proposal_id,
        "source_snapshot_fingerprint": identity.source_snapshot_fingerprint,
        "warnings": [],
    }
    artifacts["manifest.json"] = manifest
    _validate_manifest(manifest, artifacts, all_fingerprints)
    destination = _export_artifacts(Path(output_dir), artifacts, overwrite=overwrite)
    paths = tuple(destination / name for name in ARTIFACT_FILENAMES)
    return StructuralAnalysisResult(
        identity=identity,
        disposition=synthesis["decision"]["disposition"],
        decision_certainty=synthesis["decision"]["certainty"],
        certification_status=certification["certification_status"],
        semantic_fingerprint=analysis_fingerprint,
        output_dir=destination,
        artifact_paths=paths,
        artifacts=artifacts,
        manifest=manifest,
        key_summary=synthesis["summary"],
    )


def _load_proposal(value):
    if isinstance(value, (str, Path)):
        path = Path(value)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ProposalValidationError(f"Unable to load proposal JSON: {exc}") from exc
        return parse_proposal(raw)
    if isinstance(value, Mapping):
        return parse_proposal(value)
    return parse_proposal(proposal_to_dict(value))


def _load_snapshot(value):
    if isinstance(value, CurrentMetadataSnapshot):
        return value
    return load_snapshot(Path(value))


def _export_artifacts(
    output_dir: Path,
    artifacts: dict[str, dict[str, Any]],
    *,
    overwrite: bool,
) -> Path:
    destination = output_dir.resolve()
    repository_root = Path(__file__).resolve().parents[3]
    golden_artifacts = (repository_root / "artifacts").resolve()
    if destination in {repository_root, golden_artifacts, Path.home().resolve()}:
        raise OutputSafetyError("Output directory cannot be a repository, home, or frozen artifact root.")
    try:
        destination.relative_to(repository_root)
    except ValueError as exc:
        raise OutputSafetyError(
            "Output directory must be contained within the repository."
        ) from exc
    if destination.exists():
        if not overwrite:
            raise OutputSafetyError(
                "Output directory already exists; choose an isolated directory or explicitly enable overwrite."
            )
        if not destination.is_dir():
            raise OutputSafetyError("Output destination exists and is not a directory.")
        unexpected = {item.name for item in destination.iterdir()} - set(ARTIFACT_FILENAMES)
        if unexpected:
            raise OutputSafetyError(
                "Refusing to overwrite a directory containing non-analysis files."
            )
    destination.parent.mkdir(parents=True, exist_ok=True)
    staged = Path(tempfile.mkdtemp(prefix=".chronos-analysis-", dir=destination.parent))
    try:
        for name in ARTIFACT_FILENAMES:
            (staged / name).write_text(pretty_json(artifacts[name]), encoding="utf-8")
        if destination.exists():
            shutil.rmtree(destination)
        staged.replace(destination)
    except Exception:
        if staged.exists():
            shutil.rmtree(staged)
        raise
    return destination


def _identity_header(identity: AnalysisIdentity, artifact_type: str) -> dict[str, Any]:
    result = {
        "analysis_id": identity.analysis_id,
        "artifact_schema_version": "1.0",
        "artifact_type": artifact_type,
        "dataset_urn": identity.dataset_urn,
        "engine_version": GENERALIZED_ENGINE_VERSION,
        "operation": identity.operation.value,
        "proposal_fingerprint": identity.proposal_fingerprint,
        "proposal_id": identity.proposal_id,
        "source_snapshot_fingerprint": identity.source_snapshot_fingerprint,
        "source_snapshot_id": identity.source_snapshot_id,
    }
    if identity.scenario_id is not None:
        result["scenario_id"] = identity.scenario_id
    if identity.created_at is not None:
        result["created_at"] = identity.created_at
    return result


def _proposal_artifact(identity, proposal):
    result = _identity_header(identity, "structural_change_proposal")
    result["proposal"] = proposal_to_dict(proposal)
    return result


def _proposal_validation_artifact(identity):
    result = _identity_header(identity, "proposal_validation")
    result.update(
        {
            "checks": [
                "strict_discriminator",
                "exact_dataset",
                "exact_field_resolution",
                "snapshot_identity",
                "operation_semantics",
            ],
            "state": "valid",
        }
    )
    return result


def _semantic_contract_artifact(identity, proposal, future_field_path):
    classification = {
        "FIELD_RENAME": "RENAMED",
        "FIELD_DELETE": "DELETED",
        "FIELD_TYPE_CHANGE": "IDENTITY_PRESERVED_TYPE_CHANGED",
    }[identity.operation.value]
    result = _identity_header(identity, "change_semantic_contract")
    result.update(
        {
            "dataset_identity_state": "PRESERVED",
            "identity_mapping": {
                "classification": classification,
                "current_field_key": (
                    f"{identity.dataset_urn}|{identity.current_field_path}"
                ),
                "future_field_key": (
                    f"{identity.dataset_urn}|{future_field_path}"
                    if future_field_path is not None
                    else None
                ),
            },
            "operation_contract": identity.operation.value,
        }
    )
    return result


def _validate_manifest(manifest, artifacts, expected_fingerprints):
    if manifest.get("artifact_names") != list(ARTIFACT_FILENAMES):
        raise CertificationError("Analysis manifest artifact names are incomplete.")
    if set(artifacts) != set(ARTIFACT_FILENAMES):
        raise CertificationError("Analysis package does not match the manifest contract.")
    if manifest.get("artifact_fingerprints") != expected_fingerprints:
        raise CertificationError("Analysis manifest fingerprints are incomplete.")
    if manifest.get("certification_status") != "certified":
        raise CertificationError("Analysis manifest is not certified.")
