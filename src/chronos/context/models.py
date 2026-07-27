"""Immutable verified governance and business context for Phase 1.5."""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
from typing import Any

from chronos.datahub.errors import FailureCode
from chronos.lineage.models import FieldKey


class MetadataState(str, Enum):
    PRESENT = "present"
    ABSENT = "absent"
    UNRESOLVED = "unresolved"


class AssignmentScope(str, Enum):
    ENTITY = "entity"
    FIELD = "field"


class ContextRetrievalState(str, Enum):
    RETRIEVED = "retrieved"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


class BusinessIntelligenceClassification(str, Enum):
    REACHABLE_CONTEXT = "reachable_context"
    CONFIRMED_FIELD_IMPACT = "confirmed_field_impact"


@dataclass(frozen=True)
class ContextEvidence:
    source_urn: str
    interface: str
    aspect_or_relationship: str
    target_urn: str | None
    relationship_path: tuple[str, ...]
    observed_at: str


@dataclass(frozen=True)
class AssetIdentity:
    urn: str
    entity_type: str
    platform: str
    name: str
    environment: str


@dataclass(frozen=True)
class OwnerAssignment:
    owner_urn: str
    owner_kind: str
    display_name: str | None
    ownership_type: str | None
    ownership_type_urn: str | None
    state: MetadataState
    evidence: ContextEvidence


@dataclass(frozen=True)
class DomainAssignment:
    domain_urn: str
    display_name: str | None
    state: MetadataState
    evidence: ContextEvidence


@dataclass(frozen=True)
class TagAssignment:
    tag_urn: str
    name: str | None
    scope: AssignmentScope
    target_urn: str
    field_path: str | None
    state: MetadataState
    evidence: ContextEvidence


@dataclass(frozen=True)
class GlossaryTermAssignment:
    term_urn: str
    name: str | None
    parent_node_urn: str | None
    parent_node_name: str | None
    scope: AssignmentScope
    target_urn: str
    field_path: str | None
    state: MetadataState
    evidence: ContextEvidence


@dataclass(frozen=True)
class StructuredPropertyDefinition:
    property_urn: str
    qualified_name: str
    display_name: str | None
    value_type: str
    value_type_urn: str
    evidence: ContextEvidence


@dataclass(frozen=True)
class StructuredPropertyAssignment:
    property_urn: str
    qualified_name: str
    display_name: str | None
    values: tuple[str | float, ...]
    value_type: str
    value_type_urn: str
    assignment_target: str
    evidence: ContextEvidence


@dataclass(frozen=True)
class DataProductMembership:
    product_urn: str
    name: str
    asset_urn: str
    relationship: str
    evidence: ContextEvidence


@dataclass(frozen=True)
class DocumentContext:
    document_urn: str
    title: str | None
    related_asset_urn: str
    relationship: str
    state: MetadataState
    evidence: ContextEvidence


@dataclass(frozen=True)
class PipelineContext:
    job_urn: str
    job_name: str | None
    job_platform: str | None
    flow_urn: str | None
    flow_name: str | None
    flow_platform: str | None
    related_field_keys: tuple[FieldKey, ...]
    mapping_group_ids: tuple[str, ...]
    state: MetadataState
    evidence: ContextEvidence


@dataclass(frozen=True)
class BusinessIntelligenceContext:
    urn: str
    entity_type: str
    platform: str | None
    name: str | None
    qualified_name: str | None
    classification: BusinessIntelligenceClassification
    relationship_path: tuple[str, ...]
    state: MetadataState
    evidence: ContextEvidence


@dataclass(frozen=True)
class AssetContext:
    asset: AssetIdentity
    owners: tuple[OwnerAssignment, ...]
    ownership_state: MetadataState
    domains: tuple[DomainAssignment, ...]
    domain_state: MetadataState
    tags: tuple[TagAssignment, ...]
    tag_state: MetadataState
    glossary_terms: tuple[GlossaryTermAssignment, ...]
    glossary_state: MetadataState
    structured_properties: tuple[StructuredPropertyAssignment, ...]
    structured_property_state: MetadataState
    data_products: tuple[DataProductMembership, ...]
    data_product_state: MetadataState
    documents: tuple[DocumentContext, ...]
    document_state: MetadataState
    pipeline_context: tuple[PipelineContext, ...]
    pipeline_state: MetadataState
    bi_context: tuple[BusinessIntelligenceContext, ...]
    bi_state: MetadataState
    evidence: tuple[ContextEvidence, ...]


@dataclass(frozen=True)
class ContextFinding:
    code: FailureCode
    message: str
    asset_urn: str | None = None
    reference_urn: str | None = None


@dataclass(frozen=True)
class ContextFailure:
    code: FailureCode
    message: str
    diagnostic: str | None = None


@dataclass(frozen=True)
class AssetContextSnapshot:
    source_field: FieldKey
    assets: tuple[AssetContext, ...]
    structured_property_definitions: tuple[
        StructuredPropertyDefinition,
        ...,
    ]
    pipeline_context: tuple[PipelineContext, ...]
    bi_context: tuple[BusinessIntelligenceContext, ...]
    findings: tuple[ContextFinding, ...]
    observed_at: str

    @property
    def dataset_count(self) -> int:
        return len(self.assets)

    @property
    def ownership_gap_count(self) -> int:
        return sum(
            1
            for asset in self.assets
            if asset.ownership_state is MetadataState.ABSENT
        )

    def semantic_key(self) -> Any:
        return _semantic(self)

    def semantically_equals(self, other: object) -> bool:
        return (
            isinstance(other, AssetContextSnapshot)
            and self.semantic_key() == other.semantic_key()
        )

    def to_dict(self) -> dict[str, Any]:
        return _to_primitive(self)


@dataclass(frozen=True)
class ContextRetrievalResult:
    state: ContextRetrievalState
    snapshot: AssetContextSnapshot | None
    findings: tuple[ContextFinding, ...]
    failure: ContextFailure | None

    def to_dict(self) -> dict[str, Any]:
        return _to_primitive(self)


def _semantic(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return tuple(
            (item.name, _semantic(getattr(value, item.name)))
            for item in fields(value)
            if item.name != "observed_at"
        )
    if isinstance(value, tuple):
        return tuple(_semantic(item) for item in value)
    if isinstance(value, list):
        return tuple(_semantic(item) for item in value)
    if isinstance(value, dict):
        return tuple(
            (str(key), _semantic(item))
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        )
    return value


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
