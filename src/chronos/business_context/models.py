"""Immutable CHRONOS Phase 4.2 business-context propagation models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from chronos.counterfactual_source import InputArtifactHash
from chronos.snapshot import FieldMachineKey, RelationshipCategory
from chronos.technical_impact import TechnicalImpactState


BUSINESS_CONTEXT_SCHEMA_VERSION = "1.0"


class ContextCategory(str, Enum):
    OWNERSHIP = "ownership"
    DOMAIN = "domain"
    TAG = "tag"
    GLOSSARY = "glossary"
    STRUCTURED_PROPERTY = "structured_property"
    DATA_PRODUCT = "data_product"
    DOCUMENT = "document"
    PIPELINE = "pipeline"
    BI = "bi"


class ContextAssetType(str, Enum):
    OWNER_USER = "owner_user"
    OWNER_GROUP = "owner_group"
    DOMAIN = "domain"
    TAG = "tag"
    GLOSSARY_TERM = "glossary_term"
    STRUCTURED_PROPERTY_DEFINITION = "structured_property_definition"
    DATA_PRODUCT = "data_product"
    DOCUMENT = "document"
    DATA_FLOW = "data_flow"
    DATA_JOB = "data_job"
    CHART = "chart"
    DASHBOARD = "dashboard"
    BI_DATASET = "bi_dataset"
    CERTIFIED_CONTEXT = "certified_context"


class ContextExposureType(str, Enum):
    DIRECT_CONTEXT = "direct_context"
    REACHABLE_CONTEXT = "reachable_context"


class ContextLinkageState(str, Enum):
    CONTEXT_LINKED_TO_CONFIRMED_TECHNICAL_STATE = (
        "context_linked_to_confirmed_technical_state"
    )
    CONTEXT_LINKED_TO_POTENTIAL_TECHNICAL_STATE = (
        "context_linked_to_potential_technical_state"
    )
    CONTEXT_LINKED_TO_UNRESOLVED_TECHNICAL_STATE = (
        "context_linked_to_unresolved_technical_state"
    )
    CONTEXT_LINKED_TO_NO_DEMONSTRATED_TECHNICAL_STATE = (
        "context_linked_to_no_demonstrated_technical_state"
    )


class ContextResolutionState(str, Enum):
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"


class TechnicalSubjectType(str, Enum):
    FIELD = "field"


class BusinessContextValidationState(str, Enum):
    VALID = "valid"


ContextScalar = str | int | float | bool | None


@dataclass(frozen=True)
class ContextAttribute:
    name: str
    values: tuple[ContextScalar, ...]


@dataclass(frozen=True)
class ContextAssetRecord:
    asset_id: str
    category: ContextCategory
    asset_type: ContextAssetType
    display_name: str | None
    resolution_state: ContextResolutionState
    certified_relationship_ids: tuple[str, ...]
    supporting_dataset_urns: tuple[str, ...]
    supporting_field_keys: tuple[FieldMachineKey, ...]
    supporting_path_ids: tuple[str, ...]
    root_technical_cause_ids: tuple[str, ...]
    attributes: tuple[ContextAttribute, ...]
    current_evidence_ids: tuple[str, ...]
    future_graph_provenance_ids: tuple[str, ...]


@dataclass(frozen=True)
class ContextLinkRecord:
    context_relationship_id: str
    relationship_category: RelationshipCategory
    context_category: ContextCategory
    source_key: str
    target_key: str
    relationship_path: tuple[str, ...]
    anchor_dataset_urn: str
    anchor_field_key: FieldMachineKey | None
    context_asset_ids: tuple[str, ...]
    context_exposure_type: ContextExposureType
    certified_current_state: str
    attributes: tuple[ContextAttribute, ...]
    current_evidence_ids: tuple[str, ...]
    future_graph_provenance_ids: tuple[str, ...]
    phase_3_certification_fingerprint: str


@dataclass(frozen=True)
class TechnicalToContextMapping:
    mapping_id: str
    technical_subject_type: TechnicalSubjectType
    technical_subject_id: str
    technical_field_key: FieldMachineKey
    technical_impact_state: TechnicalImpactState
    dataset_urn: str
    context_relationship_id: str
    context_category: ContextCategory
    context_asset_id: str
    context_exposure_type: ContextExposureType
    context_linkage_state: ContextLinkageState
    root_technical_cause_ids: tuple[str, ...]
    supporting_field_keys: tuple[FieldMachineKey, ...]
    supporting_path_ids: tuple[str, ...]
    technical_provenance_ids: tuple[str, ...]
    context_provenance_ids: tuple[str, ...]
    human_explanation: str


@dataclass(frozen=True)
class ContextExposureCause:
    cause_id: str
    root_relationship_id: str
    technical_impact_state: TechnicalImpactState
    linked_context_asset_ids: tuple[str, ...]
    linked_dataset_urns: tuple[str, ...]
    linked_field_keys: tuple[FieldMachineKey, ...]
    mapping_ids: tuple[str, ...]
    phase_4_1_technical_impact_fingerprint: str


@dataclass(frozen=True)
class DatasetContextSummary:
    dataset_urn: str
    technical_field_keys: tuple[FieldMachineKey, ...]
    confirmed_technical_fields: int
    potential_technical_fields: int
    unresolved_technical_fields: int
    no_demonstrated_technical_fields: int
    owner_count: int
    domain_count: int
    tag_count: int
    glossary_assignment_count: int
    structured_property_assignment_count: int
    data_product_count: int
    document_count: int
    pipeline_context_link_count: int
    bi_context_link_count: int
    unique_context_asset_count: int
    context_asset_ids: tuple[str, ...]
    context_relationship_ids: tuple[str, ...]
    root_technical_cause_ids: tuple[str, ...]


@dataclass(frozen=True)
class FieldContextReverseIndex:
    field_key: FieldMachineKey
    context_asset_ids: tuple[str, ...]
    context_relationship_ids: tuple[str, ...]
    mapping_ids: tuple[str, ...]


@dataclass(frozen=True)
class DatasetContextReverseIndex:
    dataset_urn: str
    technical_field_keys: tuple[FieldMachineKey, ...]
    context_asset_ids: tuple[str, ...]
    context_relationship_ids: tuple[str, ...]
    mapping_ids: tuple[str, ...]


@dataclass(frozen=True)
class ContextAssetReverseIndex:
    context_asset_id: str
    linked_dataset_urns: tuple[str, ...]
    linked_field_keys: tuple[FieldMachineKey, ...]
    supporting_path_ids: tuple[str, ...]
    root_technical_cause_ids: tuple[str, ...]
    mapping_ids: tuple[str, ...]


@dataclass(frozen=True)
class ContextReverseIndexes:
    by_field: tuple[FieldContextReverseIndex, ...]
    by_dataset: tuple[DatasetContextReverseIndex, ...]
    by_context_asset: tuple[ContextAssetReverseIndex, ...]


@dataclass(frozen=True)
class UnresolvedContextReference:
    context_asset_id: str
    context_category: ContextCategory
    context_relationship_ids: tuple[str, ...]
    preserved_state: ContextResolutionState


@dataclass(frozen=True)
class BusinessContextAggregateMetrics:
    certified_graph_context_relationships: int
    scoped_context_relationships: int
    excluded_context_relationships: int
    unique_owners: int
    unique_domains: int
    unique_tags: int
    unique_glossary_terms: int
    structured_property_assignments: int
    structured_property_definitions: int
    unique_data_products: int
    unique_documents: int
    pipeline_context_assets: int
    bi_context_assets: int
    charts: int
    dashboards: int
    total_unique_context_assets: int
    total_technical_to_context_mappings: int
    context_assets_linked_to_multiple_datasets: int
    context_assets_linked_through_multiple_technical_fields: int


@dataclass(frozen=True)
class BusinessContextPropagation:
    schema_version: str
    demonstration_id: str
    proposal_id: str
    phase_3_certification_fingerprint: str
    technical_impact_fingerprint: str
    technical_root_causes: tuple[ContextExposureCause, ...]
    context_asset_registry: tuple[ContextAssetRecord, ...]
    context_link_registry: tuple[ContextLinkRecord, ...]
    technical_to_context_mappings: tuple[
        TechnicalToContextMapping,
        ...,
    ]
    dataset_context_summaries: tuple[DatasetContextSummary, ...]
    reverse_indexes: ContextReverseIndexes
    aggregate_metrics: BusinessContextAggregateMetrics
    unresolved_context_references: tuple[
        UnresolvedContextReference,
        ...,
    ]
    canonical_narrative: str
    warnings: tuple[str, ...]
    input_artifact_hashes: tuple[InputArtifactHash, ...]
    created_at: str
    validation_state: BusinessContextValidationState
    semantic_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        if self.schema_version != BUSINESS_CONTEXT_SCHEMA_VERSION:
            raise ValueError("Unsupported business-context schema.")
        if self.demonstration_id != "CHRONOS-DEMO-001":
            raise ValueError("Business-context demonstration is invalid.")
        if self.validation_state is not BusinessContextValidationState.VALID:
            raise ValueError("Only validated business context is allowed.")
        for value in (
            self.phase_3_certification_fingerprint,
            self.technical_impact_fingerprint,
        ):
            if not _is_sha256_fingerprint(value):
                raise ValueError("Business-context fingerprint is invalid.")
        try:
            timestamp = datetime.fromisoformat(self.created_at)
        except (TypeError, ValueError) as exc:
            raise ValueError("created_at must be ISO-8601.") from exc
        if timestamp.tzinfo is None:
            raise ValueError("created_at must include timezone.")
        _validate_internal(self)
        from .serialization import business_context_semantic_fingerprint

        object.__setattr__(
            self,
            "semantic_fingerprint",
            business_context_semantic_fingerprint(self),
        )

    def to_dict(self, *, include_volatile: bool = True) -> dict[str, Any]:
        from .serialization import business_context_to_dict

        return business_context_to_dict(
            self,
            include_volatile=include_volatile,
        )

    def to_json(self) -> str:
        from .serialization import business_context_to_json

        return business_context_to_json(self, include_volatile=True)

    def semantic_json(self) -> str:
        from .serialization import business_context_to_json

        return business_context_to_json(self, include_volatile=False)

    @classmethod
    def from_json(cls, value: str) -> BusinessContextPropagation:
        from .serialization import business_context_from_json

        return business_context_from_json(value)

    def semantically_equals(self, other: object) -> bool:
        return (
            isinstance(other, BusinessContextPropagation)
            and self.semantic_fingerprint == other.semantic_fingerprint
            and self.semantic_json() == other.semantic_json()
        )


def _validate_internal(result: BusinessContextPropagation) -> None:
    registries = (
        (result.technical_root_causes, "cause_id"),
        (result.context_asset_registry, "asset_id"),
        (result.context_link_registry, "context_relationship_id"),
        (result.technical_to_context_mappings, "mapping_id"),
        (result.dataset_context_summaries, "dataset_urn"),
        (result.reverse_indexes.by_field, "field_key"),
        (result.reverse_indexes.by_dataset, "dataset_urn"),
        (result.reverse_indexes.by_context_asset, "context_asset_id"),
        (result.unresolved_context_references, "context_asset_id"),
    )
    for values, attribute in registries:
        keys = tuple(getattr(item, attribute) for item in values)
        if len(keys) != len(set(keys)):
            raise ValueError(f"Duplicate business-context key: {attribute}.")
    assets = {item.asset_id for item in result.context_asset_registry}
    links = {
        item.context_relationship_id for item in result.context_link_registry
    }
    causes = {item.cause_id for item in result.technical_root_causes}
    fields = {
        item.field_key for item in result.reverse_indexes.by_field
    }
    datasets = {
        item.dataset_urn for item in result.dataset_context_summaries
    }
    for mapping in result.technical_to_context_mappings:
        if (
            mapping.context_asset_id not in assets
            or mapping.context_relationship_id not in links
            or mapping.technical_field_key not in fields
            or mapping.dataset_urn not in datasets
            or any(
                value not in causes
                for value in mapping.root_technical_cause_ids
            )
        ):
            raise ValueError("Dangling technical-to-context mapping.")
    for link in result.context_link_registry:
        if (
            link.anchor_dataset_urn not in datasets
            or any(value not in assets for value in link.context_asset_ids)
        ):
            raise ValueError("Dangling context link.")
    if any(not item.unchanged for item in result.input_artifact_hashes):
        raise ValueError("A business-context input artifact changed.")


def _is_sha256_fingerprint(value: object) -> bool:
    if not isinstance(value, str) or not value.startswith("sha256:"):
        return False
    digest = value.removeprefix("sha256:")
    return len(digest) == 64 and all(
        character in "0123456789abcdef" for character in digest
    )
