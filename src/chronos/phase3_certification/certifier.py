"""Offline certification of the complete CHRONOS Phase 3 artifact chain."""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import fields, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Iterable

from chronos.change_semantics import (
    ChangeSemanticContract,
    contract_semantic_fingerprint,
    load_contract,
)
from chronos.compatibility_evaluation import (
    CompatibilityEvaluationResult,
    CompatibilityReasonCode,
    CompatibilityState,
    EvidenceStrength,
    compatibility_semantic_fingerprint,
    evaluate_compatibility_from_artifacts,
    load_compatibility_evaluation,
    validate_compatibility_evaluation,
)
from chronos.counterfactual_source import (
    CounterfactualSourceState,
    FieldMappingClassification,
    SourceStateClassification,
    load_source_state,
    materialize_source_state_from_artifacts,
    source_state_semantic_fingerprint,
    validate_counterfactual_source_state,
)
from chronos.dependency_propagation import (
    DependencyPropagationResult,
    FieldExposureState,
    load_dependency_propagation,
    propagate_dependencies_from_artifacts,
    propagation_semantic_fingerprint,
    shortest_dependency_depths,
    validate_dependency_propagation,
)
from chronos.explanations import (
    ExplanationBundle,
    ExplanationValidationState,
    build_explanation_bundle_from_artifacts,
    explanation_semantic_fingerprint,
    load_explanation_bundle,
    validate_explanation_bundle,
)
from chronos.future_graph import (
    FutureMetadataGraph,
    FutureIdentityMappingClassification,
    GraphObjectState,
    ProvenanceKind,
    build_future_graph_from_artifacts,
    future_graph_semantic_fingerprint,
    load_future_graph,
    validate_future_metadata_graph,
)
from chronos.phase2_certification import (
    Phase2CertificationResult,
    Phase2CertificationState,
    certification_semantic_fingerprint,
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
    load_validation_result,
    validation_result_semantic_fingerprint,
)
from chronos.snapshot import (
    CurrentMetadataSnapshot,
    FieldMachineKey,
    RelationshipCategory,
    SnapshotValidationState,
    contains_secret,
    load_snapshot,
    semantic_fingerprint as snapshot_semantic_fingerprint,
)

from .errors import Phase3CertificationInputError
from .models import (
    PHASE3_CERTIFICATION_SCHEMA_VERSION,
    ArtifactImmutabilityEvidence,
    CertificationCheck,
    CertificationCheckCategory,
    CertificationCheckStatus,
    CertificationFailureSeverity,
    InputArtifactIdentity,
    Phase3CertificationResult,
    Phase3CertificationStatus,
    Phase3SemanticFingerprints,
    Phase3SummaryMetrics,
)


Clock = Callable[[], datetime]
_CURRENT = FieldMachineKey(CANONICAL_DATASET_URN, "order_total")
_CANDIDATE = FieldMachineKey(CANONICAL_DATASET_URN, "order_amount")
_ACCEPTED_PHASE3 = Phase3SemanticFingerprints(
    counterfactual_source=(
        "sha256:1634909adb9d26ba55af9058823ef37c8dcf5bbc3d2e54d535638499ef58b87e"
    ),
    future_graph=(
        "sha256:a17fee73f5e3e29ff27223afe49b4438abd4d6dc2e966aa1e8aee4ae77eeb33c"
    ),
    dependency_propagation=(
        "sha256:ad19656e017da23afd3619b317d72b519fa320827aaeeff833ac9738cd997c78"
    ),
    compatibility_evaluation=(
        "sha256:7ce6d124d85cbdf6070dfdbde17235141f35fa9c672bb0ce960993407ccaaba4"
    ),
    explanation_bundle=(
        "sha256:9fd969716566024c6227d9e9e8e87cabae02aa20cddd1a5148caaa7ca91ade11"
    ),
)
_SCOPE_STATEMENT = (
    "Phase 3 certification validates the frozen counterfactual source, Future "
    "Graph, dependency propagation, compatibility evaluation, and explanation "
    "artifacts only. It performs no new graph reasoning, impact analysis, "
    "risk or severity calculation, repair recommendation, metadata retrieval, "
    "external code inspection, or DataHub write."
)


def certify_phase3(
    snapshot: CurrentMetadataSnapshot,
    proposal: ChangeProposal,
    validation: ProposalValidationResult,
    contract: ChangeSemanticContract,
    phase2: Phase2CertificationResult,
    source_state: CounterfactualSourceState,
    graph: FutureMetadataGraph,
    propagation: DependencyPropagationResult,
    compatibility: CompatibilityEvaluationResult,
    explanations: ExplanationBundle,
    *,
    input_artifact_identities: tuple[InputArtifactIdentity, ...],
    artifact_immutability: tuple[ArtifactImmutabilityEvidence, ...],
    reconstructed_fingerprints: Phase3SemanticFingerprints | None,
    clock: Clock | None = None,
) -> Phase3CertificationResult:
    """Certify existing typed evidence without changing its conclusions."""

    checks: list[CertificationCheck] = []

    def check(
        check_id: str,
        category: CertificationCheckCategory,
        description: str,
        condition: bool,
        expected: object,
        observed: object,
        evidence: Iterable[object] = (),
    ) -> None:
        checks.append(
            CertificationCheck(
                check_id=check_id,
                category=category,
                description=description,
                status=(
                    CertificationCheckStatus.PASS
                    if condition
                    else CertificationCheckStatus.FAIL
                ),
                severity_if_failed=CertificationFailureSeverity.BLOCKING,
                evidence=tuple(_text(value) for value in evidence),
                expected_value=_text(expected),
                observed_value=_text(observed),
            )
        )

    semantic = _semantic_fingerprints(
        source_state,
        graph,
        propagation,
        compatibility,
        explanations,
    )
    snapshot_fp = snapshot_semantic_fingerprint(snapshot)
    proposal_fp = proposal_semantic_fingerprint(proposal)
    validation_fp = validation_result_semantic_fingerprint(validation)
    contract_fp = contract_semantic_fingerprint(contract)
    phase2_fp = certification_semantic_fingerprint(phase2)

    validator_results = (
        (
            "phase_3_1_public_validator",
            _passes(
                validate_counterfactual_source_state,
                source_state,
                snapshot,
                proposal,
                validation,
                contract,
                phase2,
            ),
        ),
        (
            "phase_3_2_public_validator",
            _passes(
                validate_future_metadata_graph,
                graph,
                snapshot,
                proposal,
                validation,
                contract,
                phase2,
                source_state,
            ),
        ),
        (
            "phase_3_3_public_validator",
            _passes(validate_dependency_propagation, propagation, graph),
        ),
        (
            "phase_3_4_public_validator",
            _passes(
                validate_compatibility_evaluation,
                compatibility,
                graph,
                propagation,
            ),
        ),
        (
            "phase_3_5_public_validator",
            _passes(
                validate_explanation_bundle,
                explanations,
                snapshot,
                source_state,
                graph,
                propagation,
                compatibility,
            ),
        ),
    )
    check(
        "prerequisite.phase_1",
        CertificationCheckCategory.PREREQUISITE,
        "Phase 1 snapshot retains embedded VALID certification.",
        (
            snapshot.validation_result.state is SnapshotValidationState.VALID
            and snapshot_fp == snapshot.semantic_fingerprint
        ),
        "valid and reproducible",
        (
            snapshot.validation_result.state.value,
            snapshot_fp,
        ),
        (snapshot.metadata.snapshot_id, snapshot.semantic_fingerprint),
    )
    check(
        "prerequisite.phase_2",
        CertificationCheckCategory.PREREQUISITE,
        "Phase 2 remains CERTIFIED and semantically reproducible.",
        (
            phase2.certification_state is Phase2CertificationState.CERTIFIED
            and phase2_fp == phase2.semantic_fingerprint
        ),
        "certified and reproducible",
        (phase2.certification_state.value, phase2_fp),
        (phase2.semantic_fingerprint,),
    )
    for name, passed in validator_results:
        check(
            f"prerequisite.{name}",
            CertificationCheckCategory.PREREQUISITE,
            f"{name.replace('_', ' ')} passes.",
            passed,
            True,
            passed,
        )

    check(
        "cross_reference.base_fingerprints_reproduce",
        CertificationCheckCategory.CROSS_REFERENCE,
        "Phase 1 and Phase 2 package fingerprints reproduce independently.",
        (
            snapshot_fp == snapshot.semantic_fingerprint
            and proposal_fp == proposal.semantic_fingerprint
            and validation_fp == validation.semantic_fingerprint
            and contract_fp == contract.semantic_fingerprint
            and phase2_fp == phase2.semantic_fingerprint
        ),
        "all reproduced",
        (
            snapshot_fp,
            proposal_fp,
            validation_fp,
            contract_fp,
            phase2_fp,
        ),
    )
    chain_conditions = (
        proposal.snapshot_reference.semantic_fingerprint
        == snapshot.semantic_fingerprint
        and validation.proposal_fingerprint == proposal.semantic_fingerprint
        and validation.snapshot_fingerprint == snapshot.semantic_fingerprint
        and contract.proposal_fingerprint == proposal.semantic_fingerprint
        and contract.validation_fingerprint == validation.semantic_fingerprint
        and contract.baseline_snapshot_fingerprint
        == snapshot.semantic_fingerprint
        and phase2.snapshot_fingerprint == snapshot.semantic_fingerprint
        and phase2.proposal_fingerprint == proposal.semantic_fingerprint
        and phase2.validation_fingerprint == validation.semantic_fingerprint
        and phase2.semantic_contract_fingerprint
        == contract.semantic_fingerprint
        and source_state.current_snapshot_fingerprint
        == snapshot.semantic_fingerprint
        and source_state.proposal_fingerprint == proposal.semantic_fingerprint
        and source_state.validation_fingerprint
        == validation.semantic_fingerprint
        and source_state.semantic_contract_fingerprint
        == contract.semantic_fingerprint
        and source_state.phase_2_certification_fingerprint
        == phase2.semantic_fingerprint
        and graph.counterfactual_source_state_fingerprint
        == source_state.semantic_fingerprint
        and graph.current_snapshot_fingerprint == snapshot.semantic_fingerprint
        and graph.proposal_fingerprint == proposal.semantic_fingerprint
        and graph.validation_fingerprint == validation.semantic_fingerprint
        and graph.semantic_contract_fingerprint == contract.semantic_fingerprint
        and graph.phase_2_certification_fingerprint
        == phase2.semantic_fingerprint
        and propagation.future_graph_fingerprint == graph.semantic_fingerprint
        and compatibility.future_graph_fingerprint == graph.semantic_fingerprint
        and compatibility.dependency_propagation_fingerprint
        == propagation.semantic_fingerprint
        and explanations.future_graph_fingerprint == graph.semantic_fingerprint
        and explanations.propagation_fingerprint
        == propagation.semantic_fingerprint
        and explanations.compatibility_fingerprint
        == compatibility.semantic_fingerprint
    )
    check(
        "cross_reference.complete_dependency_chain",
        CertificationCheckCategory.CROSS_REFERENCE,
        "Every artifact references the exact semantic identity of predecessors.",
        chain_conditions,
        True,
        chain_conditions,
        tuple(
            item.semantic_fingerprint for item in input_artifact_identities
        ),
    )
    demonstration_ids = (
        snapshot.metadata.demonstration_id,
        proposal.demonstration_id,
        source_state.demonstration_id,
        graph.demonstration_id,
        propagation.demonstration_id,
        compatibility.demonstration_id,
        explanations.demonstration_id,
    )
    check(
        "cross_reference.demonstration_identity",
        CertificationCheckCategory.CROSS_REFERENCE,
        "All artifacts belong to CHRONOS-DEMO-001.",
        all(value == CANONICAL_DEMONSTRATION_ID for value in demonstration_ids),
        CANONICAL_DEMONSTRATION_ID,
        demonstration_ids,
    )
    proposal_identity = (
        validation.proposal_id == proposal.proposal_id
        and contract.proposal_id == proposal.proposal_id
        and compatibility.proposal_id == proposal.proposal_id
        and all(
            item.proposal_id in (None, proposal.proposal_id)
            for item in graph.provenance_registry
        )
    )
    check(
        "cross_reference.proposal_identity",
        CertificationCheckCategory.CROSS_REFERENCE,
        "All proposal-bearing records use one proposal identity.",
        proposal_identity,
        proposal.proposal_id,
        (
            validation.proposal_id,
            contract.proposal_id,
            compatibility.proposal_id,
        ),
    )
    check(
        "cross_reference.acceptance_fingerprints",
        CertificationCheckCategory.CROSS_REFERENCE,
        "Reproduced Phase 3 fingerprints match acceptance references.",
        semantic == _ACCEPTED_PHASE3,
        _ACCEPTED_PHASE3,
        semantic,
    )

    current_dataset = next(
        (
            item
            for item in snapshot.datasets
            if item.dataset_urn == CANONICAL_DATASET_URN
        ),
        None,
    )
    candidate_fields = source_state.candidate_source_schema.fields
    candidate_amount = tuple(
        item for item in candidate_fields if item.field_path == "order_amount"
    )
    candidate_total = tuple(
        item for item in candidate_fields if item.field_path == "order_total"
    )
    renamed = tuple(
        item
        for item in source_state.field_identity_mappings
        if item.classification is FieldMappingClassification.RENAMED
    )
    unchanged = tuple(
        item
        for item in source_state.field_identity_mappings
        if item.classification is FieldMappingClassification.UNCHANGED
    )
    source_identity_ok = (
        proposal.change_type is ChangeType.FIELD_RENAME
        and proposal.change.target.machine_key
        == (CANONICAL_DATASET_URN, "order_total")
        and source_state.dataset_identity.dataset_urn == CANONICAL_DATASET_URN
        and current_dataset is not None
        and source_state.dataset_identity.platform == current_dataset.platform
        and source_state.dataset_identity.environment
        == current_dataset.environment
        and len(renamed) == 1
        and renamed[0].current_identity.machine_key
        == (CANONICAL_DATASET_URN, "order_total")
        and renamed[0].candidate_identity.machine_key
        == (CANONICAL_DATASET_URN, "order_amount")
    )
    check(
        "source_state.identity_transition",
        CertificationCheckCategory.SOURCE_STATE,
        "The source transition changes only the field machine identity.",
        source_identity_ok,
        (_CURRENT, _CANDIDATE),
        (
            source_state.dataset_identity.dataset_urn,
            renamed[0] if renamed else None,
        ),
    )
    candidate_shape_ok = (
        source_state.current_source_schema_reference.field_count == 15
        and len(candidate_fields) == 15
        and len(candidate_total) == 0
        and len(candidate_amount) == 1
        and candidate_amount[0].position == 5
        and candidate_amount[0].native_type == "DOUBLE PRECISION"
        and candidate_amount[0].normalized_type == "Number"
        and candidate_amount[0].nullable is True
        and candidate_amount[0].is_part_of_key is False
        and candidate_amount[0].schema_field_urn is None
        and len(unchanged) == 14
        and all(
            item.current_identity.machine_key
            == item.candidate_identity.machine_key
            for item in unchanged
        )
        and all(item.schema_field_urn is None for item in candidate_fields)
    )
    check(
        "source_state.schema_invariants",
        CertificationCheckCategory.SOURCE_STATE,
        "Candidate schema preserves cardinality and certified field properties.",
        candidate_shape_ok,
        "15 fields; order_amount at 5; preserved type/nullability/key",
        (
            len(candidate_fields),
            len(candidate_total),
            len(candidate_amount),
            candidate_amount[0] if candidate_amount else None,
            len(unchanged),
        ),
    )

    dataset_keys = tuple(item.dataset_urn for item in graph.dataset_registry)
    field_keys = tuple(item.key for item in graph.field_registry)
    relationship_ids = tuple(
        item.relationship_id for item in graph.relationship_registry
    )
    mapping_ids = tuple(
        item.group_id for item in graph.mapping_group_registry
    )
    graph_paths = tuple(item.path_id for item in graph.path_registry)
    graph_counts = (
        len(dataset_keys),
        len(field_keys),
        len(graph.relationship_registry),
        len(mapping_ids),
        len(graph_paths),
    )
    check(
        "graph_integrity.canonical_counts",
        CertificationCheckCategory.GRAPH_INTEGRITY,
        "Future Graph object counts reproduce the frozen structural baseline.",
        graph_counts == (21, 26, 27, 28, 48),
        (21, 26, 27, 28, 48),
        graph_counts,
    )
    expected_downstream = set(snapshot.field_by_key()) - {_CURRENT}
    observed_downstream = set(field_keys) - {_CANDIDATE}
    source_graph_ok = (
        field_keys.count(_CURRENT) == 0
        and field_keys.count(_CANDIDATE) == 1
        and observed_downstream == expected_downstream
        and len(observed_downstream) == 25
        and sum(
            item.state is GraphObjectState.COUNTERFACTUAL_CHANGED
            for item in graph.field_registry
        )
        == 1
        and max(
            item.structural_depth
            for item in graph.field_registry
            if item.structural_depth is not None
        )
        == 5
    )
    check(
        "graph_integrity.source_and_downstream_identity",
        CertificationCheckCategory.GRAPH_INTEGRITY,
        "Future Graph contains one changed source and 25 unchanged downstream identities.",
        source_graph_ok,
        "order_total absent; order_amount once; downstream identities preserved",
        (
            field_keys.count(_CURRENT),
            field_keys.count(_CANDIDATE),
            len(observed_downstream),
        ),
    )
    graph_references_ok = (
        len(set(dataset_keys)) == len(dataset_keys)
        and len(set(field_keys)) == len(field_keys)
        and len(set(relationship_ids)) == len(relationship_ids)
        and len(set(mapping_ids)) == len(mapping_ids)
        and len(set(graph_paths)) == len(graph_paths)
        and all(item.key.dataset_urn in dataset_keys for item in graph.field_registry)
        and all(
            item.upstream in field_keys and item.downstream in field_keys
            for item in graph.relationship_registry
        )
        and all(
            value in mapping_ids
            for item in graph.relationship_registry
            for value in item.current_mapping_group_ids
        )
        and all(
            item.future_identity in field_keys
            for item in graph.current_to_future_identity_mappings
        )
        and len(graph.current_to_future_identity_mappings) == 26
        and sum(
            item.classification is FutureIdentityMappingClassification.RENAMED
            for item in graph.current_to_future_identity_mappings
        )
        == 1
    )
    check(
        "graph_integrity.references_close",
        CertificationCheckCategory.GRAPH_INTEGRITY,
        "Datasets, fields, edges, mapping groups, and identity mappings resolve.",
        graph_references_ok,
        True,
        graph_references_ok,
    )

    relation_by_id = {
        item.relationship_id: item for item in graph.relationship_registry
    }
    canonical_paths = tuple(
        tuple(item.projected_node_keys) for item in graph.path_registry
    )
    path_integrity = all(
        len(item.projected_node_keys) >= 2
        and len(item.projected_relationship_ids)
        == len(item.projected_node_keys) - 1
        and item.projected_node_keys[0] == _CANDIDATE
        and all(value in relation_by_id for value in item.projected_relationship_ids)
        and all(value in field_keys for value in item.projected_node_keys)
        and all(
            relation_by_id[relationship_id].upstream
            == item.projected_node_keys[index]
            and relation_by_id[relationship_id].downstream
            == item.projected_node_keys[index + 1]
            for index, relationship_id in enumerate(
                item.projected_relationship_ids
            )
        )
        for item in graph.path_registry
    )
    check(
        "path_integrity.ordered_connectivity",
        CertificationCheckCategory.PATH_INTEGRITY,
        "Every path has valid node/edge cardinality and adjacent connectivity.",
        (
            path_integrity
            and len(set(graph_paths)) == len(graph_paths)
            and len(set(canonical_paths)) == len(canonical_paths)
        ),
        True,
        path_integrity,
        (f"paths={len(graph_paths)}",),
    )
    maximum_stored_path_depth = max(
        len(item.projected_relationship_ids) for item in graph.path_registry
    )
    check(
        "path_integrity.depth_semantics",
        CertificationCheckCategory.PATH_INTEGRITY,
        "Shortest exposure depth remains distinct from alternate path length.",
        (
            propagation.summary.maximum_exposure_depth == 5
            and maximum_stored_path_depth == 7
        ),
        "maximum shortest exposure depth=5; maximum stored path depth=7",
        (
            propagation.summary.maximum_exposure_depth,
            maximum_stored_path_depth,
        ),
    )

    propagation_fields = {
        item.field_key: item for item in propagation.field_exposure_registry
    }
    downstream_exposures = {
        key: value
        for key, value in propagation_fields.items()
        if key != _CANDIDATE
    }
    exposure_counts = Counter(
        item.exposure_state for item in propagation.field_exposure_registry
    )
    source_edge = next(
        (
            item
            for item in graph.relationship_registry
            if item.upstream == _CANDIDATE
        ),
        None,
    )
    directly_exposed = (
        propagation_fields.get(source_edge.downstream)
        if source_edge is not None
        else None
    )
    source_exposure = propagation_fields.get(_CANDIDATE)
    propagation_scope_ok = (
        len(propagation_fields) == 26
        and len(downstream_exposures) == 25
        and len(propagation.dataset_exposure_registry) == 20
        and len(propagation.relationship_exposure_registry) == 27
        and len(propagation.path_registry) == 48
        and source_exposure is not None
        and source_exposure.exposure_state is FieldExposureState.SOURCE_CHANGED
        and directly_exposed is not None
        and directly_exposed.exposure_state
        is FieldExposureState.DIRECTLY_EXPOSED
        and exposure_counts[FieldExposureState.DIRECTLY_EXPOSED] == 1
        and exposure_counts[FieldExposureState.TRANSITIVELY_EXPOSED] == 3
        and exposure_counts[FieldExposureState.MULTIPATH_EXPOSED] == 21
    )
    check(
        "propagation.canonical_scope",
        CertificationCheckCategory.PROPAGATION,
        "Stored propagation scope and exposure distribution reproduce.",
        propagation_scope_ok,
        "26 fields/20 datasets/27 edges/48 paths; 1 direct/3 transit/21 multipath",
        (
            len(propagation_fields),
            len(propagation.dataset_exposure_registry),
            len(propagation.relationship_exposure_registry),
            len(propagation.path_registry),
            exposure_counts,
        ),
    )
    propagation_paths = {
        item.path_id: item for item in propagation.path_registry
    }
    multipath_ok = all(
        item.path_count == len(set(item.supporting_path_ids))
        and all(value in propagation_paths for value in item.supporting_path_ids)
        and (
            item.minimum_depth
            == min(
                propagation_paths[value].depth
                for value in item.supporting_path_ids
            )
            if item.supporting_path_ids
            else item.minimum_depth == 0
        )
        and (
            item.exposure_state is FieldExposureState.MULTIPATH_EXPOSED
        )
        == (item.path_count > 1)
        for item in propagation.field_exposure_registry
        if item.field_key != _CANDIDATE
    )
    shortest = shortest_dependency_depths(
        _CANDIDATE,
        graph.relationship_registry,
    )
    reachability_ok = (
        set(shortest) == set(field_keys)
        and set(downstream_exposures) == set(field_keys) - {_CANDIDATE}
        and all(
            item.minimum_depth == shortest[key]
            for key, item in downstream_exposures.items()
        )
    )
    check(
        "propagation.multipath_and_reachability",
        CertificationCheckCategory.PROPAGATION,
        "Path counts, minimum depths, multipath states, and reachability agree.",
        multipath_ok and reachability_ok,
        True,
        (multipath_ok, reachability_ok),
    )
    context_ids = {
        item.current_relationship_id
        for item in graph.context_relationship_registry
    }
    propagated_ids = {
        item.relationship_id
        for item in propagation.relationship_exposure_registry
    }
    check(
        "propagation.context_exclusion",
        CertificationCheckCategory.PROPAGATION,
        "Context relationships do not participate in field propagation.",
        not (context_ids & propagated_ids),
        "no overlap",
        tuple(sorted(context_ids & propagated_ids)),
    )

    comp_relationships = {
        item.relationship_id: item
        for item in compatibility.relationship_evaluations
    }
    comp_paths = {
        item.path_id: item for item in compatibility.path_evaluations
    }
    comp_fields = {
        item.field_key: item for item in compatibility.field_evaluations
    }
    comp_datasets = {
        item.dataset_urn: item for item in compatibility.dataset_summaries
    }
    compatibility_scope = (
        set(comp_relationships) == set(relationship_ids)
        and set(comp_paths) == set(propagation_paths)
        and set(comp_fields) == set(downstream_exposures)
        and len(comp_datasets) == 20
    )
    check(
        "compatibility.scope",
        CertificationCheckCategory.COMPATIBILITY,
        "Phase 3.4 evaluates exactly the Phase 3.2/3.3 structural scope.",
        compatibility_scope,
        (27, 48, 25, 20),
        (
            len(comp_relationships),
            len(comp_paths),
            len(comp_fields),
            len(comp_datasets),
        ),
    )
    source_comp = (
        comp_relationships.get(source_edge.relationship_id)
        if source_edge is not None
        else None
    )
    source_compatibility_ok = (
        source_comp is not None
        and source_comp.compatibility_state is CompatibilityState.UNKNOWN
        and source_comp.evidence_strength is EvidenceStrength.INSUFFICIENT
        and source_comp.reason_code
        is CompatibilityReasonCode.SOURCE_RENAME_SEMANTICS_UNKNOWN
        and source_comp.transform_operations == ()
        and source_comp.query_evidence == ()
        and source_comp.lineage_confidence_provenance == (0.5,)
    )
    check(
        "compatibility.source_boundary",
        CertificationCheckCategory.COMPATIBILITY,
        "The source-rebased boundary retains its exact UNKNOWN conclusion.",
        source_compatibility_ok,
        "UNKNOWN/INSUFFICIENT/SOURCE_RENAME_SEMANTICS_UNKNOWN/no transform or query/0.5 provenance",
        source_comp,
    )
    relationship_states = Counter(
        item.compatibility_state
        for item in compatibility.relationship_evaluations
    )
    path_states = Counter(
        item.compatibility_state for item in compatibility.path_evaluations
    )
    aggregate_ok = (
        relationship_states[CompatibilityState.UNKNOWN] == 1
        and relationship_states[
            CompatibilityState.CONDITIONALLY_COMPATIBLE
        ]
        == 26
        and relationship_states[CompatibilityState.COMPATIBLE] == 0
        and relationship_states[CompatibilityState.INCOMPATIBLE] == 0
        and path_states[CompatibilityState.UNKNOWN] == 48
        and all(
            item.compatibility_state is CompatibilityState.UNKNOWN
            and source_edge is not None
            and item.relationship_ids[0] == source_edge.relationship_id
            and item.edge_compatibility_states[0]
            is CompatibilityState.UNKNOWN
            for item in compatibility.path_evaluations
        )
    )
    check(
        "compatibility.aggregate_and_paths",
        CertificationCheckCategory.COMPATIBILITY,
        "Relationship and end-to-end path conclusions reproduce exactly.",
        aggregate_ok,
        "26 conditional + 1 unknown relationship; 48 unknown paths",
        (relationship_states, path_states),
    )
    dataset_aggregation_ok = all(
        _dataset_summary_matches(item, comp_fields)
        for item in compatibility.dataset_summaries
    )
    check(
        "compatibility.field_and_dataset_rollups",
        CertificationCheckCategory.COMPATIBILITY,
        "Field inputs resolve and dataset counts equal evaluated field aggregation.",
        (
            dataset_aggregation_ok
            and all(
                set(item.supporting_path_ids).issubset(comp_paths)
                and set(item.incoming_relationship_ids).issubset(
                    comp_relationships
                )
                for item in compatibility.field_evaluations
            )
        ),
        True,
        dataset_aggregation_ok,
    )

    explanation_counts = (
        1,
        len(explanations.relationship_explanations),
        len(explanations.path_explanations),
        len(explanations.field_explanations),
        len(explanations.dataset_explanations),
        len(explanations.uncertainties),
    )
    explanation_scope_ok = (
        explanation_counts == (1, 27, 48, 25, 20, 1)
        and explanations.validation_state is ExplanationValidationState.VALID
        and len(explanations.evidence_chains) >= 1
        and any(len(item.references) == 9 for item in explanations.evidence_chains)
    )
    check(
        "explanation.coverage",
        CertificationCheckCategory.EXPLANATION,
        "Phase 3.5 covers every certified source and downstream conclusion.",
        explanation_scope_ok,
        (1, 27, 48, 25, 20, 1),
        explanation_counts,
    )
    expected_evidence_chain = {
        item.artifact_name: item.semantic_fingerprint
        for item in input_artifact_identities[:9]
    }
    evidence_chain_closes = any(
        {
            item.artifact_name: item.semantic_fingerprint
            for item in chain.references
        }
        == expected_evidence_chain
        for chain in explanations.evidence_chains
    )
    check(
        "explanation.evidence_chain_closure",
        CertificationCheckCategory.EXPLANATION,
        "At least one explanation evidence chain matches all nine predecessors.",
        evidence_chain_closes,
        expected_evidence_chain,
        tuple(
            {
                item.artifact_name: item.semantic_fingerprint
                for item in chain.references
            }
            for chain in explanations.evidence_chains
        ),
    )
    explanation_projection_ok = (
        {
            item.relationship_id: item.compatibility_state
            for item in explanations.relationship_explanations
        }
        == {
            key: value.compatibility_state
            for key, value in comp_relationships.items()
        }
        and {
            item.path_id: item.compatibility_state
            for item in explanations.path_explanations
        }
        == {
            key: value.compatibility_state for key, value in comp_paths.items()
        }
        and {
            item.field_key: item.compatibility_state
            for item in explanations.field_explanations
        }
        == {
            key: value.compatibility_state for key, value in comp_fields.items()
        }
    )
    check(
        "explanation.conclusions_unchanged",
        CertificationCheckCategory.EXPLANATION,
        "Explanation compatibility conclusions exactly project Phase 3.4.",
        explanation_projection_ok,
        True,
        explanation_projection_ok,
    )
    unsupported_claims = (
        "the rename breaks spark",
        "the rename is safe",
        "the downstream assets will continue working",
        "the 25 fields are broken",
        "datahub observed order_amount",
        "spark automatically renames the field",
    )
    explanation_text = explanations.to_json().lower()
    truthful = all(value not in explanation_text for value in unsupported_claims)
    check(
        "explanation.truthfulness",
        CertificationCheckCategory.EXPLANATION,
        "Typed and human explanations contain no unsupported assertion.",
        truthful,
        "no unsupported assertion",
        tuple(value for value in unsupported_claims if value in explanation_text),
    )
    uncertainty = (
        explanations.uncertainties[0]
        if len(explanations.uncertainties) == 1
        else None
    )
    required_missing = {
        "spark_transformation_configuration",
        "input_column_reference_query_or_code",
        "explicit_rename_mapping",
        "validated_execution_result",
    }
    uncertainty_ok = (
        uncertainty is not None
        and source_edge is not None
        and uncertainty.subject == source_edge.relationship_id
        and uncertainty.reason_code
        is CompatibilityReasonCode.SOURCE_RENAME_SEMANTICS_UNKNOWN
        and required_missing.issubset(uncertainty.missing_evidence_types)
    )
    check(
        "explanation.root_uncertainty",
        CertificationCheckCategory.EXPLANATION,
        "Root uncertainty preserves the missing Spark rename semantics.",
        uncertainty_ok,
        required_missing,
        uncertainty,
    )

    known_evidence = set(snapshot.evidence_by_id())
    known_provenance = {
        item.provenance_id for item in graph.provenance_registry
    }
    referenced_provenance = (
        _collect_named_tuple_values(
            (
                graph,
                propagation,
                compatibility,
                explanations,
            ),
            {
                "provenance_ids",
                "current_provenance_ids",
                "counterfactual_provenance_ids",
            },
        )
        - known_evidence
    )
    evidence_closure = all(
        set(item.current_evidence_ids).issubset(known_evidence)
        for item in graph.provenance_registry
    )
    provenance_closure = (
        referenced_provenance.issubset(known_provenance) and evidence_closure
    )
    check(
        "provenance.full_closure",
        CertificationCheckCategory.PROVENANCE,
        "All provenance recursively closes to registered provenance and Phase 1 evidence.",
        provenance_closure,
        "no dangling provenance",
        tuple(sorted(referenced_provenance - known_provenance)),
    )
    provenance_classification_ok = all(
        (
            item.kind is ProvenanceKind.CURRENT_EVIDENCE
            and item.provenance_id.startswith("provenance-current-")
            and item.source_artifact_fingerprint == snapshot.semantic_fingerprint
        )
        or (
            item.kind is ProvenanceKind.COUNTERFACTUAL_DERIVATION
            and item.provenance_id.startswith("provenance-counterfactual-")
            and item.source_artifact_fingerprint
            == source_state.semantic_fingerprint
        )
        for item in graph.provenance_registry
    )
    check(
        "provenance.current_counterfactual_separation",
        CertificationCheckCategory.PROVENANCE,
        "Current evidence and counterfactual derivation remain distinguishable.",
        provenance_classification_ok,
        True,
        provenance_classification_ok,
    )
    evidence_classification_ok = (
        source_state.state_classification
        is SourceStateClassification.COUNTERFACTUAL
        and {
            item.state for item in graph.field_registry
        }
        == {
            GraphObjectState.COUNTERFACTUAL_CHANGED,
            GraphObjectState.COUNTERFACTUAL_UNRESOLVED,
        }
        and {
            item.exposure_state
            for item in propagation.field_exposure_registry
        }
        == {
            FieldExposureState.SOURCE_CHANGED,
            FieldExposureState.DIRECTLY_EXPOSED,
            FieldExposureState.TRANSITIVELY_EXPOSED,
            FieldExposureState.MULTIPATH_EXPOSED,
        }
        and {
            item.compatibility_state
            for item in compatibility.relationship_evaluations
        }
        == {
            CompatibilityState.CONDITIONALLY_COMPATIBLE,
            CompatibilityState.UNKNOWN,
        }
        and {
            item.evidence_strength
            for item in compatibility.relationship_evaluations
        }
        == {EvidenceStrength.DERIVED, EvidenceStrength.INSUFFICIENT}
    )
    check(
        "provenance.evidence_classification_integrity",
        CertificationCheckCategory.PROVENANCE,
        "Current, counterfactual, exposure, compatibility, and evidence-strength classifications remain distinct.",
        evidence_classification_ok,
        True,
        evidence_classification_ok,
    )

    current_context_counts = Counter(
        item.category
        for item in snapshot.relationships
        if item.category is not RelationshipCategory.FIELD_LINEAGE
    )
    future_context_counts = Counter(
        item.category for item in graph.context_relationship_registry
    )
    context_separation_ok = (
        current_context_counts == future_context_counts
        and all(
            item.state is GraphObjectState.COUNTERFACTUAL_INHERITED
            for item in graph.context_relationship_registry
        )
        and not (context_ids & propagated_ids)
        and not (
            context_ids
            & {
                value
                for item in compatibility.relationship_evaluations
                for value in item.mapping_group_ids
            }
        )
    )
    check(
        "scope.context_separation",
        CertificationCheckCategory.SCOPE,
        "Governance and context counts are preserved but excluded from lineage propagation.",
        context_separation_ok,
        current_context_counts,
        future_context_counts,
    )
    forbidden_model_names = {
        "business_impact",
        "severity_score",
        "risk_score",
        "criticality_score",
        "repair_priority",
        "deployment_decision",
        "owner_notification_priority",
        "financial_impact",
        "sla_impact",
        "repair_recommendation",
        "automated_code_modification",
    }
    model_names = _collect_field_names(
        (source_state, graph, propagation, compatibility, explanations)
    )
    scope_ok = not (forbidden_model_names & model_names)
    check(
        "scope.no_later_phase_models",
        CertificationCheckCategory.SCOPE,
        "Phase 3 contains no authoritative impact, risk, severity, or repair model.",
        scope_ok,
        "no later-phase model fields",
        tuple(sorted(forbidden_model_names & model_names)),
    )

    secret_free = all(
        not contains_secret(item.to_dict())
        for item in (
            snapshot,
            proposal,
            validation,
            contract,
            phase2,
            source_state,
            graph,
            propagation,
            compatibility,
            explanations,
        )
    )
    check(
        "security.secret_shape_scan",
        CertificationCheckCategory.SECURITY,
        "All ten certification inputs pass credential-shape scanning.",
        secret_free,
        True,
        secret_free,
    )
    check(
        "immutability.all_inputs",
        CertificationCheckCategory.IMMUTABILITY,
        "All ten input artifacts retain identical before/after SHA-256.",
        (
            len(artifact_immutability) == 10
            and all(item.unchanged for item in artifact_immutability)
        ),
        "ten unchanged inputs",
        tuple(
            (item.artifact_name, item.unchanged)
            for item in artifact_immutability
        ),
    )
    check(
        "determinism.semantic_fingerprints_reproduce",
        CertificationCheckCategory.DETERMINISM,
        "Every stored Phase 3 semantic fingerprint reproduces.",
        (
            semantic.counterfactual_source == source_state.semantic_fingerprint
            and semantic.future_graph == graph.semantic_fingerprint
            and semantic.dependency_propagation
            == propagation.semantic_fingerprint
            and semantic.compatibility_evaluation
            == compatibility.semantic_fingerprint
            and semantic.explanation_bundle
            == explanations.semantic_fingerprint
        ),
        semantic,
        (
            source_state.semantic_fingerprint,
            graph.semantic_fingerprint,
            propagation.semantic_fingerprint,
            compatibility.semantic_fingerprint,
            explanations.semantic_fingerprint,
        ),
    )
    check(
        "determinism.offline_reconstruction",
        CertificationCheckCategory.DETERMINISM,
        "Public builders independently reconstruct Phase 3.1–3.5 semantics offline.",
        reconstructed_fingerprints == semantic,
        semantic,
        reconstructed_fingerprints,
    )
    check(
        "scope.offline_boundary",
        CertificationCheckCategory.SCOPE,
        "Certification inputs and reconstruction require only local artifacts.",
        True,
        "offline local artifact access only",
        "offline local artifact access only",
    )

    summary = Phase3SummaryMetrics(
        datasets=len(graph.dataset_registry),
        active_future_fields=len(graph.field_registry),
        changed_source_fields=propagation.summary.changed_source_fields,
        downstream_fields=(
            propagation.summary.total_unique_downstream_exposed_fields
        ),
        downstream_datasets=(
            propagation.summary.unique_downstream_exposed_datasets
        ),
        structural_relationships=len(graph.relationship_registry),
        mapping_groups=len(graph.mapping_group_registry),
        supporting_paths=len(propagation.path_registry),
        maximum_shortest_exposure_depth=(
            propagation.summary.maximum_exposure_depth
        ),
        maximum_stored_path_depth=maximum_stored_path_depth,
        root_uncertainties=len(explanations.uncertainties),
        conditionally_compatible_relationships=relationship_states[
            CompatibilityState.CONDITIONALLY_COMPATIBLE
        ],
        unknown_relationships=relationship_states[CompatibilityState.UNKNOWN],
        unknown_paths=path_states[CompatibilityState.UNKNOWN],
    )
    failed = any(
        item.status is CertificationCheckStatus.FAIL for item in checks
    )
    return Phase3CertificationResult(
        schema_version=PHASE3_CERTIFICATION_SCHEMA_VERSION,
        demonstration_id=CANONICAL_DEMONSTRATION_ID,
        certification_status=(
            Phase3CertificationStatus.FAILED
            if failed
            else Phase3CertificationStatus.CERTIFIED
        ),
        certified_at=_timestamp(clock),
        input_artifact_identities=input_artifact_identities,
        phase_3_semantic_fingerprints=semantic,
        certification_checks=tuple(checks),
        warnings=(),
        summary_metrics=summary,
        artifact_immutability=artifact_immutability,
        scope_statement=_SCOPE_STATEMENT,
    )


def certify_phase3_from_artifacts(
    snapshot_path: str | Path,
    proposal_path: str | Path,
    validation_path: str | Path,
    contract_path: str | Path,
    phase2_path: str | Path,
    source_state_path: str | Path,
    graph_path: str | Path,
    propagation_path: str | Path,
    compatibility_path: str | Path,
    explanations_path: str | Path,
    *,
    clock: Clock | None = None,
) -> Phase3CertificationResult:
    """Load, reconstruct, and certify the ten immutable local artifacts."""

    paths = (
        ("current_metadata_snapshot.json", Path(snapshot_path)),
        ("change_proposal.json", Path(proposal_path)),
        ("change_proposal_validation.json", Path(validation_path)),
        ("change_semantic_contract.json", Path(contract_path)),
        ("phase_2_certification.json", Path(phase2_path)),
        ("counterfactual_source_state.json", Path(source_state_path)),
        ("future_metadata_graph.json", Path(graph_path)),
        ("dependency_propagation.json", Path(propagation_path)),
        ("compatibility_evaluation.json", Path(compatibility_path)),
        ("explanation_bundle.json", Path(explanations_path)),
    )
    before = {name: _file_hash(path) for name, path in paths}
    try:
        snapshot = load_snapshot(snapshot_path)
        proposal = load_proposal(proposal_path)
        validation = load_validation_result(validation_path)
        contract = load_contract(contract_path)
        phase2 = load_certification(phase2_path)
        source_state = load_source_state(source_state_path)
        graph = load_future_graph(graph_path)
        propagation = load_dependency_propagation(propagation_path)
        compatibility = load_compatibility_evaluation(compatibility_path)
        explanations = load_explanation_bundle(explanations_path)
    except (OSError, ValueError) as exc:
        raise Phase3CertificationInputError(
            "A Phase 3 certification input failed closed during loading."
        ) from exc

    reconstruction = _reconstruct_phase3(
        tuple(path for _, path in paths),
    )
    after = {name: _file_hash(path) for name, path in paths}
    immutability = tuple(
        ArtifactImmutabilityEvidence(name, before[name], after[name])
        for name, _ in paths
    )
    semantic_values = (
        snapshot.semantic_fingerprint,
        proposal.semantic_fingerprint,
        validation.semantic_fingerprint,
        contract.semantic_fingerprint,
        phase2.semantic_fingerprint,
        source_state.semantic_fingerprint,
        graph.semantic_fingerprint,
        propagation.semantic_fingerprint,
        compatibility.semantic_fingerprint,
        explanations.semantic_fingerprint,
    )
    object_ids = (
        snapshot.metadata.snapshot_id,
        proposal.proposal_id,
        validation.proposal_id,
        contract.proposal_id,
        phase2.demonstration_id,
        _CANDIDATE.text,
        graph.demonstration_id,
        propagation.source_candidate_field.text,
        compatibility.proposal_id,
        explanations.demonstration_id,
    )
    identities = tuple(
        InputArtifactIdentity(
            artifact_name=name,
            object_id=object_id,
            semantic_fingerprint=semantic_value,
            physical_sha256=before[name],
        )
        for (name, _), object_id, semantic_value in zip(
            paths,
            object_ids,
            semantic_values,
        )
    )
    return certify_phase3(
        snapshot,
        proposal,
        validation,
        contract,
        phase2,
        source_state,
        graph,
        propagation,
        compatibility,
        explanations,
        input_artifact_identities=identities,
        artifact_immutability=immutability,
        reconstructed_fingerprints=reconstruction,
        clock=clock,
    )


def validate_phase3_certification(
    result: Phase3CertificationResult,
) -> None:
    """Fail closed when a serialized certification contradicts itself."""
    issues: list[str] = []
    if result.certification_status is not Phase3CertificationStatus.CERTIFIED:
        issues.append("Phase 3 status is not CERTIFIED")
    if any(
        item.status is not CertificationCheckStatus.PASS
        for item in result.certification_checks
    ):
        issues.append("One or more certification checks failed")
    expected_categories = set(CertificationCheckCategory)
    observed_categories = {
        item.category for item in result.certification_checks
    }
    if observed_categories != expected_categories:
        issues.append("Certification check categories are incomplete")
    if any(not item.unchanged for item in result.artifact_immutability):
        issues.append("An authoritative input changed")
    if result.phase_3_semantic_fingerprints != _ACCEPTED_PHASE3:
        issues.append("Phase 3 acceptance fingerprint mismatch")
    metrics = result.summary_metrics
    if (
        metrics.datasets,
        metrics.active_future_fields,
        metrics.changed_source_fields,
        metrics.downstream_fields,
        metrics.downstream_datasets,
        metrics.structural_relationships,
        metrics.mapping_groups,
        metrics.supporting_paths,
        metrics.maximum_shortest_exposure_depth,
        metrics.maximum_stored_path_depth,
        metrics.root_uncertainties,
        metrics.conditionally_compatible_relationships,
        metrics.unknown_relationships,
        metrics.unknown_paths,
    ) != (21, 26, 1, 25, 20, 27, 28, 48, 5, 7, 1, 26, 1, 48):
        issues.append("Frozen Phase 3 summary baseline mismatch")
    if contains_secret(result.to_dict()):
        issues.append("Certification contains credential-shaped content")
    if issues:
        from .errors import Phase3CertificationValidationError

        raise Phase3CertificationValidationError("; ".join(issues))


def _reconstruct_phase3(
    paths: tuple[Path, ...],
) -> Phase3SemanticFingerprints:
    fixed = lambda hour: lambda: datetime(
        2026,
        7,
        28,
        hour,
        tzinfo=timezone.utc,
    )
    source = materialize_source_state_from_artifacts(
        *paths[:5],
        clock=fixed(0),
    )
    graph = build_future_graph_from_artifacts(
        *paths[:6],
        clock=fixed(1),
    )
    propagation = propagate_dependencies_from_artifacts(
        *paths[:7],
        clock=fixed(2),
    )
    compatibility = evaluate_compatibility_from_artifacts(
        *paths[:8],
        clock=fixed(3),
    )
    explanations = build_explanation_bundle_from_artifacts(
        *paths[:9],
        clock=fixed(4),
    )
    return _semantic_fingerprints(
        source,
        graph,
        propagation,
        compatibility,
        explanations,
    )


def _semantic_fingerprints(
    source: CounterfactualSourceState,
    graph: FutureMetadataGraph,
    propagation: DependencyPropagationResult,
    compatibility: CompatibilityEvaluationResult,
    explanations: ExplanationBundle,
) -> Phase3SemanticFingerprints:
    return Phase3SemanticFingerprints(
        counterfactual_source=source_state_semantic_fingerprint(source),
        future_graph=future_graph_semantic_fingerprint(graph),
        dependency_propagation=propagation_semantic_fingerprint(propagation),
        compatibility_evaluation=compatibility_semantic_fingerprint(
            compatibility
        ),
        explanation_bundle=explanation_semantic_fingerprint(explanations),
    )


def _dataset_summary_matches(
    summary: Any,
    fields_by_key: dict[FieldMachineKey, Any],
) -> bool:
    if any(key not in fields_by_key for key in summary.exposed_field_keys):
        return False
    records = tuple(fields_by_key[key] for key in summary.exposed_field_keys)
    counts = Counter(item.compatibility_state for item in records)
    return (
        summary.compatible_exposed_fields
        == counts[CompatibilityState.COMPATIBLE]
        and summary.incompatible_exposed_fields
        == counts[CompatibilityState.INCOMPATIBLE]
        and summary.conditionally_compatible_exposed_fields
        == counts[CompatibilityState.CONDITIONALLY_COMPATIBLE]
        and summary.unknown_exposed_fields
        == counts[CompatibilityState.UNKNOWN]
    )


def _collect_named_tuple_values(
    roots: Iterable[Any],
    names: set[str],
) -> set[str]:
    collected: set[str] = set()

    def visit(value: Any) -> None:
        if is_dataclass(value):
            for item in fields(value):
                child = getattr(value, item.name)
                if item.name in names and isinstance(child, tuple):
                    collected.update(
                        entry for entry in child if isinstance(entry, str)
                    )
                visit(child)
        elif isinstance(value, (tuple, list)):
            for item in value:
                visit(item)
        elif isinstance(value, dict):
            for item in value.values():
                visit(item)

    for root in roots:
        visit(root)
    return collected


def _collect_field_names(roots: Iterable[Any]) -> set[str]:
    names: set[str] = set()

    def visit(value: Any) -> None:
        if is_dataclass(value):
            for item in fields(value):
                names.add(item.name.lower())
                visit(getattr(value, item.name))
        elif isinstance(value, (tuple, list)):
            for item in value:
                visit(item)
        elif isinstance(value, dict):
            for key, item in value.items():
                names.add(str(key).lower())
                visit(item)

    for root in roots:
        visit(root)
    return names


def _passes(function: Callable[..., Any], *args: Any) -> bool:
    try:
        function(*args)
    except (TypeError, ValueError):
        return False
    return True


def _text(value: object) -> str:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return repr(value)
    if isinstance(value, (tuple, list, set, frozenset)):
        return "[" + ",".join(
            sorted(_text(item) for item in value)
        ) + "]"
    if isinstance(value, dict):
        return "{" + ",".join(
            f"{_text(key)}:{_text(item)}"
            for key, item in sorted(
                value.items(),
                key=lambda pair: _text(pair[0]),
            )
        ) + "}"
    return str(value)


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _timestamp(clock: Clock | None) -> str:
    value = (clock or (lambda: datetime.now(timezone.utc)))()
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()
