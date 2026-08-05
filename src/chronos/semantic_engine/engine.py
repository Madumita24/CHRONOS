"""Public Phase 6.2 single-model semantic SQL/dbt analysis pipeline."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any, Mapping

from chronos.snapshot import CurrentMetadataSnapshot, load_snapshot

from .artifacts import build_semantic_artifacts
from .certification import certify_semantic_artifacts
from .deltas import detect_deltas
from .errors import (
    SemanticCertificationError,
    SemanticProposalError,
    UnsafeCodeInputError,
)
from .intake import load_code_input
from .models import (
    SEMANTIC_ENGINE_VERSION,
    SQL_PARSER_NAME,
    SQL_PARSER_VERSION,
    SemanticAnalysisIdentity,
    SemanticAnalysisResult,
    SemanticCodeChangeProposal,
    SemanticCompatibilityState,
)
from .parser import parse_model
from .proposals import (
    parse_semantic_proposal,
    semantic_proposal_to_dict,
)
from .resolver import resolve_semantic_entities
from .serialization import pretty_json, semantic_fingerprint


SEMANTIC_ARTIFACT_FILENAMES = (
    "semantic_change_proposal.json",
    "proposal_validation.json",
    "before_parsed_model.json",
    "after_parsed_model.json",
    "semantic_diff.json",
    "entity_resolution.json",
    "code_change_set.json",
    "counterfactual_semantic_state.json",
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


def analyze_semantic_code_change(
    snapshot: CurrentMetadataSnapshot | str | Path,
    proposal: SemanticCodeChangeProposal | Mapping[str, Any] | str | Path,
    before_sql: str | Path,
    after_sql: str | Path,
    output_dir: str | Path,
    *,
    dbt_manifest: str | Path | None = None,
    sql_dialect: str | None = None,
    overwrite: bool = False,
) -> SemanticAnalysisResult:
    repository_root = Path(__file__).resolve().parents[3]
    parsed_proposal = _load_proposal(proposal)
    loaded_snapshot = (
        snapshot if isinstance(snapshot, CurrentMetadataSnapshot) else load_snapshot(snapshot)
    )
    _validate_overrides(parsed_proposal, before_sql, after_sql, dbt_manifest, sql_dialect)
    before_input = load_code_input(
        parsed_proposal.before_code_reference,
        repository_root=repository_root,
        manifest_reference=parsed_proposal.dbt_manifest_reference,
    )
    after_input = load_code_input(
        parsed_proposal.after_code_reference,
        repository_root=repository_root,
        manifest_reference=parsed_proposal.dbt_manifest_reference,
    )
    before_model = parse_model(
        before_input.compiled_content, dialect=parsed_proposal.sql_dialect
    )
    after_model = parse_model(
        after_input.compiled_content, dialect=parsed_proposal.sql_dialect
    )
    structural_deltas, semantic_deltas = detect_deltas(
        before_model,
        after_model,
        model_dataset_urn=parsed_proposal.model_dataset_urn,
    )
    changed_outputs = {
        item.affected_output_field
        for item in structural_deltas + semantic_deltas
        if item.affected_output_field
    }
    resolution = resolve_semantic_entities(
        loaded_snapshot,
        parsed_proposal,
        before_model,
        after_model,
        changed_output_names=changed_outputs,
    )
    proposal_fingerprint = semantic_fingerprint(
        semantic_proposal_to_dict(parsed_proposal, semantic=True)
    )
    identity = SemanticAnalysisIdentity(
        analysis_id=parsed_proposal.analysis_id,
        proposal_id=parsed_proposal.proposal_id,
        operation=parsed_proposal.operation,
        model_dataset_urn=parsed_proposal.model_dataset_urn,
        sql_dialect=parsed_proposal.sql_dialect.lower(),
        parser_name=SQL_PARSER_NAME,
        parser_version=SQL_PARSER_VERSION,
        engine_version=SEMANTIC_ENGINE_VERSION,
        source_snapshot_id=loaded_snapshot.metadata.snapshot_id,
        source_snapshot_fingerprint=loaded_snapshot.semantic_fingerprint,
        proposal_fingerprint=proposal_fingerprint,
        before_content_fingerprint=before_model.canonical_ast_fingerprint,
        after_content_fingerprint=after_model.canonical_ast_fingerprint,
        scenario_id=parsed_proposal.scenario_id,
        created_at=parsed_proposal.created_at,
    )
    artifacts = build_semantic_artifacts(
        loaded_snapshot,
        parsed_proposal,
        identity,
        before_model,
        after_model,
        structural_deltas,
        semantic_deltas,
        resolution,
        before_raw_fingerprint=before_input.content_fingerprint,
        after_raw_fingerprint=after_input.content_fingerprint,
        before_input_kind=before_input.input_kind,
        after_input_kind=after_input.input_kind,
        dbt_references=tuple(
            sorted(set(before_input.dbt_references + after_input.dbt_references))
        ),
    )
    certification, fingerprints, analysis_fingerprint = certify_semantic_artifacts(
        identity, artifacts
    )
    artifacts["analysis_certification.json"] = certification
    fingerprints = {
        **fingerprints,
        "analysis_certification.json": semantic_fingerprint(certification),
    }
    synthesis = artifacts["impact_synthesis.json"]
    manifest = _manifest(
        identity,
        parsed_proposal,
        before_model,
        after_model,
        structural_deltas,
        semantic_deltas,
        synthesis,
        certification,
        fingerprints,
        analysis_fingerprint,
    )
    artifacts["manifest.json"] = manifest
    _validate_manifest(artifacts, manifest, fingerprints)
    destination = _export(
        Path(output_dir), artifacts, repository_root=repository_root, overwrite=overwrite
    )
    semantic_state = SemanticCompatibilityState(
        artifacts["compatibility_evaluation.json"]["semantic_compatibility"]
    )
    detected = structural_deltas + semantic_deltas
    affected_outputs = tuple(
        sorted(
            {
                item.affected_output_field
                for item in detected
                if item.affected_output_field
            }
        )
    )
    return SemanticAnalysisResult(
        identity=identity,
        certification_status=certification["certification_status"],
        disposition=synthesis["decision"]["disposition"],
        decision_certainty=synthesis["decision"]["certainty"],
        semantic_compatibility=semantic_state,
        semantic_fingerprint=analysis_fingerprint,
        detected_deltas=detected,
        resolved_model=resolution["model"],
        affected_outputs=affected_outputs,
        output_dir=destination,
        artifact_paths=tuple(destination / name for name in SEMANTIC_ARTIFACT_FILENAMES),
        artifacts=artifacts,
        manifest=manifest,
        key_summary=synthesis["summary"],
    )


def _load_proposal(value):
    if isinstance(value, (str, Path)):
        try:
            raw = json.loads(Path(value).read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise SemanticProposalError("Unable to load semantic proposal JSON.") from exc
        return parse_semantic_proposal(raw)
    if isinstance(value, Mapping):
        return parse_semantic_proposal(value)
    return parse_semantic_proposal(semantic_proposal_to_dict(value))


def _validate_overrides(proposal, before_sql, after_sql, manifest, dialect):
    before_ref = Path(before_sql).as_posix()
    after_ref = Path(after_sql).as_posix()
    if Path(before_sql).is_absolute() or before_ref != Path(proposal.before_code_reference).as_posix():
        raise UnsafeCodeInputError("BEFORE argument must equal the proposal repository-relative code reference.")
    if Path(after_sql).is_absolute() or after_ref != Path(proposal.after_code_reference).as_posix():
        raise UnsafeCodeInputError("AFTER argument must equal the proposal repository-relative code reference.")
    if dialect is not None and dialect.lower() != proposal.sql_dialect.lower():
        raise SemanticProposalError("CLI/API SQL dialect does not match the proposal.")
    manifest_ref = Path(manifest).as_posix() if manifest is not None else None
    if manifest is not None and Path(manifest).is_absolute():
        raise UnsafeCodeInputError("dbt manifest override must be repository-relative.")
    expected_manifest = (
        Path(proposal.dbt_manifest_reference).as_posix()
        if proposal.dbt_manifest_reference
        else None
    )
    if manifest_ref != expected_manifest:
        raise SemanticProposalError("dbt manifest argument does not match the proposal.")


def _manifest(identity, proposal, before, after, structural, semantic, synthesis, certification, fingerprints, analysis_fingerprint):
    return {
        "analysis_id": identity.analysis_id,
        "analysis_semantic_fingerprint": analysis_fingerprint,
        "artifact_fingerprints": fingerprints,
        "artifact_names": list(SEMANTIC_ARTIFACT_FILENAMES),
        "artifact_schema_version": "1.0",
        "artifact_type": "semantic_analysis_manifest",
        "certification_status": certification["certification_status"],
        "code_state": {
            "after_ast_fingerprint": after.canonical_ast_fingerprint,
            "before_ast_fingerprint": before.canonical_ast_fingerprint,
        },
        "decision": synthesis["decision"],
        "engine_version": identity.engine_version,
        "model_dataset_urn": identity.model_dataset_urn,
        "operation": identity.operation.value,
        "parser": {"name": identity.parser_name, "version": identity.parser_version},
        "proposal": semantic_proposal_to_dict(proposal),
        "proposal_fingerprint": identity.proposal_fingerprint,
        "semantic_delta_count": len(semantic),
        "source_snapshot_fingerprint": identity.source_snapshot_fingerprint,
        "sql_dialect": identity.sql_dialect,
        "structural_delta_count": len(structural),
        "warnings": artifacts_warnings(synthesis, structural, semantic),
    }


def artifacts_warnings(synthesis, structural, semantic):
    warnings = []
    if semantic:
        warnings.append("Semantic compatibility is unresolved without certified contract or execution evidence.")
    if structural:
        warnings.append("Structural output deltas require a separate structural review; no repair was generated.")
    return warnings


def _validate_manifest(artifacts, manifest, fingerprints):
    if set(artifacts) != set(SEMANTIC_ARTIFACT_FILENAMES):
        raise SemanticCertificationError("Completed semantic package is incomplete.")
    if manifest["artifact_names"] != list(SEMANTIC_ARTIFACT_FILENAMES):
        raise SemanticCertificationError("Semantic manifest names are incomplete.")
    if manifest["artifact_fingerprints"] != fingerprints:
        raise SemanticCertificationError("Semantic manifest fingerprints are inconsistent.")


def _export(output_dir, artifacts, *, repository_root, overwrite):
    destination = output_dir.resolve()
    root = repository_root.resolve()
    golden = (root / "artifacts").resolve()
    try:
        destination.relative_to(root)
    except ValueError as exc:
        raise UnsafeCodeInputError("Semantic output must be contained in the repository.") from exc
    if destination in {root, golden, Path.home().resolve()}:
        raise UnsafeCodeInputError("Semantic output cannot target a repository, home, or golden artifact root.")
    if destination.exists():
        if not overwrite:
            raise UnsafeCodeInputError("Semantic output already exists; explicit overwrite is required.")
        unknown = {item.name for item in destination.iterdir()} - set(SEMANTIC_ARTIFACT_FILENAMES)
        if unknown:
            raise UnsafeCodeInputError("Refusing to overwrite a directory with non-semantic-analysis files.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staged = Path(tempfile.mkdtemp(prefix=".chronos-semantic-", dir=destination.parent))
    try:
        for name in SEMANTIC_ARTIFACT_FILENAMES:
            (staged / name).write_text(pretty_json(artifacts[name]), encoding="utf-8")
        if destination.exists():
            shutil.rmtree(destination)
        staged.replace(destination)
    except Exception:
        if staged.exists():
            shutil.rmtree(staged)
        raise
    return destination
