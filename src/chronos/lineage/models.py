"""Immutable current-state field lineage evidence for CHRONOS Phase 1.4."""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
from typing import Any

from chronos.datahub.errors import FailureCode
from chronos.resolution.models import CanonicalSchemaFieldIdentity


FieldKey = tuple[str, str]
EdgeKey = tuple[FieldKey, FieldKey]


class LineageRetrievalState(str, Enum):
    RETRIEVED = "retrieved"
    NO_LINEAGE = "no_lineage"
    PARTIAL = "partial"
    INVALID_LINEAGE = "invalid_lineage"
    UNAVAILABLE = "unavailable"


class MappingExpansionState(str, Enum):
    EXPANDED = "expanded"
    AMBIGUOUS = "ambiguous"
    MALFORMED = "malformed"
    UNRESOLVED = "unresolved"


class LineageRelationshipClassification(str, Enum):
    DIRECT = "direct"
    DERIVED = "derived"
    UNKNOWN = "unknown"


class LineageValidationState(str, Enum):
    VALID = "valid"
    PARTIAL = "partial"


class FieldReferenceResolution(str, Enum):
    SOURCE_SNAPSHOT = "source_snapshot"
    SCHEMA_MEMBER = "schema_member"
    SCHEMA_FIELD_ENTITY = "schema_field_entity_only"
    UNVERIFIED = "unverified"


@dataclass(frozen=True)
class LineageFailure:
    code: FailureCode
    message: str
    diagnostic: str | None = None


@dataclass(frozen=True)
class LineageFinding:
    code: FailureCode
    message: str
    group_id: str | None = None
    field_reference: str | None = None


@dataclass(frozen=True)
class FieldReference:
    dataset_urn: str
    field_path: str
    field_name: str
    platform: str
    dataset_name: str
    environment: str
    canonical_identity: CanonicalSchemaFieldIdentity | None
    display_identity: str | None
    schema_field_urn: str | None
    resolution: FieldReferenceResolution

    @property
    def key(self) -> FieldKey:
        return (self.dataset_urn, self.field_path)

    def semantic_key(self) -> tuple[Any, ...]:
        canonical = self.canonical_identity
        return (
            self.dataset_urn,
            self.field_path,
            self.field_name,
            self.platform,
            self.dataset_name,
            self.environment,
            (
                canonical.parent_dataset.platform,
                canonical.parent_dataset.qualified_name,
                canonical.parent_dataset.environment,
                canonical.parent_dataset.logical_name,
                canonical.field_path,
                canonical.field_name,
            )
            if canonical is not None
            else None,
            self.display_identity,
            self.schema_field_urn,
            self.resolution.value,
        )


@dataclass(frozen=True)
class LineageMappingGroup:
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
    upstream_fields: tuple[FieldReference, ...]
    downstream_fields: tuple[FieldReference, ...]
    transform_operation: str | None
    confidence_score: float | None
    query: str | None
    match_type: str | None
    expansion_state: MappingExpansionState
    ambiguity_reason: str | None
    observed_at: str

    def semantic_key(self) -> tuple[Any, ...]:
        return (
            self.group_id,
            self.source_entity_urn,
            self.source_entity_type,
            self.source_aspect,
            self.source_interface,
            self.source_group_index,
            self.upstream_type,
            self.downstream_type,
            self.raw_upstream_references,
            self.raw_downstream_references,
            tuple(item.semantic_key() for item in self.upstream_fields),
            tuple(item.semantic_key() for item in self.downstream_fields),
            self.transform_operation,
            self.confidence_score,
            self.query,
            self.match_type,
            self.expansion_state.value,
            self.ambiguity_reason,
        )


@dataclass(frozen=True)
class FieldLineageEdge:
    upstream: FieldReference
    downstream: FieldReference
    classification: LineageRelationshipClassification
    mapping_group_ids: tuple[str, ...]
    source_entity_urns: tuple[str, ...]
    source_aspects: tuple[str, ...]
    transform_operations: tuple[str, ...]
    confidence_scores: tuple[float, ...]
    observed_at: str

    @property
    def key(self) -> EdgeKey:
        return (self.upstream.key, self.downstream.key)

    def semantic_key(self) -> tuple[Any, ...]:
        return (
            self.upstream.semantic_key(),
            self.downstream.semantic_key(),
            self.classification.value,
            self.mapping_group_ids,
            self.source_entity_urns,
            self.source_aspects,
            self.transform_operations,
            self.confidence_scores,
        )


@dataclass(frozen=True)
class LineagePath:
    nodes: tuple[FieldReference, ...]
    edge_keys: tuple[EdgeKey, ...]

    @property
    def length(self) -> int:
        return len(self.edge_keys)

    def semantic_key(self) -> tuple[Any, ...]:
        return (
            tuple(item.semantic_key() for item in self.nodes),
            self.edge_keys,
        )


@dataclass(frozen=True)
class FieldLineageNode:
    reference: FieldReference
    depth: int
    path_count: int
    paths_truncated: bool

    def semantic_key(self) -> tuple[Any, ...]:
        return (
            self.reference.semantic_key(),
            self.depth,
            self.path_count,
            self.paths_truncated,
        )


@dataclass(frozen=True)
class LineageCycle:
    nodes: tuple[FieldReference, ...]
    closing_edge: EdgeKey

    def semantic_key(self) -> tuple[Any, ...]:
        return (
            tuple(item.semantic_key() for item in self.nodes),
            self.closing_edge,
        )


@dataclass(frozen=True)
class DatasetLineageIndexEntry:
    dataset_urn: str
    platform: str
    dataset_name: str
    environment: str
    field_keys: tuple[FieldKey, ...]

    def semantic_key(self) -> tuple[Any, ...]:
        return (
            self.dataset_urn,
            self.platform,
            self.dataset_name,
            self.environment,
            self.field_keys,
        )


@dataclass(frozen=True)
class LineageEvidence:
    source_field: FieldKey
    interfaces: tuple[str, ...]
    observed_at: str
    candidate_dataset_count: int
    aspect_entity_count: int
    mapping_group_count: int
    explicit_edge_count: int
    downstream_field_count: int
    downstream_dataset_count: int
    maximum_field_depth: int
    validation_state: LineageValidationState


@dataclass(frozen=True)
class FieldLineageGraph:
    source: FieldReference
    nodes: tuple[FieldLineageNode, ...]
    edges: tuple[FieldLineageEdge, ...]
    mapping_groups: tuple[LineageMappingGroup, ...]
    paths: tuple[LineagePath, ...]
    cycles: tuple[LineageCycle, ...]
    dataset_index: tuple[DatasetLineageIndexEntry, ...]
    evidence: LineageEvidence
    findings: tuple[LineageFinding, ...]

    @property
    def downstream_field_count(self) -> int:
        return sum(
            1 for node in self.nodes if node.reference.key != self.source.key
        )

    @property
    def downstream_dataset_count(self) -> int:
        return len(
            {
                node.reference.dataset_urn
                for node in self.nodes
                if node.reference.key != self.source.key
                and node.reference.dataset_urn != self.source.dataset_urn
            }
        )

    @property
    def maximum_field_depth(self) -> int:
        return max((node.depth for node in self.nodes), default=0)

    @property
    def direct_downstream(self) -> tuple[FieldLineageNode, ...]:
        return tuple(node for node in self.nodes if node.depth == 1)

    def paths_to(self, field_key: FieldKey) -> tuple[LineagePath, ...]:
        return tuple(
            path
            for path in self.paths
            if path.nodes and path.nodes[-1].key == field_key
        )

    def semantic_key(self) -> tuple[Any, ...]:
        return (
            self.source.semantic_key(),
            tuple(item.semantic_key() for item in self.nodes),
            tuple(item.semantic_key() for item in self.edges),
            tuple(item.semantic_key() for item in self.mapping_groups),
            tuple(item.semantic_key() for item in self.paths),
            tuple(item.semantic_key() for item in self.cycles),
            tuple(item.semantic_key() for item in self.dataset_index),
            tuple(
                (
                    item.code.value,
                    item.message,
                    item.group_id,
                    item.field_reference,
                )
                for item in self.findings
            ),
        )

    def semantically_equals(self, other: object) -> bool:
        return (
            isinstance(other, FieldLineageGraph)
            and self.semantic_key() == other.semantic_key()
        )

    def to_dict(self) -> dict[str, Any]:
        return _to_primitive(self)


@dataclass(frozen=True)
class LineageRetrievalResult:
    state: LineageRetrievalState
    graph: FieldLineageGraph | None
    findings: tuple[LineageFinding, ...]
    failure: LineageFailure | None

    def to_dict(self) -> dict[str, Any]:
        return _to_primitive(self)


def _to_primitive(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {
            item.name: _to_primitive(getattr(value, item.name))
            for item in fields(value)
        }
    if isinstance(value, tuple):
        return [_to_primitive(item) for item in value]
    if isinstance(value, list):
        return [_to_primitive(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _to_primitive(item) for key, item in value.items()}
    return value
