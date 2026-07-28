"""Immutable CHRONOS Phase 3.4 compatibility evaluation models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from chronos.counterfactual_source import InputArtifactHash
from chronos.dependency_propagation import (
    FieldExposureState,
    RelationshipExposureState,
)
from chronos.future_graph import FutureRelationshipState
from chronos.snapshot import FieldMachineKey


COMPATIBILITY_EVALUATION_SCHEMA_VERSION = "1.0"


class CompatibilityState(str, Enum):
    COMPATIBLE = "compatible"
    INCOMPATIBLE = "incompatible"
    CONDITIONALLY_COMPATIBLE = "conditionally_compatible"
    UNKNOWN = "unknown"


class CompatibilityEvaluationState(str, Enum):
    EVALUATED = "evaluated"
    NOT_EVALUATED = "not_evaluated"


class EvidenceStrength(str, Enum):
    EXPLICIT = "explicit"
    DERIVED = "derived"
    INSUFFICIENT = "insufficient"


class CompatibilityReasonCode(str, Enum):
    EXPLICIT_IDENTIFIER_PRESERVED = "explicit_identifier_preserved"
    EXPLICIT_IDENTIFIER_CHANGED = "explicit_identifier_changed"
    EXPLICIT_TRANSFORM_COMPATIBLE = "explicit_transform_compatible"
    EXPLICIT_TRANSFORM_INCOMPATIBLE = "explicit_transform_incompatible"
    CONDITIONAL_TRANSFORM_DEPENDENCY = "conditional_transform_dependency"
    SOURCE_RENAME_SEMANTICS_UNKNOWN = "source_rename_semantics_unknown"
    TRANSFORM_SEMANTICS_MISSING = "transform_semantics_missing"
    QUERY_SEMANTICS_MISSING = "query_semantics_missing"
    UPSTREAM_COMPATIBILITY_UNKNOWN = "upstream_compatibility_unknown"
    MULTIPATH_MIXED_COMPATIBILITY = "multipath_mixed_compatibility"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class ExplicitRenameBehavior(str, Enum):
    ACCEPTS_RENAMED_INPUT = "accepts_renamed_input"
    REJECTS_RENAMED_INPUT = "rejects_renamed_input"
    CONDITIONAL = "conditional"


class CompatibilityValidationState(str, Enum):
    VALID = "valid"
    INVALID = "invalid"


@dataclass(frozen=True)
class SourceFieldChange:
    current_field: FieldMachineKey
    candidate_field: FieldMachineKey


@dataclass(frozen=True)
class RenameCompatibilityEvidence:
    current_upstream: FieldMachineKey
    current_downstream: FieldMachineKey
    candidate_upstream: FieldMachineKey
    candidate_downstream: FieldMachineKey
    transform_operations: tuple[str, ...]
    queries: tuple[str, ...]
    explicit_rename_behavior: ExplicitRenameBehavior | None

    @property
    def upstream_identity_changed(self) -> bool:
        return self.current_upstream != self.candidate_upstream

    @property
    def endpoints_preserved(self) -> bool:
        return (
            self.current_upstream == self.candidate_upstream
            and self.current_downstream == self.candidate_downstream
        )


@dataclass(frozen=True)
class CompatibilityDecision:
    compatibility_state: CompatibilityState
    evidence_strength: EvidenceStrength
    reason_code: CompatibilityReasonCode
    explanation: str


@dataclass(frozen=True)
class RelationshipCompatibilityEvaluation:
    relationship_id: str
    upstream_field: FieldMachineKey
    downstream_field: FieldMachineKey
    structural_state: FutureRelationshipState
    exposure_state: RelationshipExposureState
    evaluation_state: CompatibilityEvaluationState
    compatibility_state: CompatibilityState
    evidence_strength: EvidenceStrength
    reason_code: CompatibilityReasonCode
    explanation: str
    mapping_group_ids: tuple[str, ...]
    transform_operations: tuple[str, ...]
    query_evidence: tuple[str, ...]
    lineage_confidence_provenance: tuple[float, ...]
    supporting_path_ids: tuple[str, ...]
    current_provenance_ids: tuple[str, ...]
    counterfactual_provenance_ids: tuple[str, ...]


@dataclass(frozen=True)
class PathCompatibilityEvaluation:
    path_id: str
    target_field: FieldMachineKey
    depth: int
    relationship_ids: tuple[str, ...]
    edge_compatibility_states: tuple[CompatibilityState, ...]
    evaluation_state: CompatibilityEvaluationState
    compatibility_state: CompatibilityState
    reason_codes: tuple[CompatibilityReasonCode, ...]
    blocking_relationship_ids: tuple[str, ...]
    uncertain_relationship_ids: tuple[str, ...]
    current_provenance_ids: tuple[str, ...]
    counterfactual_provenance_ids: tuple[str, ...]


@dataclass(frozen=True)
class FieldCompatibilityEvaluation:
    field_key: FieldMachineKey
    exposure_state: FieldExposureState
    minimum_depth: int
    supporting_path_count: int
    supporting_path_ids: tuple[str, ...]
    incoming_relationship_ids: tuple[str, ...]
    incoming_relationship_states: tuple[CompatibilityState, ...]
    path_compatibility_states: tuple[CompatibilityState, ...]
    evaluation_state: CompatibilityEvaluationState
    compatibility_state: CompatibilityState
    evidence_strength: EvidenceStrength
    reason_codes: tuple[CompatibilityReasonCode, ...]
    current_provenance_ids: tuple[str, ...]
    counterfactual_provenance_ids: tuple[str, ...]


@dataclass(frozen=True)
class DatasetCompatibilitySummary:
    dataset_urn: str
    exposed_field_keys: tuple[FieldMachineKey, ...]
    compatible_exposed_fields: int
    incompatible_exposed_fields: int
    conditionally_compatible_exposed_fields: int
    unknown_exposed_fields: int
    compatibility_state: CompatibilityState
    reason_codes: tuple[CompatibilityReasonCode, ...]


@dataclass(frozen=True)
class CompatibilityCounts:
    compatible: int
    incompatible: int
    conditionally_compatible: int
    unknown: int

    @property
    def total(self) -> int:
        return (
            self.compatible
            + self.incompatible
            + self.conditionally_compatible
            + self.unknown
        )


@dataclass(frozen=True)
class EvidenceStrengthCounts:
    explicit: int
    derived: int
    insufficient: int

    @property
    def total(self) -> int:
        return self.explicit + self.derived + self.insufficient


@dataclass(frozen=True)
class CompatibilityAggregate:
    relationship_counts: CompatibilityCounts
    path_counts: CompatibilityCounts
    field_counts: CompatibilityCounts
    dataset_counts: CompatibilityCounts
    relationship_evidence_strength: EvidenceStrengthCounts


@dataclass(frozen=True)
class CompatibilityEvaluationResult:
    schema_version: str
    demonstration_id: str
    proposal_id: str
    source_change: SourceFieldChange
    future_graph_fingerprint: str
    dependency_propagation_fingerprint: str
    relationship_evaluations: tuple[
        RelationshipCompatibilityEvaluation,
        ...,
    ]
    path_evaluations: tuple[PathCompatibilityEvaluation, ...]
    field_evaluations: tuple[FieldCompatibilityEvaluation, ...]
    dataset_summaries: tuple[DatasetCompatibilitySummary, ...]
    aggregate: CompatibilityAggregate
    input_artifact_hashes: tuple[InputArtifactHash, ...]
    warnings: tuple[str, ...]
    validation_state: CompatibilityValidationState
    evaluated_at: str
    semantic_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        if self.schema_version != COMPATIBILITY_EVALUATION_SCHEMA_VERSION:
            raise ValueError("Unsupported compatibility schema version.")
        if self.demonstration_id != "CHRONOS-DEMO-001":
            raise ValueError("Compatibility demonstration identity is invalid.")
        if not self.proposal_id:
            raise ValueError("Proposal ID must not be empty.")
        for value in (
            self.future_graph_fingerprint,
            self.dependency_propagation_fingerprint,
        ):
            if not _is_sha256_fingerprint(value):
                raise ValueError("Input semantic fingerprint is invalid.")
        if self.validation_state is not CompatibilityValidationState.VALID:
            raise ValueError("Only validated compatibility results are allowed.")
        try:
            timestamp = datetime.fromisoformat(self.evaluated_at)
        except (TypeError, ValueError) as exc:
            raise ValueError("evaluated_at must be ISO-8601.") from exc
        if timestamp.tzinfo is None:
            raise ValueError("evaluated_at must include a timezone.")
        _validate_internal_structure(self)
        from .serialization import compatibility_semantic_fingerprint

        object.__setattr__(
            self,
            "semantic_fingerprint",
            compatibility_semantic_fingerprint(self),
        )

    def to_dict(self, *, include_volatile: bool = True) -> dict[str, Any]:
        from .serialization import compatibility_to_dict

        return compatibility_to_dict(self, include_volatile=include_volatile)

    def to_json(self) -> str:
        from .serialization import compatibility_to_json

        return compatibility_to_json(self, include_volatile=True)

    def semantic_json(self) -> str:
        from .serialization import compatibility_to_json

        return compatibility_to_json(self, include_volatile=False)

    @classmethod
    def from_json(cls, value: str) -> CompatibilityEvaluationResult:
        from .serialization import compatibility_from_json

        return compatibility_from_json(value)

    def semantically_equals(self, other: object) -> bool:
        return (
            isinstance(other, CompatibilityEvaluationResult)
            and self.semantic_fingerprint == other.semantic_fingerprint
            and self.semantic_json() == other.semantic_json()
        )


def _validate_internal_structure(
    result: CompatibilityEvaluationResult,
) -> None:
    relationship_ids = tuple(
        item.relationship_id for item in result.relationship_evaluations
    )
    path_ids = tuple(item.path_id for item in result.path_evaluations)
    field_keys = tuple(item.field_key for item in result.field_evaluations)
    dataset_urns = tuple(
        item.dataset_urn for item in result.dataset_summaries
    )
    for values, label in (
        (relationship_ids, "relationship"),
        (path_ids, "path"),
        (field_keys, "field"),
        (dataset_urns, "Dataset"),
    ):
        if len(values) != len(set(values)):
            raise ValueError(f"Compatibility {label} keys must be unique.")
    if any(
        item.evaluation_state is not CompatibilityEvaluationState.EVALUATED
        for item in result.relationship_evaluations
        + result.path_evaluations
        + result.field_evaluations
    ):
        raise ValueError("Every compatibility record must be evaluated.")
    known_relationships = set(relationship_ids)
    known_paths = set(path_ids)
    for item in result.path_evaluations:
        if len(item.relationship_ids) != len(
            item.edge_compatibility_states
        ):
            raise ValueError("Path edge compatibility is incomplete.")
        if any(
            value not in known_relationships
            for value in item.relationship_ids
        ):
            raise ValueError("Path references a missing relationship.")
    for item in result.field_evaluations:
        if (
            len(item.supporting_path_ids) != item.supporting_path_count
            or any(value not in known_paths for value in item.supporting_path_ids)
        ):
            raise ValueError("Field path references are inconsistent.")
        if len(item.incoming_relationship_ids) != len(
            item.incoming_relationship_states
        ):
            raise ValueError("Field incoming compatibility is incomplete.")
    if result.aggregate.relationship_counts.total != len(
        result.relationship_evaluations
    ):
        raise ValueError("Relationship aggregate is inconsistent.")
    if result.aggregate.path_counts.total != len(result.path_evaluations):
        raise ValueError("Path aggregate is inconsistent.")
    if result.aggregate.field_counts.total != len(result.field_evaluations):
        raise ValueError("Field aggregate is inconsistent.")
    if result.aggregate.dataset_counts.total != len(result.dataset_summaries):
        raise ValueError("Dataset aggregate is inconsistent.")
    if result.aggregate.relationship_evidence_strength.total != len(
        result.relationship_evaluations
    ):
        raise ValueError("Evidence-strength aggregate is inconsistent.")
    if any(not item.unchanged for item in result.input_artifact_hashes):
        raise ValueError("An authoritative compatibility input changed.")


def _is_sha256_fingerprint(value: object) -> bool:
    if not isinstance(value, str) or not value.startswith("sha256:"):
        return False
    digest = value.removeprefix("sha256:")
    return len(digest) == 64 and all(
        character in "0123456789abcdef" for character in digest
    )
