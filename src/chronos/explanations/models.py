"""Immutable models for CHRONOS Phase 3.5 evidence explanations."""

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


EXPLANATION_BUNDLE_SCHEMA_VERSION = "1.0"


class ExplanationStepType(str, Enum):
    CURRENT_FACT = "current_fact"
    PROPOSED_CHANGE = "proposed_change"
    COUNTERFACTUAL_DERIVATION = "counterfactual_derivation"
    STRUCTURAL_DEPENDENCY = "structural_dependency"
    DEPENDENCY_EXPOSURE = "dependency_exposure"
    COMPATIBILITY_EVIDENCE = "compatibility_evidence"
    COMPATIBILITY_UNCERTAINTY = "compatibility_uncertainty"
    CONCLUSION = "conclusion"


class ExplanationClassification(str, Enum):
    VERIFIED_CURRENT = "verified_current"
    PROPOSED = "proposed"
    COUNTERFACTUAL = "counterfactual"
    DERIVED = "derived"
    INSUFFICIENT = "insufficient"
    CONCLUSION = "conclusion"


class ExplanationValidationState(str, Enum):
    VALID = "valid"
    INVALID = "invalid"


@dataclass(frozen=True)
class ArtifactEvidenceReference:
    artifact_name: str
    semantic_fingerprint: str
    supporting_object_id: str


@dataclass(frozen=True)
class EvidenceChain:
    chain_id: str
    references: tuple[ArtifactEvidenceReference, ...]


@dataclass(frozen=True)
class ExplanationStep:
    step_id: str
    step_type: ExplanationStepType
    subject: str
    statement_code: str
    human_statement: str
    supporting_artifact: str
    supporting_object_id: str
    provenance_ids: tuple[str, ...]
    classification: ExplanationClassification


@dataclass(frozen=True)
class UncertaintyRecord:
    uncertainty_id: str
    subject: str
    reason_code: CompatibilityReasonCode
    missing_evidence_types: tuple[str, ...]
    affected_relationship_ids: tuple[str, ...]
    affected_path_ids: tuple[str, ...]
    affected_field_keys: tuple[FieldMachineKey, ...]
    upstream_uncertainty_ids: tuple[str, ...]
    human_explanation: str
    evidence_chain_id: str


@dataclass(frozen=True)
class SourceExplanation:
    current_field: FieldMachineKey
    candidate_field: FieldMachineKey
    current_native_type: str | None
    current_normalized_type: str | None
    nullable: bool | None
    is_part_of_key: bool | None
    preserved_properties: tuple[str, ...]
    steps: tuple[ExplanationStep, ...]
    human_explanation: str
    evidence_chain_id: str


@dataclass(frozen=True)
class RelationshipExplanation:
    relationship_id: str
    current_upstream: FieldMachineKey
    current_downstream: FieldMachineKey
    candidate_upstream: FieldMachineKey
    candidate_downstream: FieldMachineKey
    exposure_state: RelationshipExposureState
    compatibility_state: CompatibilityState
    evidence_strength: EvidenceStrength
    reason_codes: tuple[CompatibilityReasonCode, ...]
    transform_operations: tuple[str, ...]
    query_evidence: tuple[str, ...]
    lineage_confidence_provenance: tuple[float, ...]
    mapping_group_ids: tuple[str, ...]
    uncertainty_ids: tuple[str, ...]
    steps: tuple[ExplanationStep, ...]
    human_explanation: str
    evidence_chain_id: str


@dataclass(frozen=True)
class PathExplanation:
    path_id: str
    ordered_fields: tuple[FieldMachineKey, ...]
    ordered_relationship_ids: tuple[str, ...]
    depth: int
    edge_compatibility_states: tuple[CompatibilityState, ...]
    first_uncertain_or_blocking_relationship_id: str | None
    compatibility_state: CompatibilityState
    reason_codes: tuple[CompatibilityReasonCode, ...]
    uncertainty_ids: tuple[str, ...]
    steps: tuple[ExplanationStep, ...]
    human_explanation: str
    current_provenance_ids: tuple[str, ...]
    counterfactual_provenance_ids: tuple[str, ...]
    evidence_chain_id: str


@dataclass(frozen=True)
class FieldExplanation:
    field_key: FieldMachineKey
    platform: str
    dataset_urn: str
    minimum_depth: int
    exposure_state: FieldExposureState
    supporting_path_ids: tuple[str, ...]
    incoming_relationship_ids: tuple[str, ...]
    compatibility_state: CompatibilityState
    reason_codes: tuple[CompatibilityReasonCode, ...]
    uncertain_or_blocking_relationship_ids: tuple[str, ...]
    all_paths_share_first_uncertainty: bool
    path_conclusions_differ: bool
    uncertainty_ids: tuple[str, ...]
    steps: tuple[ExplanationStep, ...]
    human_explanation: str
    current_provenance_ids: tuple[str, ...]
    counterfactual_provenance_ids: tuple[str, ...]
    evidence_chain_id: str


@dataclass(frozen=True)
class DatasetExplanation:
    dataset_urn: str
    exposed_field_keys: tuple[FieldMachineKey, ...]
    compatible_fields: int
    incompatible_fields: int
    conditionally_compatible_fields: int
    unknown_fields: int
    compatibility_state: CompatibilityState
    steps: tuple[ExplanationStep, ...]
    human_explanation: str
    evidence_chain_id: str


@dataclass(frozen=True)
class ExplanationBundle:
    schema_version: str
    demonstration_id: str
    compatibility_fingerprint: str
    future_graph_fingerprint: str
    propagation_fingerprint: str
    source_explanation: SourceExplanation
    relationship_explanations: tuple[RelationshipExplanation, ...]
    path_explanations: tuple[PathExplanation, ...]
    field_explanations: tuple[FieldExplanation, ...]
    dataset_explanations: tuple[DatasetExplanation, ...]
    uncertainties: tuple[UncertaintyRecord, ...]
    evidence_chains: tuple[EvidenceChain, ...]
    canonical_narrative: str
    input_artifact_hashes: tuple[InputArtifactHash, ...]
    created_at: str
    validation_state: ExplanationValidationState
    semantic_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        if self.schema_version != EXPLANATION_BUNDLE_SCHEMA_VERSION:
            raise ValueError("Unsupported explanation schema.")
        if self.demonstration_id != "CHRONOS-DEMO-001":
            raise ValueError("Explanation demonstration identity is invalid.")
        if self.validation_state is not ExplanationValidationState.VALID:
            raise ValueError("Only validated explanation bundles are allowed.")
        for value in (
            self.compatibility_fingerprint,
            self.future_graph_fingerprint,
            self.propagation_fingerprint,
        ):
            if not _is_sha256_fingerprint(value):
                raise ValueError("Explanation input fingerprint is invalid.")
        timestamp = datetime.fromisoformat(self.created_at)
        if timestamp.tzinfo is None:
            raise ValueError("created_at must include a timezone.")
        _validate_internal(self)
        from .serialization import explanation_semantic_fingerprint

        object.__setattr__(
            self,
            "semantic_fingerprint",
            explanation_semantic_fingerprint(self),
        )

    def to_dict(self, *, include_volatile: bool = True) -> dict[str, Any]:
        from .serialization import explanation_to_dict

        return explanation_to_dict(self, include_volatile=include_volatile)

    def to_json(self) -> str:
        from .serialization import explanation_to_json

        return explanation_to_json(self, include_volatile=True)

    def semantic_json(self) -> str:
        from .serialization import explanation_to_json

        return explanation_to_json(self, include_volatile=False)

    @classmethod
    def from_json(cls, value: str) -> ExplanationBundle:
        from .serialization import explanation_from_json

        return explanation_from_json(value)

    def explain_source_change(self) -> SourceExplanation:
        return self.source_explanation

    def explain_relationship(self, relationship_id: str) -> RelationshipExplanation:
        return _find(
            self.relationship_explanations,
            "relationship_id",
            relationship_id,
        )

    def explain_path(self, path_id: str) -> PathExplanation:
        return _find(self.path_explanations, "path_id", path_id)

    def explain_field(self, field_key: FieldMachineKey) -> FieldExplanation:
        return _find(self.field_explanations, "field_key", field_key)

    def explain_dataset(self, dataset_urn: str) -> DatasetExplanation:
        return _find(self.dataset_explanations, "dataset_urn", dataset_urn)

    def explain_uncertainty(self, uncertainty_id: str) -> UncertaintyRecord:
        return _find(self.uncertainties, "uncertainty_id", uncertainty_id)

    def semantically_equals(self, other: object) -> bool:
        return (
            isinstance(other, ExplanationBundle)
            and self.semantic_fingerprint == other.semantic_fingerprint
            and self.semantic_json() == other.semantic_json()
        )


def _validate_internal(bundle: ExplanationBundle) -> None:
    registries = (
        (bundle.relationship_explanations, "relationship_id"),
        (bundle.path_explanations, "path_id"),
        (bundle.field_explanations, "field_key"),
        (bundle.dataset_explanations, "dataset_urn"),
        (bundle.uncertainties, "uncertainty_id"),
        (bundle.evidence_chains, "chain_id"),
    )
    for registry, attribute in registries:
        keys = tuple(getattr(item, attribute) for item in registry)
        if len(keys) != len(set(keys)):
            raise ValueError(f"Duplicate explanation key: {attribute}.")
    chain_ids = {item.chain_id for item in bundle.evidence_chains}
    chain_references = (
        (bundle.source_explanation.evidence_chain_id,)
        + tuple(item.evidence_chain_id for item in bundle.relationship_explanations)
        + tuple(item.evidence_chain_id for item in bundle.path_explanations)
        + tuple(item.evidence_chain_id for item in bundle.field_explanations)
        + tuple(item.evidence_chain_id for item in bundle.dataset_explanations)
        + tuple(item.evidence_chain_id for item in bundle.uncertainties)
    )
    if any(value not in chain_ids for value in chain_references):
        raise ValueError("Dangling explanation evidence chain.")
    uncertainty_ids = {item.uncertainty_id for item in bundle.uncertainties}
    referenced_uncertainties = (
        tuple(
            value
            for item in bundle.relationship_explanations
            for value in item.uncertainty_ids
        )
        + tuple(
            value
            for item in bundle.path_explanations
            for value in item.uncertainty_ids
        )
        + tuple(
            value
            for item in bundle.field_explanations
            for value in item.uncertainty_ids
        )
    )
    if any(value not in uncertainty_ids for value in referenced_uncertainties):
        raise ValueError("Dangling explanation uncertainty.")
    if any(
        value not in uncertainty_ids
        for item in bundle.uncertainties
        for value in item.upstream_uncertainty_ids
    ):
        raise ValueError("Dangling upstream uncertainty.")
    steps = (
        bundle.source_explanation.steps
        + tuple(
            step
            for item in bundle.relationship_explanations
            for step in item.steps
        )
        + tuple(
            step for item in bundle.path_explanations for step in item.steps
        )
        + tuple(
            step for item in bundle.field_explanations for step in item.steps
        )
        + tuple(
            step for item in bundle.dataset_explanations for step in item.steps
        )
    )
    if len({item.step_id for item in steps}) != len(steps):
        raise ValueError("Duplicate explanation step ID.")
    for chain in bundle.evidence_chains:
        artifact_names = tuple(item.artifact_name for item in chain.references)
        if len(artifact_names) != len(set(artifact_names)):
            raise ValueError("Duplicate artifact in evidence chain.")
        if any(
            not _is_sha256_fingerprint(item.semantic_fingerprint)
            for item in chain.references
        ):
            raise ValueError("Invalid evidence-chain fingerprint.")
    if any(not item.unchanged for item in bundle.input_artifact_hashes):
        raise ValueError("An explanation input artifact changed.")


def _find(values: tuple[Any, ...], attribute: str, key: Any) -> Any:
    matches = tuple(item for item in values if getattr(item, attribute) == key)
    if len(matches) != 1:
        raise KeyError(key)
    return matches[0]


def _is_sha256_fingerprint(value: object) -> bool:
    if not isinstance(value, str):
        return False
    if not value.startswith("sha256:"):
        return False
    digest = value.removeprefix("sha256:")
    return len(digest) == 64 and all(c in "0123456789abcdef" for c in digest)
