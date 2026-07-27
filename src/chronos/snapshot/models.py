"""Immutable normalized current-state snapshot models for CHRONOS Phase 1.6."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


SnapshotScalar = str | int | float | bool | None


class EvidenceClassification(str, Enum):
    VERIFIED = "verified"
    DERIVED = "derived"
    UNKNOWN = "unknown"


class RelationshipCategory(str, Enum):
    FIELD_LINEAGE = "field_lineage"
    PIPELINE_CONTEXT = "pipeline_context"
    BI_REACHABLE_CONTEXT = "bi_reachable_context"
    DATA_PRODUCT_MEMBERSHIP = "data_product_membership"
    DOCUMENT_RELATIONSHIP = "document_relationship"
    OWNERSHIP = "ownership"
    DOMAIN_ASSIGNMENT = "domain_assignment"
    TAG_ASSIGNMENT = "tag_assignment"
    GLOSSARY_ASSIGNMENT = "glossary_assignment"
    STRUCTURED_PROPERTY_ASSIGNMENT = "structured_property_assignment"


class SnapshotValidationState(str, Enum):
    VALID = "valid"
    INVALID = "invalid"


class SnapshotBuildState(str, Enum):
    VALIDATED = "validated"
    INVALID_INPUT = "invalid_input"
    INVALID_SNAPSHOT = "invalid_snapshot"


@dataclass(frozen=True, order=True)
class FieldMachineKey:
    dataset_urn: str
    field_path: str

    @property
    def text(self) -> str:
        return f"{self.dataset_urn}|{self.field_path}"


@dataclass(frozen=True, order=True)
class SnapshotAttribute:
    name: str
    values: tuple[SnapshotScalar, ...]


@dataclass(frozen=True)
class SnapshotEvidence:
    evidence_id: str
    classification: EvidenceClassification
    source_phase: str
    subject_key: str
    interface: str
    aspect_or_relationship: str
    source_urn: str | None
    target_urn: str | None
    relationship_path: tuple[str, ...]
    observed_at: str | None
    attributes: tuple[SnapshotAttribute, ...]


@dataclass(frozen=True)
class SnapshotEnvironment:
    endpoint: str
    gms_version: str | None
    sdk_version: str | None
    server_type: str | None
    server_environment: str | None
    configuration_source: str
    authentication_state: str


@dataclass(frozen=True)
class SnapshotMetadata:
    snapshot_id: str
    demonstration_id: str
    snapshot_schema_version: str
    created_at: str
    environment: SnapshotEnvironment
    source_phase_results: tuple[SnapshotAttribute, ...]


@dataclass(frozen=True)
class SnapshotSchemaField:
    position: int
    field_path: str
    field_name: str
    native_type: str | None
    normalized_type: str
    datahub_type: str | None
    description: str | None
    nullable: bool | None
    is_part_of_key: bool | None
    is_partitioning_key: bool | None
    json_path: str | None
    label: str | None
    recursive: bool | None
    schema_field_urn: str | None
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class SourceSchema:
    dataset_urn: str
    schema_name: str
    platform: str
    source_platform: str
    environment: str
    schema_version: int | None
    schema_hash: str | None
    fields: tuple[SnapshotSchemaField, ...]
    created_time: int | None
    last_modified_time: int | None
    dataset_reference: str | None
    cluster: str | None
    primary_keys: tuple[str, ...] | None
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class SnapshotDataset:
    dataset_urn: str
    platform: str
    environment: str
    qualified_name: str | None
    logical_name: str | None
    display_identity: str | None
    schema_field_paths: tuple[str, ...]
    lineage_field_keys: tuple[FieldMachineKey, ...]
    metadata_states: tuple[SnapshotAttribute, ...]
    relationship_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class SnapshotField:
    key: FieldMachineKey
    field_name: str
    platform: str
    dataset_name: str
    environment: str
    native_type: str | None
    normalized_type: str | None
    schema_position: int | None
    description: str | None
    nullable: bool | None
    is_part_of_key: bool | None
    is_partitioning_key: bool | None
    schema_field_urn: str | None
    reference_resolution: str
    lineage_depth: int
    path_count: int
    paths_truncated: bool
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class SnapshotLineageEdge:
    edge_id: str
    upstream: FieldMachineKey
    downstream: FieldMachineKey
    classification: str
    mapping_group_ids: tuple[str, ...]
    source_entity_urns: tuple[str, ...]
    source_aspects: tuple[str, ...]
    transform_operations: tuple[str, ...]
    confidence_scores: tuple[float, ...]
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class SnapshotMappingGroup:
    group_id: str
    source_entity_urn: str
    source_entity_type: str
    source_aspect: str
    source_interface: str
    source_group_index: int
    upstream_type: str | None
    downstream_type: str | None
    raw_upstream_references: tuple[str, ...]
    raw_downstream_references: tuple[str, ...]
    upstream_fields: tuple[FieldMachineKey, ...]
    downstream_fields: tuple[FieldMachineKey, ...]
    transform_operation: str | None
    confidence_score: float | None
    query: str | None
    match_type: str | None
    expansion_state: str
    ambiguity_reason: str | None
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class SnapshotStructuredPropertyDefinition:
    property_urn: str
    qualified_name: str
    display_name: str | None
    value_type: str
    value_type_urn: str
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class SnapshotLineagePath:
    node_keys: tuple[FieldMachineKey, ...]
    edge_ids: tuple[str, ...]


@dataclass(frozen=True)
class SnapshotRelationship:
    relationship_id: str
    category: RelationshipCategory
    source_key: str
    target_key: str
    relationship_path: tuple[str, ...]
    state: str
    attributes: tuple[SnapshotAttribute, ...]
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class SnapshotValidationFinding:
    invariant: str
    expected: str
    observed: str
    evidence_ids: tuple[str, ...]
    affected_key: str | None = None


@dataclass(frozen=True)
class SnapshotValidationResult:
    state: SnapshotValidationState
    checked_invariants: tuple[str, ...]
    findings: tuple[SnapshotValidationFinding, ...]


@dataclass(frozen=True)
class SnapshotSummary:
    demonstration_id: str
    dataset_count: int
    source_schema_field_count: int
    lineage_field_node_count: int
    downstream_field_count: int
    downstream_dataset_count: int
    maximum_field_depth: int
    lineage_edge_count: int
    mapping_group_count: int
    ownership_assignment_count: int
    dashboard_context_count: int
    data_product_membership_count: int
    document_relationship_count: int
    unresolved_reference_count: int
    semantic_fingerprint: str


@dataclass(frozen=True)
class CurrentMetadataSnapshot:
    metadata: SnapshotMetadata
    source_dataset_urn: str
    source_field_key: FieldMachineKey
    source_schema: SourceSchema
    datasets: tuple[SnapshotDataset, ...]
    fields: tuple[SnapshotField, ...]
    lineage_edges: tuple[SnapshotLineageEdge, ...]
    mapping_groups: tuple[SnapshotMappingGroup, ...]
    structured_property_definitions: tuple[
        SnapshotStructuredPropertyDefinition,
        ...,
    ]
    lineage_paths: tuple[SnapshotLineagePath, ...]
    relationships: tuple[SnapshotRelationship, ...]
    evidence: tuple[SnapshotEvidence, ...]
    validation_result: SnapshotValidationResult
    semantic_fingerprint: str

    def dataset_by_urn(self) -> dict[str, SnapshotDataset]:
        return {item.dataset_urn: item for item in self.datasets}

    def field_by_key(self) -> dict[FieldMachineKey, SnapshotField]:
        return {item.key: item for item in self.fields}

    def evidence_by_id(self) -> dict[str, SnapshotEvidence]:
        return {item.evidence_id: item for item in self.evidence}

    def semantic_json(self) -> str:
        from .serialization import snapshot_to_json

        return snapshot_to_json(self, include_volatile=False)

    def to_json(self) -> str:
        from .serialization import snapshot_to_json

        return snapshot_to_json(self, include_volatile=True)

    @classmethod
    def from_json(cls, value: str) -> CurrentMetadataSnapshot:
        from .serialization import snapshot_from_json

        return snapshot_from_json(value)

    def semantically_equals(self, other: object) -> bool:
        return (
            isinstance(other, CurrentMetadataSnapshot)
            and self.semantic_fingerprint == other.semantic_fingerprint
            and self.semantic_json() == other.semantic_json()
        )

    def summary(self) -> SnapshotSummary:
        categories = [item.category for item in self.relationships]
        unresolved = sum(
            1 for item in self.relationships if item.state == "unresolved"
        )
        downstream_fields = sum(
            1 for item in self.fields if item.key != self.source_field_key
        )
        downstream_datasets = len(
            {
                item.key.dataset_urn
                for item in self.fields
                if item.key != self.source_field_key
                and item.key.dataset_urn != self.source_dataset_urn
            }
        )
        return SnapshotSummary(
            demonstration_id=self.metadata.demonstration_id,
            dataset_count=len(self.datasets),
            source_schema_field_count=len(self.source_schema.fields),
            lineage_field_node_count=len(self.fields),
            downstream_field_count=downstream_fields,
            downstream_dataset_count=downstream_datasets,
            maximum_field_depth=max(
                (item.lineage_depth for item in self.fields),
                default=0,
            ),
            lineage_edge_count=len(self.lineage_edges),
            mapping_group_count=len(self.mapping_groups),
            ownership_assignment_count=categories.count(
                RelationshipCategory.OWNERSHIP
            ),
            dashboard_context_count=sum(
                1
                for item in self.relationships
                if item.category
                is RelationshipCategory.BI_REACHABLE_CONTEXT
                and any(
                    attribute.name == "entity_type"
                    and attribute.values == ("DASHBOARD",)
                    for attribute in item.attributes
                )
            ),
            data_product_membership_count=categories.count(
                RelationshipCategory.DATA_PRODUCT_MEMBERSHIP
            ),
            document_relationship_count=categories.count(
                RelationshipCategory.DOCUMENT_RELATIONSHIP
            ),
            unresolved_reference_count=unresolved,
            semantic_fingerprint=self.semantic_fingerprint,
        )

    def to_dict(self, *, include_volatile: bool = True) -> dict[str, Any]:
        from .serialization import snapshot_to_dict

        return snapshot_to_dict(self, include_volatile=include_volatile)


@dataclass(frozen=True)
class SnapshotBuildResult:
    state: SnapshotBuildState
    snapshot: CurrentMetadataSnapshot | None
    findings: tuple[SnapshotValidationFinding, ...]
