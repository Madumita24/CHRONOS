"""Cycle-safe Phase 3.3 dependency-state propagation."""

from __future__ import annotations

import hashlib
from collections import defaultdict, deque
from dataclasses import dataclass
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
from chronos.future_graph import (
    FutureGraphValidationState,
    FutureLineageRelationship,
    FutureMetadataGraph,
    FutureRelationshipState,
    GraphObjectState,
    ProvenanceKind,
    RelationshipEvaluationState,
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
    RelationshipCategory,
    SnapshotValidationState,
    load_snapshot,
)

from .errors import (
    DependencyPropagationEntryPreconditionError,
    DependencyPropagationValidationError,
)
from .models import (
    DEPENDENCY_PROPAGATION_SCHEMA_VERSION,
    DatasetExposureRecord,
    DatasetExposureState,
    DependencyPathRecord,
    DependencyPropagationResult,
    FieldExposureRecord,
    FieldExposureState,
    PropagationSummary,
    PropagationValidationState,
    RelationshipExposureRecord,
    RelationshipExposureState,
)


Clock = Callable[[], datetime]
_SOURCE = FieldMachineKey(CANONICAL_DATASET_URN, "order_amount")
_CURRENT_SOURCE = FieldMachineKey(CANONICAL_DATASET_URN, "order_total")


@dataclass(frozen=True)
class TraversalPath:
    node_keys: tuple[FieldMachineKey, ...]
    relationship_ids: tuple[str, ...]

    @property
    def target(self) -> FieldMachineKey:
        return self.node_keys[-1]

    @property
    def depth(self) -> int:
        return len(self.relationship_ids)

    @property
    def signature(self) -> str:
        return "|".join(
            tuple(item.text for item in self.node_keys)
            + self.relationship_ids
        )


def propagate_dependencies(
    snapshot: CurrentMetadataSnapshot,
    proposal: ChangeProposal,
    validation: ProposalValidationResult,
    contract: ChangeSemanticContract,
    phase_2_certification: Phase2CertificationResult,
    source_state: CounterfactualSourceState,
    future_graph: FutureMetadataGraph,
    *,
    input_artifact_hashes: tuple[InputArtifactHash, ...],
    clock: Clock | None = None,
) -> DependencyPropagationResult:
    """Propagate dependency exposure without resolving compatibility."""

    _require_entry_preconditions(
        snapshot,
        proposal,
        validation,
        contract,
        phase_2_certification,
        source_state,
        future_graph,
        input_artifact_hashes,
    )
    depths = shortest_dependency_depths(
        _SOURCE,
        future_graph.relationship_registry,
    )
    traversal_paths = enumerate_dependency_paths(
        _SOURCE,
        future_graph.relationship_registry,
    )
    future_paths_by_signature: dict[
        tuple[tuple[FieldMachineKey, ...], tuple[str, ...]],
        str,
    ] = {}
    future_path_provenance: dict[str, tuple[str, ...]] = {}
    for item in sorted(
        future_graph.path_registry,
        key=lambda value: value.path_id,
    ):
        signature = (
            item.projected_node_keys,
            item.projected_relationship_ids,
        )
        future_paths_by_signature.setdefault(signature, item.path_id)
        future_path_provenance[item.path_id] = item.provenance_ids

    provenance_by_id = {
        item.provenance_id: item
        for item in future_graph.provenance_registry
    }

    def split_provenance(
        provenance_ids: Iterable[str],
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        unique = sorted(set(provenance_ids))
        current = tuple(
            value
            for value in unique
            if provenance_by_id[value].kind is ProvenanceKind.CURRENT_EVIDENCE
        )
        counterfactual = tuple(
            value
            for value in unique
            if provenance_by_id[value].kind
            is ProvenanceKind.COUNTERFACTUAL_DERIVATION
        )
        return current, counterfactual

    path_records: list[DependencyPathRecord] = []
    for item in traversal_paths:
        signature = (item.node_keys, item.relationship_ids)
        future_path_id = future_paths_by_signature.get(signature)
        provenance_ids = (
            future_path_provenance.get(future_path_id, ())
            if future_path_id is not None
            else ()
        )
        current_ids, counterfactual_ids = split_provenance(provenance_ids)
        path_records.append(
            DependencyPathRecord(
                path_id=_stable_id("dependency-path", item.signature),
                future_graph_path_id=future_path_id,
                source_field=_SOURCE,
                target_field=item.target,
                node_keys=item.node_keys,
                relationship_ids=item.relationship_ids,
                depth=item.depth,
                current_provenance_ids=current_ids,
                counterfactual_provenance_ids=counterfactual_ids,
            )
        )
    path_records.sort(
        key=lambda item: (
            item.depth,
            item.target_field.dataset_urn,
            item.target_field.field_path,
            item.path_id,
        )
    )
    paths_by_target: dict[FieldMachineKey, list[DependencyPathRecord]] = (
        defaultdict(list)
    )
    paths_by_relationship: dict[str, list[DependencyPathRecord]] = (
        defaultdict(list)
    )
    for item in path_records:
        paths_by_target[item.target_field].append(item)
        for relationship_id in item.relationship_ids:
            paths_by_relationship[relationship_id].append(item)

    graph_fields = {
        item.key: item for item in future_graph.field_registry
    }
    source_field = graph_fields[_SOURCE]
    source_current, source_counterfactual = split_provenance(
        source_field.provenance_ids
    )
    field_records: list[FieldExposureRecord] = [
        FieldExposureRecord(
            field_key=_SOURCE,
            parent_dataset_urn=_SOURCE.dataset_urn,
            identity_state=source_field.state,
            exposure_state=FieldExposureState.SOURCE_CHANGED,
            minimum_depth=0,
            path_count=0,
            supporting_path_ids=(),
            representative_path_id=None,
            incoming_exposed_relationship_ids=(),
            current_provenance_ids=source_current,
            counterfactual_provenance_ids=source_counterfactual,
        )
    ]
    relationships_by_id = {
        item.relationship_id: item
        for item in future_graph.relationship_registry
    }
    for field_key in sorted(
        (value for value in depths if value != _SOURCE),
        key=lambda value: (
            depths[value],
            value.dataset_urn,
            value.field_path,
        ),
    ):
        supporting = sorted(
            paths_by_target[field_key],
            key=lambda item: (item.depth, item.path_id),
        )
        minimum_depth = depths[field_key]
        state = (
            FieldExposureState.MULTIPATH_EXPOSED
            if len(supporting) > 1
            else (
                FieldExposureState.DIRECTLY_EXPOSED
                if minimum_depth == 1
                else FieldExposureState.TRANSITIVELY_EXPOSED
            )
        )
        path_ids = tuple(item.path_id for item in supporting)
        incoming = tuple(
            sorted(
                {
                    item.relationship_ids[-1]
                    for item in supporting
                    if item.relationship_ids
                }
            )
        )
        provenance_ids: set[str] = set(
            graph_fields[field_key].provenance_ids
        )
        for path in supporting:
            provenance_ids.update(path.current_provenance_ids)
            provenance_ids.update(path.counterfactual_provenance_ids)
            for relationship_id in path.relationship_ids:
                provenance_ids.update(
                    relationships_by_id[relationship_id].provenance_ids
                )
        current_ids, counterfactual_ids = split_provenance(provenance_ids)
        field_records.append(
            FieldExposureRecord(
                field_key=field_key,
                parent_dataset_urn=field_key.dataset_urn,
                identity_state=graph_fields[field_key].state,
                exposure_state=state,
                minimum_depth=minimum_depth,
                path_count=len(path_ids),
                supporting_path_ids=path_ids,
                representative_path_id=path_ids[0],
                incoming_exposed_relationship_ids=incoming,
                current_provenance_ids=current_ids,
                counterfactual_provenance_ids=counterfactual_ids,
            )
        )

    fields_by_dataset: dict[str, list[FieldExposureRecord]] = defaultdict(list)
    for item in field_records:
        if (
            item.field_key != _SOURCE
            and item.parent_dataset_urn != _SOURCE.dataset_urn
        ):
            fields_by_dataset[item.parent_dataset_urn].append(item)
    dataset_records: list[DatasetExposureRecord] = []
    for dataset_urn, fields in sorted(fields_by_dataset.items()):
        ordered_fields = sorted(
            fields,
            key=lambda item: (
                item.minimum_depth,
                item.field_key.field_path,
            ),
        )
        minimum_depth = min(item.minimum_depth for item in ordered_fields)
        multipath_count = sum(
            item.exposure_state is FieldExposureState.MULTIPATH_EXPOSED
            for item in ordered_fields
        )
        state = (
            DatasetExposureState.MULTIPATH_EXPOSED_DATASET
            if multipath_count
            else (
                DatasetExposureState.DIRECTLY_EXPOSED_DATASET
                if minimum_depth == 1
                else DatasetExposureState.TRANSITIVELY_EXPOSED_DATASET
            )
        )
        supporting_path_ids = tuple(
            sorted(
                {
                    value
                    for item in ordered_fields
                    for value in item.supporting_path_ids
                }
            )
        )
        dataset_records.append(
            DatasetExposureRecord(
                dataset_urn=dataset_urn,
                exposure_state=state,
                minimum_depth=minimum_depth,
                exposed_field_count=len(ordered_fields),
                multipath_field_count=multipath_count,
                field_keys=tuple(item.field_key for item in ordered_fields),
                path_count=len(supporting_path_ids),
                supporting_path_ids=supporting_path_ids,
            )
        )
    dataset_records.sort(
        key=lambda item: (item.minimum_depth, item.dataset_urn)
    )

    mapping_groups_by_id = {
        item.group_id: item
        for item in future_graph.mapping_group_registry
    }
    relationship_records: list[RelationshipExposureRecord] = []
    for relationship in sorted(
        future_graph.relationship_registry,
        key=lambda item: item.relationship_id,
    ):
        supporting = sorted(
            {
                item.path_id: item
                for item in paths_by_relationship.get(
                    relationship.relationship_id,
                    (),
                )
            }.values(),
            key=lambda item: item.path_id,
        )
        if supporting:
            exposure_state = (
                RelationshipExposureState.SOURCE_REBASED_EDGE
                if (
                    relationship.upstream == _SOURCE
                    and relationship.relationship_state
                    is FutureRelationshipState.COUNTERFACTUAL_PROJECTED
                )
                else RelationshipExposureState.DOWNSTREAM_EXPOSED_EDGE
            )
        else:
            exposure_state = RelationshipExposureState.NOT_EXPOSED_EDGE
        provenance_ids: set[str] = set(relationship.provenance_ids)
        for group_id in relationship.current_mapping_group_ids:
            group = mapping_groups_by_id.get(group_id)
            if group is not None:
                provenance_ids.update(group.provenance_ids)
        for path in supporting:
            provenance_ids.update(path.current_provenance_ids)
            provenance_ids.update(path.counterfactual_provenance_ids)
        current_ids, counterfactual_ids = split_provenance(provenance_ids)
        relationship_records.append(
            RelationshipExposureRecord(
                relationship_id=relationship.relationship_id,
                source_field=relationship.upstream,
                target_field=relationship.downstream,
                exposure_state=exposure_state,
                structural_state=relationship.relationship_state,
                compatibility_state=relationship.evaluation_state,
                mapping_group_ids=relationship.current_mapping_group_ids,
                supporting_path_ids=tuple(
                    item.path_id for item in supporting
                ),
                path_count=len(supporting),
                current_provenance_ids=current_ids,
                counterfactual_provenance_ids=counterfactual_ids,
            )
        )

    downstream_records = tuple(
        item for item in field_records if item.field_key != _SOURCE
    )
    summary = PropagationSummary(
        changed_source_fields=1,
        directly_exposed_fields=sum(
            item.exposure_state is FieldExposureState.DIRECTLY_EXPOSED
            for item in downstream_records
        ),
        transitively_exposed_fields=sum(
            item.exposure_state is FieldExposureState.TRANSITIVELY_EXPOSED
            for item in downstream_records
        ),
        multipath_exposed_fields=sum(
            item.exposure_state is FieldExposureState.MULTIPATH_EXPOSED
            for item in downstream_records
        ),
        total_unique_downstream_exposed_fields=len(downstream_records),
        unique_downstream_exposed_datasets=len(dataset_records),
        maximum_exposure_depth=max(
            item.minimum_depth for item in downstream_records
        ),
        exposed_structural_relationships=sum(
            item.exposure_state
            is not RelationshipExposureState.NOT_EXPOSED_EDGE
            for item in relationship_records
        ),
        processed_structural_relationships=len(relationship_records),
    )
    result = DependencyPropagationResult(
        schema_version=DEPENDENCY_PROPAGATION_SCHEMA_VERSION,
        demonstration_id=CANONICAL_DEMONSTRATION_ID,
        future_graph_fingerprint=future_graph.semantic_fingerprint,
        source_candidate_field=_SOURCE,
        field_exposure_registry=tuple(field_records),
        dataset_exposure_registry=tuple(dataset_records),
        relationship_exposure_registry=tuple(relationship_records),
        path_registry=tuple(path_records),
        summary=summary,
        input_artifact_hashes=input_artifact_hashes,
        validation_state=PropagationValidationState.VALID,
        created_at=_timestamp(clock),
    )
    validate_dependency_propagation(result, future_graph)
    return result


def propagate_dependencies_from_artifacts(
    snapshot_path: str | Path,
    proposal_path: str | Path,
    validation_path: str | Path,
    contract_path: str | Path,
    phase_2_certification_path: str | Path,
    source_state_path: str | Path,
    future_graph_path: str | Path,
    *,
    clock: Clock | None = None,
) -> DependencyPropagationResult:
    paths = (
        ("current_metadata_snapshot.json", Path(snapshot_path)),
        ("change_proposal.json", Path(proposal_path)),
        ("change_proposal_validation.json", Path(validation_path)),
        ("change_semantic_contract.json", Path(contract_path)),
        ("phase_2_certification.json", Path(phase_2_certification_path)),
        ("counterfactual_source_state.json", Path(source_state_path)),
        ("future_metadata_graph.json", Path(future_graph_path)),
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
    future_graph = load_future_graph(future_graph_path)
    after_load = {
        name: hashlib.sha256(path.read_bytes()).hexdigest()
        for name, path in paths
    }
    hashes = tuple(
        InputArtifactHash(name, before[name], after_load[name])
        for name, _ in paths
    )
    result = propagate_dependencies(
        snapshot,
        proposal,
        validation,
        contract,
        phase_2_certification,
        source_state,
        future_graph,
        input_artifact_hashes=hashes,
        clock=clock,
    )
    after_build = {
        name: hashlib.sha256(path.read_bytes()).hexdigest()
        for name, path in paths
    }
    if after_build != before:
        raise DependencyPropagationValidationError(
            "An authoritative artifact changed during propagation."
        )
    return result


def shortest_dependency_depths(
    source: FieldMachineKey,
    relationships: tuple[FutureLineageRelationship, ...],
) -> dict[FieldMachineKey, int]:
    """Return cycle-safe minimum field-lineage depth from the source."""

    adjacency: dict[
        FieldMachineKey,
        list[FutureLineageRelationship],
    ] = defaultdict(list)
    for item in relationships:
        if not isinstance(item, FutureLineageRelationship):
            continue
        adjacency[item.upstream].append(item)
    for values in adjacency.values():
        values.sort(
            key=lambda item: (
                item.downstream.dataset_urn,
                item.downstream.field_path,
                item.relationship_id,
            )
        )
    depths = {source: 0}
    queue = deque([source])
    while queue:
        current = queue.popleft()
        for relationship in adjacency.get(current, ()):
            candidate = relationship.downstream
            if candidate in depths:
                continue
            depths[candidate] = depths[current] + 1
            queue.append(candidate)
    return depths


def enumerate_dependency_paths(
    source: FieldMachineKey,
    relationships: tuple[FutureLineageRelationship, ...],
) -> tuple[TraversalPath, ...]:
    """Enumerate deterministic distinct simple paths without cycling."""

    adjacency: dict[
        FieldMachineKey,
        list[FutureLineageRelationship],
    ] = defaultdict(list)
    for item in relationships:
        if not isinstance(item, FutureLineageRelationship):
            continue
        adjacency[item.upstream].append(item)
    for values in adjacency.values():
        values.sort(
            key=lambda item: (
                item.downstream.dataset_urn,
                item.downstream.field_path,
                item.relationship_id,
            )
        )
    stack: list[
        tuple[
            FieldMachineKey,
            tuple[FieldMachineKey, ...],
            tuple[str, ...],
        ]
    ] = [(source, (source,), ())]
    by_signature: dict[
        tuple[tuple[FieldMachineKey, ...], tuple[str, ...]],
        TraversalPath,
    ] = {}
    while stack:
        current, node_keys, relationship_ids = stack.pop()
        for relationship in reversed(adjacency.get(current, ())):
            if relationship.downstream in node_keys:
                continue
            candidate_nodes = node_keys + (relationship.downstream,)
            candidate_relationships = (
                relationship_ids + (relationship.relationship_id,)
            )
            path = TraversalPath(
                node_keys=candidate_nodes,
                relationship_ids=candidate_relationships,
            )
            by_signature.setdefault(
                (candidate_nodes, candidate_relationships),
                path,
            )
            stack.append(
                (
                    relationship.downstream,
                    candidate_nodes,
                    candidate_relationships,
                )
            )
    return tuple(
        sorted(
            by_signature.values(),
            key=lambda item: (
                item.depth,
                item.target.dataset_urn,
                item.target.field_path,
                item.signature,
            ),
        )
    )


def validate_dependency_propagation(
    result: DependencyPropagationResult,
    future_graph: FutureMetadataGraph,
) -> None:
    """Validate dependency exposure without evaluating compatibility."""

    issues: list[str] = []

    def require(condition: bool, message: str) -> None:
        if not condition:
            issues.append(message)

    require(
        result.future_graph_fingerprint == future_graph.semantic_fingerprint,
        "Future Graph fingerprint mismatch",
    )
    graph_fields = {
        item.key: item for item in future_graph.field_registry
    }
    graph_datasets = {
        item.dataset_urn for item in future_graph.dataset_registry
    }
    graph_relationships = {
        item.relationship_id: item
        for item in future_graph.relationship_registry
    }
    depths = shortest_dependency_depths(
        result.source_candidate_field,
        future_graph.relationship_registry,
    )
    expected_paths = enumerate_dependency_paths(
        result.source_candidate_field,
        future_graph.relationship_registry,
    )
    expected_signatures = {
        (item.node_keys, item.relationship_ids)
        for item in expected_paths
    }
    observed_signatures = {
        (item.node_keys, item.relationship_ids)
        for item in result.path_registry
    }
    require(
        expected_signatures == observed_signatures,
        "Dependency paths do not match structural traversal",
    )
    require(
        len(observed_signatures) == len(result.path_registry),
        "Duplicate dependency path exists",
    )
    field_records = {
        item.field_key: item for item in result.field_exposure_registry
    }
    require(
        set(field_records) == set(depths),
        "Field exposure registry does not match reachable fields",
    )
    for field_key, record in field_records.items():
        require(field_key in graph_fields, "Exposed field is dangling")
        require(
            record.parent_dataset_urn in graph_datasets,
            "Exposed field parent Dataset is dangling",
        )
        require(
            record.identity_state == graph_fields[field_key].state,
            f"Identity state changed: {field_key.text}",
        )
        require(
            record.minimum_depth == depths[field_key],
            f"Minimum depth mismatch: {field_key.text}",
        )
        supporting = tuple(
            item
            for item in result.path_registry
            if item.target_field == field_key
        )
        expected_count = 0 if field_key == _SOURCE else len(supporting)
        require(
            record.path_count == expected_count,
            f"Path count mismatch: {field_key.text}",
        )
        expected_state = (
            FieldExposureState.SOURCE_CHANGED
            if field_key == result.source_candidate_field
            else (
                FieldExposureState.MULTIPATH_EXPOSED
                if expected_count > 1
                else (
                    FieldExposureState.DIRECTLY_EXPOSED
                    if depths[field_key] == 1
                    else FieldExposureState.TRANSITIVELY_EXPOSED
                )
            )
        )
        require(
            record.exposure_state is expected_state,
            f"Field exposure state mismatch: {field_key.text}",
        )
        if field_key != _SOURCE and supporting:
            require(
                min(item.depth for item in supporting)
                == record.minimum_depth,
                f"Shortest path mismatch: {field_key.text}",
            )
    for path in result.path_registry:
        for index, relationship_id in enumerate(path.relationship_ids):
            relationship = graph_relationships.get(relationship_id)
            require(
                relationship is not None,
                f"Path edge is dangling: {relationship_id}",
            )
            if relationship is not None:
                require(
                    relationship.upstream == path.node_keys[index]
                    and relationship.downstream == path.node_keys[index + 1],
                    f"Path edge endpoints mismatch: {relationship_id}",
                )
    future_paths = {
        item.path_id: (
            item.projected_node_keys,
            item.projected_relationship_ids,
        )
        for item in future_graph.path_registry
    }
    for path in result.path_registry:
        require(
            path.future_graph_path_id in future_paths,
            f"Future Graph path provenance is missing: {path.path_id}",
        )
        if path.future_graph_path_id in future_paths:
            require(
                future_paths[path.future_graph_path_id]
                == (path.node_keys, path.relationship_ids),
                f"Future Graph path provenance mismatch: {path.path_id}",
            )
    relationship_records = {
        item.relationship_id: item
        for item in result.relationship_exposure_registry
    }
    require(
        set(relationship_records) == set(graph_relationships),
        "Relationship exposure registry is incomplete",
    )
    for relationship_id, record in relationship_records.items():
        graph_record = graph_relationships[relationship_id]
        require(
            record.source_field == graph_record.upstream
            and record.target_field == graph_record.downstream,
            f"Relationship identity changed: {relationship_id}",
        )
        require(
            record.structural_state == graph_record.relationship_state,
            f"Structural relationship state changed: {relationship_id}",
        )
        require(
            record.compatibility_state
            is RelationshipEvaluationState.NOT_EVALUATED
            and graph_record.evaluation_state
            is RelationshipEvaluationState.NOT_EVALUATED,
            f"Compatibility was resolved: {relationship_id}",
        )
        expected_path_count = sum(
            relationship_id in item.relationship_ids
            for item in result.path_registry
        )
        require(
            record.path_count == expected_path_count,
            f"Relationship path count mismatch: {relationship_id}",
        )
        expected_exposure_state = (
            RelationshipExposureState.NOT_EXPOSED_EDGE
            if expected_path_count == 0
            else (
                RelationshipExposureState.SOURCE_REBASED_EDGE
                if (
                    graph_record.upstream == result.source_candidate_field
                    and graph_record.relationship_state
                    is FutureRelationshipState.COUNTERFACTUAL_PROJECTED
                )
                else RelationshipExposureState.DOWNSTREAM_EXPOSED_EDGE
            )
        )
        require(
            record.exposure_state is expected_exposure_state,
            f"Relationship exposure state mismatch: {relationship_id}",
        )
    downstream = tuple(
        item
        for item in result.field_exposure_registry
        if item.field_key != result.source_candidate_field
    )
    require(
        all(item.field_key != _CURRENT_SOURCE for item in downstream),
        "Current source identity was propagated as active",
    )
    current_downstream = {
        item.key
        for item in future_graph.field_registry
        if item.key != _SOURCE
    }
    require(
        {item.field_key for item in downstream} == current_downstream,
        "A downstream identity was renamed, added, or removed",
    )
    expected_dataset_urns = {
        item.field_key.dataset_urn
        for item in downstream
        if item.field_key.dataset_urn != result.source_candidate_field.dataset_urn
    }
    require(
        {
            item.dataset_urn for item in result.dataset_exposure_registry
        }
        == expected_dataset_urns,
        "Dataset exposure is not derived from exposed fields",
    )
    fields_by_dataset: dict[str, list[FieldExposureRecord]] = defaultdict(list)
    for field_record in downstream:
        if (
            field_record.parent_dataset_urn
            != result.source_candidate_field.dataset_urn
        ):
            fields_by_dataset[field_record.parent_dataset_urn].append(
                field_record
            )
    for dataset_record in result.dataset_exposure_registry:
        fields = fields_by_dataset[dataset_record.dataset_urn]
        minimum_depth = min(item.minimum_depth for item in fields)
        multipath_count = sum(
            item.exposure_state is FieldExposureState.MULTIPATH_EXPOSED
            for item in fields
        )
        expected_dataset_state = (
            DatasetExposureState.MULTIPATH_EXPOSED_DATASET
            if multipath_count
            else (
                DatasetExposureState.DIRECTLY_EXPOSED_DATASET
                if minimum_depth == 1
                else DatasetExposureState.TRANSITIVELY_EXPOSED_DATASET
            )
        )
        require(
            dataset_record.exposure_state is expected_dataset_state,
            f"Dataset exposure state mismatch: {dataset_record.dataset_urn}",
        )
        require(
            dataset_record.minimum_depth == minimum_depth
            and dataset_record.exposed_field_count == len(fields)
            and dataset_record.multipath_field_count == multipath_count,
            f"Dataset exposure summary mismatch: {dataset_record.dataset_urn}",
        )
    context_ids = {
        item.current_relationship_id
        for item in future_graph.context_relationship_registry
    }
    require(
        all(
            relationship_id not in context_ids
            for path in result.path_registry
            for relationship_id in path.relationship_ids
        ),
        "A context relationship was used for propagation",
    )
    require(
        result.summary.changed_source_fields == 1,
        "Changed source count is invalid",
    )
    require(
        result.summary.directly_exposed_fields
        == sum(
            item.exposure_state is FieldExposureState.DIRECTLY_EXPOSED
            for item in downstream
        ),
        "Direct exposure summary is inconsistent",
    )
    require(
        result.summary.transitively_exposed_fields
        == sum(
            item.exposure_state is FieldExposureState.TRANSITIVELY_EXPOSED
            for item in downstream
        ),
        "Transitive exposure summary is inconsistent",
    )
    require(
        result.summary.multipath_exposed_fields
        == sum(
            item.exposure_state is FieldExposureState.MULTIPATH_EXPOSED
            for item in downstream
        ),
        "Multipath exposure summary is inconsistent",
    )
    require(
        result.summary.total_unique_downstream_exposed_fields
        == len(downstream),
        "Downstream exposure summary is inconsistent",
    )
    require(
        result.summary.unique_downstream_exposed_datasets
        == len(expected_dataset_urns),
        "Dataset exposure summary is inconsistent",
    )
    require(
        result.summary.maximum_exposure_depth
        == max(item.minimum_depth for item in downstream),
        "Maximum exposure depth is inconsistent",
    )
    require(
        result.summary.exposed_structural_relationships
        == sum(
            item.exposure_state
            is not RelationshipExposureState.NOT_EXPOSED_EDGE
            for item in result.relationship_exposure_registry
        ),
        "Exposed relationship summary is inconsistent",
    )
    require(
        result.summary.processed_structural_relationships
        == len(future_graph.relationship_registry),
        "Processed relationship count is inconsistent",
    )
    require(
        len(downstream) == 25,
        "Canonical downstream exposure baseline is not 25",
    )
    require(
        len(expected_dataset_urns) == 20,
        "Canonical downstream Dataset baseline is not 20",
    )
    require(
        result.summary.maximum_exposure_depth == 5,
        "Canonical maximum exposure depth is not 5",
    )
    forbidden = {
        "broken",
        "impacted",
        "compatible",
        "incompatible",
        "safe",
        "risk",
        "repair_required",
        "requires_repair",
    }
    generated_states = {
        item.exposure_state.value
        for item in result.field_exposure_registry
    } | {
        item.exposure_state.value
        for item in result.dataset_exposure_registry
    } | {
        item.exposure_state.value
        for item in result.relationship_exposure_registry
    } | {
        item.compatibility_state.value
        for item in result.relationship_exposure_registry
    }
    require(
        generated_states.isdisjoint(forbidden),
        "A prohibited impact, compatibility, or repair state exists",
    )
    require(
        all(item.unchanged for item in result.input_artifact_hashes),
        "An authoritative artifact hash changed",
    )
    if issues:
        raise DependencyPropagationValidationError("; ".join(issues))


def _require_entry_preconditions(
    snapshot: CurrentMetadataSnapshot,
    proposal: ChangeProposal,
    validation: ProposalValidationResult,
    contract: ChangeSemanticContract,
    phase_2_certification: Phase2CertificationResult,
    source_state: CounterfactualSourceState,
    future_graph: FutureMetadataGraph,
    input_artifact_hashes: tuple[InputArtifactHash, ...],
) -> None:
    if snapshot.validation_result.state is not SnapshotValidationState.VALID:
        raise DependencyPropagationEntryPreconditionError(
            "Phase 1 is not certified."
        )
    if (
        phase_2_certification.certification_state
        is not Phase2CertificationState.CERTIFIED
    ):
        raise DependencyPropagationEntryPreconditionError(
            "Phase 2 is not certified."
        )
    if validation.validation_state is not ProposalValidationState.VALID:
        raise DependencyPropagationEntryPreconditionError(
            "Phase 2 proposal validation is not VALID."
        )
    if (
        source_state.state_classification
        is not SourceStateClassification.COUNTERFACTUAL
        or source_state_semantic_fingerprint(source_state)
        != source_state.semantic_fingerprint
    ):
        raise DependencyPropagationEntryPreconditionError(
            "Phase 3.1 is not valid."
        )
    if (
        future_graph.validation_state
        is not FutureGraphValidationState.VALID
        or future_graph_semantic_fingerprint(future_graph)
        != future_graph.semantic_fingerprint
    ):
        raise DependencyPropagationEntryPreconditionError(
            "Phase 3.2 is not valid."
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
        validate_future_metadata_graph(
            future_graph,
            snapshot,
            proposal,
            validation,
            contract,
            phase_2_certification,
            source_state,
        )
    except ValueError as exc:
        raise DependencyPropagationEntryPreconditionError(
            "The certified artifact chain is invalid."
        ) from exc
    if (
        snapshot.metadata.demonstration_id
        != CANONICAL_DEMONSTRATION_ID
        or proposal.demonstration_id != CANONICAL_DEMONSTRATION_ID
        or source_state.demonstration_id != CANONICAL_DEMONSTRATION_ID
        or future_graph.demonstration_id != CANONICAL_DEMONSTRATION_ID
    ):
        raise DependencyPropagationEntryPreconditionError(
            "Demonstration identity mismatch."
        )
    if proposal.change_type is not ChangeType.FIELD_RENAME:
        raise DependencyPropagationEntryPreconditionError(
            "Operation must be FIELD_RENAME."
        )
    if future_graph.source_schema != source_state.candidate_source_schema:
        raise DependencyPropagationEntryPreconditionError(
            "Candidate source schema mismatch."
        )
    source_fields = tuple(
        item for item in future_graph.field_registry if item.key == _SOURCE
    )
    if (
        len(source_fields) != 1
        or source_fields[0].state
        is not GraphObjectState.COUNTERFACTUAL_CHANGED
    ):
        raise DependencyPropagationEntryPreconditionError(
            "Candidate source identity is invalid."
        )
    if (
        future_graph.current_snapshot_fingerprint
        != snapshot.semantic_fingerprint
        or future_graph.proposal_fingerprint
        != proposal.semantic_fingerprint
        or future_graph.validation_fingerprint
        != validation.semantic_fingerprint
        or future_graph.semantic_contract_fingerprint
        != contract.semantic_fingerprint
        or future_graph.phase_2_certification_fingerprint
        != phase_2_certification.semantic_fingerprint
        or future_graph.counterfactual_source_state_fingerprint
        != source_state.semantic_fingerprint
    ):
        raise DependencyPropagationEntryPreconditionError(
            "Artifact semantic fingerprints do not cross-reference."
        )
    if any(
        item.evaluation_state
        is not RelationshipEvaluationState.NOT_EVALUATED
        for item in future_graph.relationship_registry
    ):
        raise DependencyPropagationEntryPreconditionError(
            "Phase 3.2 compatibility state was changed."
        )
    endpoint_pairs = tuple(
        (item.upstream, item.downstream)
        for item in future_graph.relationship_registry
    )
    if len(endpoint_pairs) != len(set(endpoint_pairs)):
        raise DependencyPropagationEntryPreconditionError(
            "Duplicate structural edge endpoints are not allowed."
        )
    expected_artifacts = {
        "current_metadata_snapshot.json",
        "change_proposal.json",
        "change_proposal_validation.json",
        "change_semantic_contract.json",
        "phase_2_certification.json",
        "counterfactual_source_state.json",
        "future_metadata_graph.json",
    }
    if (
        {item.artifact_name for item in input_artifact_hashes}
        != expected_artifacts
        or any(not item.unchanged for item in input_artifact_hashes)
    ):
        raise DependencyPropagationEntryPreconditionError(
            "All seven authoritative artifact hashes must be unchanged."
        )


def _stable_id(prefix: str, value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]
    return f"{prefix}-{digest}"


def _timestamp(clock: Clock | None) -> str:
    value = (clock or (lambda: datetime.now(timezone.utc)))()
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()
