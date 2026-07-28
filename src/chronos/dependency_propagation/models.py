"""Immutable models for CHRONOS Phase 3.3 dependency propagation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from chronos.counterfactual_source import InputArtifactHash
from chronos.future_graph import (
    FutureRelationshipState,
    GraphObjectState,
    RelationshipEvaluationState,
)
from chronos.snapshot import FieldMachineKey


DEPENDENCY_PROPAGATION_SCHEMA_VERSION = "1.0"


class FieldExposureState(str, Enum):
    SOURCE_CHANGED = "source_changed"
    DIRECTLY_EXPOSED = "directly_exposed"
    TRANSITIVELY_EXPOSED = "transitively_exposed"
    MULTIPATH_EXPOSED = "multipath_exposed"
    NOT_EXPOSED = "not_exposed"
    UNRESOLVED = "unresolved"


class DatasetExposureState(str, Enum):
    DIRECTLY_EXPOSED_DATASET = "directly_exposed_dataset"
    TRANSITIVELY_EXPOSED_DATASET = "transitively_exposed_dataset"
    MULTIPATH_EXPOSED_DATASET = "multipath_exposed_dataset"
    NOT_EXPOSED_DATASET = "not_exposed_dataset"
    UNRESOLVED_DATASET = "unresolved_dataset"


class RelationshipExposureState(str, Enum):
    SOURCE_REBASED_EDGE = "source_rebased_edge"
    DOWNSTREAM_EXPOSED_EDGE = "downstream_exposed_edge"
    NOT_EXPOSED_EDGE = "not_exposed_edge"
    UNRESOLVED_EDGE = "unresolved_edge"


class PropagationValidationState(str, Enum):
    VALID = "valid"
    INVALID = "invalid"


@dataclass(frozen=True)
class DependencyPathRecord:
    path_id: str
    future_graph_path_id: str | None
    source_field: FieldMachineKey
    target_field: FieldMachineKey
    node_keys: tuple[FieldMachineKey, ...]
    relationship_ids: tuple[str, ...]
    depth: int
    current_provenance_ids: tuple[str, ...]
    counterfactual_provenance_ids: tuple[str, ...]


@dataclass(frozen=True)
class FieldExposureRecord:
    field_key: FieldMachineKey
    parent_dataset_urn: str
    identity_state: GraphObjectState
    exposure_state: FieldExposureState
    minimum_depth: int
    path_count: int
    supporting_path_ids: tuple[str, ...]
    representative_path_id: str | None
    incoming_exposed_relationship_ids: tuple[str, ...]
    current_provenance_ids: tuple[str, ...]
    counterfactual_provenance_ids: tuple[str, ...]


@dataclass(frozen=True)
class DatasetExposureRecord:
    dataset_urn: str
    exposure_state: DatasetExposureState
    minimum_depth: int
    exposed_field_count: int
    multipath_field_count: int
    field_keys: tuple[FieldMachineKey, ...]
    path_count: int
    supporting_path_ids: tuple[str, ...]


@dataclass(frozen=True)
class RelationshipExposureRecord:
    relationship_id: str
    source_field: FieldMachineKey
    target_field: FieldMachineKey
    exposure_state: RelationshipExposureState
    structural_state: FutureRelationshipState
    compatibility_state: RelationshipEvaluationState
    mapping_group_ids: tuple[str, ...]
    supporting_path_ids: tuple[str, ...]
    path_count: int
    current_provenance_ids: tuple[str, ...]
    counterfactual_provenance_ids: tuple[str, ...]


@dataclass(frozen=True)
class PropagationSummary:
    changed_source_fields: int
    directly_exposed_fields: int
    transitively_exposed_fields: int
    multipath_exposed_fields: int
    total_unique_downstream_exposed_fields: int
    unique_downstream_exposed_datasets: int
    maximum_exposure_depth: int
    exposed_structural_relationships: int
    processed_structural_relationships: int


@dataclass(frozen=True)
class DependencyPropagationResult:
    schema_version: str
    demonstration_id: str
    future_graph_fingerprint: str
    source_candidate_field: FieldMachineKey
    field_exposure_registry: tuple[FieldExposureRecord, ...]
    dataset_exposure_registry: tuple[DatasetExposureRecord, ...]
    relationship_exposure_registry: tuple[
        RelationshipExposureRecord,
        ...,
    ]
    path_registry: tuple[DependencyPathRecord, ...]
    summary: PropagationSummary
    input_artifact_hashes: tuple[InputArtifactHash, ...]
    validation_state: PropagationValidationState
    created_at: str
    semantic_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        if self.schema_version != DEPENDENCY_PROPAGATION_SCHEMA_VERSION:
            raise ValueError("Unsupported dependency propagation schema.")
        if self.demonstration_id != "CHRONOS-DEMO-001":
            raise ValueError("Propagation demonstration identity is invalid.")
        if self.validation_state is not PropagationValidationState.VALID:
            raise ValueError("Only validated propagation results are allowed.")
        if not _is_sha256_fingerprint(self.future_graph_fingerprint):
            raise ValueError("Future Graph fingerprint is not canonical.")
        try:
            timestamp = datetime.fromisoformat(self.created_at)
        except (TypeError, ValueError) as exc:
            raise ValueError("created_at must be ISO-8601.") from exc
        if timestamp.tzinfo is None:
            raise ValueError("created_at must include a timezone.")
        _validate_internal_structure(self)
        from .serialization import propagation_semantic_fingerprint

        object.__setattr__(
            self,
            "semantic_fingerprint",
            propagation_semantic_fingerprint(self),
        )

    def to_dict(self, *, include_volatile: bool = True) -> dict[str, Any]:
        from .serialization import propagation_to_dict

        return propagation_to_dict(self, include_volatile=include_volatile)

    def to_json(self) -> str:
        from .serialization import propagation_to_json

        return propagation_to_json(self, include_volatile=True)

    def semantic_json(self) -> str:
        from .serialization import propagation_to_json

        return propagation_to_json(self, include_volatile=False)

    @classmethod
    def from_json(cls, value: str) -> DependencyPropagationResult:
        from .serialization import propagation_from_json

        return propagation_from_json(value)

    def semantically_equals(self, other: object) -> bool:
        return (
            isinstance(other, DependencyPropagationResult)
            and self.semantic_fingerprint == other.semantic_fingerprint
            and self.semantic_json() == other.semantic_json()
        )

    def summary_text(self) -> str:
        return "\n".join(
            (
                f"Demonstration: {self.demonstration_id}",
                f"Source changed: {self.source_candidate_field.text}",
                (
                    "Directly exposed fields: "
                    f"{self.summary.directly_exposed_fields}"
                ),
                (
                    "Transitively exposed fields: "
                    f"{self.summary.transitively_exposed_fields}"
                ),
                (
                    "Multipath-exposed fields: "
                    f"{self.summary.multipath_exposed_fields}"
                ),
                (
                    "Unique downstream exposed fields: "
                    f"{self.summary.total_unique_downstream_exposed_fields}"
                ),
                (
                    "Unique downstream exposed datasets: "
                    f"{self.summary.unique_downstream_exposed_datasets}"
                ),
                (
                    "Maximum exposure depth: "
                    f"{self.summary.maximum_exposure_depth}"
                ),
                "Compatibility evaluation: NOT_EVALUATED",
            )
        )


def _validate_internal_structure(
    result: DependencyPropagationResult,
) -> None:
    field_keys = tuple(
        item.field_key for item in result.field_exposure_registry
    )
    if len(field_keys) != len(set(field_keys)):
        raise ValueError("Field exposure keys must be unique.")
    source_records = tuple(
        item
        for item in result.field_exposure_registry
        if item.field_key == result.source_candidate_field
    )
    if (
        len(source_records) != 1
        or source_records[0].exposure_state
        is not FieldExposureState.SOURCE_CHANGED
        or source_records[0].minimum_depth != 0
    ):
        raise ValueError("Changed source exposure record is invalid.")
    dataset_urns = tuple(
        item.dataset_urn for item in result.dataset_exposure_registry
    )
    if len(dataset_urns) != len(set(dataset_urns)):
        raise ValueError("Dataset exposure keys must be unique.")
    relationship_ids = tuple(
        item.relationship_id
        for item in result.relationship_exposure_registry
    )
    if len(relationship_ids) != len(set(relationship_ids)):
        raise ValueError("Relationship exposure keys must be unique.")
    path_ids = tuple(item.path_id for item in result.path_registry)
    if len(path_ids) != len(set(path_ids)):
        raise ValueError("Dependency path IDs must be unique.")
    known_paths = set(path_ids)
    for item in result.field_exposure_registry:
        if item.parent_dataset_urn != item.field_key.dataset_urn:
            raise ValueError("Field exposure parent Dataset is inconsistent.")
        if item.minimum_depth < 0 or item.path_count < 0:
            raise ValueError("Field exposure depth/count cannot be negative.")
        if len(item.supporting_path_ids) != item.path_count:
            raise ValueError("Field exposure path count is inconsistent.")
        if any(value not in known_paths for value in item.supporting_path_ids):
            raise ValueError("Field exposure references a missing path.")
        if (
            item.representative_path_id is not None
            and item.representative_path_id not in item.supporting_path_ids
        ):
            raise ValueError("Representative dependency path is invalid.")
    known_fields = set(field_keys)
    for item in result.path_registry:
        if (
            not item.node_keys
            or item.node_keys[0] != result.source_candidate_field
            or item.node_keys[-1] != item.target_field
            or item.source_field != result.source_candidate_field
        ):
            raise ValueError("Dependency path source or target is invalid.")
        if len(item.relationship_ids) + 1 != len(item.node_keys):
            raise ValueError("Dependency path topology is malformed.")
        if item.depth != len(item.relationship_ids) or item.depth <= 0:
            raise ValueError("Dependency path depth is invalid.")
        if any(value not in known_fields for value in item.node_keys):
            raise ValueError("Dependency path references a missing field.")
    known_relationships = set(relationship_ids)
    for item in result.path_registry:
        if any(
            value not in known_relationships
            for value in item.relationship_ids
        ):
            raise ValueError("Dependency path references a missing edge.")
    for item in result.relationship_exposure_registry:
        if (
            item.compatibility_state
            is not RelationshipEvaluationState.NOT_EVALUATED
        ):
            raise ValueError("Relationship compatibility was resolved.")
        if len(item.supporting_path_ids) != item.path_count:
            raise ValueError("Relationship path count is inconsistent.")
        if any(value not in known_paths for value in item.supporting_path_ids):
            raise ValueError("Relationship references a missing path.")
    if any(not item.unchanged for item in result.input_artifact_hashes):
        raise ValueError("An authoritative artifact changed.")


def _is_sha256_fingerprint(value: object) -> bool:
    if not isinstance(value, str) or not value.startswith("sha256:"):
        return False
    digest = value.removeprefix("sha256:")
    return len(digest) == 64 and all(
        character in "0123456789abcdef" for character in digest
    )
