"""Strict browser-facing DTOs for the Phase 5.3 impact explorer."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from .models import (
    CertificationDTO,
    FieldIdentityDTO,
    PresentationModel,
    SeverityDistributionDTO,
)


class ExplorerSummaryDTO(PresentationModel):
    downstream_fields: int
    downstream_datasets: int
    dependency_paths: int
    structural_relationships: int
    context_assets: int
    context_relationships: int
    field_to_context_mappings: int
    root_causes: int
    blocking_questions: int
    required_evidence_classes: int
    confirmed_failures: int
    unresolved_fields: int
    compatibility_unknown: int
    compatibility_conditional: int
    compatibility_compatible: int
    compatibility_incompatible: int
    field_severity_distribution: SeverityDistributionDTO
    dataset_severity_distribution: SeverityDistributionDTO
    technical_consequence: str
    technical_certainty: str
    decision_certainty: str
    severity_if_realized: str
    breadth: str
    criticality: str
    sensitivity: str
    explicit_business_criticality_present: bool


class RootCauseStepDTO(PresentationModel):
    step_id: str
    stage: str
    label: str
    value: str
    classification: Literal[
        "observed",
        "proposed",
        "counterfactual",
        "unresolved",
        "conditional",
        "decision",
    ]


class ExplorerRootCauseDTO(PresentationModel):
    cause_id: str
    root_relationship_id: str
    proposed_source: FieldIdentityDTO
    first_downstream_dependency: FieldIdentityDTO
    compatibility_state: Literal["unknown"]
    evidence_state: Literal["insufficient"]
    technical_consequence: Literal["unresolved_impact"]
    affected_fields: int
    affected_datasets: int
    affected_paths: int
    confirmed_failures: int
    human_explanation: str
    steps: tuple[RootCauseStepDTO, ...]
    provenance_references: tuple[str, ...]


class ExplorerBlockingQuestionDTO(PresentationModel):
    question_id: str
    question: str
    subject: str
    reason: str
    root_cause_id: str
    root_relationship_id: str
    resolution_state: Literal["unresolved"]
    affected_fields: int
    affected_datasets: int
    affected_paths: int
    required_evidence_ids: tuple[str, ...]


class ExplorerRequiredEvidenceDTO(PresentationModel):
    evidence_id: str
    evidence_class: str
    label: str
    subject: str
    reason: str
    state: str
    availability: Literal["not_available_required"]
    source_uncertainty_id: str


class ExplorerEvidenceRecordDTO(PresentationModel):
    evidence_id: str
    classification: Literal[
        "observed",
        "counterfactual",
        "derived",
        "missing",
        "decision",
    ]
    category: str
    source_artifact: str
    subject: str
    claim_supported: str
    verification_state: Literal[
        "verified",
        "certified_derivation",
        "insufficient",
        "required",
        "certified_decision",
    ]
    description: str
    provenance_references: tuple[str, ...]


class FieldImpactDTO(PresentationModel):
    field_id: str
    machine_key: str
    identity: FieldIdentityDTO
    display_identity: str
    dataset_urn: str
    dataset_display_name: str
    platform: str
    shortest_exposure_depth: int = Field(ge=1)
    exposure_classification: str
    supporting_path_ids: tuple[str, ...]
    supporting_path_count: int = Field(ge=1)
    compatibility_state: str
    technical_impact_state: str
    certainty: str
    severity_if_realized: str
    criticality: str
    breadth: str
    sensitivity: str
    reason_codes: tuple[str, ...]
    root_cause_id: str
    evidence_references: tuple[str, ...]
    context_asset_ids: tuple[str, ...]
    context_mapping_ids: tuple[str, ...]
    human_explanation: str
    provenance_references: tuple[str, ...]


class DatasetImpactDTO(PresentationModel):
    dataset_id: str
    dataset_urn: str
    display_name: str
    platform: str
    exposed_field_count: int = Field(ge=1)
    field_ids: tuple[str, ...]
    supporting_path_ids: tuple[str, ...]
    technical_impact_state: str
    technical_summary: str
    severity_if_realized: str
    certainty: str
    criticality: str
    breadth: str
    sensitivity: str
    root_cause_ids: tuple[str, ...]
    context_asset_ids: tuple[str, ...]
    context_mapping_ids: tuple[str, ...]
    reason_codes: tuple[str, ...]
    provenance_references: tuple[str, ...]


class ContextAttributeDTO(PresentationModel):
    name: str
    values: tuple[str, ...]


class ContextAssetDTO(PresentationModel):
    context_asset_id: str
    group: Literal["governance", "operational", "consumer"]
    category: str
    asset_type: str
    display_name: str
    resolution_state: str
    connected_dataset_urns: tuple[str, ...]
    connected_field_ids: tuple[str, ...]
    relationship_count: int = Field(ge=1)
    relationship_ids: tuple[str, ...]
    mapping_ids: tuple[str, ...]
    supporting_path_ids: tuple[str, ...]
    attributes: tuple[ContextAttributeDTO, ...]
    provenance_references: tuple[str, ...]


class ContextRelationshipDTO(PresentationModel):
    relationship_id: str
    relationship_category: str
    context_category: str
    anchor_dataset_urn: str
    anchor_field_id: str | None
    context_asset_ids: tuple[str, ...]
    exposure_type: str


class ContextMappingDTO(PresentationModel):
    mapping_id: str
    field_id: str
    dataset_urn: str
    context_relationship_id: str
    context_asset_id: str
    context_category: str
    exposure_type: str
    linkage_state: str
    supporting_path_ids: tuple[str, ...]
    provenance_references: tuple[str, ...]


class ExplorerPathDTO(PresentationModel):
    path_id: str
    graph_node_ids: tuple[str, ...]
    graph_edge_ids: tuple[str, ...]
    ordered_fields: tuple[FieldIdentityDTO, ...]
    relationship_ids: tuple[str, ...]
    target_field_id: str
    target_field: FieldIdentityDTO
    target_dataset_urn: str
    depth: int = Field(ge=1)
    compatibility_state: str
    technical_impact_state: str
    severity_if_realized: str
    certainty: str
    uncertain_relationship_ids: tuple[str, ...]
    evidence_references: tuple[str, ...]
    context_asset_ids: tuple[str, ...]
    human_explanation: str
    provenance_references: tuple[str, ...]


class ExplorerRelationshipDTO(PresentationModel):
    graph_edge_id: str
    relationship_id: str
    upstream: FieldIdentityDTO
    downstream: FieldIdentityDTO
    is_root_uncertainty: bool
    compatibility_state: str
    technical_impact_state: str
    evidence_strength: str
    reason_codes: tuple[str, ...]
    supporting_path_ids: tuple[str, ...]
    path_participation_count: int = Field(ge=1)
    human_explanation: str
    evidence_references: tuple[str, ...]
    provenance_references: tuple[str, ...]


class DecisionReasonDetailDTO(PresentationModel):
    reason_id: str
    reason_code: str
    statement: str
    evidence_ids: tuple[str, ...]


class DecisionInputDTO(PresentationModel):
    technical_consequence: str
    impact_certainty: str
    severity_if_realized: str
    breadth: str
    criticality: str


class DecisionExplanationDTO(PresentationModel):
    disposition: Literal["hold_for_review"]
    decision_rule_id: Literal["decision-hold-unresolved-material-broad"]
    decision_certainty: Literal["high_confidence"]
    technical_certainty: Literal["unresolved"]
    inputs: DecisionInputDTO
    reasons: tuple[DecisionReasonDetailDTO, ...]
    narrative: str
    what_we_know: tuple[str, ...]
    what_we_do_not_know: tuple[str, ...]
    confirmed_failure_distinction: str


class CertifiedImpactExplorer(PresentationModel):
    certification: CertificationDTO
    summary: ExplorerSummaryDTO
    root_cause: ExplorerRootCauseDTO
    blocking_question: ExplorerBlockingQuestionDTO
    required_evidence: tuple[ExplorerRequiredEvidenceDTO, ...]
    evidence_chain: tuple[ExplorerEvidenceRecordDTO, ...]
    fields: tuple[FieldImpactDTO, ...]
    datasets: tuple[DatasetImpactDTO, ...]
    context_assets: tuple[ContextAssetDTO, ...]
    context_relationships: tuple[ContextRelationshipDTO, ...]
    context_mappings: tuple[ContextMappingDTO, ...]
    paths: tuple[ExplorerPathDTO, ...]
    relationships: tuple[ExplorerRelationshipDTO, ...]
    decision_explanation: DecisionExplanationDTO

    @model_validator(mode="after")
    def validate_explorer(self) -> "CertifiedImpactExplorer":
        expected = {
            "downstream_fields": 25,
            "downstream_datasets": 20,
            "dependency_paths": 48,
            "structural_relationships": 27,
            "context_assets": 66,
            "context_relationships": 211,
            "field_to_context_mappings": 257,
            "root_causes": 1,
            "blocking_questions": 1,
            "required_evidence_classes": 4,
            "confirmed_failures": 0,
            "unresolved_fields": 25,
            "compatibility_unknown": 1,
            "compatibility_conditional": 26,
            "compatibility_compatible": 0,
            "compatibility_incompatible": 0,
        }
        if any(getattr(self.summary, key) != value for key, value in expected.items()):
            raise ValueError("Certified explorer summary is invalid.")
        collections = (
            (self.fields, "field_id", 25),
            (self.datasets, "dataset_id", 20),
            (self.context_assets, "context_asset_id", 66),
            (self.context_relationships, "relationship_id", 211),
            (self.context_mappings, "mapping_id", 257),
            (self.paths, "path_id", 48),
            (self.relationships, "relationship_id", 27),
        )
        for records, attribute, count in collections:
            values = tuple(getattr(item, attribute) for item in records)
            if len(values) != count or len(values) != len(set(values)):
                raise ValueError(f"Explorer {attribute} cardinality is invalid.")
        field_ids = {item.field_id for item in self.fields}
        dataset_ids = {item.dataset_id for item in self.datasets}
        asset_ids = {item.context_asset_id for item in self.context_assets}
        context_relationship_ids = {
            item.relationship_id for item in self.context_relationships
        }
        mapping_ids = {item.mapping_id for item in self.context_mappings}
        path_ids = {item.path_id for item in self.paths}
        relationship_ids = {
            item.relationship_id for item in self.relationships
        }
        if any(
            not set(item.field_ids) <= field_ids
            or not set(item.context_asset_ids) <= asset_ids
            or not set(item.context_mapping_ids) <= mapping_ids
            for item in self.datasets
        ):
            raise ValueError("A dataset explorer reference is dangling.")
        if any(
            not set(item.connected_field_ids) <= field_ids
            or not set(item.mapping_ids) <= mapping_ids
            for item in self.context_assets
        ):
            raise ValueError("A context asset explorer reference is dangling.")
        if any(
            item.field_id not in field_ids
            or item.context_asset_id not in asset_ids
            or item.context_relationship_id not in context_relationship_ids
            for item in self.context_mappings
        ):
            raise ValueError("A context mapping explorer reference is dangling.")
        if any(
            item.target_field_id not in field_ids
            or not set(item.relationship_ids) <= relationship_ids
            for item in self.paths
        ):
            raise ValueError("A path explorer reference is dangling.")
        if any(
            not set(item.supporting_path_ids) <= path_ids
            for item in self.fields + self.relationships
        ):
            raise ValueError("A supporting path reference is dangling.")
        if (
            self.root_cause.cause_id
            != "technical-impact-cause-source-rename-semantics"
            or self.root_cause.compatibility_state != "unknown"
            or self.root_cause.confirmed_failures != 0
            or len(self.required_evidence) != 4
            or self.summary.explicit_business_criticality_present
        ):
            raise ValueError("Certified explorer semantics are invalid.")
        if not dataset_ids:
            raise ValueError("Certified explorer datasets are missing.")
        return self
