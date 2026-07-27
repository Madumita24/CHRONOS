"""Immutable typed schema evidence for CHRONOS Phase 1.3."""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
from typing import Any

from chronos.datahub.errors import FailureCode
from chronos.datahub.schema_types import NormalizedFieldType
from chronos.resolution.models import (
    CanonicalDatasetIdentity,
    ResolvedDatasetIdentity,
)


class SchemaRetrievalState(str, Enum):
    RETRIEVED = "retrieved"
    NOT_FOUND = "not_found"
    INVALID_SCHEMA = "invalid_schema"
    UNAVAILABLE = "unavailable"


class SchemaValidationState(str, Enum):
    VALID = "valid"
    INVALID = "invalid"


class FieldLookupState(str, Enum):
    FOUND = "found"
    NOT_FOUND = "not_found"


@dataclass(frozen=True)
class SchemaValidationFinding:
    code: FailureCode
    message: str
    field_path: str | None = None


@dataclass(frozen=True)
class SchemaFailure:
    code: FailureCode
    message: str
    diagnostic: str | None = None


@dataclass(frozen=True)
class SchemaFieldRecord:
    """One field in the order supplied by DataHub SchemaMetadata."""

    position: int
    field_path: str
    field_name: str
    native_type: str | None
    normalized_type: NormalizedFieldType
    datahub_type: str | None
    description: str | None
    nullable: bool | None
    is_part_of_key: bool | None
    is_partitioning_key: bool | None
    json_path: str | None
    label: str | None
    recursive: bool | None
    schema_field_urn: str | None

    def semantic_key(self) -> tuple[Any, ...]:
        return (
            self.position,
            self.field_path,
            self.field_name,
            self.native_type,
            self.normalized_type.value,
            self.datahub_type,
            self.description,
            self.nullable,
            self.is_part_of_key,
            self.is_partitioning_key,
            self.json_path,
            self.label,
            self.recursive,
            self.schema_field_urn,
        )


@dataclass(frozen=True)
class SchemaEvidence:
    dataset_urn: str
    aspect: str
    interface: str
    observed_at: str
    schema_name: str
    schema_version: int | None
    schema_hash: str | None
    field_count: int
    validation_state: SchemaValidationState


@dataclass(frozen=True)
class SchemaFieldLookupResult:
    state: FieldLookupState
    requested_field_path: str
    field: SchemaFieldRecord | None
    failure: SchemaFailure | None


@dataclass(frozen=True)
class DatasetSchemaSnapshot:
    """An immutable observation of one resolved DataHub dataset schema."""

    dataset: ResolvedDatasetIdentity
    canonical_identity: CanonicalDatasetIdentity
    schema_name: str
    platform: str
    source_platform: str
    environment: str
    schema_version: int | None
    schema_hash: str | None
    fields: tuple[SchemaFieldRecord, ...]
    observed_at: str
    evidence: SchemaEvidence
    created_time: int | None
    last_modified_time: int | None
    dataset_reference: str | None
    cluster: str | None
    primary_keys: tuple[str, ...] | None

    @property
    def dataset_urn(self) -> str:
        return self.dataset.urn

    @property
    def field_count(self) -> int:
        return len(self.fields)

    def lookup_field(self, field_path: str) -> SchemaFieldLookupResult:
        """Perform exact, case-sensitive lookup without any DataHub request."""

        for field in self.fields:
            if field.field_path == field_path:
                return SchemaFieldLookupResult(
                    state=FieldLookupState.FOUND,
                    requested_field_path=field_path,
                    field=field,
                    failure=None,
                )
        return SchemaFieldLookupResult(
            state=FieldLookupState.NOT_FOUND,
            requested_field_path=field_path,
            field=None,
            failure=SchemaFailure(
                code=FailureCode.FIELD_NOT_FOUND,
                message="The field is absent from this schema snapshot.",
                diagnostic=f"Requested exact field path: {field_path}.",
            ),
        )

    def semantic_key(self) -> tuple[Any, ...]:
        """Return deterministic content identity excluding observation time."""

        canonical = self.canonical_identity
        dataset = self.dataset
        return (
            dataset.urn,
            dataset.urn_name,
            dataset.platform,
            dataset.environment,
            dataset.qualified_name,
            dataset.logical_name,
            dataset.platform_instance,
            dataset.properties_qualified_name,
            canonical.platform,
            canonical.qualified_name,
            canonical.environment,
            canonical.logical_name,
            canonical.database,
            canonical.schema,
            self.schema_name,
            self.platform,
            self.source_platform,
            self.environment,
            self.schema_version,
            self.schema_hash,
            tuple(field.semantic_key() for field in self.fields),
            self.created_time,
            self.last_modified_time,
            self.dataset_reference,
            self.cluster,
            self.primary_keys,
        )

    def semantically_equals(self, other: object) -> bool:
        return (
            isinstance(other, DatasetSchemaSnapshot)
            and self.semantic_key() == other.semantic_key()
        )

    def to_dict(self) -> dict[str, Any]:
        return _to_primitive(self)


@dataclass(frozen=True)
class SchemaRetrievalResult:
    state: SchemaRetrievalState
    requested: CanonicalDatasetIdentity
    dataset: ResolvedDatasetIdentity
    snapshot: DatasetSchemaSnapshot | None
    findings: tuple[SchemaValidationFinding, ...]
    failure: SchemaFailure | None

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
