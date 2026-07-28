"""Fail-closed construction and validation of the Phase 3.2 Future Graph."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from chronos.change_semantics import (
    ChangeSemanticContract,
    load_contract,
)
from chronos.counterfactual_source import (
    CounterfactualSourceState,
    InputArtifactHash,
    SourceStateClassification,
    load_source_state,
    source_state_semantic_fingerprint,
    validate_counterfactual_source_state,
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
    RelationshipCategory,
    SnapshotValidationState,
    load_snapshot,
)

from .errors import (
    FutureGraphEntryPreconditionError,
    FutureGraphValidationError,
)
from .models import (
    FUTURE_GRAPH_SCHEMA_VERSION,
    CurrentToFutureIdentityMapping,
    FutureAttribute,
    FutureContextRelationship,
    FutureDataset,
    FutureField,
    FutureGraphValidationState,
    FutureIdentityMappingClassification,
    FutureLineagePath,
    FutureLineageRelationship,
    FutureMappingGroup,
    FutureMetadataGraph,
    FuturePathClassification,
    FutureRelationshipState,
    FutureStructuredPropertyDefinition,
    GraphObjectState,
    GraphProvenanceRecord,
    GraphStateAnnotation,
    ProvenanceKind,
    RelationshipEvaluationState,
)


Clock = Callable[[], datetime]
_CURRENT_SOURCE = FieldMachineKey(CANONICAL_DATASET_URN, "order_total")
_FUTURE_SOURCE = FieldMachineKey(CANONICAL_DATASET_URN, "order_amount")


def build_future_metadata_graph(
    snapshot: CurrentMetadataSnapshot,
    proposal: ChangeProposal,
    validation: ProposalValidationResult,
    contract: ChangeSemanticContract,
    phase_2_certification: Phase2CertificationResult,
    source_state: CounterfactualSourceState,
    *,
    input_artifact_hashes: tuple[InputArtifactHash, ...],
    clock: Clock | None = None,
) -> FutureMetadataGraph:
    """Project current structure around the candidate source identity."""

    _require_entry_preconditions(
        snapshot,
        proposal,
        validation,
        contract,
        phase_2_certification,
        source_state,
        input_artifact_hashes,
    )
    provenance: dict[str, GraphProvenanceRecord] = {}

    def current_provenance(
        object_type: str,
        object_key: str,
        evidence_ids: tuple[str, ...],
    ) -> str:
        provenance_id = _stable_id(
            "provenance-current",
            f"{object_type}|{object_key}|{snapshot.semantic_fingerprint}",
        )
        provenance[provenance_id] = GraphProvenanceRecord(
            provenance_id=provenance_id,
            kind=ProvenanceKind.CURRENT_EVIDENCE,
            source_artifact_fingerprint=snapshot.semantic_fingerprint,
            source_object_type=object_type,
            source_object_key=object_key,
            current_evidence_ids=evidence_ids,
            proposal_id=None,
            proposal_fingerprint=None,
            semantic_contract_fingerprint=None,
            counterfactual_source_state_fingerprint=None,
            projection_classification=None,
        )
        return provenance_id

    def derivation_provenance(
        object_type: str,
        object_key: str,
        projection_classification: str,
    ) -> str:
        provenance_id = _stable_id(
            "provenance-counterfactual",
            (
                f"{object_type}|{object_key}|{proposal.semantic_fingerprint}|"
                f"{source_state.semantic_fingerprint}|"
                f"{projection_classification}"
            ),
        )
        provenance[provenance_id] = GraphProvenanceRecord(
            provenance_id=provenance_id,
            kind=ProvenanceKind.COUNTERFACTUAL_DERIVATION,
            source_artifact_fingerprint=source_state.semantic_fingerprint,
            source_object_type=object_type,
            source_object_key=object_key,
            current_evidence_ids=(),
            proposal_id=proposal.proposal_id,
            proposal_fingerprint=proposal.semantic_fingerprint,
            semantic_contract_fingerprint=contract.semantic_fingerprint,
            counterfactual_source_state_fingerprint=(
                source_state.semantic_fingerprint
            ),
            projection_classification=projection_classification,
        )
        return provenance_id

    datasets: list[FutureDataset] = []
    for item in sorted(snapshot.datasets, key=lambda value: value.dataset_urn):
        current_id = current_provenance(
            "dataset",
            item.dataset_urn,
            item.evidence_ids,
        )
        is_source = item.dataset_urn == CANONICAL_DATASET_URN
        active_schema_paths = (
            tuple(
                field.field_path
                for field in source_state.candidate_source_schema.fields
            )
            if is_source
            else item.schema_field_paths
        )
        active_lineage_keys = tuple(
            _project_key(key) for key in item.lineage_field_keys
        )
        datasets.append(
            FutureDataset(
                dataset_urn=item.dataset_urn,
                platform=item.platform,
                environment=item.environment,
                qualified_name=item.qualified_name,
                logical_name=item.logical_name,
                display_identity=item.display_identity,
                current_schema_field_paths=item.schema_field_paths,
                active_schema_field_paths=active_schema_paths,
                current_lineage_field_keys=item.lineage_field_keys,
                active_lineage_field_keys=active_lineage_keys,
                metadata_states=tuple(
                    FutureAttribute(value.name, value.values)
                    for value in item.metadata_states
                ),
                current_relationship_ids=item.relationship_ids,
                current_evidence_ids=item.evidence_ids,
                state=GraphObjectState.COUNTERFACTUAL_INHERITED,
                provenance_ids=(current_id,),
            )
        )

    candidate_target = next(
        item
        for item in source_state.candidate_source_schema.fields
        if item.field_path == "order_amount"
    )
    fields: list[FutureField] = []
    identity_mappings: list[CurrentToFutureIdentityMapping] = []
    for item in sorted(snapshot.fields, key=lambda value: value.key.text):
        is_source = item.key == _CURRENT_SOURCE
        current_id = current_provenance(
            "field",
            item.key.text,
            item.evidence_ids,
        )
        provenance_ids = [current_id]
        future_key = _project_key(item.key)
        state = (
            GraphObjectState.COUNTERFACTUAL_CHANGED
            if is_source
            else GraphObjectState.COUNTERFACTUAL_UNRESOLVED
        )
        if is_source:
            provenance_ids.append(
                derivation_provenance(
                    "field",
                    future_key.text,
                    "source_identity_renamed",
                )
            )
        fields.append(
            FutureField(
                key=future_key,
                current_key=item.key,
                field_name=(
                    candidate_target.field_name
                    if is_source
                    else item.field_name
                ),
                platform=item.platform,
                dataset_name=item.dataset_name,
                environment=item.environment,
                native_type=(
                    candidate_target.native_type
                    if is_source
                    else item.native_type
                ),
                normalized_type=(
                    candidate_target.normalized_type
                    if is_source
                    else item.normalized_type
                ),
                schema_position=(
                    candidate_target.position
                    if is_source
                    else item.schema_position
                ),
                description=(
                    candidate_target.description
                    if is_source
                    else item.description
                ),
                nullable=(
                    candidate_target.nullable
                    if is_source
                    else item.nullable
                ),
                is_part_of_key=(
                    candidate_target.is_part_of_key
                    if is_source
                    else item.is_part_of_key
                ),
                is_partitioning_key=(
                    candidate_target.is_partitioning_key
                    if is_source
                    else item.is_partitioning_key
                ),
                schema_field_urn=(
                    candidate_target.schema_field_urn
                    if is_source
                    else item.schema_field_urn
                ),
                reference_resolution=item.reference_resolution,
                structural_depth=item.lineage_depth,
                current_path_count=item.path_count,
                current_paths_truncated=item.paths_truncated,
                current_evidence_ids=item.evidence_ids,
                state=state,
                provenance_ids=tuple(provenance_ids),
            )
        )
        identity_mappings.append(
            CurrentToFutureIdentityMapping(
                current_identity=item.key,
                future_identity=future_key,
                classification=(
                    FutureIdentityMappingClassification.RENAMED
                    if is_source
                    else (
                        FutureIdentityMappingClassification
                        .IDENTITY_PRESERVED
                    )
                ),
                provenance_ids=tuple(provenance_ids),
            )
        )

    edge_id_by_current: dict[str, str] = {}
    relationships: list[FutureLineageRelationship] = []
    for item in sorted(
        snapshot.lineage_edges,
        key=lambda value: value.edge_id,
    ):
        upstream = _project_key(item.upstream)
        downstream = _project_key(item.downstream)
        rebased = upstream != item.upstream or downstream != item.downstream
        relationship_id = _stable_id(
            "future-lineage",
            f"{item.edge_id}|{upstream.text}|{downstream.text}",
        )
        edge_id_by_current[item.edge_id] = relationship_id
        current_id = current_provenance(
            "lineage_edge",
            item.edge_id,
            item.evidence_ids,
        )
        provenance_ids = [current_id]
        if rebased:
            provenance_ids.append(
                derivation_provenance(
                    "lineage_edge",
                    relationship_id,
                    "source_endpoint_rebased",
                )
            )
        relationships.append(
            FutureLineageRelationship(
                relationship_id=relationship_id,
                current_edge_id=item.edge_id,
                upstream=upstream,
                downstream=downstream,
                current_upstream=item.upstream,
                current_downstream=item.downstream,
                current_classification=item.classification,
                current_mapping_group_ids=item.mapping_group_ids,
                current_source_entity_urns=item.source_entity_urns,
                current_source_aspects=item.source_aspects,
                current_transform_operations=item.transform_operations,
                current_confidence_scores=item.confidence_scores,
                current_evidence_ids=item.evidence_ids,
                relationship_state=(
                    FutureRelationshipState.COUNTERFACTUAL_PROJECTED
                    if rebased
                    else FutureRelationshipState.COUNTERFACTUAL_INHERITED
                ),
                evaluation_state=(
                    RelationshipEvaluationState.NOT_EVALUATED
                ),
                provenance_ids=tuple(provenance_ids),
            )
        )

    mapping_groups: list[FutureMappingGroup] = []
    for item in sorted(
        snapshot.mapping_groups,
        key=lambda value: value.group_id,
    ):
        projected_upstream = tuple(
            _project_key(value) for value in item.upstream_fields
        )
        projected_downstream = tuple(
            _project_key(value) for value in item.downstream_fields
        )
        projected = (
            projected_upstream != item.upstream_fields
            or projected_downstream != item.downstream_fields
        )
        current_id = current_provenance(
            "mapping_group",
            item.group_id,
            item.evidence_ids,
        )
        provenance_ids = [current_id]
        if projected:
            provenance_ids.append(
                derivation_provenance(
                    "mapping_group",
                    item.group_id,
                    "source_endpoint_projected",
                )
            )
        mapping_groups.append(
            FutureMappingGroup(
                group_id=item.group_id,
                current_source_entity_urn=item.source_entity_urn,
                current_source_entity_type=item.source_entity_type,
                current_source_aspect=item.source_aspect,
                current_source_interface=item.source_interface,
                current_source_group_index=item.source_group_index,
                current_upstream_type=item.upstream_type,
                current_downstream_type=item.downstream_type,
                current_raw_upstream_references=item.raw_upstream_references,
                current_raw_downstream_references=(
                    item.raw_downstream_references
                ),
                current_upstream_fields=item.upstream_fields,
                current_downstream_fields=item.downstream_fields,
                projected_upstream_fields=projected_upstream,
                projected_downstream_fields=projected_downstream,
                current_transform_operation=item.transform_operation,
                current_confidence_score=item.confidence_score,
                current_query=item.query,
                current_match_type=item.match_type,
                current_expansion_state=item.expansion_state,
                current_evidence_ids=item.evidence_ids,
                relationship_state=(
                    FutureRelationshipState.COUNTERFACTUAL_PROJECTED
                    if projected
                    else FutureRelationshipState.COUNTERFACTUAL_INHERITED
                ),
                evaluation_state=(
                    RelationshipEvaluationState.NOT_EVALUATED
                ),
                provenance_ids=tuple(provenance_ids),
            )
        )

    paths: list[FutureLineagePath] = []
    ordered_paths = sorted(
        snapshot.lineage_paths,
        key=lambda item: (
            tuple(value.text for value in item.node_keys),
            item.edge_ids,
        ),
    )
    for current in ordered_paths:
        current_key = "|".join(
            tuple(value.text for value in current.node_keys)
            + current.edge_ids
        )
        path_id = _stable_id("future-path", current_key)
        current_id = current_provenance(
            "lineage_path",
            current_key,
            (),
        )
        derivation_id = derivation_provenance(
            "lineage_path",
            path_id,
            "source_identity_rebased_structure",
        )
        paths.append(
            FutureLineagePath(
                path_id=path_id,
                current_node_keys=current.node_keys,
                current_edge_ids=current.edge_ids,
                projected_node_keys=tuple(
                    _project_key(value) for value in current.node_keys
                ),
                projected_relationship_ids=tuple(
                    edge_id_by_current[value] for value in current.edge_ids
                ),
                classification=(
                    FuturePathClassification.COUNTERFACTUAL_STRUCTURE
                ),
                evaluation_state=(
                    RelationshipEvaluationState.NOT_EVALUATED
                ),
                provenance_ids=(current_id, derivation_id),
            )
        )

    context_relationships: list[FutureContextRelationship] = []
    for item in sorted(
        (
            value
            for value in snapshot.relationships
            if value.category is not RelationshipCategory.FIELD_LINEAGE
        ),
        key=lambda value: value.relationship_id,
    ):
        current_id = current_provenance(
            "context_relationship",
            item.relationship_id,
            item.evidence_ids,
        )
        context_relationships.append(
            FutureContextRelationship(
                current_relationship_id=item.relationship_id,
                category=item.category,
                source_key=item.source_key,
                target_key=item.target_key,
                relationship_path=item.relationship_path,
                current_state=item.state,
                current_attributes=tuple(
                    FutureAttribute(value.name, value.values)
                    for value in item.attributes
                ),
                current_evidence_ids=item.evidence_ids,
                state=GraphObjectState.COUNTERFACTUAL_INHERITED,
                provenance_ids=(current_id,),
            )
        )

    definitions: list[FutureStructuredPropertyDefinition] = []
    for item in sorted(
        snapshot.structured_property_definitions,
        key=lambda value: value.property_urn,
    ):
        current_id = current_provenance(
            "structured_property_definition",
            item.property_urn,
            item.evidence_ids,
        )
        definitions.append(
            FutureStructuredPropertyDefinition(
                property_urn=item.property_urn,
                qualified_name=item.qualified_name,
                display_name=item.display_name,
                value_type=item.value_type,
                value_type_urn=item.value_type_urn,
                current_evidence_ids=item.evidence_ids,
                state=GraphObjectState.COUNTERFACTUAL_INHERITED,
                provenance_ids=(current_id,),
            )
        )

    annotations = _state_annotations(
        datasets,
        fields,
        relationships,
        mapping_groups,
        paths,
        context_relationships,
        definitions,
        identity_mappings,
    )
    graph = FutureMetadataGraph(
        schema_version=FUTURE_GRAPH_SCHEMA_VERSION,
        demonstration_id=CANONICAL_DEMONSTRATION_ID,
        current_snapshot_fingerprint=snapshot.semantic_fingerprint,
        proposal_fingerprint=proposal.semantic_fingerprint,
        validation_fingerprint=validation.semantic_fingerprint,
        semantic_contract_fingerprint=contract.semantic_fingerprint,
        phase_2_certification_fingerprint=(
            phase_2_certification.semantic_fingerprint
        ),
        counterfactual_source_state_fingerprint=(
            source_state.semantic_fingerprint
        ),
        source_schema=source_state.candidate_source_schema,
        dataset_registry=tuple(datasets),
        field_registry=tuple(fields),
        relationship_registry=tuple(relationships),
        mapping_group_registry=tuple(mapping_groups),
        path_registry=tuple(paths),
        context_relationship_registry=tuple(context_relationships),
        structured_property_registry=tuple(definitions),
        current_to_future_identity_mappings=tuple(
            sorted(
                identity_mappings,
                key=lambda item: item.current_identity.text,
            )
        ),
        provenance_registry=tuple(
            provenance[key] for key in sorted(provenance)
        ),
        state_annotations=tuple(
            sorted(
                annotations,
                key=lambda item: (item.object_type, item.object_key),
            )
        ),
        input_artifact_hashes=input_artifact_hashes,
        validation_state=FutureGraphValidationState.VALID,
        created_at=_timestamp(clock),
    )
    validate_future_metadata_graph(
        graph,
        snapshot,
        proposal,
        validation,
        contract,
        phase_2_certification,
        source_state,
    )
    return graph


def build_future_graph_from_artifacts(
    snapshot_path: str | Path,
    proposal_path: str | Path,
    validation_path: str | Path,
    contract_path: str | Path,
    phase_2_certification_path: str | Path,
    source_state_path: str | Path,
    *,
    clock: Clock | None = None,
) -> FutureMetadataGraph:
    paths = (
        ("current_metadata_snapshot.json", Path(snapshot_path)),
        ("change_proposal.json", Path(proposal_path)),
        ("change_proposal_validation.json", Path(validation_path)),
        ("change_semantic_contract.json", Path(contract_path)),
        ("phase_2_certification.json", Path(phase_2_certification_path)),
        ("counterfactual_source_state.json", Path(source_state_path)),
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
    source_state = load_source_state(source_state_path)
    after_load = {
        name: hashlib.sha256(path.read_bytes()).hexdigest()
        for name, path in paths
    }
    hashes = tuple(
        InputArtifactHash(name, before[name], after_load[name])
        for name, _ in paths
    )
    graph = build_future_metadata_graph(
        snapshot,
        proposal,
        validation,
        contract,
        phase_2_certification,
        source_state,
        input_artifact_hashes=hashes,
        clock=clock,
    )
    after_build = {
        name: hashlib.sha256(path.read_bytes()).hexdigest()
        for name, path in paths
    }
    if after_build != before:
        raise FutureGraphValidationError(
            "An authoritative artifact changed during Future Graph build."
        )
    return graph


def validate_future_metadata_graph(
    graph: FutureMetadataGraph,
    snapshot: CurrentMetadataSnapshot,
    proposal: ChangeProposal,
    validation: ProposalValidationResult,
    contract: ChangeSemanticContract,
    phase_2_certification: Phase2CertificationResult,
    source_state: CounterfactualSourceState,
) -> None:
    """Validate structure and provenance without resolving later semantics."""

    issues: list[str] = []

    def require(condition: bool, message: str) -> None:
        if not condition:
            issues.append(message)

    require(
        graph.current_snapshot_fingerprint == snapshot.semantic_fingerprint,
        "snapshot fingerprint mismatch",
    )
    require(
        graph.proposal_fingerprint == proposal.semantic_fingerprint,
        "proposal fingerprint mismatch",
    )
    require(
        graph.validation_fingerprint == validation.semantic_fingerprint,
        "validation fingerprint mismatch",
    )
    require(
        graph.semantic_contract_fingerprint == contract.semantic_fingerprint,
        "semantic-contract fingerprint mismatch",
    )
    require(
        graph.phase_2_certification_fingerprint
        == phase_2_certification.semantic_fingerprint,
        "Phase 2 certification fingerprint mismatch",
    )
    require(
        graph.counterfactual_source_state_fingerprint
        == source_state.semantic_fingerprint,
        "source-state fingerprint mismatch",
    )
    require(
        graph.source_schema == source_state.candidate_source_schema,
        "candidate source schema was not integrated exactly",
    )
    current_dataset_urns = {
        item.dataset_urn for item in snapshot.datasets
    }
    future_dataset_urns = {
        item.dataset_urn for item in graph.dataset_registry
    }
    require(
        future_dataset_urns == current_dataset_urns,
        "Dataset registry identity changed",
    )
    current_downstream = {
        item.key for item in snapshot.fields if item.key != _CURRENT_SOURCE
    }
    future_downstream = {
        item.key for item in graph.field_registry if item.key != _FUTURE_SOURCE
    }
    require(
        future_downstream == current_downstream,
        "downstream field identities changed",
    )
    require(
        all(
            item.state is GraphObjectState.COUNTERFACTUAL_UNRESOLVED
            for item in graph.field_registry
            if item.key != _FUTURE_SOURCE
        ),
        "a downstream field was resolved prematurely",
    )
    source_fields = tuple(
        item for item in graph.field_registry if item.key == _FUTURE_SOURCE
    )
    require(len(source_fields) == 1, "candidate source must exist once")
    if source_fields:
        require(
            source_fields[0].state
            is GraphObjectState.COUNTERFACTUAL_CHANGED,
            "candidate source must be COUNTERFACTUAL_CHANGED",
        )
        require(
            source_fields[0].current_key == _CURRENT_SOURCE,
            "candidate source current identity provenance is missing",
        )
    current_edges = {
        item.edge_id: item for item in snapshot.lineage_edges
    }
    future_edges = {
        item.current_edge_id: item for item in graph.relationship_registry
    }
    require(
        set(future_edges) == set(current_edges),
        "lineage relationship provenance set changed",
    )
    for edge_id, current in current_edges.items():
        future = future_edges.get(edge_id)
        if future is None:
            continue
        require(
            future.upstream == _project_key(current.upstream)
            and future.downstream == _project_key(current.downstream),
            f"edge projection mismatch: {edge_id}",
        )
        require(
            future.current_upstream == current.upstream
            and future.current_downstream == current.downstream,
            f"current edge endpoints not retained: {edge_id}",
        )
        require(
            future.evaluation_state
            is RelationshipEvaluationState.NOT_EVALUATED,
            f"edge evaluation resolved: {edge_id}",
        )
    current_groups = {
        item.group_id: item for item in snapshot.mapping_groups
    }
    future_groups = {
        item.group_id: item for item in graph.mapping_group_registry
    }
    require(
        set(future_groups) == set(current_groups),
        "mapping-group provenance set changed",
    )
    for group_id, current in current_groups.items():
        future = future_groups.get(group_id)
        if future is None:
            continue
        require(
            future.current_upstream_fields == current.upstream_fields
            and future.current_downstream_fields == current.downstream_fields,
            f"current mapping group was rewritten: {group_id}",
        )
        require(
            future.projected_upstream_fields
            == tuple(_project_key(item) for item in current.upstream_fields)
            and future.projected_downstream_fields
            == tuple(_project_key(item) for item in current.downstream_fields),
            f"mapping projection mismatch: {group_id}",
        )
    require(
        len(graph.path_registry) == len(snapshot.lineage_paths),
        "current path count changed",
    )
    for path in graph.path_registry:
        require(
            path.projected_node_keys
            == tuple(_project_key(item) for item in path.current_node_keys),
            f"path source projection mismatch: {path.path_id}",
        )
        require(
            all(
                current == projected
                for current, projected in zip(
                    path.current_node_keys[1:],
                    path.projected_node_keys[1:],
                )
            ),
            f"a downstream path identity changed: {path.path_id}",
        )
    require(
        max(item.structural_depth for item in graph.field_registry) == 5,
        "maximum structural depth changed",
    )
    current_context = tuple(
        item
        for item in snapshot.relationships
        if item.category is not RelationshipCategory.FIELD_LINEAGE
    )
    require(
        len(graph.context_relationship_registry) == len(current_context),
        "context relationship count changed",
    )
    context_by_id = {
        item.current_relationship_id: item
        for item in graph.context_relationship_registry
    }
    for current in current_context:
        future = context_by_id.get(current.relationship_id)
        require(future is not None, "context relationship missing")
        if future is not None:
            require(
                future.source_key == current.source_key
                and future.target_key == current.target_key
                and future.current_state == current.state,
                f"context relationship changed: {current.relationship_id}",
            )
    require(
        all(item.unchanged for item in graph.input_artifact_hashes),
        "an input artifact hash changed",
    )
    provenance_by_id = {
        item.provenance_id: item for item in graph.provenance_registry
    }
    for field in graph.field_registry:
        records = [
            provenance_by_id[value] for value in field.provenance_ids
        ]
        require(
            any(item.kind is ProvenanceKind.CURRENT_EVIDENCE for item in records),
            f"field current provenance missing: {field.key.text}",
        )
        if field.key == _FUTURE_SOURCE:
            require(
                any(
                    item.kind is ProvenanceKind.COUNTERFACTUAL_DERIVATION
                    for item in records
                ),
                "candidate source derivation provenance missing",
            )
    forbidden_state_tokens = {
        "broken",
        "impacted",
        "compatible",
        "incompatible",
        "safe",
        "risk",
        "requires_repair",
    }
    generated_states = {
        item.state.value for item in graph.field_registry
    } | {
        item.relationship_state.value for item in graph.relationship_registry
    } | {
        item.evaluation_state.value for item in graph.relationship_registry
    }
    require(
        generated_states.isdisjoint(forbidden_state_tokens),
        "a prohibited semantic state exists",
    )
    if issues:
        raise FutureGraphValidationError("; ".join(issues))


def _require_entry_preconditions(
    snapshot: CurrentMetadataSnapshot,
    proposal: ChangeProposal,
    validation: ProposalValidationResult,
    contract: ChangeSemanticContract,
    phase_2_certification: Phase2CertificationResult,
    source_state: CounterfactualSourceState,
    input_artifact_hashes: tuple[InputArtifactHash, ...],
) -> None:
    if snapshot.validation_result.state is not SnapshotValidationState.VALID:
        raise FutureGraphEntryPreconditionError("Phase 1 is not certified.")
    if (
        phase_2_certification.certification_state
        is not Phase2CertificationState.CERTIFIED
    ):
        raise FutureGraphEntryPreconditionError("Phase 2 is not certified.")
    if validation.validation_state is not ProposalValidationState.VALID:
        raise FutureGraphEntryPreconditionError(
            "Proposal validation is not VALID."
        )
    if source_state.state_classification is not (
        SourceStateClassification.COUNTERFACTUAL
    ):
        raise FutureGraphEntryPreconditionError(
            "Phase 3.1 source state is not counterfactual."
        )
    if (
        source_state_semantic_fingerprint(source_state)
        != source_state.semantic_fingerprint
    ):
        raise FutureGraphEntryPreconditionError(
            "Phase 3.1 fingerprint does not reproduce."
        )
    try:
        validate_counterfactual_source_state(
            source_state,
            snapshot,
            proposal,
            validation,
            contract,
            phase_2_certification,
        )
    except ValueError as exc:
        raise FutureGraphEntryPreconditionError(
            "Phase 3.1 source state is invalid."
        ) from exc
    if (
        snapshot.metadata.demonstration_id
        != proposal.demonstration_id
        or proposal.demonstration_id != CANONICAL_DEMONSTRATION_ID
        or source_state.demonstration_id != CANONICAL_DEMONSTRATION_ID
    ):
        raise FutureGraphEntryPreconditionError(
            "Demonstration identity mismatch."
        )
    if proposal.change_type is not ChangeType.FIELD_RENAME:
        raise FutureGraphEntryPreconditionError(
            "Operation must be FIELD_RENAME."
        )
    if (
        source_state.current_snapshot_fingerprint
        != snapshot.semantic_fingerprint
        or source_state.proposal_fingerprint
        != proposal.semantic_fingerprint
        or source_state.validation_fingerprint
        != validation.semantic_fingerprint
        or source_state.semantic_contract_fingerprint
        != contract.semantic_fingerprint
        or source_state.phase_2_certification_fingerprint
        != phase_2_certification.semantic_fingerprint
    ):
        raise FutureGraphEntryPreconditionError(
            "Authoritative fingerprints do not cross-reference."
        )
    if (
        len(snapshot.datasets) != 21
        or len(snapshot.fields) != 26
        or len(snapshot.lineage_edges) != 27
        or len(snapshot.mapping_groups) != 28
        or len(snapshot.lineage_paths) != 48
        or max(item.lineage_depth for item in snapshot.fields) != 5
    ):
        raise FutureGraphEntryPreconditionError(
            "Certified current graph counts are inconsistent."
        )
    expected_artifacts = {
        "current_metadata_snapshot.json",
        "change_proposal.json",
        "change_proposal_validation.json",
        "change_semantic_contract.json",
        "phase_2_certification.json",
        "counterfactual_source_state.json",
    }
    if (
        {item.artifact_name for item in input_artifact_hashes}
        != expected_artifacts
        or any(not item.unchanged for item in input_artifact_hashes)
    ):
        raise FutureGraphEntryPreconditionError(
            "All six input artifact hashes must be unchanged."
        )


def _state_annotations(
    datasets: list[FutureDataset],
    fields: list[FutureField],
    relationships: list[FutureLineageRelationship],
    mapping_groups: list[FutureMappingGroup],
    paths: list[FutureLineagePath],
    context: list[FutureContextRelationship],
    definitions: list[FutureStructuredPropertyDefinition],
    identity_mappings: list[CurrentToFutureIdentityMapping],
) -> list[GraphStateAnnotation]:
    annotations: list[GraphStateAnnotation] = []
    for item in datasets:
        annotations.append(
            GraphStateAnnotation(
                "dataset",
                item.dataset_urn,
                item.state,
                None,
                None,
                "Dataset identity is inherited from certified current state.",
                item.provenance_ids,
            )
        )
    for item in fields:
        annotations.append(
            GraphStateAnnotation(
                "field",
                item.key.text,
                item.state,
                None,
                (
                    RelationshipEvaluationState.NOT_EVALUATED
                    if item.state is GraphObjectState.COUNTERFACTUAL_UNRESOLVED
                    else None
                ),
                (
                    "Source identity changed by the certified proposal."
                    if item.state is GraphObjectState.COUNTERFACTUAL_CHANGED
                    else (
                        "Identity is preserved; later evaluation has not "
                        "occurred."
                    )
                ),
                item.provenance_ids,
            )
        )
    for item in relationships:
        annotations.append(
            GraphStateAnnotation(
                "lineage_relationship",
                item.relationship_id,
                (
                    GraphObjectState.COUNTERFACTUAL_CHANGED
                    if item.relationship_state
                    is FutureRelationshipState.COUNTERFACTUAL_PROJECTED
                    else GraphObjectState.COUNTERFACTUAL_UNRESOLVED
                ),
                item.relationship_state,
                item.evaluation_state,
                "Structural relationship retained; evaluation not performed.",
                item.provenance_ids,
            )
        )
    for item in mapping_groups:
        annotations.append(
            GraphStateAnnotation(
                "mapping_group",
                item.group_id,
                (
                    GraphObjectState.COUNTERFACTUAL_CHANGED
                    if item.relationship_state
                    is FutureRelationshipState.COUNTERFACTUAL_PROJECTED
                    else GraphObjectState.COUNTERFACTUAL_INHERITED
                ),
                item.relationship_state,
                item.evaluation_state,
                "Current mapping evidence retained with separate projection.",
                item.provenance_ids,
            )
        )
    for item in paths:
        annotations.append(
            GraphStateAnnotation(
                "lineage_path",
                item.path_id,
                GraphObjectState.COUNTERFACTUAL_CHANGED,
                FutureRelationshipState.COUNTERFACTUAL_PROJECTED,
                item.evaluation_state,
                "Current path retained and source identity rebased structurally.",
                item.provenance_ids,
            )
        )
    for item in context:
        annotations.append(
            GraphStateAnnotation(
                "context_relationship",
                item.current_relationship_id,
                item.state,
                FutureRelationshipState.COUNTERFACTUAL_INHERITED,
                None,
                "Current context is attached without transformation.",
                item.provenance_ids,
            )
        )
    for item in definitions:
        annotations.append(
            GraphStateAnnotation(
                "structured_property_definition",
                item.property_urn,
                item.state,
                None,
                None,
                "Current definition is retained without transformation.",
                item.provenance_ids,
            )
        )
    for item in identity_mappings:
        annotations.append(
            GraphStateAnnotation(
                "identity_mapping",
                (
                    f"{item.current_identity.text}->"
                    f"{item.future_identity.text}"
                ),
                (
                    GraphObjectState.COUNTERFACTUAL_CHANGED
                    if item.classification
                    is FutureIdentityMappingClassification.RENAMED
                    else GraphObjectState.COUNTERFACTUAL_INHERITED
                ),
                None,
                RelationshipEvaluationState.NOT_EVALUATED,
                (
                    "Identity mapping records structural identity only; "
                    "compatibility has not been evaluated."
                ),
                item.provenance_ids,
            )
        )
    return annotations


def _project_key(value: FieldMachineKey) -> FieldMachineKey:
    return _FUTURE_SOURCE if value == _CURRENT_SOURCE else value


def _stable_id(prefix: str, value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]
    return f"{prefix}-{digest}"


def _timestamp(clock: Clock | None) -> str:
    value = (clock or (lambda: datetime.now(timezone.utc)))()
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()
