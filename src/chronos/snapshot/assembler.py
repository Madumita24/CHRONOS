"""Pure composition of authoritative Phase 1.1-1.5 outputs."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Callable, Iterable

from chronos.context.models import (
    AssetContextSnapshot,
    AssignmentScope,
    ContextEvidence,
    ContextRetrievalResult,
    ContextRetrievalState,
)
from chronos.datahub.models import ReadinessResult, ReadinessState
from chronos.lineage.models import (
    FieldKey,
    FieldLineageGraph,
    LineageRetrievalResult,
    LineageRetrievalState,
)
from chronos.resolution.models import (
    DatasetResolutionResult,
    FieldResolutionResult,
    ResolutionState,
)
from chronos.schema.models import (
    DatasetSchemaSnapshot,
    SchemaRetrievalResult,
    SchemaRetrievalState,
)

from .models import (
    CurrentMetadataSnapshot,
    EvidenceClassification,
    FieldMachineKey,
    RelationshipCategory,
    SnapshotAttribute,
    SnapshotBuildResult,
    SnapshotBuildState,
    SnapshotDataset,
    SnapshotEnvironment,
    SnapshotEvidence,
    SnapshotField,
    SnapshotLineageEdge,
    SnapshotLineagePath,
    SnapshotMappingGroup,
    SnapshotMetadata,
    SnapshotRelationship,
    SnapshotSchemaField,
    SnapshotStructuredPropertyDefinition,
    SnapshotValidationFinding,
    SnapshotValidationResult,
    SnapshotValidationState,
    SourceSchema,
)
from .serialization import semantic_fingerprint
from .validation import validate_snapshot


Clock = Callable[[], datetime]
DEMONSTRATION_ID = "CHRONOS-DEMO-001"
SNAPSHOT_SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class SnapshotCompositionInputs:
    readiness: ReadinessResult
    dataset_resolution: DatasetResolutionResult
    field_resolution: FieldResolutionResult
    schema_retrieval: SchemaRetrievalResult
    lineage_retrieval: LineageRetrievalResult
    context_retrieval: ContextRetrievalResult


class _EvidenceRegistry:
    def __init__(self) -> None:
        self._items: dict[str, SnapshotEvidence] = {}

    def add(
        self,
        *,
        classification: EvidenceClassification,
        source_phase: str,
        subject_key: str,
        interface: str,
        aspect_or_relationship: str,
        source_urn: str | None = None,
        target_urn: str | None = None,
        relationship_path: tuple[str, ...] = (),
        observed_at: str | None = None,
        attributes: tuple[SnapshotAttribute, ...] = (),
    ) -> str:
        semantic = {
            "classification": classification.value,
            "source_phase": source_phase,
            "subject_key": subject_key,
            "interface": interface,
            "aspect_or_relationship": aspect_or_relationship,
            "source_urn": source_urn,
            "target_urn": target_urn,
            "relationship_path": relationship_path,
            "attributes": [
                (item.name, item.values) for item in attributes
            ],
        }
        evidence_id = _stable_id("evidence", semantic)
        self._items.setdefault(
            evidence_id,
            SnapshotEvidence(
                evidence_id=evidence_id,
                classification=classification,
                source_phase=source_phase,
                subject_key=subject_key,
                interface=interface,
                aspect_or_relationship=aspect_or_relationship,
                source_urn=source_urn,
                target_urn=target_urn,
                relationship_path=relationship_path,
                observed_at=observed_at,
                attributes=attributes,
            ),
        )
        return evidence_id

    def context(self, evidence: ContextEvidence, subject_key: str) -> str:
        return self.add(
            classification=EvidenceClassification.VERIFIED,
            source_phase="1.5",
            subject_key=subject_key,
            interface=evidence.interface,
            aspect_or_relationship=evidence.aspect_or_relationship,
            source_urn=evidence.source_urn,
            target_urn=evidence.target_urn,
            relationship_path=evidence.relationship_path,
            observed_at=evidence.observed_at,
        )

    def values(self) -> tuple[SnapshotEvidence, ...]:
        return tuple(
            sorted(self._items.values(), key=lambda item: item.evidence_id)
        )


class CurrentMetadataSnapshotAssembler:
    """Compose verified public results without making any metadata request."""

    def __init__(self, *, clock: Clock | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def assemble(
        self,
        inputs: SnapshotCompositionInputs,
    ) -> SnapshotBuildResult:
        input_findings = _validate_inputs(inputs)
        if input_findings:
            return SnapshotBuildResult(
                state=SnapshotBuildState.INVALID_INPUT,
                snapshot=None,
                findings=input_findings,
            )

        readiness = inputs.readiness
        dataset_resolution = inputs.dataset_resolution
        field_resolution = inputs.field_resolution
        schema_result = inputs.schema_retrieval
        lineage_result = inputs.lineage_retrieval
        context_result = inputs.context_retrieval
        assert dataset_resolution.resolved is not None
        assert field_resolution.resolved is not None
        assert schema_result.snapshot is not None
        assert lineage_result.graph is not None
        assert context_result.snapshot is not None

        schema = schema_result.snapshot
        graph = lineage_result.graph
        context = context_result.snapshot
        evidence = _EvidenceRegistry()

        readiness_evidence = evidence.add(
            classification=EvidenceClassification.VERIFIED,
            source_phase="1.1",
            subject_key=dataset_resolution.resolved.urn,
            interface="ChronosDataHubAccess.check_readiness",
            aspect_or_relationship="readiness_and_capabilities",
            source_urn=dataset_resolution.resolved.urn,
            observed_at=None,
            attributes=_attributes(
                readiness_state=readiness.state.value,
                can_continue=readiness.can_continue,
                gms_version=readiness.environment.observed_gms_version,
                sdk_version=readiness.environment.observed_sdk_version,
                server_type=readiness.environment.server_type,
                server_environment=readiness.environment.server_environment,
            ),
        )
        dataset_evidence = _resolution_evidence(
            evidence,
            dataset_resolution.evidence,
            "1.2",
            dataset_resolution.resolved.urn,
        )
        source_key = FieldMachineKey(
            field_resolution.resolved.parent_dataset_urn,
            field_resolution.resolved.field_path,
        )
        field_evidence = _resolution_evidence(
            evidence,
            field_resolution.evidence,
            "1.2",
            source_key.text,
        )
        schema_evidence = evidence.add(
            classification=EvidenceClassification.VERIFIED,
            source_phase="1.3",
            subject_key=schema.dataset_urn,
            interface=schema.evidence.interface,
            aspect_or_relationship=schema.evidence.aspect,
            source_urn=schema.dataset_urn,
            observed_at=schema.evidence.observed_at,
            attributes=_attributes(
                schema_name=schema.evidence.schema_name,
                schema_version=schema.evidence.schema_version,
                schema_hash=schema.evidence.schema_hash,
                field_count=schema.evidence.field_count,
                validation_state=schema.evidence.validation_state.value,
            ),
        )
        graph_evidence = evidence.add(
            classification=EvidenceClassification.VERIFIED,
            source_phase="1.4",
            subject_key=source_key.text,
            interface=";".join(graph.evidence.interfaces),
            aspect_or_relationship="field_lineage_graph",
            source_urn=source_key.dataset_urn,
            observed_at=graph.evidence.observed_at,
            attributes=_attributes(
                candidate_dataset_count=graph.evidence.candidate_dataset_count,
                aspect_entity_count=graph.evidence.aspect_entity_count,
                mapping_group_count=graph.evidence.mapping_group_count,
                explicit_edge_count=graph.evidence.explicit_edge_count,
                downstream_field_count=graph.evidence.downstream_field_count,
                downstream_dataset_count=graph.evidence.downstream_dataset_count,
                maximum_field_depth=graph.evidence.maximum_field_depth,
                validation_state=graph.evidence.validation_state.value,
            ),
        )

        mapping_groups, mapping_evidence = _mapping_groups(
            graph,
            evidence,
        )
        lineage_edges, edge_id_by_key = _lineage_edges(
            graph,
            graph_evidence,
            mapping_evidence,
        )
        lineage_paths = _lineage_paths(graph, edge_id_by_key)
        source_schema = _source_schema(schema, schema_evidence)
        relationships = _context_relationships(
            graph,
            context,
            evidence,
            lineage_edges,
        )
        structured_definitions = _structured_definitions(context, evidence)
        fields = _field_registry(
            graph,
            schema,
            graph_evidence,
            schema_evidence,
            field_evidence,
            mapping_evidence,
        )
        datasets = _dataset_registry(
            graph,
            context,
            schema,
            dataset_resolution.resolved.qualified_name,
            dataset_resolution.resolved.logical_name,
            relationships,
            evidence,
            graph_evidence,
            dataset_evidence,
            readiness_evidence,
        )

        created_at = _timestamp(self._clock)
        configuration_source = (
            readiness.configuration_source.value
            if readiness.configuration_source is not None
            else "unknown"
        )
        metadata = SnapshotMetadata(
            snapshot_id="",
            demonstration_id=DEMONSTRATION_ID,
            snapshot_schema_version=SNAPSHOT_SCHEMA_VERSION,
            created_at=created_at,
            environment=SnapshotEnvironment(
                endpoint=readiness.environment.endpoint,
                gms_version=readiness.environment.observed_gms_version,
                sdk_version=readiness.environment.observed_sdk_version,
                server_type=readiness.environment.server_type,
                server_environment=readiness.environment.server_environment,
                configuration_source=configuration_source,
                authentication_state=readiness.authentication.state.value,
            ),
            source_phase_results=_attributes(
                phase_1_1=readiness.state.value,
                phase_1_2_dataset=dataset_resolution.state.value,
                phase_1_2_field=field_resolution.state.value,
                phase_1_3=schema_result.state.value,
                phase_1_4=lineage_result.state.value,
                phase_1_5=context_result.state.value,
            ),
        )
        placeholder_validation = SnapshotValidationResult(
            state=SnapshotValidationState.VALID,
            checked_invariants=(),
            findings=(),
        )
        candidate = CurrentMetadataSnapshot(
            metadata=metadata,
            source_dataset_urn=dataset_resolution.resolved.urn,
            source_field_key=source_key,
            source_schema=source_schema,
            datasets=datasets,
            fields=fields,
            lineage_edges=lineage_edges,
            mapping_groups=mapping_groups,
            structured_property_definitions=structured_definitions,
            lineage_paths=lineage_paths,
            relationships=relationships,
            evidence=evidence.values(),
            validation_result=placeholder_validation,
            semantic_fingerprint="",
        )
        fingerprint = semantic_fingerprint(candidate)
        snapshot_id = _stable_id(
            "snapshot",
            {
                "demonstration_id": DEMONSTRATION_ID,
                "created_at": created_at,
                "environment": readiness.environment.endpoint,
                "semantic_fingerprint": fingerprint,
            },
        )
        candidate = replace(
            candidate,
            metadata=replace(metadata, snapshot_id=snapshot_id),
            semantic_fingerprint=fingerprint,
        )
        validation = validate_snapshot(candidate)
        snapshot = replace(candidate, validation_result=validation)
        return SnapshotBuildResult(
            state=(
                SnapshotBuildState.VALIDATED
                if validation.state is SnapshotValidationState.VALID
                else SnapshotBuildState.INVALID_SNAPSHOT
            ),
            snapshot=snapshot,
            findings=validation.findings,
        )


def _validate_inputs(
    inputs: SnapshotCompositionInputs,
) -> tuple[SnapshotValidationFinding, ...]:
    findings: list[SnapshotValidationFinding] = []

    def require(invariant: str, condition: bool, expected: str, observed: str):
        if not condition:
            findings.append(
                SnapshotValidationFinding(
                    invariant=invariant,
                    expected=expected,
                    observed=observed,
                    evidence_ids=(),
                )
            )

    require(
        "phase_1_1_ready",
        inputs.readiness.state is ReadinessState.READY
        and inputs.readiness.can_continue,
        "ready and can_continue=true",
        f"{inputs.readiness.state.value}; "
        f"can_continue={inputs.readiness.can_continue}",
    )
    require(
        "phase_1_2_dataset_resolved",
        inputs.dataset_resolution.state is ResolutionState.RESOLVED
        and inputs.dataset_resolution.resolved is not None,
        ResolutionState.RESOLVED.value,
        inputs.dataset_resolution.state.value,
    )
    require(
        "phase_1_2_field_resolved",
        inputs.field_resolution.state is ResolutionState.RESOLVED
        and inputs.field_resolution.resolved is not None,
        ResolutionState.RESOLVED.value,
        inputs.field_resolution.state.value,
    )
    require(
        "phase_1_3_schema_retrieved",
        inputs.schema_retrieval.state is SchemaRetrievalState.RETRIEVED
        and inputs.schema_retrieval.snapshot is not None,
        SchemaRetrievalState.RETRIEVED.value,
        inputs.schema_retrieval.state.value,
    )
    require(
        "phase_1_4_lineage_retrieved",
        inputs.lineage_retrieval.state is LineageRetrievalState.RETRIEVED
        and inputs.lineage_retrieval.graph is not None,
        LineageRetrievalState.RETRIEVED.value,
        inputs.lineage_retrieval.state.value,
    )
    require(
        "phase_1_5_context_retrieved",
        inputs.context_retrieval.state is ContextRetrievalState.RETRIEVED
        and inputs.context_retrieval.snapshot is not None,
        ContextRetrievalState.RETRIEVED.value,
        inputs.context_retrieval.state.value,
    )
    if (
        inputs.lineage_retrieval.graph is not None
        and inputs.context_retrieval.snapshot is not None
    ):
        require(
            "phase_1_5_context_bound_to_lineage_source",
            inputs.context_retrieval.snapshot.source_field
            == inputs.lineage_retrieval.graph.source.key,
            str(inputs.lineage_retrieval.graph.source.key),
            str(inputs.context_retrieval.snapshot.source_field),
        )
    if (
        inputs.field_resolution.resolved is not None
        and inputs.lineage_retrieval.graph is not None
    ):
        resolved_key = (
            inputs.field_resolution.resolved.parent_dataset_urn,
            inputs.field_resolution.resolved.field_path,
        )
        require(
            "phase_1_4_source_matches_resolved_field",
            resolved_key == inputs.lineage_retrieval.graph.source.key,
            str(resolved_key),
            str(inputs.lineage_retrieval.graph.source.key),
        )
    if (
        inputs.dataset_resolution.resolved is not None
        and inputs.schema_retrieval.snapshot is not None
    ):
        require(
            "phase_1_3_schema_matches_resolved_dataset",
            inputs.dataset_resolution.resolved.urn
            == inputs.schema_retrieval.snapshot.dataset_urn,
            inputs.dataset_resolution.resolved.urn,
            inputs.schema_retrieval.snapshot.dataset_urn,
        )
    return tuple(
        sorted(findings, key=lambda item: item.invariant)
    )


def _resolution_evidence(
    registry: _EvidenceRegistry,
    source: object,
    phase: str,
    subject_key: str,
) -> str:
    if source is None:
        return registry.add(
            classification=EvidenceClassification.UNKNOWN,
            source_phase=phase,
            subject_key=subject_key,
            interface="unknown",
            aspect_or_relationship="resolution_evidence_absent",
        )
    return registry.add(
        classification=EvidenceClassification.VERIFIED,
        source_phase=phase,
        subject_key=subject_key,
        interface=";".join(source.interfaces),
        aspect_or_relationship=source.method,
        source_urn=source.resolved_urn,
        observed_at=source.observed_at,
        attributes=_attributes(
            canonical_request=source.canonical_request,
            snapshot_context=source.snapshot_context,
        ),
    )


def _mapping_groups(
    graph: FieldLineageGraph,
    registry: _EvidenceRegistry,
) -> tuple[tuple[SnapshotMappingGroup, ...], dict[str, str]]:
    records: list[SnapshotMappingGroup] = []
    evidence_ids: dict[str, str] = {}
    for item in sorted(graph.mapping_groups, key=lambda group: group.group_id):
        evidence_id = registry.add(
            classification=EvidenceClassification.VERIFIED,
            source_phase="1.4",
            subject_key=item.group_id,
            interface=item.source_interface,
            aspect_or_relationship=item.source_aspect,
            source_urn=item.source_entity_urn,
            observed_at=item.observed_at,
            attributes=_attributes(
                source_entity_type=item.source_entity_type,
                source_group_index=item.source_group_index,
                expansion_state=item.expansion_state.value,
                confidence_score=item.confidence_score,
                transform_operation=item.transform_operation,
            ),
        )
        evidence_ids[item.group_id] = evidence_id
        records.append(
            SnapshotMappingGroup(
                group_id=item.group_id,
                source_entity_urn=item.source_entity_urn,
                source_entity_type=item.source_entity_type,
                source_aspect=item.source_aspect,
                source_interface=item.source_interface,
                source_group_index=item.source_group_index,
                upstream_type=item.upstream_type,
                downstream_type=item.downstream_type,
                raw_upstream_references=item.raw_upstream_references,
                raw_downstream_references=item.raw_downstream_references,
                upstream_fields=tuple(
                    sorted(
                        FieldMachineKey(*field.key)
                        for field in item.upstream_fields
                    )
                ),
                downstream_fields=tuple(
                    sorted(
                        FieldMachineKey(*field.key)
                        for field in item.downstream_fields
                    )
                ),
                transform_operation=item.transform_operation,
                confidence_score=item.confidence_score,
                query=item.query,
                match_type=item.match_type,
                expansion_state=item.expansion_state.value,
                ambiguity_reason=item.ambiguity_reason,
                evidence_ids=(evidence_id,),
            )
        )
    return tuple(records), evidence_ids


def _lineage_edges(
    graph: FieldLineageGraph,
    graph_evidence: str,
    mapping_evidence: dict[str, str],
) -> tuple[
    tuple[SnapshotLineageEdge, ...],
    dict[tuple[FieldKey, FieldKey], str],
]:
    records: list[SnapshotLineageEdge] = []
    edge_ids: dict[tuple[FieldKey, FieldKey], str] = {}
    for item in sorted(graph.edges, key=lambda edge: edge.key):
        edge_id = _stable_id(
            "lineage-edge",
            {"upstream": item.upstream.key, "downstream": item.downstream.key},
        )
        edge_ids[item.key] = edge_id
        records.append(
            SnapshotLineageEdge(
                edge_id=edge_id,
                upstream=FieldMachineKey(*item.upstream.key),
                downstream=FieldMachineKey(*item.downstream.key),
                classification=item.classification.value,
                mapping_group_ids=item.mapping_group_ids,
                source_entity_urns=item.source_entity_urns,
                source_aspects=item.source_aspects,
                transform_operations=item.transform_operations,
                confidence_scores=item.confidence_scores,
                evidence_ids=tuple(
                    sorted(
                        {
                            graph_evidence,
                            *(
                                mapping_evidence[group_id]
                                for group_id in item.mapping_group_ids
                            ),
                        }
                    )
                ),
            )
        )
    return tuple(records), edge_ids


def _lineage_paths(
    graph: FieldLineageGraph,
    edge_ids: dict[tuple[FieldKey, FieldKey], str],
) -> tuple[SnapshotLineagePath, ...]:
    return tuple(
        sorted(
            (
                SnapshotLineagePath(
                    node_keys=tuple(
                        FieldMachineKey(*item.key) for item in path.nodes
                    ),
                    edge_ids=tuple(edge_ids[key] for key in path.edge_keys),
                )
                for path in graph.paths
            ),
            key=lambda path: (
                tuple(key.text for key in path.node_keys),
                path.edge_ids,
            ),
        )
    )


def _source_schema(
    schema: DatasetSchemaSnapshot,
    evidence_id: str,
) -> SourceSchema:
    return SourceSchema(
        dataset_urn=schema.dataset_urn,
        schema_name=schema.schema_name,
        platform=schema.platform,
        source_platform=schema.source_platform,
        environment=schema.environment,
        schema_version=schema.schema_version,
        schema_hash=schema.schema_hash,
        fields=tuple(
            SnapshotSchemaField(
                position=item.position,
                field_path=item.field_path,
                field_name=item.field_name,
                native_type=item.native_type,
                normalized_type=item.normalized_type.value,
                datahub_type=item.datahub_type,
                description=item.description,
                nullable=item.nullable,
                is_part_of_key=item.is_part_of_key,
                is_partitioning_key=item.is_partitioning_key,
                json_path=item.json_path,
                label=item.label,
                recursive=item.recursive,
                schema_field_urn=item.schema_field_urn,
                evidence_ids=(evidence_id,),
            )
            for item in schema.fields
        ),
        created_time=schema.created_time,
        last_modified_time=schema.last_modified_time,
        dataset_reference=schema.dataset_reference,
        cluster=schema.cluster,
        primary_keys=schema.primary_keys,
        evidence_ids=(evidence_id,),
    )


def _field_registry(
    graph: FieldLineageGraph,
    schema: DatasetSchemaSnapshot,
    graph_evidence: str,
    schema_evidence: str,
    field_evidence: str,
    mapping_evidence: dict[str, str],
) -> tuple[SnapshotField, ...]:
    schema_fields = {item.field_path: item for item in schema.fields}
    evidence_by_field: dict[FieldKey, set[str]] = {
        node.reference.key: {graph_evidence} for node in graph.nodes
    }
    for group in graph.mapping_groups:
        group_evidence = mapping_evidence[group.group_id]
        for reference in (*group.upstream_fields, *group.downstream_fields):
            evidence_by_field.setdefault(reference.key, set()).add(
                group_evidence
            )
    records: list[SnapshotField] = []
    for node in sorted(graph.nodes, key=lambda item: item.reference.key):
        reference = node.reference
        observed_schema = (
            schema_fields.get(reference.field_path)
            if reference.dataset_urn == schema.dataset_urn
            else None
        )
        ids = evidence_by_field.get(reference.key, {graph_evidence})
        if reference.key == graph.source.key:
            ids.update({schema_evidence, field_evidence})
        records.append(
            SnapshotField(
                key=FieldMachineKey(*reference.key),
                field_name=reference.field_name,
                platform=reference.platform,
                dataset_name=reference.dataset_name,
                environment=reference.environment,
                native_type=(
                    observed_schema.native_type if observed_schema else None
                ),
                normalized_type=(
                    observed_schema.normalized_type.value
                    if observed_schema
                    else None
                ),
                schema_position=(
                    observed_schema.position if observed_schema else None
                ),
                description=(
                    observed_schema.description if observed_schema else None
                ),
                nullable=(
                    observed_schema.nullable if observed_schema else None
                ),
                is_part_of_key=(
                    observed_schema.is_part_of_key if observed_schema else None
                ),
                is_partitioning_key=(
                    observed_schema.is_partitioning_key
                    if observed_schema
                    else None
                ),
                schema_field_urn=reference.schema_field_urn
                or (
                    observed_schema.schema_field_urn
                    if observed_schema
                    else None
                ),
                reference_resolution=reference.resolution.value,
                lineage_depth=node.depth,
                path_count=node.path_count,
                paths_truncated=node.paths_truncated,
                evidence_ids=tuple(sorted(ids)),
            )
        )
    return tuple(records)


def _structured_definitions(
    context: AssetContextSnapshot,
    registry: _EvidenceRegistry,
) -> tuple[SnapshotStructuredPropertyDefinition, ...]:
    records: list[SnapshotStructuredPropertyDefinition] = []
    for item in sorted(
        context.structured_property_definitions,
        key=lambda definition: definition.property_urn,
    ):
        evidence_id = registry.context(item.evidence, item.property_urn)
        records.append(
            SnapshotStructuredPropertyDefinition(
                property_urn=item.property_urn,
                qualified_name=item.qualified_name,
                display_name=item.display_name,
                value_type=item.value_type,
                value_type_urn=item.value_type_urn,
                evidence_ids=(evidence_id,),
            )
        )
    return tuple(records)


def _context_relationships(
    graph: FieldLineageGraph,
    context: AssetContextSnapshot,
    registry: _EvidenceRegistry,
    lineage_edges: tuple[SnapshotLineageEdge, ...],
) -> tuple[SnapshotRelationship, ...]:
    records: dict[str, SnapshotRelationship] = {}

    def add(
        category: RelationshipCategory,
        source_key: str,
        target_key: str,
        *,
        state: str,
        evidence_id: str,
        path: tuple[str, ...] = (),
        attributes: tuple[SnapshotAttribute, ...] = (),
    ) -> None:
        relationship_id = _stable_id(
            "relationship",
            {
                "category": category.value,
                "source_key": source_key,
                "target_key": target_key,
                "path": path,
                "state": state,
                "attributes": [
                    (item.name, item.values) for item in attributes
                ],
            },
        )
        records.setdefault(
            relationship_id,
            SnapshotRelationship(
                relationship_id=relationship_id,
                category=category,
                source_key=source_key,
                target_key=target_key,
                relationship_path=path,
                state=state,
                attributes=attributes,
                evidence_ids=(evidence_id,),
            ),
        )

    for edge in lineage_edges:
        add(
            RelationshipCategory.FIELD_LINEAGE,
            edge.upstream.text,
            edge.downstream.text,
            state="verified",
            evidence_id=edge.evidence_ids[0],
            attributes=_attributes(
                edge_id=edge.edge_id,
                classification=edge.classification,
                mapping_group_ids=edge.mapping_group_ids,
                confidence_scores=edge.confidence_scores,
                transform_operations=edge.transform_operations,
            ),
        )

    for asset in context.assets:
        asset_urn = asset.asset.urn
        for item in asset.owners:
            evidence_id = registry.context(item.evidence, asset_urn)
            add(
                RelationshipCategory.OWNERSHIP,
                asset_urn,
                item.owner_urn,
                state=item.state.value,
                evidence_id=evidence_id,
                attributes=_attributes(
                    owner_kind=item.owner_kind,
                    display_name=item.display_name,
                    ownership_type=item.ownership_type,
                    ownership_type_urn=item.ownership_type_urn,
                ),
            )
        for item in asset.domains:
            evidence_id = registry.context(item.evidence, asset_urn)
            add(
                RelationshipCategory.DOMAIN_ASSIGNMENT,
                asset_urn,
                item.domain_urn,
                state=item.state.value,
                evidence_id=evidence_id,
                attributes=_attributes(display_name=item.display_name),
            )
        for item in asset.tags:
            evidence_id = registry.context(item.evidence, asset_urn)
            target = _assignment_subject(
                item.scope,
                item.target_urn,
                item.field_path,
            )
            add(
                RelationshipCategory.TAG_ASSIGNMENT,
                target,
                item.tag_urn,
                state=item.state.value,
                evidence_id=evidence_id,
                attributes=_attributes(
                    name=item.name,
                    scope=item.scope.value,
                    field_path=item.field_path,
                ),
            )
        for item in asset.glossary_terms:
            evidence_id = registry.context(item.evidence, asset_urn)
            target = _assignment_subject(
                item.scope,
                item.target_urn,
                item.field_path,
            )
            add(
                RelationshipCategory.GLOSSARY_ASSIGNMENT,
                target,
                item.term_urn,
                state=item.state.value,
                evidence_id=evidence_id,
                attributes=_attributes(
                    name=item.name,
                    parent_node_urn=item.parent_node_urn,
                    parent_node_name=item.parent_node_name,
                    scope=item.scope.value,
                    field_path=item.field_path,
                ),
            )
        for item in asset.structured_properties:
            evidence_id = registry.context(item.evidence, asset_urn)
            add(
                RelationshipCategory.STRUCTURED_PROPERTY_ASSIGNMENT,
                item.assignment_target,
                item.property_urn,
                state="present",
                evidence_id=evidence_id,
                attributes=_attributes(
                    qualified_name=item.qualified_name,
                    display_name=item.display_name,
                    values=item.values,
                    value_type=item.value_type,
                    value_type_urn=item.value_type_urn,
                ),
            )
        for item in asset.data_products:
            evidence_id = registry.context(item.evidence, asset_urn)
            add(
                RelationshipCategory.DATA_PRODUCT_MEMBERSHIP,
                item.asset_urn,
                item.product_urn,
                state="present",
                evidence_id=evidence_id,
                attributes=_attributes(
                    name=item.name,
                    relationship=item.relationship,
                ),
            )
        for item in asset.documents:
            evidence_id = registry.context(item.evidence, asset_urn)
            add(
                RelationshipCategory.DOCUMENT_RELATIONSHIP,
                item.related_asset_urn,
                item.document_urn,
                state=item.state.value,
                evidence_id=evidence_id,
                attributes=_attributes(
                    title=item.title,
                    relationship=item.relationship,
                ),
            )
        for item in asset.evidence:
            registry.context(item, asset_urn)

    for item in context.pipeline_context:
        evidence_id = registry.context(item.evidence, item.job_urn)
        for field_key in item.related_field_keys:
            add(
                RelationshipCategory.PIPELINE_CONTEXT,
                item.job_urn,
                FieldMachineKey(*field_key).text,
                state=item.state.value,
                evidence_id=evidence_id,
                path=tuple(
                    part
                    for part in (item.flow_urn, item.job_urn)
                    if part is not None
                ),
                attributes=_attributes(
                    job_name=item.job_name,
                    job_platform=item.job_platform,
                    flow_urn=item.flow_urn,
                    flow_name=item.flow_name,
                    flow_platform=item.flow_platform,
                    mapping_group_ids=item.mapping_group_ids,
                ),
            )
    for item in context.bi_context:
        evidence_id = registry.context(item.evidence, item.urn)
        source_key = (
            item.relationship_path[0]
            if item.relationship_path
            else graph.source.dataset_urn
        )
        add(
            RelationshipCategory.BI_REACHABLE_CONTEXT,
            source_key,
            item.urn,
            state=item.state.value,
            evidence_id=evidence_id,
            path=item.relationship_path,
            attributes=_attributes(
                entity_type=item.entity_type,
                platform=item.platform,
                name=item.name,
                qualified_name=item.qualified_name,
                classification=item.classification.value,
            ),
        )
    for finding in context.findings:
        registry.add(
            classification=EvidenceClassification.UNKNOWN,
            source_phase="1.5",
            subject_key=finding.asset_urn or "context",
            interface="AssetContextRetriever",
            aspect_or_relationship="context_finding",
            source_urn=finding.asset_urn,
            target_urn=finding.reference_urn,
            attributes=_attributes(
                code=finding.code.value,
                message=finding.message,
            ),
        )
    return tuple(
        sorted(
            records.values(),
            key=lambda item: (
                item.category.value,
                item.source_key,
                item.target_key,
                item.relationship_id,
            ),
        )
    )


def _dataset_registry(
    graph: FieldLineageGraph,
    context: AssetContextSnapshot,
    schema: DatasetSchemaSnapshot,
    source_qualified_name: str,
    source_logical_name: str,
    relationships: tuple[SnapshotRelationship, ...],
    registry: _EvidenceRegistry,
    graph_evidence: str,
    dataset_evidence: str,
    readiness_evidence: str,
) -> tuple[SnapshotDataset, ...]:
    assets = {item.asset.urn: item for item in context.assets}
    field_to_dataset = {
        FieldMachineKey(*node.reference.key).text: node.reference.dataset_urn
        for node in graph.nodes
    }
    relation_ids: dict[str, set[str]] = {
        entry.dataset_urn: set() for entry in graph.dataset_index
    }
    for relationship in relationships:
        touched: set[str] = set()
        if relationship.source_key in relation_ids:
            touched.add(relationship.source_key)
        if relationship.target_key in relation_ids:
            touched.add(relationship.target_key)
        if relationship.source_key in field_to_dataset:
            touched.add(field_to_dataset[relationship.source_key])
        if relationship.target_key in field_to_dataset:
            touched.add(field_to_dataset[relationship.target_key])
        touched.update(
            urn
            for urn in relationship.relationship_path
            if urn in relation_ids
        )
        for urn in touched:
            relation_ids[urn].add(relationship.relationship_id)

    display_by_dataset: dict[str, str] = {}
    for node in graph.nodes:
        if node.reference.display_identity:
            display_by_dataset.setdefault(
                node.reference.dataset_urn,
                node.reference.display_identity,
            )
    records: list[SnapshotDataset] = []
    for entry in sorted(
        graph.dataset_index,
        key=lambda item: item.dataset_urn,
    ):
        asset = assets.get(entry.dataset_urn)
        asset_evidence = {
            registry.context(item, entry.dataset_urn)
            for item in (asset.evidence if asset is not None else ())
        }
        ids = {graph_evidence, *asset_evidence}
        if entry.dataset_urn == schema.dataset_urn:
            ids.update(
                {dataset_evidence, readiness_evidence}
            )
        records.append(
            SnapshotDataset(
                dataset_urn=entry.dataset_urn,
                platform=entry.platform,
                environment=entry.environment,
                qualified_name=(
                    source_qualified_name
                    if entry.dataset_urn == schema.dataset_urn
                    else None
                ),
                logical_name=(
                    source_logical_name
                    if entry.dataset_urn == schema.dataset_urn
                    else (asset.asset.name if asset is not None else None)
                ),
                display_identity=display_by_dataset.get(entry.dataset_urn),
                schema_field_paths=(
                    tuple(field.field_path for field in schema.fields)
                    if entry.dataset_urn == schema.dataset_urn
                    else ()
                ),
                lineage_field_keys=tuple(
                    sorted(FieldMachineKey(*key) for key in entry.field_keys)
                ),
                metadata_states=(
                    _attributes(
                        ownership=asset.ownership_state.value,
                        domain=asset.domain_state.value,
                        tag=asset.tag_state.value,
                        glossary=asset.glossary_state.value,
                        structured_property=(
                            asset.structured_property_state.value
                        ),
                        data_product=asset.data_product_state.value,
                        document=asset.document_state.value,
                        pipeline=asset.pipeline_state.value,
                        bi=asset.bi_state.value,
                    )
                    if asset is not None
                    else ()
                ),
                relationship_ids=tuple(
                    sorted(relation_ids.get(entry.dataset_urn, set()))
                ),
                evidence_ids=tuple(sorted(ids)),
            )
        )
    return tuple(records)


def _assignment_subject(
    scope: AssignmentScope,
    target_urn: str,
    field_path: str | None,
) -> str:
    if scope is AssignmentScope.FIELD and field_path is not None:
        return FieldMachineKey(target_urn, field_path).text
    return target_urn


def _attributes(**values: object) -> tuple[SnapshotAttribute, ...]:
    records: list[SnapshotAttribute] = []
    for name, value in sorted(values.items()):
        if isinstance(value, Enum):
            normalized = (value.value,)
        elif isinstance(value, (tuple, list, set, frozenset)):
            normalized = tuple(
                item.value if isinstance(item, Enum) else item for item in value
            )
        else:
            normalized = (value,)
        records.append(SnapshotAttribute(name=name, values=normalized))
    return tuple(records)


def _stable_id(prefix: str, value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"{prefix}-{hashlib.sha256(payload).hexdigest()[:20]}"


def _timestamp(clock: Clock) -> str:
    value = clock()
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()
