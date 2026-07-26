"""Typed canonical and resolved identity models for Phase 1.2."""

from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from enum import Enum
from typing import Any

from chronos.datahub.errors import FailureCode


class CanonicalEntityType(str, Enum):
    DATASET = "dataset"
    SCHEMA_FIELD = "schema_field"
    DATA_JOB = "data_job"
    DATA_FLOW = "data_flow"
    CHART = "chart"
    DASHBOARD = "dashboard"
    DOMAIN = "domain"
    TAG = "tag"
    GLOSSARY_TERM = "glossary_term"
    DATA_PRODUCT = "data_product"
    DOCUMENT = "document"
    CORPORATE_USER = "corporate_user"
    CORPORATE_GROUP = "corporate_group"


class ResolutionState(str, Enum):
    RESOLVED = "resolved"
    NOT_FOUND = "not_found"
    AMBIGUOUS = "ambiguous"
    INVALID_IDENTITY = "invalid_identity"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class CanonicalDatasetIdentity:
    platform: str
    qualified_name: str
    environment: str
    logical_name: str
    database: str | None = None
    schema: str | None = None
    display_identity: str | None = None
    entity_type: CanonicalEntityType = field(
        default=CanonicalEntityType.DATASET,
        init=False,
    )


@dataclass(frozen=True)
class CanonicalSchemaFieldIdentity:
    parent_dataset: CanonicalDatasetIdentity
    field_path: str
    field_name: str
    display_identity: str | None = None
    entity_type: CanonicalEntityType = field(
        default=CanonicalEntityType.SCHEMA_FIELD,
        init=False,
    )


@dataclass(frozen=True)
class ResolvedDatasetIdentity:
    urn: str
    urn_name: str
    platform: str
    environment: str
    qualified_name: str
    logical_name: str
    platform_instance: str | None
    properties_qualified_name: str | None


@dataclass(frozen=True)
class ResolvedSchemaFieldIdentity:
    parent_dataset_urn: str
    field_path: str
    field_name: str
    native_type: str | None
    normalized_type: str
    description: str | None
    schema_field_urn: str | None


@dataclass(frozen=True)
class EvidenceAttribute:
    attribute: str
    requested: str
    observed: str
    matched: bool


@dataclass(frozen=True)
class ResolutionEvidence:
    method: str
    interfaces: tuple[str, ...]
    canonical_request: str
    resolved_urn: str
    verified_attributes: tuple[EvidenceAttribute, ...]
    observed_at: str
    snapshot_context: str


@dataclass(frozen=True)
class ResolutionFailure:
    code: FailureCode
    message: str
    diagnostic: str | None = None


@dataclass(frozen=True)
class DatasetResolutionResult:
    state: ResolutionState
    requested: CanonicalDatasetIdentity
    discovered_candidate_count: int
    verified_candidate_count: int
    resolved: ResolvedDatasetIdentity | None
    candidates: tuple[ResolvedDatasetIdentity, ...]
    evidence: ResolutionEvidence | None
    failure: ResolutionFailure | None

    def to_dict(self) -> dict[str, Any]:
        return _to_primitive(self)


@dataclass(frozen=True)
class FieldResolutionResult:
    state: ResolutionState
    requested: CanonicalSchemaFieldIdentity
    parent_dataset: ResolvedDatasetIdentity
    verified_candidate_count: int
    resolved: ResolvedSchemaFieldIdentity | None
    candidates: tuple[ResolvedSchemaFieldIdentity, ...]
    evidence: ResolutionEvidence | None
    failure: ResolutionFailure | None

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
