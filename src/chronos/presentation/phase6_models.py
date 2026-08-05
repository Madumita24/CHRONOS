"""Strict read-only presentation DTOs for certified Phase 6 packages."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .models import PresentationModel


CertificationState = Literal[
    "PHASE_6_CERTIFIED",
    "PHASE_6_CERTIFIED_WITH_NON_BLOCKING_LIMITATIONS",
    "PHASE_6_NOT_CERTIFIED",
]
AnalysisType = Literal["structural", "semantic", "pull_request", "repair"]
EvidenceClass = Literal[
    "OBSERVED DATAHUB",
    "CODE-DERIVED",
    "COUNTERFACTUAL",
    "MISSING EVIDENCE",
    "STATIC PROJECTED",
    "DECISION EVIDENCE",
]
EdgeCategory = Literal[
    "OBSERVED_DATAHUB_EDGE",
    "CODE_DERIVED_PROPOSED_EDGE",
    "COUNTERFACTUAL_EDGE",
    "REMOVED_EDGE",
    "UNRESOLVED_REFERENCE",
]
GraphMode = Literal["CURRENT", "PROPOSED", "DIFF", "PROJECTED_REPAIRED"]


class Phase6CertificationDTO(PresentationModel):
    state: CertificationState
    release_id: str
    certification_version: Literal["6.5.0"]
    package_fingerprint: str
    release_manifest_fingerprint: str
    top_level_certification_fingerprint: str
    limitations: tuple[str, ...]
    runtime_verified: Literal[False] = False


class TestTotalsDTO(PresentationModel):
    executed: int = Field(ge=0)
    passed: int = Field(ge=0)
    skipped: int = Field(ge=0)
    failed: int = Field(ge=0)

    @model_validator(mode="after")
    def arithmetic(self) -> "TestTotalsDTO":
        if self.executed != self.passed + self.skipped + self.failed:
            raise ValueError("Test totals are inconsistent.")
        return self


class ReleaseCertificationDTO(PresentationModel):
    certification: Phase6CertificationDTO
    source_commit: str
    source_tree: str
    test_totals: TestTotalsDTO
    skipped_test_count: int = Field(ge=0)
    supported_capabilities: tuple[str, ...]
    unsupported_capabilities: tuple[str, ...]
    golden_preservation_state: Literal["PASS"]


class AnalysisSummaryDTO(PresentationModel):
    analysis_id: str
    analysis_type: AnalysisType
    display_name: str
    scenario_id: str
    proposal_id: str
    certification_state: CertificationState
    decision: str
    operation: str
    repository_identity: str | None
    base_identity: str | None
    head_identity: str | None
    coherence: str | None
    conflict_count: int = Field(ge=0)
    root_cause_count: int = Field(ge=0)
    affected_file_count: int = Field(ge=0)
    affected_dataset_count: int = Field(ge=0)
    repair_action_count: int = Field(ge=0)
    configured_at: str | None
    warnings: tuple[str, ...]
    limitations: tuple[str, ...]
    manifest_fingerprint: str


class AnalysisIndexDTO(PresentationModel):
    certification: Phase6CertificationDTO
    analyses: tuple[AnalysisSummaryDTO, ...]


class EvidenceDTO(PresentationModel):
    evidence_id: str
    evidence_class: EvidenceClass
    subject: str
    statement: str
    certainty: str


class GraphNodeDTO(PresentationModel):
    node_id: str
    label: str
    node_type: str
    state: str
    evidence_class: EvidenceClass


class GraphEdgeDTO(PresentationModel):
    edge_id: str
    source: str
    target: str
    category: EdgeCategory
    evidence_class: EvidenceClass
    state: str


class GraphPathDTO(PresentationModel):
    path_id: str
    node_ids: tuple[str, ...]
    edge_ids: tuple[str, ...]
    root_ids: tuple[str, ...]
    contributing_file_ids: tuple[str, ...]
    target: str
    evidence_class: EvidenceClass


class AnalysisGraphDTO(PresentationModel):
    analysis_id: str
    mode: GraphMode
    available_modes: tuple[GraphMode, ...]
    runtime_verified: Literal[False] = False
    nodes: tuple[GraphNodeDTO, ...]
    edges: tuple[GraphEdgeDTO, ...]
    representative_paths: tuple[GraphPathDTO, ...]

    @model_validator(mode="after")
    def closure(self) -> "AnalysisGraphDTO":
        nodes = {item.node_id for item in self.nodes}
        edges = {item.edge_id for item in self.edges}
        if len(nodes) != len(self.nodes) or len(edges) != len(self.edges):
            raise ValueError("Graph IDs must be unique.")
        if any(item.source not in nodes or item.target not in nodes for item in self.edges):
            raise ValueError("Graph has a dangling edge endpoint.")
        if any(not set(path.node_ids) <= nodes or not set(path.edge_ids) <= edges for path in self.representative_paths):
            raise ValueError("Graph has a dangling representative path.")
        if self.mode not in self.available_modes or len(set(self.available_modes)) != len(self.available_modes):
            raise ValueError("Graph mode availability is invalid.")
        return self


class BaseAnalysisDTO(PresentationModel):
    analysis_id: str
    analysis_type: AnalysisType
    display_name: str
    scenario_id: str
    proposal_id: str
    operation: str
    decision: str
    certification: Phase6CertificationDTO
    manifest_fingerprint: str
    warnings: tuple[str, ...]
    limitations: tuple[str, ...]
    confirmed_runtime_failures: Literal[0] = 0
    execution_validity: Literal["UNVERIFIED"] = "UNVERIFIED"


class StructuralChangeDTO(PresentationModel):
    dataset_urn: str
    current_field: str
    proposed_field: str | None
    current_type: str | None
    proposed_type: str | None
    identity_mapping: str
    compatibility: Literal["COMPATIBLE", "INCOMPATIBLE", "UNKNOWN"]
    downstream_fields: int = Field(ge=0)
    downstream_datasets: int = Field(ge=0)
    root_causes: tuple[str, ...]
    blocking_questions: tuple[str, ...]
    required_evidence: tuple[str, ...]


class StructuralAnalysisView(BaseAnalysisDTO):
    analysis_type: Literal["structural"]
    change: StructuralChangeDTO


class SemanticDeltaDTO(PresentationModel):
    delta_id: str
    delta_type: Literal[
        "AGGREGATION_CHANGE",
        "FILTER_CHANGE",
        "JOIN_TYPE_CHANGE",
        "DERIVED_EXPRESSION_CHANGE",
        "OUTPUT_STRUCTURAL_CHANGE",
    ]
    before: str
    after: str
    affected_output: str | None
    affected_model: str
    scope: Literal["FIELD-SPECIFIC", "MODEL-WIDE"]
    certainty: str
    evidence_class: EvidenceClass
    potential_consequence: str
    missing_evidence: tuple[str, ...]


class SemanticAnalysisView(BaseAnalysisDTO):
    analysis_type: Literal["semantic"]
    model_dataset_urn: str
    before_fingerprint: str
    after_fingerprint: str
    semantic_compatibility: Literal[
        "SEMANTICALLY_COMPATIBLE",
        "SEMANTICALLY_INCOMPATIBLE",
        "SEMANTIC_COMPATIBILITY_UNKNOWN",
    ]
    structural_compatibility: Literal[
        "STRUCTURALLY_COMPATIBLE",
        "STRUCTURALLY_INCOMPATIBLE",
        "STRUCTURAL_COMPATIBILITY_UNKNOWN",
    ]
    deltas: tuple[SemanticDeltaDTO, ...]
    affected_output_fields: tuple[str, ...]
    root_causes: tuple[str, ...]
    blocking_questions: tuple[str, ...]


class ChangedFileDTO(PresentationModel):
    file_id: str
    path: str
    status: str
    category: str
    parser: str
    material_state: str
    delta_count: int = Field(ge=0)
    warning_count: int = Field(ge=0)
    resolved_entity_count: int = Field(ge=0)
    unresolved_reference_count: int = Field(ge=0)


class LogicalGroupDTO(PresentationModel):
    group_id: str
    current_identity: str | None
    proposed_identities: tuple[str, ...]
    contributing_file_ids: tuple[str, ...]
    structural_change_ids: tuple[str, ...]
    semantic_change_ids: tuple[str, ...]
    stale_reference_ids: tuple[str, ...]
    coherence: str
    conflict_ids: tuple[str, ...]
    root_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]


class ConflictDTO(PresentationModel):
    conflict_id: str
    current_entity: str
    proposed_identities: tuple[str, ...]
    supporting_file_ids: tuple[str, ...]
    reason: str
    required_evidence: tuple[str, ...]


class PullRequestAnalysisView(BaseAnalysisDTO):
    analysis_type: Literal["pull_request"]
    repository: str
    base_identity: str
    head_identity: str
    coherence: Literal["COHERENT", "PARTIALLY_COHERENT", "INCONSISTENT", "UNRESOLVED"]
    changed_files: tuple[ChangedFileDTO, ...]
    logical_groups: tuple[LogicalGroupDTO, ...]
    conflicts: tuple[ConflictDTO, ...]
    root_causes: tuple[str, ...]


class RepairabilityDTO(PresentationModel):
    root_id: str
    root_type: str
    state: Literal[
        "AUTO_REPAIRABLE",
        "CONDITIONALLY_REPAIRABLE",
        "MANUAL_DECISION_REQUIRED",
        "UNSUPPORTED",
        "BLOCKED_BY_CONFLICT",
        "BLOCKED_BY_MISSING_EVIDENCE",
    ]
    reason: str
    evidence_ids: tuple[str, ...]
    remaining_uncertainty: tuple[str, ...]
    evidence_class: Literal["CODE-DERIVED"] = "CODE-DERIVED"


class RepairActionDTO(PresentationModel):
    action_id: str
    application_order: int = Field(ge=1)
    file: str
    exact_target: str
    current_value: str
    proposed_value: str
    rule: str
    root_id: str
    evidence_ids: tuple[str, ...]
    dependencies: tuple[str, ...]
    protected_semantics: tuple[str, ...]
    remaining_validation: tuple[str, ...]
    evidence_class: Literal["STATIC PROJECTED"] = "STATIC PROJECTED"


class PatchSummaryDTO(PresentationModel):
    patch_id: str
    file: str
    hunk_count: int = Field(ge=0)
    fingerprint: str
    action_ids: tuple[str, ...]
    protected_semantics_state: str
    static_validation_state: str


class RepairComparisonDTO(PresentationModel):
    original_coherence: str
    projected_coherence: str
    original_stale_references: int = Field(ge=0)
    projected_stale_references: int = Field(ge=0)
    targeted_roots: int = Field(ge=0)
    projected_closed_roots: int = Field(ge=0)
    remaining_roots: int = Field(ge=0)
    new_roots: int = Field(ge=0)
    conflicts_before: int = Field(ge=0)
    conflicts_after: int = Field(ge=0)
    unresolved_semantic_questions: int = Field(ge=0)
    execution_validity: Literal["UNVERIFIED"] = "UNVERIFIED"


class RepairAnalysisView(BaseAnalysisDTO):
    analysis_type: Literal["repair"]
    predecessor_analysis_id: str
    repair_disposition: Literal[
        "PARTIAL_REPAIR_CANDIDATE",
        "NO_SUPPORTED_AUTOMATIC_REPAIR",
        "REPAIR_BLOCKED_BY_CONFLICT",
        "REPAIR_CANDIDATE_READY_FOR_REVIEW",
    ]
    repair_completeness: Literal[
        "PARTIALLY_ADDRESSED_SELECTED_ROOTS",
        "FULLY_ADDRESSED_SELECTED_ROOTS",
        "NO_SUPPORTED_REPAIR",
    ]
    projected_state_label: Literal["PROJECTED REPAIRED - STATIC ONLY - RUNTIME UNVERIFIED"]
    repairability: tuple[RepairabilityDTO, ...]
    actions: tuple[RepairActionDTO, ...]
    patches: tuple[PatchSummaryDTO, ...]
    comparison: RepairComparisonDTO
    remaining_findings: tuple[str, ...]
    phase_7_requirements: tuple[str, ...]


AnalysisDetailDTO = Annotated[
    StructuralAnalysisView | SemanticAnalysisView | PullRequestAnalysisView | RepairAnalysisView,
    Field(discriminator="analysis_type"),
]


class PatchLineDTO(PresentationModel):
    old_line: int | None
    new_line: int | None
    kind: Literal["context", "addition", "removal", "header"]
    text: str


class PatchPreviewDTO(PresentationModel):
    analysis_id: str
    patch_id: str
    file: str
    fingerprint: str
    lines: tuple[PatchLineDTO, ...]
    original_excerpt: tuple[str, ...]
    candidate_excerpt: tuple[str, ...]
    label: Literal["CANDIDATE - NOT APPLIED"]
    runtime_verified: Literal[False] = False
