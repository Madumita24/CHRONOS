"""Fail-closed FIELD_RENAME compatibility evaluation for Phase 3.4."""

from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

from chronos.change_semantics import ChangeSemanticContract, load_contract
from chronos.counterfactual_source import (
    CounterfactualSourceState,
    InputArtifactHash,
    SourceStateClassification,
    load_source_state,
    source_state_semantic_fingerprint,
    validate_counterfactual_source_state,
)
from chronos.dependency_propagation import (
    DependencyPropagationResult,
    FieldExposureState,
    PropagationValidationState,
    RelationshipExposureState,
    load_dependency_propagation,
    propagation_semantic_fingerprint,
    validate_dependency_propagation,
)
from chronos.future_graph import (
    FutureGraphValidationState,
    FutureLineageRelationship,
    FutureMetadataGraph,
    FutureRelationshipState,
    GraphObjectState,
    future_graph_semantic_fingerprint,
    load_future_graph,
    validate_future_metadata_graph,
)
from chronos.phase2_certification import (
    Phase2CertificationResult,
    Phase2CertificationState,
    load_certification,
)
from chronos.proposal import (
    CANONICAL_DATASET_URN,
    CANONICAL_DEMONSTRATION_ID,
    ChangeProposal,
    ChangeType,
    load_proposal,
)
from chronos.proposal_validation import (
    ProposalValidationResult,
    ProposalValidationState,
    load_validation_result,
)
from chronos.snapshot import (
    CurrentMetadataSnapshot,
    FieldMachineKey,
    SnapshotValidationState,
    load_snapshot,
)

from .errors import (
    CompatibilityEntryPreconditionError,
    CompatibilityValidationError,
)
from .models import (
    COMPATIBILITY_EVALUATION_SCHEMA_VERSION,
    CompatibilityAggregate,
    CompatibilityCounts,
    CompatibilityDecision,
    CompatibilityEvaluationResult,
    CompatibilityEvaluationState,
    CompatibilityReasonCode,
    CompatibilityState,
    CompatibilityValidationState,
    DatasetCompatibilitySummary,
    EvidenceStrength,
    EvidenceStrengthCounts,
    ExplicitRenameBehavior,
    FieldCompatibilityEvaluation,
    PathCompatibilityEvaluation,
    RelationshipCompatibilityEvaluation,
    RenameCompatibilityEvidence,
    SourceFieldChange,
)


Clock = Callable[[], datetime]
_CURRENT_SOURCE = FieldMachineKey(CANONICAL_DATASET_URN, "order_total")
_CANDIDATE_SOURCE = FieldMachineKey(CANONICAL_DATASET_URN, "order_amount")


def evaluate_field_rename_evidence(
    evidence: RenameCompatibilityEvidence,
) -> CompatibilityDecision:
    """Evaluate only captured FIELD_RENAME-specific relationship evidence."""

    behavior = evidence.explicit_rename_behavior
    if behavior is ExplicitRenameBehavior.ACCEPTS_RENAMED_INPUT:
        return CompatibilityDecision(
            CompatibilityState.COMPATIBLE,
            EvidenceStrength.EXPLICIT,
            CompatibilityReasonCode.EXPLICIT_TRANSFORM_COMPATIBLE,
            (
                "Captured rename behavior explicitly accepts the candidate "
                "upstream identifier."
            ),
        )
    if behavior is ExplicitRenameBehavior.REJECTS_RENAMED_INPUT:
        return CompatibilityDecision(
            CompatibilityState.INCOMPATIBLE,
            EvidenceStrength.EXPLICIT,
            CompatibilityReasonCode.EXPLICIT_TRANSFORM_INCOMPATIBLE,
            (
                "Captured rename behavior explicitly rejects the candidate "
                "upstream identifier."
            ),
        )
    if behavior is ExplicitRenameBehavior.CONDITIONAL:
        return CompatibilityDecision(
            CompatibilityState.CONDITIONALLY_COMPATIBLE,
            EvidenceStrength.EXPLICIT,
            CompatibilityReasonCode.CONDITIONAL_TRANSFORM_DEPENDENCY,
            (
                "Captured rename behavior establishes compatibility only "
                "under an explicit unresolved condition."
            ),
        )
    if evidence.upstream_identity_changed:
        missing = []
        if not evidence.transform_operations:
            missing.append("transform semantics")
        if not evidence.queries:
            missing.append("query semantics")
        suffix = (
            " Missing " + " and ".join(missing) + "."
            if missing
            else (
                " Captured current transform/query text does not explicitly "
                "establish candidate-identifier behavior."
            )
        )
        return CompatibilityDecision(
            CompatibilityState.UNKNOWN,
            EvidenceStrength.INSUFFICIENT,
            CompatibilityReasonCode.SOURCE_RENAME_SEMANTICS_UNKNOWN,
            (
                "The structural edge was rebased from the current source "
                "identifier to the candidate identifier, but captured "
                "metadata does not establish whether the implementation "
                "accepts that rename."
            )
            + suffix,
        )
    if evidence.endpoints_preserved:
        return CompatibilityDecision(
            CompatibilityState.CONDITIONALLY_COMPATIBLE,
            EvidenceStrength.DERIVED,
            CompatibilityReasonCode.CONDITIONAL_TRANSFORM_DEPENDENCY,
            (
                "The certified proposal does not change either local endpoint "
                "identity. Local continuity is conditional on the upstream "
                "field remaining available through the unresolved source "
                "rename; current lineage alone does not prove future "
                "execution."
            ),
        )
    return CompatibilityDecision(
        CompatibilityState.UNKNOWN,
        EvidenceStrength.INSUFFICIENT,
        CompatibilityReasonCode.INSUFFICIENT_EVIDENCE,
        (
            "Captured metadata does not establish how the changed endpoint "
            "identity is handled."
        ),
    )


def roll_up_path_compatibility(
    edge_states: tuple[CompatibilityState, ...],
) -> CompatibilityDecision:
    if not edge_states:
        raise ValueError("A compatibility path must contain an edge.")
    if CompatibilityState.INCOMPATIBLE in edge_states:
        return CompatibilityDecision(
            CompatibilityState.INCOMPATIBLE,
            EvidenceStrength.DERIVED,
            CompatibilityReasonCode.EXPLICIT_TRANSFORM_INCOMPATIBLE,
            "At least one required path relationship is incompatible.",
        )
    if CompatibilityState.UNKNOWN in edge_states:
        return CompatibilityDecision(
            CompatibilityState.UNKNOWN,
            EvidenceStrength.INSUFFICIENT,
            CompatibilityReasonCode.UPSTREAM_COMPATIBILITY_UNKNOWN,
            "At least one required path relationship remains unknown.",
        )
    if CompatibilityState.CONDITIONALLY_COMPATIBLE in edge_states:
        return CompatibilityDecision(
            CompatibilityState.CONDITIONALLY_COMPATIBLE,
            EvidenceStrength.DERIVED,
            CompatibilityReasonCode.CONDITIONAL_TRANSFORM_DEPENDENCY,
            "At least one required path relationship is conditional.",
        )
    return CompatibilityDecision(
        CompatibilityState.COMPATIBLE,
        EvidenceStrength.DERIVED,
        CompatibilityReasonCode.EXPLICIT_IDENTIFIER_PRESERVED,
        "Every required path relationship is explicitly compatible.",
    )


def roll_up_field_compatibility(
    path_states: tuple[CompatibilityState, ...],
) -> CompatibilityDecision:
    if not path_states:
        raise ValueError("A downstream field must have a supporting path.")
    unique = set(path_states)
    if len(unique) > 1:
        return CompatibilityDecision(
            CompatibilityState.UNKNOWN,
            EvidenceStrength.INSUFFICIENT,
            CompatibilityReasonCode.MULTIPATH_MIXED_COMPATIBILITY,
            (
                "Supporting paths have mixed compatibility conclusions, and "
                "captured evidence does not establish whether they are "
                "alternatives or jointly required."
            ),
        )
    state = path_states[0]
    if state is CompatibilityState.UNKNOWN:
        return CompatibilityDecision(
            state,
            EvidenceStrength.INSUFFICIENT,
            CompatibilityReasonCode.UPSTREAM_COMPATIBILITY_UNKNOWN,
            "Every supporting path contains unresolved compatibility.",
        )
    if state is CompatibilityState.INCOMPATIBLE:
        return CompatibilityDecision(
            state,
            EvidenceStrength.DERIVED,
            CompatibilityReasonCode.EXPLICIT_TRANSFORM_INCOMPATIBLE,
            "Every supporting path is incompatible.",
        )
    if state is CompatibilityState.CONDITIONALLY_COMPATIBLE:
        return CompatibilityDecision(
            state,
            EvidenceStrength.DERIVED,
            CompatibilityReasonCode.CONDITIONAL_TRANSFORM_DEPENDENCY,
            "Every supporting path is conditionally compatible.",
        )
    return CompatibilityDecision(
        state,
        EvidenceStrength.DERIVED,
        CompatibilityReasonCode.EXPLICIT_IDENTIFIER_PRESERVED,
        "Every supporting path is compatible.",
    )


def evaluate_compatibility(
    snapshot: CurrentMetadataSnapshot,
    proposal: ChangeProposal,
    validation: ProposalValidationResult,
    contract: ChangeSemanticContract,
    phase_2_certification: Phase2CertificationResult,
    source_state: CounterfactualSourceState,
    future_graph: FutureMetadataGraph,
    propagation: DependencyPropagationResult,
    *,
    input_artifact_hashes: tuple[InputArtifactHash, ...],
    clock: Clock | None = None,
) -> CompatibilityEvaluationResult:
    """Evaluate compatibility without deriving impact or repair semantics."""

    _require_entry_preconditions(
        snapshot,
        proposal,
        validation,
        contract,
        phase_2_certification,
        source_state,
        future_graph,
        propagation,
        input_artifact_hashes,
    )
    graph_relationships = {
        item.relationship_id: item
        for item in future_graph.relationship_registry
    }
    propagation_relationships = {
        item.relationship_id: item
        for item in propagation.relationship_exposure_registry
    }
    mapping_groups = {
        item.group_id: item
        for item in future_graph.mapping_group_registry
    }

    relationship_evaluations: list[
        RelationshipCompatibilityEvaluation
    ] = []
    for relationship_id in sorted(propagation_relationships):
        graph_record = graph_relationships[relationship_id]
        exposure_record = propagation_relationships[relationship_id]
        groups = tuple(
            mapping_groups[value]
            for value in graph_record.current_mapping_group_ids
        )
        transform_operations = tuple(
            sorted(
                set(graph_record.current_transform_operations)
                | {
                    item.current_transform_operation
                    for item in groups
                    if item.current_transform_operation is not None
                }
            )
        )
        queries = tuple(
            sorted(
                {
                    item.current_query
                    for item in groups
                    if item.current_query is not None
                }
            )
        )
        decision = evaluate_field_rename_evidence(
            RenameCompatibilityEvidence(
                current_upstream=graph_record.current_upstream,
                current_downstream=graph_record.current_downstream,
                candidate_upstream=graph_record.upstream,
                candidate_downstream=graph_record.downstream,
                transform_operations=transform_operations,
                queries=queries,
                explicit_rename_behavior=None,
            )
        )
        relationship_evaluations.append(
            RelationshipCompatibilityEvaluation(
                relationship_id=relationship_id,
                upstream_field=graph_record.upstream,
                downstream_field=graph_record.downstream,
                structural_state=graph_record.relationship_state,
                exposure_state=exposure_record.exposure_state,
                evaluation_state=CompatibilityEvaluationState.EVALUATED,
                compatibility_state=decision.compatibility_state,
                evidence_strength=decision.evidence_strength,
                reason_code=decision.reason_code,
                explanation=decision.explanation,
                mapping_group_ids=graph_record.current_mapping_group_ids,
                transform_operations=transform_operations,
                query_evidence=queries,
                lineage_confidence_provenance=(
                    graph_record.current_confidence_scores
                ),
                supporting_path_ids=exposure_record.supporting_path_ids,
                current_provenance_ids=(
                    exposure_record.current_provenance_ids
                ),
                counterfactual_provenance_ids=(
                    exposure_record.counterfactual_provenance_ids
                ),
            )
        )
    relationship_by_id = {
        item.relationship_id: item
        for item in relationship_evaluations
    }

    path_evaluations: list[PathCompatibilityEvaluation] = []
    for path in sorted(propagation.path_registry, key=lambda item: item.path_id):
        edge_evaluations = tuple(
            relationship_by_id[value] for value in path.relationship_ids
        )
        edge_states = tuple(
            item.compatibility_state for item in edge_evaluations
        )
        decision = roll_up_path_compatibility(edge_states)
        current_ids = _ordered_union(
            path.current_provenance_ids,
            *(
                item.current_provenance_ids
                for item in edge_evaluations
            ),
        )
        counterfactual_ids = _ordered_union(
            path.counterfactual_provenance_ids,
            *(
                item.counterfactual_provenance_ids
                for item in edge_evaluations
            ),
        )
        path_evaluations.append(
            PathCompatibilityEvaluation(
                path_id=path.path_id,
                target_field=path.target_field,
                depth=path.depth,
                relationship_ids=path.relationship_ids,
                edge_compatibility_states=edge_states,
                evaluation_state=CompatibilityEvaluationState.EVALUATED,
                compatibility_state=decision.compatibility_state,
                reason_codes=(decision.reason_code,),
                blocking_relationship_ids=tuple(
                    item.relationship_id
                    for item in edge_evaluations
                    if item.compatibility_state
                    is CompatibilityState.INCOMPATIBLE
                ),
                uncertain_relationship_ids=tuple(
                    item.relationship_id
                    for item in edge_evaluations
                    if item.compatibility_state
                    in {
                        CompatibilityState.UNKNOWN,
                        CompatibilityState.CONDITIONALLY_COMPATIBLE,
                    }
                ),
                current_provenance_ids=current_ids,
                counterfactual_provenance_ids=counterfactual_ids,
            )
        )
    path_by_id = {item.path_id: item for item in path_evaluations}

    field_evaluations: list[FieldCompatibilityEvaluation] = []
    downstream_fields = tuple(
        item
        for item in propagation.field_exposure_registry
        if item.field_key != propagation.source_candidate_field
    )
    for field_record in sorted(
        downstream_fields,
        key=lambda item: (
            item.minimum_depth,
            item.field_key.dataset_urn,
            item.field_key.field_path,
        ),
    ):
        paths = tuple(
            path_by_id[value] for value in field_record.supporting_path_ids
        )
        path_states = tuple(item.compatibility_state for item in paths)
        decision = roll_up_field_compatibility(path_states)
        incoming = tuple(
            relationship_by_id[value]
            for value in field_record.incoming_exposed_relationship_ids
        )
        field_evaluations.append(
            FieldCompatibilityEvaluation(
                field_key=field_record.field_key,
                exposure_state=field_record.exposure_state,
                minimum_depth=field_record.minimum_depth,
                supporting_path_count=field_record.path_count,
                supporting_path_ids=field_record.supporting_path_ids,
                incoming_relationship_ids=(
                    field_record.incoming_exposed_relationship_ids
                ),
                incoming_relationship_states=tuple(
                    item.compatibility_state for item in incoming
                ),
                path_compatibility_states=path_states,
                evaluation_state=CompatibilityEvaluationState.EVALUATED,
                compatibility_state=decision.compatibility_state,
                evidence_strength=decision.evidence_strength,
                reason_codes=(decision.reason_code,),
                current_provenance_ids=_ordered_union(
                    field_record.current_provenance_ids,
                    *(item.current_provenance_ids for item in paths),
                ),
                counterfactual_provenance_ids=_ordered_union(
                    field_record.counterfactual_provenance_ids,
                    *(
                        item.counterfactual_provenance_ids
                        for item in paths
                    ),
                ),
            )
        )

    fields_by_dataset: dict[
        str,
        list[FieldCompatibilityEvaluation],
    ] = defaultdict(list)
    for item in field_evaluations:
        fields_by_dataset[item.field_key.dataset_urn].append(item)
    dataset_summaries: list[DatasetCompatibilitySummary] = []
    for dataset_urn, fields in sorted(fields_by_dataset.items()):
        ordered_fields = sorted(
            fields,
            key=lambda item: item.field_key.field_path,
        )
        counts = _compatibility_counts(
            item.compatibility_state for item in ordered_fields
        )
        states = {item.compatibility_state for item in ordered_fields}
        if len(states) == 1:
            dataset_state = next(iter(states))
            reason_codes = tuple(
                sorted(
                    {
                        value
                        for item in ordered_fields
                        for value in item.reason_codes
                    },
                    key=lambda value: value.value,
                )
            )
        else:
            dataset_state = CompatibilityState.UNKNOWN
            reason_codes = (
                CompatibilityReasonCode.INSUFFICIENT_EVIDENCE,
            )
        dataset_summaries.append(
            DatasetCompatibilitySummary(
                dataset_urn=dataset_urn,
                exposed_field_keys=tuple(
                    item.field_key for item in ordered_fields
                ),
                compatible_exposed_fields=counts.compatible,
                incompatible_exposed_fields=counts.incompatible,
                conditionally_compatible_exposed_fields=(
                    counts.conditionally_compatible
                ),
                unknown_exposed_fields=counts.unknown,
                compatibility_state=dataset_state,
                reason_codes=reason_codes,
            )
        )

    aggregate = CompatibilityAggregate(
        relationship_counts=_compatibility_counts(
            item.compatibility_state for item in relationship_evaluations
        ),
        path_counts=_compatibility_counts(
            item.compatibility_state for item in path_evaluations
        ),
        field_counts=_compatibility_counts(
            item.compatibility_state for item in field_evaluations
        ),
        dataset_counts=_compatibility_counts(
            item.compatibility_state for item in dataset_summaries
        ),
        relationship_evidence_strength=_evidence_strength_counts(
            item.evidence_strength for item in relationship_evaluations
        ),
    )
    result = CompatibilityEvaluationResult(
        schema_version=COMPATIBILITY_EVALUATION_SCHEMA_VERSION,
        demonstration_id=CANONICAL_DEMONSTRATION_ID,
        proposal_id=proposal.proposal_id,
        source_change=SourceFieldChange(
            current_field=_CURRENT_SOURCE,
            candidate_field=_CANDIDATE_SOURCE,
        ),
        future_graph_fingerprint=future_graph.semantic_fingerprint,
        dependency_propagation_fingerprint=(
            propagation.semantic_fingerprint
        ),
        relationship_evaluations=tuple(relationship_evaluations),
        path_evaluations=tuple(path_evaluations),
        field_evaluations=tuple(field_evaluations),
        dataset_summaries=tuple(dataset_summaries),
        aggregate=aggregate,
        input_artifact_hashes=input_artifact_hashes,
        warnings=(
            "Dependency exposure is not incompatibility or business impact.",
            (
                "Current lineage confidence is retained as provenance and is "
                "not a compatibility probability."
            ),
            (
                "UNKNOWN is a successful evidence-limited evaluation, not a "
                "Phase 3.4 failure."
            ),
        ),
        validation_state=CompatibilityValidationState.VALID,
        evaluated_at=_timestamp(clock),
    )
    validate_compatibility_evaluation(result, future_graph, propagation)
    return result


def evaluate_compatibility_from_artifacts(
    snapshot_path: str | Path,
    proposal_path: str | Path,
    validation_path: str | Path,
    contract_path: str | Path,
    phase_2_certification_path: str | Path,
    source_state_path: str | Path,
    future_graph_path: str | Path,
    propagation_path: str | Path,
    *,
    clock: Clock | None = None,
) -> CompatibilityEvaluationResult:
    paths = (
        ("current_metadata_snapshot.json", Path(snapshot_path)),
        ("change_proposal.json", Path(proposal_path)),
        ("change_proposal_validation.json", Path(validation_path)),
        ("change_semantic_contract.json", Path(contract_path)),
        ("phase_2_certification.json", Path(phase_2_certification_path)),
        ("counterfactual_source_state.json", Path(source_state_path)),
        ("future_metadata_graph.json", Path(future_graph_path)),
        ("dependency_propagation.json", Path(propagation_path)),
    )
    before = {
        name: hashlib.sha256(path.read_bytes()).hexdigest()
        for name, path in paths
    }
    snapshot = load_snapshot(snapshot_path)
    proposal = load_proposal(proposal_path)
    validation = load_validation_result(validation_path)
    contract = load_contract(contract_path)
    certification = load_certification(phase_2_certification_path)
    source_state = load_source_state(source_state_path)
    future_graph = load_future_graph(future_graph_path)
    propagation = load_dependency_propagation(propagation_path)
    after_load = {
        name: hashlib.sha256(path.read_bytes()).hexdigest()
        for name, path in paths
    }
    hashes = tuple(
        InputArtifactHash(name, before[name], after_load[name])
        for name, _ in paths
    )
    result = evaluate_compatibility(
        snapshot,
        proposal,
        validation,
        contract,
        certification,
        source_state,
        future_graph,
        propagation,
        input_artifact_hashes=hashes,
        clock=clock,
    )
    after_evaluation = {
        name: hashlib.sha256(path.read_bytes()).hexdigest()
        for name, path in paths
    }
    if after_evaluation != before:
        raise CompatibilityValidationError(
            "An authoritative artifact changed during compatibility evaluation."
        )
    return result


def validate_compatibility_evaluation(
    result: CompatibilityEvaluationResult,
    future_graph: FutureMetadataGraph,
    propagation: DependencyPropagationResult,
) -> None:
    issues: list[str] = []

    def require(condition: bool, message: str) -> None:
        if not condition:
            issues.append(message)

    require(
        result.future_graph_fingerprint == future_graph.semantic_fingerprint,
        "Future Graph fingerprint mismatch",
    )
    require(
        result.dependency_propagation_fingerprint
        == propagation.semantic_fingerprint,
        "Dependency propagation fingerprint mismatch",
    )
    require(
        result.source_change.current_field == _CURRENT_SOURCE
        and result.source_change.candidate_field == _CANDIDATE_SOURCE,
        "Source change identity mismatch",
    )
    graph_relationships = {
        item.relationship_id: item
        for item in future_graph.relationship_registry
    }
    propagation_relationships = {
        item.relationship_id: item
        for item in propagation.relationship_exposure_registry
    }
    evaluation_relationships = {
        item.relationship_id: item
        for item in result.relationship_evaluations
    }
    require(
        set(evaluation_relationships)
        == set(propagation_relationships)
        == set(graph_relationships),
        "Relationship evaluation scope mismatch",
    )
    mapping_groups = {
        item.group_id: item
        for item in future_graph.mapping_group_registry
    }
    for relationship_id, evaluation in evaluation_relationships.items():
        graph_record = graph_relationships[relationship_id]
        propagation_record = propagation_relationships[relationship_id]
        groups = tuple(
            mapping_groups[value]
            for value in graph_record.current_mapping_group_ids
            if value in mapping_groups
        )
        transform_operations = tuple(
            sorted(
                set(graph_record.current_transform_operations)
                | {
                    item.current_transform_operation
                    for item in groups
                    if item.current_transform_operation is not None
                }
            )
        )
        queries = tuple(
            sorted(
                {
                    item.current_query
                    for item in groups
                    if item.current_query is not None
                }
            )
        )
        decision = evaluate_field_rename_evidence(
            RenameCompatibilityEvidence(
                current_upstream=graph_record.current_upstream,
                current_downstream=graph_record.current_downstream,
                candidate_upstream=graph_record.upstream,
                candidate_downstream=graph_record.downstream,
                transform_operations=transform_operations,
                queries=queries,
                explicit_rename_behavior=None,
            )
        )
        require(
            evaluation.upstream_field == graph_record.upstream
            and evaluation.downstream_field == graph_record.downstream,
            f"Relationship endpoint mismatch: {relationship_id}",
        )
        require(
            evaluation.structural_state == graph_record.relationship_state
            and evaluation.exposure_state
            == propagation_record.exposure_state,
            f"Relationship state mismatch: {relationship_id}",
        )
        require(
            evaluation.evaluation_state
            is CompatibilityEvaluationState.EVALUATED,
            f"Relationship not evaluated: {relationship_id}",
        )
        require(
            all(value in mapping_groups for value in evaluation.mapping_group_ids),
            f"Dangling mapping-group provenance: {relationship_id}",
        )
        require(
            evaluation.lineage_confidence_provenance
            == graph_record.current_confidence_scores,
            f"Lineage confidence provenance changed: {relationship_id}",
        )
        require(
            evaluation.transform_operations == transform_operations
            and evaluation.query_evidence == queries,
            f"Relationship evidence changed: {relationship_id}",
        )
        require(
            evaluation.compatibility_state
            is decision.compatibility_state
            and evaluation.evidence_strength is decision.evidence_strength
            and evaluation.reason_code is decision.reason_code
            and evaluation.explanation == decision.explanation,
            f"Relationship compatibility decision mismatch: {relationship_id}",
        )
    propagation_paths = {
        item.path_id: item for item in propagation.path_registry
    }
    evaluation_paths = {
        item.path_id: item for item in result.path_evaluations
    }
    require(
        set(evaluation_paths) == set(propagation_paths),
        "Path evaluation scope mismatch",
    )
    for path_id, evaluation in evaluation_paths.items():
        source = propagation_paths[path_id]
        require(
            evaluation.target_field == source.target_field
            and evaluation.depth == source.depth
            and evaluation.relationship_ids == source.relationship_ids,
            f"Path identity mismatch: {path_id}",
        )
        edge_states = tuple(
            evaluation_relationships[value].compatibility_state
            for value in source.relationship_ids
        )
        decision = roll_up_path_compatibility(edge_states)
        expected_blocking = tuple(
            relationship_id
            for relationship_id, state in zip(
                source.relationship_ids,
                edge_states,
            )
            if state is CompatibilityState.INCOMPATIBLE
        )
        expected_uncertain = tuple(
            relationship_id
            for relationship_id, state in zip(
                source.relationship_ids,
                edge_states,
            )
            if state
            in {
                CompatibilityState.UNKNOWN,
                CompatibilityState.CONDITIONALLY_COMPATIBLE,
            }
        )
        require(
            evaluation.edge_compatibility_states == edge_states
            and evaluation.compatibility_state
            is decision.compatibility_state,
            f"Path compatibility mismatch: {path_id}",
        )
        require(
            evaluation.reason_codes == (decision.reason_code,)
            and evaluation.blocking_relationship_ids == expected_blocking
            and evaluation.uncertain_relationship_ids == expected_uncertain,
            f"Path decision evidence mismatch: {path_id}",
        )
    propagation_fields = {
        item.field_key: item
        for item in propagation.field_exposure_registry
        if item.field_key != propagation.source_candidate_field
    }
    evaluation_fields = {
        item.field_key: item for item in result.field_evaluations
    }
    require(
        set(evaluation_fields) == set(propagation_fields),
        "Field evaluation scope mismatch",
    )
    for field_key, evaluation in evaluation_fields.items():
        source = propagation_fields[field_key]
        require(
            evaluation.exposure_state == source.exposure_state
            and evaluation.minimum_depth == source.minimum_depth
            and evaluation.supporting_path_ids == source.supporting_path_ids,
            f"Field exposure evidence changed: {field_key.text}",
        )
        states = tuple(
            evaluation_paths[value].compatibility_state
            for value in source.supporting_path_ids
        )
        decision = roll_up_field_compatibility(states)
        incoming_states = tuple(
            evaluation_relationships[value].compatibility_state
            for value in source.incoming_exposed_relationship_ids
        )
        require(
            evaluation.path_compatibility_states == states
            and evaluation.compatibility_state
            is decision.compatibility_state,
            f"Field compatibility mismatch: {field_key.text}",
        )
        require(
            evaluation.incoming_relationship_ids
            == source.incoming_exposed_relationship_ids
            and evaluation.incoming_relationship_states == incoming_states
            and evaluation.evidence_strength is decision.evidence_strength
            and evaluation.reason_codes == (decision.reason_code,),
            f"Field decision evidence mismatch: {field_key.text}",
        )
    expected_dataset_urns = {
        item.field_key.dataset_urn for item in result.field_evaluations
    }
    require(
        {item.dataset_urn for item in result.dataset_summaries}
        == expected_dataset_urns,
        "Dataset summary scope mismatch",
    )
    for item in result.dataset_summaries:
        fields = tuple(
            value
            for value in result.field_evaluations
            if value.field_key.dataset_urn == item.dataset_urn
        )
        counts = _compatibility_counts(
            value.compatibility_state for value in fields
        )
        states = {value.compatibility_state for value in fields}
        if len(states) == 1:
            expected_state = next(iter(states))
            expected_reasons = tuple(
                sorted(
                    {
                        reason
                        for field in fields
                        for reason in field.reason_codes
                    },
                    key=lambda value: value.value,
                )
            )
        else:
            expected_state = CompatibilityState.UNKNOWN
            expected_reasons = (
                CompatibilityReasonCode.INSUFFICIENT_EVIDENCE,
            )
        require(
            (
                item.compatible_exposed_fields,
                item.incompatible_exposed_fields,
                item.conditionally_compatible_exposed_fields,
                item.unknown_exposed_fields,
            )
            == (
                counts.compatible,
                counts.incompatible,
                counts.conditionally_compatible,
                counts.unknown,
            ),
            f"Dataset compatibility counts mismatch: {item.dataset_urn}",
        )
        require(
            item.compatibility_state is expected_state
            and item.reason_codes == expected_reasons
            and set(item.exposed_field_keys)
            == {value.field_key for value in fields},
            f"Dataset compatibility decision mismatch: {item.dataset_urn}",
        )
    require(
        result.aggregate.relationship_counts
        == _compatibility_counts(
            item.compatibility_state
            for item in result.relationship_evaluations
        ),
        "Relationship aggregate mismatch",
    )
    require(
        result.aggregate.path_counts
        == _compatibility_counts(
            item.compatibility_state for item in result.path_evaluations
        ),
        "Path aggregate mismatch",
    )
    require(
        result.aggregate.field_counts
        == _compatibility_counts(
            item.compatibility_state for item in result.field_evaluations
        ),
        "Field aggregate mismatch",
    )
    require(
        result.aggregate.dataset_counts
        == _compatibility_counts(
            item.compatibility_state for item in result.dataset_summaries
        ),
        "Dataset aggregate mismatch",
    )
    require(
        result.aggregate.relationship_evidence_strength
        == _evidence_strength_counts(
            item.evidence_strength
            for item in result.relationship_evaluations
        ),
        "Relationship evidence-strength aggregate mismatch",
    )
    require(
        len(result.relationship_evaluations) == 27
        and len(result.path_evaluations) == 48
        and len(result.field_evaluations) == 25
        and len(result.dataset_summaries) == 20,
        "Canonical compatibility acceptance scope mismatch",
    )
    require(
        all(
            item.field_key.field_path != "order_amount"
            for item in result.field_evaluations
        ),
        "A downstream field was renamed",
    )
    forbidden_public_names = {
        "impact",
        "severity",
        "risk",
        "criticality",
        "repair",
        "priority",
    }
    public_keys = set(result.to_dict())
    require(
        public_keys.isdisjoint(forbidden_public_names),
        "Impact, risk, or repair semantics entered the public model",
    )
    require(
        all(item.unchanged for item in result.input_artifact_hashes),
        "An authoritative input hash changed",
    )
    known_provenance = {
        item.provenance_id for item in future_graph.provenance_registry
    }
    provenance_references = (
        tuple(
            value
            for item in result.relationship_evaluations
            for value in (
                item.current_provenance_ids
                + item.counterfactual_provenance_ids
            )
        )
        + tuple(
            value
            for item in result.path_evaluations
            for value in (
                item.current_provenance_ids
                + item.counterfactual_provenance_ids
            )
        )
        + tuple(
            value
            for item in result.field_evaluations
            for value in (
                item.current_provenance_ids
                + item.counterfactual_provenance_ids
            )
        )
    )
    require(
        all(value in known_provenance for value in provenance_references),
        "A compatibility provenance reference is dangling",
    )
    if issues:
        raise CompatibilityValidationError("; ".join(issues))


def _require_entry_preconditions(
    snapshot: CurrentMetadataSnapshot,
    proposal: ChangeProposal,
    validation: ProposalValidationResult,
    contract: ChangeSemanticContract,
    certification: Phase2CertificationResult,
    source_state: CounterfactualSourceState,
    future_graph: FutureMetadataGraph,
    propagation: DependencyPropagationResult,
    input_artifact_hashes: tuple[InputArtifactHash, ...],
) -> None:
    if snapshot.validation_result.state is not SnapshotValidationState.VALID:
        raise CompatibilityEntryPreconditionError(
            "Phase 1 is not certified."
        )
    if (
        certification.certification_state
        is not Phase2CertificationState.CERTIFIED
        or validation.validation_state is not ProposalValidationState.VALID
    ):
        raise CompatibilityEntryPreconditionError(
            "Phase 2 is not certified."
        )
    if (
        source_state.state_classification
        is not SourceStateClassification.COUNTERFACTUAL
        or source_state_semantic_fingerprint(source_state)
        != source_state.semantic_fingerprint
    ):
        raise CompatibilityEntryPreconditionError("Phase 3.1 is invalid.")
    if (
        future_graph.validation_state
        is not FutureGraphValidationState.VALID
        or future_graph_semantic_fingerprint(future_graph)
        != future_graph.semantic_fingerprint
    ):
        raise CompatibilityEntryPreconditionError("Phase 3.2 is invalid.")
    if (
        propagation.validation_state is not PropagationValidationState.VALID
        or propagation_semantic_fingerprint(propagation)
        != propagation.semantic_fingerprint
    ):
        raise CompatibilityEntryPreconditionError("Phase 3.3 is invalid.")
    try:
        validate_counterfactual_source_state(
            source_state,
            snapshot,
            proposal,
            validation,
            contract,
            certification,
        )
        validate_future_metadata_graph(
            future_graph,
            snapshot,
            proposal,
            validation,
            contract,
            certification,
            source_state,
        )
        validate_dependency_propagation(
            propagation,
            future_graph,
        )
    except ValueError as exc:
        raise CompatibilityEntryPreconditionError(
            "The authoritative artifact chain is malformed."
        ) from exc
    if (
        proposal.demonstration_id != CANONICAL_DEMONSTRATION_ID
        or source_state.demonstration_id != CANONICAL_DEMONSTRATION_ID
        or future_graph.demonstration_id != CANONICAL_DEMONSTRATION_ID
        or propagation.demonstration_id != CANONICAL_DEMONSTRATION_ID
    ):
        raise CompatibilityEntryPreconditionError(
            "Demonstration identity mismatch."
        )
    if proposal.change_type is not ChangeType.FIELD_RENAME:
        raise CompatibilityEntryPreconditionError(
            "Operation must be FIELD_RENAME."
        )
    if (
        propagation.future_graph_fingerprint
        != future_graph.semantic_fingerprint
        or future_graph.current_snapshot_fingerprint
        != snapshot.semantic_fingerprint
        or future_graph.proposal_fingerprint
        != proposal.semantic_fingerprint
        or future_graph.validation_fingerprint
        != validation.semantic_fingerprint
        or future_graph.semantic_contract_fingerprint
        != contract.semantic_fingerprint
        or future_graph.phase_2_certification_fingerprint
        != certification.semantic_fingerprint
        or future_graph.counterfactual_source_state_fingerprint
        != source_state.semantic_fingerprint
    ):
        raise CompatibilityEntryPreconditionError(
            "Semantic artifact cross-reference mismatch."
        )
    source = tuple(
        item
        for item in future_graph.field_registry
        if item.key == _CANDIDATE_SOURCE
    )
    if (
        len(source) != 1
        or source[0].state is not GraphObjectState.COUNTERFACTUAL_CHANGED
        or propagation.source_candidate_field != _CANDIDATE_SOURCE
    ):
        raise CompatibilityEntryPreconditionError(
            "Candidate source identity mismatch."
        )
    mapping_group_ids = {
        item.group_id for item in future_graph.mapping_group_registry
    }
    if any(
        value not in mapping_group_ids
        for item in future_graph.relationship_registry
        for value in item.current_mapping_group_ids
    ):
        raise CompatibilityEntryPreconditionError(
            "A structural relationship has dangling mapping provenance."
        )
    expected_artifacts = {
        "current_metadata_snapshot.json",
        "change_proposal.json",
        "change_proposal_validation.json",
        "change_semantic_contract.json",
        "phase_2_certification.json",
        "counterfactual_source_state.json",
        "future_metadata_graph.json",
        "dependency_propagation.json",
    }
    if (
        {item.artifact_name for item in input_artifact_hashes}
        != expected_artifacts
        or any(not item.unchanged for item in input_artifact_hashes)
    ):
        raise CompatibilityEntryPreconditionError(
            "All eight authoritative artifact hashes must be unchanged."
        )


def _compatibility_counts(
    values: Iterable[CompatibilityState],
) -> CompatibilityCounts:
    counts = Counter(values)
    return CompatibilityCounts(
        compatible=counts[CompatibilityState.COMPATIBLE],
        incompatible=counts[CompatibilityState.INCOMPATIBLE],
        conditionally_compatible=counts[
            CompatibilityState.CONDITIONALLY_COMPATIBLE
        ],
        unknown=counts[CompatibilityState.UNKNOWN],
    )


def _evidence_strength_counts(
    values: Iterable[EvidenceStrength],
) -> EvidenceStrengthCounts:
    counts = Counter(values)
    return EvidenceStrengthCounts(
        explicit=counts[EvidenceStrength.EXPLICIT],
        derived=counts[EvidenceStrength.DERIVED],
        insufficient=counts[EvidenceStrength.INSUFFICIENT],
    )


def _ordered_union(*values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({item for group in values for item in group}))


def _timestamp(clock: Clock | None) -> str:
    value = (clock or (lambda: datetime.now(timezone.utc)))()
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()
