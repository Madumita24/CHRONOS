"""Fail-closed materialization of the Phase 3.1 source-only candidate."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from chronos.change_semantics import (
    ChangeSemanticContract,
    IdentityClassification,
    RuleDisposition,
    SemanticRuleCode,
    contract_semantic_fingerprint,
    load_contract,
)
from chronos.phase2_certification import (
    CertificationCheckStatus,
    Phase2CertificationResult,
    Phase2CertificationState,
    certification_semantic_fingerprint,
    certify_phase2,
    load_certification,
)
from chronos.proposal import (
    CANONICAL_DATASET_URN,
    CANONICAL_DEMONSTRATION_ID,
    ChangeProposal,
    ChangeType,
    load_proposal,
    proposal_semantic_fingerprint,
)
from chronos.proposal_validation import (
    ProposalValidationResult,
    ProposalValidationState,
    load_validation_result,
    validation_result_semantic_fingerprint,
)
from chronos.snapshot import (
    CurrentMetadataSnapshot,
    SnapshotValidationState,
    load_snapshot,
    semantic_fingerprint as snapshot_semantic_fingerprint,
)

from .errors import (
    CounterfactualSourceStateValidationError,
    Phase3EntryPreconditionError,
)
from .models import (
    COUNTERFACTUAL_SOURCE_SCHEMA_VERSION,
    CandidateSourceField,
    CandidateSourceSchema,
    CounterfactualDatasetIdentity,
    CounterfactualSourceState,
    CurrentSourceSchemaReference,
    FieldIdentityMapping,
    FieldMappingClassification,
    InputArtifactHash,
    SourceFieldIdentity,
    SourceStateClassification,
    TransformationSummary,
)


Clock = Callable[[], datetime]
_CURRENT_FIELD = "order_total"
_CANDIDATE_FIELD = "order_amount"


def materialize_counterfactual_source_state(
    snapshot: CurrentMetadataSnapshot,
    proposal: ChangeProposal,
    validation: ProposalValidationResult,
    contract: ChangeSemanticContract,
    phase_2_certification: Phase2CertificationResult,
    *,
    input_artifact_hashes: tuple[InputArtifactHash, ...],
    clock: Clock | None = None,
) -> CounterfactualSourceState:
    """Apply the certified rename only to a new source-schema representation."""

    _require_entry_preconditions(
        snapshot,
        proposal,
        validation,
        contract,
        phase_2_certification,
        input_artifact_hashes,
    )
    source_dataset = tuple(
        item
        for item in snapshot.datasets
        if item.dataset_urn == snapshot.source_dataset_urn
    )[0]
    dataset_identity = CounterfactualDatasetIdentity(
        dataset_urn=snapshot.source_schema.dataset_urn,
        platform=snapshot.source_schema.platform,
        environment=snapshot.source_schema.environment,
        qualified_name=source_dataset.qualified_name,
        logical_name=source_dataset.logical_name,
        schema_name=snapshot.source_schema.schema_name,
        source_platform=snapshot.source_schema.source_platform,
        state_classification=SourceStateClassification.COUNTERFACTUAL,
    )
    candidate_fields: list[CandidateSourceField] = []
    mappings: list[FieldIdentityMapping] = []
    for current in snapshot.source_schema.fields:
        renamed = current.field_path == _CURRENT_FIELD
        candidate_path = _CANDIDATE_FIELD if renamed else current.field_path
        candidate_name = _CANDIDATE_FIELD if renamed else current.field_name
        current_identity = SourceFieldIdentity(
            dataset_urn=snapshot.source_schema.dataset_urn,
            field_path=current.field_path,
            state_classification=(
                SourceStateClassification.CERTIFIED_CURRENT
            ),
        )
        candidate_identity = SourceFieldIdentity(
            dataset_urn=snapshot.source_schema.dataset_urn,
            field_path=candidate_path,
            state_classification=SourceStateClassification.COUNTERFACTUAL,
        )
        candidate_fields.append(
            CandidateSourceField(
                position=current.position,
                field_path=candidate_path,
                field_name=candidate_name,
                native_type=current.native_type,
                normalized_type=current.normalized_type,
                datahub_type=current.datahub_type,
                description=current.description,
                nullable=current.nullable,
                is_part_of_key=current.is_part_of_key,
                is_partitioning_key=current.is_partitioning_key,
                json_path=current.json_path,
                label=current.label,
                recursive=current.recursive,
                schema_field_urn=current.schema_field_urn,
                current_evidence_ids=current.evidence_ids,
                state_classification=(
                    SourceStateClassification.COUNTERFACTUAL
                ),
                current_source_identity=current_identity,
            )
        )
        mappings.append(
            FieldIdentityMapping(
                current_identity=current_identity,
                candidate_identity=candidate_identity,
                classification=(
                    FieldMappingClassification.RENAMED
                    if renamed
                    else FieldMappingClassification.UNCHANGED
                ),
            )
        )
    source_schema = snapshot.source_schema
    state = CounterfactualSourceState(
        schema_version=COUNTERFACTUAL_SOURCE_SCHEMA_VERSION,
        demonstration_id=CANONICAL_DEMONSTRATION_ID,
        state_classification=SourceStateClassification.COUNTERFACTUAL,
        operation=ChangeType.FIELD_RENAME,
        dataset_identity=dataset_identity,
        current_snapshot_fingerprint=snapshot.semantic_fingerprint,
        proposal_fingerprint=proposal.semantic_fingerprint,
        validation_fingerprint=validation.semantic_fingerprint,
        semantic_contract_fingerprint=contract.semantic_fingerprint,
        phase_2_certification_fingerprint=(
            phase_2_certification.semantic_fingerprint
        ),
        current_source_schema_reference=CurrentSourceSchemaReference(
            snapshot_id=snapshot.metadata.snapshot_id,
            snapshot_fingerprint=snapshot.semantic_fingerprint,
            dataset_urn=source_schema.dataset_urn,
            schema_name=source_schema.schema_name,
            field_count=len(source_schema.fields),
            field_paths=tuple(
                item.field_path for item in source_schema.fields
            ),
            target_field=SourceFieldIdentity(
                dataset_urn=source_schema.dataset_urn,
                field_path=_CURRENT_FIELD,
                state_classification=(
                    SourceStateClassification.CERTIFIED_CURRENT
                ),
            ),
            state_classification=(
                SourceStateClassification.CERTIFIED_CURRENT
            ),
        ),
        candidate_source_schema=CandidateSourceSchema(
            dataset_identity=dataset_identity,
            schema_name=source_schema.schema_name,
            schema_version=source_schema.schema_version,
            schema_hash=source_schema.schema_hash,
            created_time=source_schema.created_time,
            last_modified_time=source_schema.last_modified_time,
            dataset_reference=source_schema.dataset_reference,
            cluster=source_schema.cluster,
            primary_keys=source_schema.primary_keys,
            current_evidence_ids=source_schema.evidence_ids,
            fields=tuple(candidate_fields),
            state_classification=SourceStateClassification.COUNTERFACTUAL,
        ),
        field_identity_mappings=tuple(mappings),
        transformation_summary=TransformationSummary(14, 1, 0, 0, 0, 0, 0),
        input_artifact_hashes=input_artifact_hashes,
        created_at=_timestamp(clock),
    )
    validate_counterfactual_source_state(
        state,
        snapshot,
        proposal,
        validation,
        contract,
        phase_2_certification,
    )
    return state


def materialize_source_state_from_artifacts(
    snapshot_path: str | Path,
    proposal_path: str | Path,
    validation_path: str | Path,
    contract_path: str | Path,
    phase_2_certification_path: str | Path,
    *,
    clock: Clock | None = None,
) -> CounterfactualSourceState:
    paths = (
        ("current_metadata_snapshot.json", Path(snapshot_path)),
        ("change_proposal.json", Path(proposal_path)),
        ("change_proposal_validation.json", Path(validation_path)),
        ("change_semantic_contract.json", Path(contract_path)),
        ("phase_2_certification.json", Path(phase_2_certification_path)),
    )
    before = {
        name: hashlib.sha256(path.read_bytes()).hexdigest()
        for name, path in paths
    }
    snapshot = load_snapshot(snapshot_path)
    proposal = load_proposal(proposal_path)
    validation = load_validation_result(validation_path)
    contract = load_contract(contract_path)
    phase_2_certification = load_certification(
        phase_2_certification_path
    )
    after_load = {
        name: hashlib.sha256(path.read_bytes()).hexdigest()
        for name, path in paths
    }
    hashes = tuple(
        InputArtifactHash(
            artifact_name=name,
            before_sha256=before[name],
            after_sha256=after_load[name],
        )
        for name, _ in paths
    )
    state = materialize_counterfactual_source_state(
        snapshot,
        proposal,
        validation,
        contract,
        phase_2_certification,
        input_artifact_hashes=hashes,
        clock=clock,
    )
    after_materialization = {
        name: hashlib.sha256(path.read_bytes()).hexdigest()
        for name, path in paths
    }
    if after_materialization != before:
        raise CounterfactualSourceStateValidationError(
            "An authoritative input artifact changed during materialization."
        )
    return state


def validate_counterfactual_source_state(
    state: CounterfactualSourceState,
    snapshot: CurrentMetadataSnapshot,
    proposal: ChangeProposal,
    validation: ProposalValidationResult,
    contract: ChangeSemanticContract,
    phase_2_certification: Phase2CertificationResult,
) -> None:
    """Validate source-only semantics against the certified artifacts."""

    issues: list[str] = []

    def require(condition: bool, message: str) -> None:
        if not condition:
            issues.append(message)

    require(
        state.state_classification
        is SourceStateClassification.COUNTERFACTUAL,
        "state classification must be COUNTERFACTUAL",
    )
    require(
        state.current_snapshot_fingerprint == snapshot.semantic_fingerprint,
        "snapshot fingerprint mismatch",
    )
    require(
        state.proposal_fingerprint == proposal.semantic_fingerprint,
        "proposal fingerprint mismatch",
    )
    require(
        state.validation_fingerprint == validation.semantic_fingerprint,
        "validation fingerprint mismatch",
    )
    require(
        state.semantic_contract_fingerprint == contract.semantic_fingerprint,
        "semantic-contract fingerprint mismatch",
    )
    require(
        state.phase_2_certification_fingerprint
        == phase_2_certification.semantic_fingerprint,
        "Phase 2 certification fingerprint mismatch",
    )
    source_schema = snapshot.source_schema
    source_datasets = tuple(
        item
        for item in snapshot.datasets
        if item.dataset_urn == source_schema.dataset_urn
    )
    require(len(source_datasets) == 1, "source Dataset must exist once")
    if source_datasets:
        source_dataset = source_datasets[0]
        identity = state.dataset_identity
        require(
            identity.dataset_urn == source_schema.dataset_urn,
            "Dataset URN changed",
        )
        require(
            identity.platform == source_schema.platform,
            "Dataset platform changed",
        )
        require(
            identity.environment == source_schema.environment,
            "Dataset environment changed",
        )
        require(
            identity.qualified_name == source_dataset.qualified_name,
            "qualified Dataset identity changed",
        )
        require(
            identity.logical_name == source_dataset.logical_name,
            "logical Dataset identity changed",
        )
        require(
            identity.schema_name == source_schema.schema_name,
            "schema identity changed",
        )
    candidate_schema = state.candidate_source_schema
    schema_attributes_match = (
        candidate_schema.schema_name == source_schema.schema_name
        and candidate_schema.schema_version == source_schema.schema_version
        and candidate_schema.schema_hash == source_schema.schema_hash
        and candidate_schema.created_time == source_schema.created_time
        and candidate_schema.last_modified_time
        == source_schema.last_modified_time
        and candidate_schema.dataset_reference
        == source_schema.dataset_reference
        and candidate_schema.cluster == source_schema.cluster
        and candidate_schema.primary_keys == source_schema.primary_keys
        and candidate_schema.current_evidence_ids
        == source_schema.evidence_ids
    )
    require(schema_attributes_match, "source schema metadata changed")
    current_fields = source_schema.fields
    candidate_fields = candidate_schema.fields
    require(len(candidate_fields) == len(current_fields), "field count changed")
    for index, current in enumerate(current_fields):
        if index >= len(candidate_fields):
            break
        candidate = candidate_fields[index]
        renamed = current.field_path == _CURRENT_FIELD
        expected_path = _CANDIDATE_FIELD if renamed else current.field_path
        expected_name = _CANDIDATE_FIELD if renamed else current.field_name
        expected = (
            current.position,
            expected_path,
            expected_name,
            current.native_type,
            current.normalized_type,
            current.datahub_type,
            current.description,
            current.nullable,
            current.is_part_of_key,
            current.is_partitioning_key,
            current.json_path,
            current.label,
            current.recursive,
            current.schema_field_urn,
            current.evidence_ids,
        )
        observed = (
            candidate.position,
            candidate.field_path,
            candidate.field_name,
            candidate.native_type,
            candidate.normalized_type,
            candidate.datahub_type,
            candidate.description,
            candidate.nullable,
            candidate.is_part_of_key,
            candidate.is_partitioning_key,
            candidate.json_path,
            candidate.label,
            candidate.recursive,
            candidate.schema_field_urn,
            candidate.current_evidence_ids,
        )
        require(
            observed == expected,
            f"candidate field at position {index} changed outside contract",
        )
        require(
            candidate.current_source_identity.machine_key
            == (source_schema.dataset_urn, current.field_path),
            f"current-source reference at position {index} is invalid",
        )
    target = tuple(
        item
        for item in candidate_fields
        if item.field_path == _CANDIDATE_FIELD
    )
    require(len(target) == 1, "candidate target occurrence must equal 1")
    if target:
        item = target[0]
        require(item.position == 5, "candidate target position changed")
        require(
            item.native_type == "DOUBLE PRECISION",
            "candidate native type changed",
        )
        require(
            item.normalized_type == "Number",
            "candidate normalized type changed",
        )
        require(item.nullable is True, "candidate nullability changed")
        require(
            item.is_part_of_key is False,
            "candidate key status changed",
        )
        require(
            item.schema_field_urn is None,
            "candidate schema-field URN was fabricated",
        )
    require(
        all(item.unchanged for item in state.input_artifact_hashes),
        "an input artifact hash changed",
    )
    require(
        not hasattr(state, "lineage_edges")
        and not hasattr(state, "lineage_paths")
        and not hasattr(state, "relationships")
        and not hasattr(state, "downstream_fields"),
        "downstream, lineage, or governance state was materialized",
    )
    if issues:
        raise CounterfactualSourceStateValidationError("; ".join(issues))


def _require_entry_preconditions(
    snapshot: CurrentMetadataSnapshot,
    proposal: ChangeProposal,
    validation: ProposalValidationResult,
    contract: ChangeSemanticContract,
    phase_2_certification: Phase2CertificationResult,
    input_artifact_hashes: tuple[InputArtifactHash, ...],
) -> None:
    if snapshot.validation_result.state is not SnapshotValidationState.VALID:
        raise Phase3EntryPreconditionError(
            "Phase 1 snapshot is not certified valid."
        )
    if (
        phase_2_certification.certification_state
        is not Phase2CertificationState.CERTIFIED
        or phase_2_certification.findings
        or phase_2_certification.warnings
        or any(
            item.status is not CertificationCheckStatus.PASS
            for item in phase_2_certification.checks
        )
    ):
        raise Phase3EntryPreconditionError("Phase 2 is not CERTIFIED.")
    if validation.validation_state is not ProposalValidationState.VALID:
        raise Phase3EntryPreconditionError(
            "Proposal validation must be VALID."
        )
    fingerprint_checks = (
        (
            snapshot_semantic_fingerprint(snapshot),
            snapshot.semantic_fingerprint,
            "snapshot",
        ),
        (
            proposal_semantic_fingerprint(proposal),
            proposal.semantic_fingerprint,
            "proposal",
        ),
        (
            validation_result_semantic_fingerprint(validation),
            validation.semantic_fingerprint,
            "validation",
        ),
        (
            contract_semantic_fingerprint(contract),
            contract.semantic_fingerprint,
            "semantic contract",
        ),
        (
            certification_semantic_fingerprint(phase_2_certification),
            phase_2_certification.semantic_fingerprint,
            "Phase 2 certification",
        ),
    )
    for recomputed, stored, label in fingerprint_checks:
        if recomputed != stored:
            raise Phase3EntryPreconditionError(
                f"Stored {label} fingerprint does not reproduce."
            )
    if (
        phase_2_certification.snapshot_fingerprint
        != snapshot.semantic_fingerprint
        or phase_2_certification.proposal_fingerprint
        != proposal.semantic_fingerprint
        or phase_2_certification.validation_fingerprint
        != validation.semantic_fingerprint
        or phase_2_certification.semantic_contract_fingerprint
        != contract.semantic_fingerprint
    ):
        raise Phase3EntryPreconditionError(
            "Phase 2 certification references do not match inputs."
        )
    recomputed_certification = certify_phase2(
        snapshot,
        proposal,
        validation,
        contract,
        artifact_hashes=phase_2_certification.artifact_hashes,
    )
    if not recomputed_certification.semantically_equals(
        phase_2_certification
    ):
        raise Phase3EntryPreconditionError(
            "Phase 2 certification does not reproduce."
        )
    if (
        snapshot.metadata.demonstration_id
        != proposal.demonstration_id
        or proposal.demonstration_id != CANONICAL_DEMONSTRATION_ID
        or phase_2_certification.demonstration_id
        != CANONICAL_DEMONSTRATION_ID
    ):
        raise Phase3EntryPreconditionError(
            "Demonstration identity mismatch."
        )
    if proposal.change_type is not ChangeType.FIELD_RENAME:
        raise Phase3EntryPreconditionError("Operation must be FIELD_RENAME.")
    if (
        snapshot.source_schema.dataset_urn != CANONICAL_DATASET_URN
        or proposal.change.target.dataset_urn != CANONICAL_DATASET_URN
        or contract.current_target.dataset_urn != CANONICAL_DATASET_URN
        or contract.counterfactual_candidate.dataset_urn
        != CANONICAL_DATASET_URN
    ):
        raise Phase3EntryPreconditionError("Target Dataset URN mismatch.")
    if (
        proposal.change.target.field_path != _CURRENT_FIELD
        or proposal.change.before.field_path != _CURRENT_FIELD
        or proposal.change.requested_after.field_path != _CANDIDATE_FIELD
        or proposal.change.requested_after.field_name != _CANDIDATE_FIELD
        or contract.current_target.field_path != _CURRENT_FIELD
        or contract.counterfactual_candidate.field_path != _CANDIDATE_FIELD
    ):
        raise Phase3EntryPreconditionError(
            "Current or candidate field identity mismatch."
        )
    target_count = sum(
        item.field_path == _CURRENT_FIELD
        for item in snapshot.source_schema.fields
    )
    collision_count = sum(
        item.field_path == _CANDIDATE_FIELD
        for item in snapshot.source_schema.fields
    )
    if target_count != 1:
        raise Phase3EntryPreconditionError(
            "Current target field must exist exactly once."
        )
    if collision_count:
        raise Phase3EntryPreconditionError(
            "Candidate field collides with current source schema."
        )
    if len(snapshot.source_schema.fields) != 15:
        raise Phase3EntryPreconditionError(
            "Certified source schema must contain 15 fields."
        )
    changed = {
        item.property_name for item in contract.changed_properties
    }
    if changed != {"field_path", "field_name"}:
        raise Phase3EntryPreconditionError(
            "Semantic contract changed-property set is invalid."
        )
    rules = {item.code: item.disposition for item in contract.semantic_rules}
    if (
        rules.get(SemanticRuleCode.AUTOMATIC_DOWNSTREAM_RENAME)
        is not RuleDisposition.FORBIDDEN
        or contract.counterfactual_candidate.classification
        is not IdentityClassification.COUNTERFACTUAL_CANDIDATE
    ):
        raise Phase3EntryPreconditionError(
            "Semantic contract does not preserve non-propagation."
        )
    if len(input_artifact_hashes) != 5 or any(
        not item.unchanged for item in input_artifact_hashes
    ):
        raise Phase3EntryPreconditionError(
            "All five authoritative artifact hashes must be unchanged."
        )


def _timestamp(clock: Clock | None) -> str:
    value = (clock or (lambda: datetime.now(timezone.utc)))()
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()
