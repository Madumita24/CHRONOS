"""Immutable CHRONOS Phase 4.1 technical-impact models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from chronos.compatibility_evaluation import (
    CompatibilityReasonCode,
    CompatibilityState,
    EvidenceStrength,
)
from chronos.counterfactual_source import InputArtifactHash
from chronos.dependency_propagation import (
    FieldExposureState,
    RelationshipExposureState,
)
from chronos.snapshot import FieldMachineKey


TECHNICAL_IMPACT_SCHEMA_VERSION = "1.0"


class TechnicalImpactState(str, Enum):
    CONFIRMED_IMPACT = "confirmed_impact"
    POTENTIAL_IMPACT = "potential_impact"
    UNRESOLVED_IMPACT = "unresolved_impact"
    NO_DEMONSTRATED_IMPACT = "no_demonstrated_impact"


class SourceTechnicalRole(str, Enum):
    CHANGE_ORIGIN = "change_origin"


class TechnicalImpactReasonCode(str, Enum):
    CONFIRMED_INCOMPATIBLE_DEPENDENCY = (
        "confirmed_incompatible_dependency"
    )
    SOURCE_BOUNDARY_UNRESOLVED = "source_boundary_unresolved"
    DEPENDS_ON_UNRESOLVED_UPSTREAM = "depends_on_unresolved_upstream"
    CONDITIONAL_LOCAL_CONTINUITY = "conditional_local_continuity"
    COMPATIBILITY_CONFIRMED = "compatibility_confirmed"
    NO_TECHNICAL_CONSEQUENCE_OBSERVED = (
        "no_technical_consequence_observed"
    )
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class TechnicalImpactValidationState(str, Enum):
    VALID = "valid"


@dataclass(frozen=True)
class ImpactArtifactReference:
    artifact_name: str
    semantic_fingerprint: str
    object_id: str


@dataclass(frozen=True)
class ImpactCausalChain:
    chain_id: str
    cause_id: str
    ordered_references: tuple[ImpactArtifactReference, ...]


@dataclass(frozen=True)
class SourceChangeImpact:
    current_field: FieldMachineKey
    candidate_field: FieldMachineKey
    role: SourceTechnicalRole
    proposal_id: str
    human_explanation: str
    causal_chain_id: str


@dataclass(frozen=True)
class TechnicalImpactCause:
    cause_id: str
    root_relationship_id: str
    upstream_field: FieldMachineKey
    downstream_field: FieldMachineKey
    impact_state: TechnicalImpactState
    reason_codes: tuple[TechnicalImpactReasonCode, ...]
    compatibility_reason: CompatibilityReasonCode
    evidence_strength: EvidenceStrength
    affected_relationship_ids: tuple[str, ...]
    affected_path_ids: tuple[str, ...]
    affected_field_keys: tuple[FieldMachineKey, ...]
    affected_dataset_urns: tuple[str, ...]
    human_explanation: str
    causal_chain_id: str


@dataclass(frozen=True)
class RelationshipTechnicalImpact:
    relationship_id: str
    upstream_field: FieldMachineKey
    downstream_field: FieldMachineKey
    exposure_state: RelationshipExposureState
    compatibility_state: CompatibilityState
    technical_impact_state: TechnicalImpactState
    reason_codes: tuple[TechnicalImpactReasonCode, ...]
    supporting_compatibility_record_id: str
    supporting_path_ids: tuple[str, ...]
    upstream_cause_ids: tuple[str, ...]
    evidence_strength: EvidenceStrength
    current_provenance_ids: tuple[str, ...]
    counterfactual_provenance_ids: tuple[str, ...]
    explanation_relationship_id: str
    human_explanation: str
    causal_chain_id: str


@dataclass(frozen=True)
class PathTechnicalImpact:
    path_id: str
    ordered_relationship_ids: tuple[str, ...]
    target_field: FieldMachineKey
    depth: int
    compatibility_state: CompatibilityState
    technical_impact_state: TechnicalImpactState
    reason_codes: tuple[TechnicalImpactReasonCode, ...]
    relationship_impact_states: tuple[TechnicalImpactState, ...]
    uncertain_or_blocking_relationship_ids: tuple[str, ...]
    cause_ids: tuple[str, ...]
    current_provenance_ids: tuple[str, ...]
    counterfactual_provenance_ids: tuple[str, ...]
    explanation_path_id: str
    human_explanation: str
    causal_chain_id: str


@dataclass(frozen=True)
class FieldTechnicalImpact:
    field_key: FieldMachineKey
    dataset_urn: str
    exposure_state: FieldExposureState
    compatibility_state: CompatibilityState
    technical_impact_state: TechnicalImpactState
    minimum_depth: int
    path_count: int
    supporting_path_ids: tuple[str, ...]
    supporting_path_impact_states: tuple[TechnicalImpactState, ...]
    uncertain_or_blocking_relationship_ids: tuple[str, ...]
    reason_codes: tuple[TechnicalImpactReasonCode, ...]
    cause_ids: tuple[str, ...]
    current_provenance_ids: tuple[str, ...]
    counterfactual_provenance_ids: tuple[str, ...]
    explanation_field_key: FieldMachineKey
    human_explanation: str
    causal_chain_id: str


@dataclass(frozen=True)
class DatasetTechnicalImpactSummary:
    dataset_urn: str
    exposed_field_keys: tuple[FieldMachineKey, ...]
    confirmed_impacted_fields: int
    potential_impacted_fields: int
    unresolved_impacted_fields: int
    no_demonstrated_impact_fields: int
    technical_impact_state: TechnicalImpactState
    cause_ids: tuple[str, ...]
    human_explanation: str
    causal_chain_id: str


@dataclass(frozen=True)
class TechnicalImpactAggregateMetrics:
    technical_impact_causes: int
    confirmed_impacted_relationships: int
    potential_impacted_relationships: int
    unresolved_relationships: int
    no_demonstrated_impact_relationships: int
    confirmed_impacted_paths: int
    potential_impacted_paths: int
    unresolved_paths: int
    no_demonstrated_impact_paths: int
    confirmed_impacted_fields: int
    potential_impacted_fields: int
    unresolved_fields: int
    no_demonstrated_impact_fields: int
    downstream_dataset_summaries: int


@dataclass(frozen=True)
class TechnicalImpactAnalysis:
    schema_version: str
    demonstration_id: str
    proposal_id: str
    phase_3_certification_fingerprint: str
    source_change: SourceChangeImpact
    technical_impact_causes: tuple[TechnicalImpactCause, ...]
    relationship_impacts: tuple[RelationshipTechnicalImpact, ...]
    path_impacts: tuple[PathTechnicalImpact, ...]
    field_impacts: tuple[FieldTechnicalImpact, ...]
    dataset_summaries: tuple[DatasetTechnicalImpactSummary, ...]
    causal_chains: tuple[ImpactCausalChain, ...]
    aggregate_metrics: TechnicalImpactAggregateMetrics
    canonical_narrative: str
    warnings: tuple[str, ...]
    input_artifact_hashes: tuple[InputArtifactHash, ...]
    created_at: str
    validation_state: TechnicalImpactValidationState
    semantic_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        if self.schema_version != TECHNICAL_IMPACT_SCHEMA_VERSION:
            raise ValueError("Unsupported technical-impact schema.")
        if self.demonstration_id != "CHRONOS-DEMO-001":
            raise ValueError("Technical-impact demonstration is invalid.")
        if self.validation_state is not TechnicalImpactValidationState.VALID:
            raise ValueError("Only validated technical impact is allowed.")
        if not _is_sha256_fingerprint(
            self.phase_3_certification_fingerprint
        ):
            raise ValueError("Phase 3 certification fingerprint is invalid.")
        try:
            timestamp = datetime.fromisoformat(self.created_at)
        except (TypeError, ValueError) as exc:
            raise ValueError("created_at must be ISO-8601.") from exc
        if timestamp.tzinfo is None:
            raise ValueError("created_at must include timezone.")
        _validate_internal(self)
        from .serialization import technical_impact_semantic_fingerprint

        object.__setattr__(
            self,
            "semantic_fingerprint",
            technical_impact_semantic_fingerprint(self),
        )

    def to_dict(self, *, include_volatile: bool = True) -> dict[str, Any]:
        from .serialization import technical_impact_to_dict

        return technical_impact_to_dict(
            self,
            include_volatile=include_volatile,
        )

    def to_json(self) -> str:
        from .serialization import technical_impact_to_json

        return technical_impact_to_json(self, include_volatile=True)

    def semantic_json(self) -> str:
        from .serialization import technical_impact_to_json

        return technical_impact_to_json(self, include_volatile=False)

    @classmethod
    def from_json(cls, value: str) -> TechnicalImpactAnalysis:
        from .serialization import technical_impact_from_json

        return technical_impact_from_json(value)

    def semantically_equals(self, other: object) -> bool:
        return (
            isinstance(other, TechnicalImpactAnalysis)
            and self.semantic_fingerprint == other.semantic_fingerprint
            and self.semantic_json() == other.semantic_json()
        )


def _validate_internal(result: TechnicalImpactAnalysis) -> None:
    registries = (
        (result.technical_impact_causes, "cause_id"),
        (result.relationship_impacts, "relationship_id"),
        (result.path_impacts, "path_id"),
        (result.field_impacts, "field_key"),
        (result.dataset_summaries, "dataset_urn"),
        (result.causal_chains, "chain_id"),
    )
    for values, attribute in registries:
        keys = tuple(getattr(item, attribute) for item in values)
        if len(keys) != len(set(keys)):
            raise ValueError(f"Duplicate technical-impact key: {attribute}.")
    cause_ids = {item.cause_id for item in result.technical_impact_causes}
    referenced_causes = (
        tuple(
            value
            for item in result.relationship_impacts
            for value in item.upstream_cause_ids
        )
        + tuple(
            value for item in result.path_impacts for value in item.cause_ids
        )
        + tuple(
            value for item in result.field_impacts for value in item.cause_ids
        )
        + tuple(
            value for item in result.dataset_summaries for value in item.cause_ids
        )
    )
    if any(value not in cause_ids for value in referenced_causes):
        raise ValueError("Dangling technical-impact cause.")
    chain_ids = {item.chain_id for item in result.causal_chains}
    chain_refs = (
        (result.source_change.causal_chain_id,)
        + tuple(item.causal_chain_id for item in result.technical_impact_causes)
        + tuple(item.causal_chain_id for item in result.relationship_impacts)
        + tuple(item.causal_chain_id for item in result.path_impacts)
        + tuple(item.causal_chain_id for item in result.field_impacts)
        + tuple(item.causal_chain_id for item in result.dataset_summaries)
    )
    if any(value not in chain_ids for value in chain_refs):
        raise ValueError("Dangling technical-impact causal chain.")
    if any(not item.unchanged for item in result.input_artifact_hashes):
        raise ValueError("A technical-impact input artifact changed.")


def _is_sha256_fingerprint(value: object) -> bool:
    if not isinstance(value, str) or not value.startswith("sha256:"):
        return False
    digest = value.removeprefix("sha256:")
    return len(digest) == 64 and all(
        character in "0123456789abcdef" for character in digest
    )
