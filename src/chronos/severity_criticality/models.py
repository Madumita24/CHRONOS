"""Immutable CHRONOS Phase 4.3 severity and criticality models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from chronos.business_context import ContextAssetType, ContextCategory
from chronos.counterfactual_source import InputArtifactHash
from chronos.snapshot import FieldMachineKey
from chronos.technical_impact import TechnicalImpactState


SEVERITY_CRITICALITY_SCHEMA_VERSION = "1.0"


class AssessmentSubjectType(str, Enum):
    CHANGE = "change"
    FIELD = "field"
    DATASET = "dataset"
    CONTEXT_ASSET = "context_asset"


class TechnicalConsequence(str, Enum):
    CONFIRMED_IMPACT = "confirmed_impact"
    POTENTIAL_IMPACT = "potential_impact"
    UNRESOLVED_IMPACT = "unresolved_impact"
    NO_DEMONSTRATED_IMPACT = "no_demonstrated_impact"


class ContextCriticality(str, Enum):
    EXPLICITLY_CRITICAL = "explicitly_critical"
    ELEVATED_CONTEXT = "elevated_context"
    STANDARD_CONTEXT = "standard_context"
    CRITICALITY_UNKNOWN = "criticality_unknown"


class ExposureBreadth(str, Enum):
    LOCAL = "local"
    LIMITED = "limited"
    BROAD = "broad"
    WIDESPREAD = "widespread"


class EvidenceCertainty(str, Enum):
    ESTABLISHED = "established"
    CONDITIONAL = "conditional"
    UNRESOLVED = "unresolved"
    INSUFFICIENT = "insufficient"


class SeverityIfRealized(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    UNDETERMINED = "undetermined"


class SensitivityState(str, Enum):
    PII = "pii"
    NO_CERTIFIED_SENSITIVITY_SIGNAL = (
        "no_certified_sensitivity_signal"
    )
    SENSITIVITY_UNKNOWN = "sensitivity_unknown"


class ContextSignificance(str, Enum):
    ACCOUNTABILITY = "accountability"
    ORGANIZATIONAL_GROUPING = "organizational_grouping"
    CLASSIFICATION = "classification"
    BUSINESS_SEMANTICS = "business_semantics"
    CONFIGURED_METADATA = "configured_metadata"
    PRODUCT_GROUPING = "product_grouping"
    DOCUMENTATION_CONTEXT = "documentation_context"
    OPERATIONAL_DEPENDENCY_CONTEXT = "operational_dependency_context"
    CONSUMER_FACING_CONTEXT = "consumer_facing_context"


class CriticalityReasonCode(str, Enum):
    EXPLICIT_CRITICALITY_METADATA = "explicit_criticality_metadata"
    CONSUMER_REACH_PRESENT = "consumer_reach_present"
    MULTI_DATASET_CONTEXT = "multi_dataset_context"
    DATA_PRODUCT_CONTEXT_PRESENT = "data_product_context_present"
    PIPELINE_CONTEXT_PRESENT = "pipeline_context_present"
    BI_CONTEXT_PRESENT = "bi_context_present"
    SENSITIVITY_CLASSIFICATION_PRESENT = (
        "sensitivity_classification_present"
    )
    NO_EXPLICIT_CRITICALITY_METADATA = (
        "no_explicit_criticality_metadata"
    )
    CRITICALITY_EVIDENCE_INSUFFICIENT = (
        "criticality_evidence_insufficient"
    )


class SeverityReasonCode(str, Enum):
    CONFIRMED_TECHNICAL_FAILURE = "confirmed_technical_failure"
    UNRESOLVED_TECHNICAL_BOUNDARY = "unresolved_technical_boundary"
    POTENTIAL_DOWNSTREAM_CONSEQUENCE = (
        "potential_downstream_consequence"
    )
    EXPLICIT_CRITICAL_ASSET = "explicit_critical_asset"
    BROAD_CONSUMER_REACH = "broad_consumer_reach"
    LIMITED_CONSUMER_REACH = "limited_consumer_reach"
    CERTAINTY_UNRESOLVED = "certainty_unresolved"
    CERTAINTY_CONDITIONAL = "certainty_conditional"
    NO_DEMONSTRATED_TECHNICAL_IMPACT = (
        "no_demonstrated_technical_impact"
    )
    CRITICALITY_NOT_EXPLICIT = "criticality_not_explicit"


class MissingEvidenceClass(str, Enum):
    BUSINESS_CRITICALITY_TIER = "business_criticality_tier"
    CRITICALITY_BEARING_SLA_CLASSIFICATION = (
        "criticality_bearing_sla_classification"
    )
    PRODUCTION_TIER = "production_tier"
    EXPLICIT_ASSET_IMPORTANCE = "explicit_asset_importance"
    CONSUMER_CRITICALITY = "consumer_criticality"


class SeverityCriticalityValidationState(str, Enum):
    VALID = "valid"


@dataclass(frozen=True)
class SeverityRule:
    rule_id: str
    precedence: int
    technical_conditions: tuple[TechnicalConsequence, ...]
    criticality_conditions: tuple[ContextCriticality, ...]
    breadth_conditions: tuple[ExposureBreadth, ...]
    certainty_conditions: tuple[EvidenceCertainty, ...]
    result: SeverityIfRealized
    description: str


@dataclass(frozen=True)
class BreadthRule:
    rule_id: str
    precedence: int
    minimum_datasets: int
    minimum_consumer_assets: int
    minimum_context_assets: int
    result: ExposureBreadth
    description: str


@dataclass(frozen=True)
class SeverityRuleInputs:
    technical_consequence: TechnicalConsequence
    context_criticality: ContextCriticality
    exposure_breadth: ExposureBreadth
    evidence_certainty: EvidenceCertainty


@dataclass(frozen=True)
class SeverityRuleResult:
    rule_id: str
    inputs: SeverityRuleInputs
    severity_if_realized: SeverityIfRealized
    reason_codes: tuple[SeverityReasonCode, ...]


@dataclass(frozen=True)
class CriticalityEvidence:
    evidence_id: str
    subject_type: AssessmentSubjectType
    subject_id: str
    criticality: ContextCriticality
    reason_codes: tuple[CriticalityReasonCode, ...]
    explicit_semantic_identity: str | None
    explicit_semantic_value: str | None
    supporting_context_asset_ids: tuple[str, ...]
    supporting_context_relationship_ids: tuple[str, ...]
    explanation: str
    provenance_ids: tuple[str, ...]


@dataclass(frozen=True)
class BreadthMetrics:
    breadth_metrics_id: str
    subject_type: AssessmentSubjectType
    subject_id: str
    supporting_technical_fields: int
    supporting_datasets: int
    context_relationship_count: int
    unique_context_assets: int
    owners: int
    domains: int
    data_products: int
    documents: int
    pipeline_assets: int
    bi_assets: int
    charts: int
    dashboards: int
    supporting_technical_paths: int
    exposure_breadth: ExposureBreadth
    breadth_rule_id: str
    supporting_context_asset_ids: tuple[str, ...]
    supporting_path_ids: tuple[str, ...]

    @property
    def consumer_assets(self) -> int:
        return self.data_products + self.pipeline_assets + self.bi_assets


@dataclass(frozen=True)
class SensitivityEvidence:
    sensitivity_evidence_id: str
    subject_type: AssessmentSubjectType
    subject_id: str
    sensitivity_state: SensitivityState
    supporting_tag_ids: tuple[str, ...]
    explanation: str
    provenance_ids: tuple[str, ...]


@dataclass(frozen=True)
class MissingEvidence:
    missing_evidence_id: str
    subject_type: AssessmentSubjectType
    subject_id: str
    missing_classes: tuple[MissingEvidenceClass, ...]
    explanation: str


@dataclass(frozen=True)
class RootCauseReference:
    cause_id: str
    root_relationship_id: str
    technical_consequence: TechnicalConsequence
    evidence_certainty: EvidenceCertainty
    source_evidence_strength: str
    phase_4_1_technical_impact_fingerprint: str


@dataclass(frozen=True)
class FieldSeverityAssessment:
    field_key: FieldMachineKey
    dataset_urn: str
    technical_impact_state: TechnicalImpactState
    technical_consequence: TechnicalConsequence
    root_cause_ids: tuple[str, ...]
    context_mapping_ids: tuple[str, ...]
    criticality_evidence_id: str
    breadth_metrics_id: str
    sensitivity_evidence_id: str
    evidence_certainty: EvidenceCertainty
    severity_if_realized: SeverityIfRealized
    severity_rule_id: str
    severity_rule_inputs: SeverityRuleInputs
    criticality_reason_codes: tuple[CriticalityReasonCode, ...]
    severity_reason_codes: tuple[SeverityReasonCode, ...]
    missing_evidence_id: str
    provenance_ids: tuple[str, ...]
    explanation: str


@dataclass(frozen=True)
class DatasetSeverityAssessment:
    dataset_urn: str
    field_keys: tuple[FieldMachineKey, ...]
    confirmed_fields: int
    potential_fields: int
    unresolved_fields: int
    no_demonstrated_fields: int
    technical_consequence: TechnicalConsequence
    root_cause_ids: tuple[str, ...]
    context_asset_ids: tuple[str, ...]
    context_mapping_ids: tuple[str, ...]
    criticality_evidence_id: str
    breadth_metrics_id: str
    sensitivity_evidence_id: str
    evidence_certainty: EvidenceCertainty
    severity_if_realized: SeverityIfRealized
    severity_rule_id: str
    severity_rule_inputs: SeverityRuleInputs
    criticality_reason_codes: tuple[CriticalityReasonCode, ...]
    severity_reason_codes: tuple[SeverityReasonCode, ...]
    missing_evidence_id: str
    provenance_ids: tuple[str, ...]
    explanation: str


@dataclass(frozen=True)
class ContextAssetSignificanceAssessment:
    context_asset_id: str
    context_category: ContextCategory
    context_asset_type: ContextAssetType
    context_significance: ContextSignificance
    linked_technical_consequences: tuple[TechnicalConsequence, ...]
    supporting_dataset_urns: tuple[str, ...]
    supporting_field_keys: tuple[FieldMachineKey, ...]
    root_cause_ids: tuple[str, ...]
    context_mapping_ids: tuple[str, ...]
    criticality_evidence_id: str
    breadth_metrics_id: str
    sensitivity_evidence_id: str
    evidence_certainty: EvidenceCertainty
    missing_evidence_id: str
    provenance_ids: tuple[str, ...]
    explanation: str


@dataclass(frozen=True)
class ChangeLevelSeverityProfile:
    subject_id: str
    technical_consequence: TechnicalConsequence
    context_criticality: ContextCriticality
    exposure_breadth: ExposureBreadth
    sensitivity_state: SensitivityState
    evidence_certainty: EvidenceCertainty
    severity_if_realized: SeverityIfRealized
    root_cause_ids: tuple[str, ...]
    criticality_evidence_id: str
    breadth_metrics_id: str
    sensitivity_evidence_id: str
    missing_evidence_id: str
    severity_rule_id: str
    severity_rule_inputs: SeverityRuleInputs
    criticality_reason_codes: tuple[CriticalityReasonCode, ...]
    severity_reason_codes: tuple[SeverityReasonCode, ...]
    explanation: str
    provenance_ids: tuple[str, ...]


@dataclass(frozen=True)
class SeverityCriticalityAggregateMetrics:
    field_assessments: int
    dataset_assessments: int
    context_asset_assessments: int
    explicitly_critical_subjects: int
    elevated_context_subjects: int
    standard_context_subjects: int
    criticality_unknown_subjects: int
    pii_sensitive_subjects: int
    sensitivity_unknown_subjects: int
    critical_severity_fields: int
    high_severity_fields: int
    moderate_severity_fields: int
    low_severity_fields: int
    undetermined_severity_fields: int
    critical_severity_datasets: int
    high_severity_datasets: int
    moderate_severity_datasets: int
    low_severity_datasets: int
    undetermined_severity_datasets: int
    unique_context_assets: int
    context_relationships: int
    technical_to_context_mappings: int


@dataclass(frozen=True)
class SeverityCriticalityAnalysis:
    schema_version: str
    demonstration_id: str
    proposal_id: str
    phase_3_certification_fingerprint: str
    technical_impact_fingerprint: str
    business_context_fingerprint: str
    root_causes: tuple[RootCauseReference, ...]
    severity_rule_registry: tuple[SeverityRule, ...]
    breadth_rule_registry: tuple[BreadthRule, ...]
    field_assessments: tuple[FieldSeverityAssessment, ...]
    dataset_assessments: tuple[DatasetSeverityAssessment, ...]
    context_asset_assessments: tuple[
        ContextAssetSignificanceAssessment,
        ...,
    ]
    change_level_profile: ChangeLevelSeverityProfile
    criticality_evidence: tuple[CriticalityEvidence, ...]
    breadth_metrics: tuple[BreadthMetrics, ...]
    sensitivity_evidence: tuple[SensitivityEvidence, ...]
    missing_evidence: tuple[MissingEvidence, ...]
    aggregate_metrics: SeverityCriticalityAggregateMetrics
    canonical_narrative: str
    warnings: tuple[str, ...]
    input_artifact_hashes: tuple[InputArtifactHash, ...]
    created_at: str
    validation_state: SeverityCriticalityValidationState
    semantic_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        if self.schema_version != SEVERITY_CRITICALITY_SCHEMA_VERSION:
            raise ValueError("Unsupported severity-criticality schema.")
        if self.demonstration_id != "CHRONOS-DEMO-001":
            raise ValueError("Severity demonstration is invalid.")
        if self.validation_state is not SeverityCriticalityValidationState.VALID:
            raise ValueError("Only validated severity analysis is allowed.")
        for value in (
            self.phase_3_certification_fingerprint,
            self.technical_impact_fingerprint,
            self.business_context_fingerprint,
        ):
            if not _is_sha256_fingerprint(value):
                raise ValueError("Severity predecessor fingerprint is invalid.")
        try:
            timestamp = datetime.fromisoformat(self.created_at)
        except (TypeError, ValueError) as exc:
            raise ValueError("created_at must be ISO-8601.") from exc
        if timestamp.tzinfo is None:
            raise ValueError("created_at must include timezone.")
        _validate_internal(self)
        from .serialization import severity_semantic_fingerprint

        object.__setattr__(
            self,
            "semantic_fingerprint",
            severity_semantic_fingerprint(self),
        )

    def to_dict(self, *, include_volatile: bool = True) -> dict[str, Any]:
        from .serialization import severity_to_dict

        return severity_to_dict(self, include_volatile=include_volatile)

    def to_json(self) -> str:
        from .serialization import severity_to_json

        return severity_to_json(self, include_volatile=True)

    def semantic_json(self) -> str:
        from .serialization import severity_to_json

        return severity_to_json(self, include_volatile=False)

    @classmethod
    def from_json(cls, value: str) -> SeverityCriticalityAnalysis:
        from .serialization import severity_from_json

        return severity_from_json(value)

    def semantically_equals(self, other: object) -> bool:
        return (
            isinstance(other, SeverityCriticalityAnalysis)
            and self.semantic_fingerprint == other.semantic_fingerprint
            and self.semantic_json() == other.semantic_json()
        )


def _validate_internal(result: SeverityCriticalityAnalysis) -> None:
    registries = (
        (result.root_causes, "cause_id"),
        (result.severity_rule_registry, "rule_id"),
        (result.breadth_rule_registry, "rule_id"),
        (result.field_assessments, "field_key"),
        (result.dataset_assessments, "dataset_urn"),
        (result.context_asset_assessments, "context_asset_id"),
        (result.criticality_evidence, "evidence_id"),
        (result.breadth_metrics, "breadth_metrics_id"),
        (result.sensitivity_evidence, "sensitivity_evidence_id"),
        (result.missing_evidence, "missing_evidence_id"),
    )
    for values, attribute in registries:
        keys = tuple(getattr(item, attribute) for item in values)
        if len(keys) != len(set(keys)):
            raise ValueError(f"Duplicate severity key: {attribute}.")
    rule_ids = {item.rule_id for item in result.severity_rule_registry}
    breadth_rule_ids = {
        item.rule_id for item in result.breadth_rule_registry
    }
    criticality_ids = {
        item.evidence_id for item in result.criticality_evidence
    }
    breadth_ids = {
        item.breadth_metrics_id for item in result.breadth_metrics
    }
    sensitivity_ids = {
        item.sensitivity_evidence_id
        for item in result.sensitivity_evidence
    }
    missing_ids = {
        item.missing_evidence_id for item in result.missing_evidence
    }
    assessments = (
        tuple(result.field_assessments)
        + tuple(result.dataset_assessments)
        + (result.change_level_profile,)
    )
    for item in assessments:
        if (
            item.severity_rule_id not in rule_ids
            or item.criticality_evidence_id not in criticality_ids
            or item.breadth_metrics_id not in breadth_ids
            or item.sensitivity_evidence_id not in sensitivity_ids
            or item.missing_evidence_id not in missing_ids
        ):
            raise ValueError("Dangling severity assessment reference.")
    for item in result.context_asset_assessments:
        if (
            item.criticality_evidence_id not in criticality_ids
            or item.breadth_metrics_id not in breadth_ids
            or item.sensitivity_evidence_id not in sensitivity_ids
            or item.missing_evidence_id not in missing_ids
        ):
            raise ValueError("Dangling context significance reference.")
    if any(
        item.breadth_rule_id not in breadth_rule_ids
        for item in result.breadth_metrics
    ):
        raise ValueError("Dangling breadth rule reference.")
    if any(not item.unchanged for item in result.input_artifact_hashes):
        raise ValueError("A severity input artifact changed.")


def _is_sha256_fingerprint(value: object) -> bool:
    if not isinstance(value, str) or not value.startswith("sha256:"):
        return False
    digest = value.removeprefix("sha256:")
    return len(digest) == 64 and all(
        character in "0123456789abcdef" for character in digest
    )
