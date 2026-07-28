"""Immutable CHRONOS Phase 4.4 impact-synthesis models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from chronos.counterfactual_source import InputArtifactHash
from chronos.severity_criticality import (
    ContextCriticality,
    EvidenceCertainty,
    ExposureBreadth,
    SeverityIfRealized,
    TechnicalConsequence,
)
from chronos.snapshot import FieldMachineKey
from chronos.technical_impact import SourceChangeImpact


IMPACT_SYNTHESIS_SCHEMA_VERSION = "1.0"


class DecisionDisposition(str, Enum):
    PROCEED = "proceed"
    PROCEED_WITH_CONDITIONS = "proceed_with_conditions"
    HOLD_FOR_REVIEW = "hold_for_review"
    BLOCK_CONFIRMED_INCOMPATIBILITY = (
        "block_confirmed_incompatibility"
    )


class DecisionCertainty(str, Enum):
    HIGH_CONFIDENCE = "high_confidence"
    SUPPORTED = "supported"
    LIMITED = "limited"
    UNRESOLVED = "unresolved"


class DecisionReasonCode(str, Enum):
    UNRESOLVED_SOURCE_COMPATIBILITY = (
        "unresolved_source_compatibility"
    )
    MATERIAL_SEVERITY_IF_REALIZED = (
        "material_severity_if_realized"
    )
    WIDESPREAD_DEPENDENCY_REACH = "widespread_dependency_reach"
    MISSING_EXECUTION_EVIDENCE = "missing_execution_evidence"
    CONFIRMED_INCOMPATIBILITY = "confirmed_incompatibility"
    NO_DEMONSTRATED_TECHNICAL_IMPACT = (
        "no_demonstrated_technical_impact"
    )
    ADEQUATE_COMPATIBILITY_EVIDENCE = (
        "adequate_compatibility_evidence"
    )
    CONDITIONAL_APPROVAL_REQUIREMENTS = (
        "conditional_approval_requirements"
    )


class DecisionEvidenceType(str, Enum):
    TECHNICAL_FINDING = "technical_finding"
    BUSINESS_CONTEXT = "business_context"
    SEVERITY_PROFILE = "severity_profile"
    COMPATIBILITY_EVIDENCE = "compatibility_evidence"
    EXPLANATION_EVIDENCE = "explanation_evidence"


class BlockingQuestionResolutionState(str, Enum):
    UNRESOLVED = "unresolved"
    RESOLVED_COMPATIBLE = "resolved_compatible"
    RESOLVED_INCOMPATIBLE = "resolved_incompatible"


class RequiredEvidenceState(str, Enum):
    REQUIRED_FOR_DECISION_RESOLUTION = (
        "required_for_decision_resolution"
    )
    SATISFIED = "satisfied"


class RepresentativePathKind(str, Enum):
    SHORT = "short"
    DEEP = "deep"
    MULTIPATH = "multipath"


class ContextHighlightKind(str, Enum):
    TECHNICAL_DATASET = "technical_dataset"
    BI_CONSUMER = "bi_consumer"
    DATA_PRODUCT = "data_product"
    PIPELINE_CONTEXT = "pipeline_context"
    ASSOCIATED_OWNER = "associated_owner"


class ImpactSynthesisValidationState(str, Enum):
    VALID = "valid"


@dataclass(frozen=True)
class DecisionRule:
    rule_id: str
    precedence: int
    technical_consequence_conditions: tuple[TechnicalConsequence, ...]
    impact_certainty_conditions: tuple[EvidenceCertainty, ...]
    severity_if_realized_conditions: tuple[SeverityIfRealized, ...]
    breadth_conditions: tuple[ExposureBreadth, ...]
    criticality_conditions: tuple[ContextCriticality, ...]
    requires_explicit_conditions: bool | None
    resulting_disposition: DecisionDisposition
    decision_certainty: DecisionCertainty
    reason_codes: tuple[DecisionReasonCode, ...]
    description: str


@dataclass(frozen=True)
class DecisionRuleInputs:
    technical_consequence: TechnicalConsequence
    impact_certainty: EvidenceCertainty
    severity_if_realized: SeverityIfRealized
    breadth: ExposureBreadth
    criticality: ContextCriticality
    has_explicit_conditions: bool


@dataclass(frozen=True)
class DecisionRuleResult:
    rule_id: str
    inputs: DecisionRuleInputs
    disposition: DecisionDisposition
    decision_certainty: DecisionCertainty
    reason_codes: tuple[DecisionReasonCode, ...]


@dataclass(frozen=True)
class DecisionEvidence:
    evidence_id: str
    evidence_type: DecisionEvidenceType
    source_artifact: str
    source_fingerprint: str
    supporting_object_ids: tuple[str, ...]
    statement: str


@dataclass(frozen=True)
class DecisionReason:
    reason_id: str
    reason_code: DecisionReasonCode
    statement: str
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class RequiredEvidence:
    required_evidence_id: str
    evidence_class: str
    subject: str
    reason: str
    state: RequiredEvidenceState
    source_uncertainty_id: str


@dataclass(frozen=True)
class BlockingQuestion:
    question_id: str
    question: str
    subject: str
    reason: str
    root_cause_id: str
    affected_field_keys: tuple[FieldMachineKey, ...]
    affected_dataset_urns: tuple[str, ...]
    affected_path_ids: tuple[str, ...]
    required_evidence_ids: tuple[str, ...]
    resolution_state: BlockingQuestionResolutionState


@dataclass(frozen=True)
class ImpactSynthesisSummary:
    changed_source_fields: int
    technical_root_causes: int
    confirmed_downstream_failures: int
    potential_downstream_fields: int
    unresolved_downstream_fields: int
    no_demonstrated_impact_fields: int
    downstream_datasets: int
    technical_relationships: int
    unresolved_relationships: int
    dependency_paths: int
    unresolved_paths: int
    context_assets: int
    context_relationships: int
    field_to_context_mappings: int
    breadth: ExposureBreadth
    criticality: ContextCriticality
    severity_if_realized: SeverityIfRealized
    technical_certainty: EvidenceCertainty
    downstream_field_keys: tuple[FieldMachineKey, ...]
    downstream_dataset_urns: tuple[str, ...]
    technical_relationship_ids: tuple[str, ...]
    dependency_path_ids: tuple[str, ...]
    context_asset_ids: tuple[str, ...]


@dataclass(frozen=True)
class RepresentativeEvidencePath:
    representative_path_id: str
    kind: RepresentativePathKind
    technical_path_id: str
    source_field: FieldMachineKey
    unresolved_boundary_relationship_id: str
    ordered_relationship_ids: tuple[str, ...]
    downstream_field: FieldMachineKey
    downstream_dataset_urn: str
    context_mapping_id: str
    context_asset_id: str
    explanation: str


@dataclass(frozen=True)
class ContextHighlight:
    highlight_id: str
    kind: ContextHighlightKind
    subject_id: str
    display_name: str | None
    selection_basis: str
    supporting_dataset_urns: tuple[str, ...]
    supporting_field_keys: tuple[FieldMachineKey, ...]


@dataclass(frozen=True)
class ChangeReviewAssessment:
    disposition: DecisionDisposition
    decision_certainty: DecisionCertainty
    technical_consequence: TechnicalConsequence
    impact_certainty: EvidenceCertainty
    criticality: ContextCriticality
    breadth: ExposureBreadth
    severity_if_realized: SeverityIfRealized
    root_cause_ids: tuple[str, ...]
    decision_rule_id: str
    selected_rule_inputs: DecisionRuleInputs
    decision_reason_ids: tuple[str, ...]
    blocking_question_ids: tuple[str, ...]
    required_evidence_ids: tuple[str, ...]
    scope_summary: ImpactSynthesisSummary
    narrative: str


@dataclass(frozen=True)
class ImpactSynthesis:
    schema_version: str
    demonstration_id: str
    proposal_id: str
    operation: str
    phase_3_certification_fingerprint: str
    technical_impact_fingerprint: str
    business_context_fingerprint: str
    severity_criticality_fingerprint: str
    source_change: SourceChangeImpact
    root_causes: tuple[str, ...]
    decision_rule_registry: tuple[DecisionRule, ...]
    decision_evidence: tuple[DecisionEvidence, ...]
    decision_reasons: tuple[DecisionReason, ...]
    blocking_questions: tuple[BlockingQuestion, ...]
    required_evidence: tuple[RequiredEvidence, ...]
    representative_evidence_paths: tuple[
        RepresentativeEvidencePath, ...
    ]
    context_highlights: tuple[ContextHighlight, ...]
    scope_summary: ImpactSynthesisSummary
    change_severity_profile: DecisionRuleInputs
    decision_disposition: DecisionDisposition
    decision_certainty: DecisionCertainty
    decision_rule_id: str
    decision_reason_codes: tuple[DecisionReasonCode, ...]
    assessment: ChangeReviewAssessment
    what_we_know: tuple[str, ...]
    what_we_do_not_know: tuple[str, ...]
    warnings: tuple[str, ...]
    input_artifact_hashes: tuple[InputArtifactHash, ...]
    created_at: str
    validation_state: ImpactSynthesisValidationState
    semantic_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        if self.schema_version != IMPACT_SYNTHESIS_SCHEMA_VERSION:
            raise ValueError("Unsupported impact-synthesis schema.")
        if self.demonstration_id != "CHRONOS-DEMO-001":
            raise ValueError("Impact-synthesis demonstration is invalid.")
        if self.validation_state is not ImpactSynthesisValidationState.VALID:
            raise ValueError("Only validated impact synthesis is allowed.")
        if self.operation != "field_rename":
            raise ValueError("Phase 4.4 supports FIELD_RENAME only.")
        for value in (
            self.phase_3_certification_fingerprint,
            self.technical_impact_fingerprint,
            self.business_context_fingerprint,
            self.severity_criticality_fingerprint,
        ):
            if not _is_sha256_fingerprint(value):
                raise ValueError("Invalid predecessor fingerprint.")
        try:
            timestamp = datetime.fromisoformat(self.created_at)
        except (TypeError, ValueError) as exc:
            raise ValueError("created_at must be ISO-8601.") from exc
        if timestamp.tzinfo is None:
            raise ValueError("created_at must include timezone.")
        _validate_internal(self)
        from .serialization import impact_synthesis_semantic_fingerprint

        object.__setattr__(
            self,
            "semantic_fingerprint",
            impact_synthesis_semantic_fingerprint(self),
        )

    def to_dict(self, *, include_volatile: bool = True) -> dict[str, Any]:
        from .serialization import impact_synthesis_to_dict

        return impact_synthesis_to_dict(
            self, include_volatile=include_volatile
        )

    def to_json(self) -> str:
        from .serialization import impact_synthesis_to_json

        return impact_synthesis_to_json(self, include_volatile=True)

    def semantic_json(self) -> str:
        from .serialization import impact_synthesis_to_json

        return impact_synthesis_to_json(self, include_volatile=False)

    @classmethod
    def from_json(cls, value: str) -> ImpactSynthesis:
        from .serialization import impact_synthesis_from_json

        return impact_synthesis_from_json(value)

    def semantically_equals(self, other: object) -> bool:
        return (
            isinstance(other, ImpactSynthesis)
            and self.semantic_fingerprint == other.semantic_fingerprint
            and self.semantic_json() == other.semantic_json()
        )


def _validate_internal(result: ImpactSynthesis) -> None:
    registries = (
        (result.decision_rule_registry, "rule_id"),
        (result.decision_evidence, "evidence_id"),
        (result.decision_reasons, "reason_id"),
        (result.blocking_questions, "question_id"),
        (result.required_evidence, "required_evidence_id"),
        (result.representative_evidence_paths, "representative_path_id"),
        (result.context_highlights, "highlight_id"),
    )
    indexes: dict[str, set[str]] = {}
    for values, attribute in registries:
        ids = tuple(getattr(item, attribute) for item in values)
        if len(ids) != len(set(ids)):
            raise ValueError(f"Duplicate impact-synthesis key: {attribute}.")
        indexes[attribute] = set(ids)
    assessment = result.assessment
    if (
        result.scope_summary != assessment.scope_summary
        or result.change_severity_profile
        != assessment.selected_rule_inputs
        or result.decision_disposition is not assessment.disposition
        or result.decision_certainty is not assessment.decision_certainty
        or result.decision_rule_id != assessment.decision_rule_id
        or result.decision_reason_codes
        != tuple(
            reason.reason_code
            for reason in result.decision_reasons
            if reason.reason_id in assessment.decision_reason_ids
        )
    ):
        raise ValueError("Top-level decision summary is inconsistent.")
    if assessment.decision_rule_id not in indexes["rule_id"]:
        raise ValueError("Selected decision rule does not exist.")
    if not set(assessment.decision_reason_ids) <= indexes["reason_id"]:
        raise ValueError("Assessment has a dangling decision reason.")
    if not set(assessment.blocking_question_ids) <= indexes["question_id"]:
        raise ValueError("Assessment has a dangling blocking question.")
    if not set(assessment.required_evidence_ids) <= indexes[
        "required_evidence_id"
    ]:
        raise ValueError("Assessment has dangling required evidence.")
    evidence_ids = indexes["evidence_id"]
    if any(
        not set(reason.evidence_ids) <= evidence_ids
        for reason in result.decision_reasons
    ):
        raise ValueError("Decision reason has dangling evidence.")
    required_ids = indexes["required_evidence_id"]
    if any(
        not set(question.required_evidence_ids) <= required_ids
        for question in result.blocking_questions
    ):
        raise ValueError("Blocking question has dangling evidence.")
    if any(not item.unchanged for item in result.input_artifact_hashes):
        raise ValueError("An authoritative Phase 4.4 input changed.")


def _is_sha256_fingerprint(value: object) -> bool:
    if not isinstance(value, str) or not value.startswith("sha256:"):
        return False
    digest = value.removeprefix("sha256:")
    return len(digest) == 64 and all(
        character in "0123456789abcdef" for character in digest
    )
