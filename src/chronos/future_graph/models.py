"""Immutable models for the CHRONOS Phase 3.2 Future Graph."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from chronos.counterfactual_source import (
    CandidateSourceSchema,
    InputArtifactHash,
)
from chronos.snapshot import FieldMachineKey, RelationshipCategory


FUTURE_GRAPH_SCHEMA_VERSION = "1.0"
CANONICAL_DATASET_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:postgres,"
    "b2fd91.order_entry_db.order_entry.orders,PROD)"
)


class GraphObjectState(str, Enum):
    COUNTERFACTUAL_CHANGED = "counterfactual_changed"
    COUNTERFACTUAL_INHERITED = "counterfactual_inherited"
    COUNTERFACTUAL_UNRESOLVED = "counterfactual_unresolved"


class FutureRelationshipState(str, Enum):
    COUNTERFACTUAL_PROJECTED = "counterfactual_projected"
    COUNTERFACTUAL_INHERITED = "counterfactual_inherited"


class RelationshipEvaluationState(str, Enum):
    NOT_EVALUATED = "not_evaluated"


class FutureIdentityMappingClassification(str, Enum):
    RENAMED = "renamed"
    IDENTITY_PRESERVED = "identity_preserved"


class FuturePathClassification(str, Enum):
    COUNTERFACTUAL_STRUCTURE = "counterfactual_structure"


class ProvenanceKind(str, Enum):
    CURRENT_EVIDENCE = "current_evidence"
    COUNTERFACTUAL_DERIVATION = "counterfactual_derivation"


class FutureGraphValidationState(str, Enum):
    VALID = "valid"
    INVALID = "invalid"


@dataclass(frozen=True)
class FutureAttribute:
    name: str
    values: tuple[str | int | float | bool | None, ...]


@dataclass(frozen=True)
class FutureDataset:
    dataset_urn: str
    platform: str
    environment: str
    qualified_name: str | None
    logical_name: str | None
    display_identity: str | None
    current_schema_field_paths: tuple[str, ...]
    active_schema_field_paths: tuple[str, ...]
    current_lineage_field_keys: tuple[FieldMachineKey, ...]
    active_lineage_field_keys: tuple[FieldMachineKey, ...]
    metadata_states: tuple[FutureAttribute, ...]
    current_relationship_ids: tuple[str, ...]
    current_evidence_ids: tuple[str, ...]
    state: GraphObjectState
    provenance_ids: tuple[str, ...]


@dataclass(frozen=True)
class FutureField:
    key: FieldMachineKey
    current_key: FieldMachineKey
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
    structural_depth: int
    current_path_count: int
    current_paths_truncated: bool
    current_evidence_ids: tuple[str, ...]
    state: GraphObjectState
    provenance_ids: tuple[str, ...]


@dataclass(frozen=True)
class FutureLineageRelationship:
    relationship_id: str
    current_edge_id: str
    upstream: FieldMachineKey
    downstream: FieldMachineKey
    current_upstream: FieldMachineKey
    current_downstream: FieldMachineKey
    current_classification: str
    current_mapping_group_ids: tuple[str, ...]
    current_source_entity_urns: tuple[str, ...]
    current_source_aspects: tuple[str, ...]
    current_transform_operations: tuple[str, ...]
    current_confidence_scores: tuple[float, ...]
    current_evidence_ids: tuple[str, ...]
    relationship_state: FutureRelationshipState
    evaluation_state: RelationshipEvaluationState
    provenance_ids: tuple[str, ...]


@dataclass(frozen=True)
class FutureMappingGroup:
    group_id: str
    current_source_entity_urn: str
    current_source_entity_type: str
    current_source_aspect: str
    current_source_interface: str
    current_source_group_index: int
    current_upstream_type: str | None
    current_downstream_type: str | None
    current_raw_upstream_references: tuple[str, ...]
    current_raw_downstream_references: tuple[str, ...]
    current_upstream_fields: tuple[FieldMachineKey, ...]
    current_downstream_fields: tuple[FieldMachineKey, ...]
    projected_upstream_fields: tuple[FieldMachineKey, ...]
    projected_downstream_fields: tuple[FieldMachineKey, ...]
    current_transform_operation: str | None
    current_confidence_score: float | None
    current_query: str | None
    current_match_type: str | None
    current_expansion_state: str
    current_evidence_ids: tuple[str, ...]
    relationship_state: FutureRelationshipState
    evaluation_state: RelationshipEvaluationState
    provenance_ids: tuple[str, ...]


@dataclass(frozen=True)
class FutureLineagePath:
    path_id: str
    current_node_keys: tuple[FieldMachineKey, ...]
    current_edge_ids: tuple[str, ...]
    projected_node_keys: tuple[FieldMachineKey, ...]
    projected_relationship_ids: tuple[str, ...]
    classification: FuturePathClassification
    evaluation_state: RelationshipEvaluationState
    provenance_ids: tuple[str, ...]


@dataclass(frozen=True)
class FutureContextRelationship:
    current_relationship_id: str
    category: RelationshipCategory
    source_key: str
    target_key: str
    relationship_path: tuple[str, ...]
    current_state: str
    current_attributes: tuple[FutureAttribute, ...]
    current_evidence_ids: tuple[str, ...]
    state: GraphObjectState
    provenance_ids: tuple[str, ...]


@dataclass(frozen=True)
class FutureStructuredPropertyDefinition:
    property_urn: str
    qualified_name: str
    display_name: str | None
    value_type: str
    value_type_urn: str
    current_evidence_ids: tuple[str, ...]
    state: GraphObjectState
    provenance_ids: tuple[str, ...]


@dataclass(frozen=True)
class CurrentToFutureIdentityMapping:
    current_identity: FieldMachineKey
    future_identity: FieldMachineKey
    classification: FutureIdentityMappingClassification
    provenance_ids: tuple[str, ...]


@dataclass(frozen=True)
class GraphProvenanceRecord:
    provenance_id: str
    kind: ProvenanceKind
    source_artifact_fingerprint: str
    source_object_type: str
    source_object_key: str
    current_evidence_ids: tuple[str, ...]
    proposal_id: str | None
    proposal_fingerprint: str | None
    semantic_contract_fingerprint: str | None
    counterfactual_source_state_fingerprint: str | None
    projection_classification: str | None


@dataclass(frozen=True)
class GraphStateAnnotation:
    object_type: str
    object_key: str
    object_state: GraphObjectState
    relationship_state: FutureRelationshipState | None
    evaluation_state: RelationshipEvaluationState | None
    rationale: str
    provenance_ids: tuple[str, ...]


@dataclass(frozen=True)
class FutureMetadataGraph:
    schema_version: str
    demonstration_id: str
    current_snapshot_fingerprint: str
    proposal_fingerprint: str
    validation_fingerprint: str
    semantic_contract_fingerprint: str
    phase_2_certification_fingerprint: str
    counterfactual_source_state_fingerprint: str
    source_schema: CandidateSourceSchema
    dataset_registry: tuple[FutureDataset, ...]
    field_registry: tuple[FutureField, ...]
    relationship_registry: tuple[FutureLineageRelationship, ...]
    mapping_group_registry: tuple[FutureMappingGroup, ...]
    path_registry: tuple[FutureLineagePath, ...]
    context_relationship_registry: tuple[FutureContextRelationship, ...]
    structured_property_registry: tuple[
        FutureStructuredPropertyDefinition,
        ...,
    ]
    current_to_future_identity_mappings: tuple[
        CurrentToFutureIdentityMapping,
        ...,
    ]
    provenance_registry: tuple[GraphProvenanceRecord, ...]
    state_annotations: tuple[GraphStateAnnotation, ...]
    input_artifact_hashes: tuple[InputArtifactHash, ...]
    validation_state: FutureGraphValidationState
    created_at: str
    semantic_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        if self.schema_version != FUTURE_GRAPH_SCHEMA_VERSION:
            raise ValueError("Unsupported Future Graph schema version.")
        if self.demonstration_id != "CHRONOS-DEMO-001":
            raise ValueError("Future Graph demonstration identity is invalid.")
        if self.validation_state is not FutureGraphValidationState.VALID:
            raise ValueError("Only validated Future Graphs may be represented.")
        try:
            timestamp = datetime.fromisoformat(self.created_at)
        except (TypeError, ValueError) as exc:
            raise ValueError("created_at must be ISO-8601.") from exc
        if timestamp.tzinfo is None:
            raise ValueError("created_at must include a timezone.")
        for value, label in (
            (self.current_snapshot_fingerprint, "snapshot fingerprint"),
            (self.proposal_fingerprint, "proposal fingerprint"),
            (self.validation_fingerprint, "validation fingerprint"),
            (
                self.semantic_contract_fingerprint,
                "semantic-contract fingerprint",
            ),
            (
                self.phase_2_certification_fingerprint,
                "Phase 2 certification fingerprint",
            ),
            (
                self.counterfactual_source_state_fingerprint,
                "counterfactual source-state fingerprint",
            ),
        ):
            if not _is_sha256_fingerprint(value):
                raise ValueError(f"{label} is not canonical sha256.")
        _validate_internal_structure(self)
        from .serialization import future_graph_semantic_fingerprint

        object.__setattr__(
            self,
            "semantic_fingerprint",
            future_graph_semantic_fingerprint(self),
        )

    def to_dict(self, *, include_volatile: bool = True) -> dict[str, Any]:
        from .serialization import future_graph_to_dict

        return future_graph_to_dict(self, include_volatile=include_volatile)

    def to_json(self) -> str:
        from .serialization import future_graph_to_json

        return future_graph_to_json(self, include_volatile=True)

    def semantic_json(self) -> str:
        from .serialization import future_graph_to_json

        return future_graph_to_json(self, include_volatile=False)

    @classmethod
    def from_json(cls, value: str) -> FutureMetadataGraph:
        from .serialization import future_graph_from_json

        return future_graph_from_json(value)

    def semantically_equals(self, other: object) -> bool:
        return (
            isinstance(other, FutureMetadataGraph)
            and self.semantic_fingerprint == other.semantic_fingerprint
            and self.semantic_json() == other.semantic_json()
        )

    @property
    def maximum_structural_depth(self) -> int:
        return max(item.structural_depth for item in self.field_registry)

    def summary(self) -> str:
        changed = sum(
            item.state is GraphObjectState.COUNTERFACTUAL_CHANGED
            for item in self.field_registry
        )
        unresolved = sum(
            item.state is GraphObjectState.COUNTERFACTUAL_UNRESOLVED
            for item in self.field_registry
        )
        return "\n".join(
            (
                f"Demonstration: {self.demonstration_id}",
                "Graph: COUNTERFACTUAL STRUCTURE",
                f"Datasets: {len(self.dataset_registry)}",
                f"Active fields: {len(self.field_registry)}",
                f"Changed source fields: {changed}",
                f"Unresolved downstream fields: {unresolved}",
                (
                    "Structural lineage relationships: "
                    f"{len(self.relationship_registry)}"
                ),
                f"Mapping groups retained: {len(self.mapping_group_registry)}",
                f"Current paths retained/projected: {len(self.path_registry)}",
                "Relationship evaluation: NOT_EVALUATED",
            )
        )


def _validate_internal_structure(graph: FutureMetadataGraph) -> None:
    if len(graph.dataset_registry) != 21:
        raise ValueError("Future Graph must contain 21 datasets.")
    dataset_urns = tuple(item.dataset_urn for item in graph.dataset_registry)
    if len(set(dataset_urns)) != 21:
        raise ValueError("Future Dataset URNs must be unique.")
    if len(graph.field_registry) != 26:
        raise ValueError("Future Graph must contain 26 active field nodes.")
    field_keys = tuple(item.key for item in graph.field_registry)
    if len(set(field_keys)) != 26:
        raise ValueError("Future field machine keys must be unique.")
    current_source = FieldMachineKey(CANONICAL_DATASET_URN, "order_total")
    candidate_source = FieldMachineKey(CANONICAL_DATASET_URN, "order_amount")
    if current_source in field_keys or field_keys.count(candidate_source) != 1:
        raise ValueError("Active source replacement is invalid.")
    if any(item.key.dataset_urn not in dataset_urns for item in graph.field_registry):
        raise ValueError("A future field has a missing parent Dataset.")
    if len(graph.relationship_registry) != 27:
        raise ValueError("Future Graph must contain 27 structural edges.")
    relationship_ids = tuple(
        item.relationship_id for item in graph.relationship_registry
    )
    if len(set(relationship_ids)) != 27:
        raise ValueError("Future relationship IDs must be unique.")
    active_keys = set(field_keys)
    if any(
        item.upstream not in active_keys or item.downstream not in active_keys
        for item in graph.relationship_registry
    ):
        raise ValueError("A structural relationship endpoint is dangling.")
    if any(
        item.evaluation_state is not RelationshipEvaluationState.NOT_EVALUATED
        for item in graph.relationship_registry
    ):
        raise ValueError("Relationship evaluation was resolved prematurely.")
    if len(graph.mapping_group_registry) != 28:
        raise ValueError("Exactly 28 mapping groups must be retained.")
    if len(graph.path_registry) != 48:
        raise ValueError("Exactly 48 current paths must be retained.")
    if len(graph.current_to_future_identity_mappings) != 26:
        raise ValueError("Exactly 26 field identity mappings are required.")
    mappings = graph.current_to_future_identity_mappings
    if sum(
        item.classification is FutureIdentityMappingClassification.RENAMED
        for item in mappings
    ) != 1:
        raise ValueError("Exactly one field identity must be RENAMED.")
    if sum(
        item.classification
        is FutureIdentityMappingClassification.IDENTITY_PRESERVED
        for item in mappings
    ) != 25:
        raise ValueError("Exactly 25 identities must be preserved.")
    provenance_ids = tuple(
        item.provenance_id for item in graph.provenance_registry
    )
    if len(set(provenance_ids)) != len(provenance_ids):
        raise ValueError("Provenance record IDs must be unique.")
    known_provenance = set(provenance_ids)
    provenance_references = (
        tuple(
            value
            for item in graph.dataset_registry
            for value in item.provenance_ids
        )
        + tuple(
            value
            for item in graph.field_registry
            for value in item.provenance_ids
        )
        + tuple(
            value
            for item in graph.relationship_registry
            for value in item.provenance_ids
        )
        + tuple(
            value
            for item in graph.mapping_group_registry
            for value in item.provenance_ids
        )
        + tuple(
            value
            for item in graph.path_registry
            for value in item.provenance_ids
        )
        + tuple(
            value
            for item in graph.context_relationship_registry
            for value in item.provenance_ids
        )
        + tuple(
            value
            for item in graph.structured_property_registry
            for value in item.provenance_ids
        )
        + tuple(
            value
            for item in graph.current_to_future_identity_mappings
            for value in item.provenance_ids
        )
        + tuple(
            value
            for item in graph.state_annotations
            for value in item.provenance_ids
        )
    )
    if any(value not in known_provenance for value in provenance_references):
        raise ValueError("A Future Graph provenance reference is dangling.")
    expected_annotation_keys = (
        {("dataset", item.dataset_urn) for item in graph.dataset_registry}
        | {("field", item.key.text) for item in graph.field_registry}
        | {
            ("lineage_relationship", item.relationship_id)
            for item in graph.relationship_registry
        }
        | {
            ("mapping_group", item.group_id)
            for item in graph.mapping_group_registry
        }
        | {("lineage_path", item.path_id) for item in graph.path_registry}
        | {
            ("context_relationship", item.current_relationship_id)
            for item in graph.context_relationship_registry
        }
        | {
            ("structured_property_definition", item.property_urn)
            for item in graph.structured_property_registry
        }
        | {
            (
                "identity_mapping",
                f"{item.current_identity.text}->{item.future_identity.text}",
            )
            for item in graph.current_to_future_identity_mappings
        }
    )
    actual_annotation_keys = {
        (item.object_type, item.object_key)
        for item in graph.state_annotations
    }
    if actual_annotation_keys != expected_annotation_keys:
        raise ValueError(
            "Every Future Graph object must have exactly one state annotation."
        )
    if len(actual_annotation_keys) != len(graph.state_annotations):
        raise ValueError("Future Graph state annotations must be unique.")
    if any(not item.unchanged for item in graph.input_artifact_hashes):
        raise ValueError("An authoritative input artifact changed.")


def _is_sha256_fingerprint(value: object) -> bool:
    if not isinstance(value, str) or not value.startswith("sha256:"):
        return False
    digest = value.removeprefix("sha256:")
    return len(digest) == 64 and all(
        character in "0123456789abcdef" for character in digest
    )
