"""Strict browser-facing DTOs for certified change review."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


def _camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


class PresentationModel(BaseModel):
    """Immutable strict DTO base with a camelCase JSON contract."""

    model_config = ConfigDict(
        alias_generator=_camel,
        populate_by_name=True,
        serialize_by_alias=True,
        extra="forbid",
        frozen=True,
    )


class CertificationDTO(PresentationModel):
    status: str
    fingerprint: str
    certified_at: str
    checks_passed: int
    check_count: int
    scope_statement: str


class FieldIdentityDTO(PresentationModel):
    dataset_urn: str
    field_path: str


class ChangeDTO(PresentationModel):
    demonstration_id: str
    proposal_id: str
    operation: str
    dataset_urn: str
    display_identity: str
    platform: str
    environment: str
    current_field: str
    requested_field: str
    description: str | None
    rationale: str | None


class DecisionReasonDTO(PresentationModel):
    code: str
    statement: str


class DecisionDTO(PresentationModel):
    disposition: str
    disposition_label: str
    decision_certainty: str
    technical_certainty: str
    decision_rule_id: str
    reasons: tuple[DecisionReasonDTO, ...]
    narrative: str


class TechnicalSummaryDTO(PresentationModel):
    change_origins: int
    root_causes: int
    relationship_impacts: int
    dependency_paths: int
    downstream_fields: int
    downstream_datasets: int
    confirmed_downstream_failures: int
    potential_relationships: int
    unresolved_relationships: int
    unresolved_paths: int
    unresolved_fields: int


class ScopeSummaryDTO(PresentationModel):
    datasets: int
    downstream_fields: int
    connected_context_assets: int
    context_relationships: int
    field_to_context_mappings: int
    context_categories: tuple[str, ...]
    unresolved_context_references: int


class SeverityDistributionDTO(PresentationModel):
    critical: int
    high: int
    moderate: int
    low: int
    undetermined: int


class SeverityProfileDTO(PresentationModel):
    technical_consequence: str
    technical_certainty: str
    context_criticality: str
    breadth: str
    sensitivity: str
    severity_if_realized: str
    field_distribution: SeverityDistributionDTO
    dataset_distribution: SeverityDistributionDTO


class RootCauseDTO(PresentationModel):
    root_cause_id: str
    root_relationship_id: str
    title: str
    explanation: str


class BlockingQuestionDTO(PresentationModel):
    question_id: str
    question: str
    subject: str
    reason: str
    resolution_state: str
    affected_fields: int
    affected_datasets: int
    affected_paths: int
    required_evidence_ids: tuple[str, ...]


class RequiredEvidenceDTO(PresentationModel):
    evidence_id: str
    evidence_class: str
    subject: str
    reason: str
    state: str


class RepresentativePathDTO(PresentationModel):
    path_id: str
    kind: str
    technical_path_id: str
    source_field: FieldIdentityDTO
    downstream_field: FieldIdentityDTO
    downstream_dataset_urn: str
    context_asset_id: str
    unresolved_boundary_relationship_id: str
    relationship_ids: tuple[str, ...]
    hop_count: int = Field(ge=1)
    explanation: str


class ContextHighlightDTO(PresentationModel):
    highlight_id: str
    kind: str
    subject_id: str
    display_name: str | None
    selection_basis: str
    supporting_dataset_urns: tuple[str, ...]
    supporting_field_count: int


class SourceStateDTO(PresentationModel):
    classification: str
    dataset_urn: str
    field_path: str
    field_name: str
    native_type: str | None
    normalized_type: str
    schema_field_count: int


class CertifiedChangeReview(PresentationModel):
    certification: CertificationDTO
    change: ChangeDTO
    decision: DecisionDTO
    technical_summary: TechnicalSummaryDTO
    scope_summary: ScopeSummaryDTO
    severity_profile: SeverityProfileDTO
    root_cause: RootCauseDTO
    blocking_questions: tuple[BlockingQuestionDTO, ...]
    required_evidence: tuple[RequiredEvidenceDTO, ...]
    representative_paths: tuple[RepresentativePathDTO, ...]
    context_highlights: tuple[ContextHighlightDTO, ...]
    current_state: SourceStateDTO
    counterfactual_state: SourceStateDTO


class HealthDTO(PresentationModel):
    status: str
    review_id: str
    certification_fingerprint: str
