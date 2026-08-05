"""Immutable Phase 6.4 repair-generation contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any


REPAIR_ENGINE_VERSION = "6.4.0"
REPAIR_ARTIFACT_SCHEMA_VERSION = "1.0"
MAX_PREDECESSOR_ARTIFACT_BYTES = 5 * 1024 * 1024
MAX_PATCH_HUNKS = 500
MAX_REPAIR_ACTIONS = 500


class RepairOperation(str, Enum):
    GENERATE_REPAIR = "GENERATE_REPAIR"


class RepairMode(str, Enum):
    ALL_SUPPORTED = "ALL_SUPPORTED"
    SELECTED_ROOTS = "SELECTED_ROOTS"
    SELECTED_GROUPS = "SELECTED_GROUPS"


class RepairabilityState(str, Enum):
    AUTO_REPAIRABLE = "AUTO_REPAIRABLE"
    CONDITIONALLY_REPAIRABLE = "CONDITIONALLY_REPAIRABLE"
    MANUAL_DECISION_REQUIRED = "MANUAL_DECISION_REQUIRED"
    UNSUPPORTED = "UNSUPPORTED"
    BLOCKED_BY_CONFLICT = "BLOCKED_BY_CONFLICT"
    BLOCKED_BY_MISSING_EVIDENCE = "BLOCKED_BY_MISSING_EVIDENCE"


class RepairDisposition(str, Enum):
    REPAIR_CANDIDATE_READY_FOR_REVIEW = "REPAIR_CANDIDATE_READY_FOR_REVIEW"
    PARTIAL_REPAIR_CANDIDATE = "PARTIAL_REPAIR_CANDIDATE"
    NO_SUPPORTED_AUTOMATIC_REPAIR = "NO_SUPPORTED_AUTOMATIC_REPAIR"
    REPAIR_BLOCKED_BY_CONFLICT = "REPAIR_BLOCKED_BY_CONFLICT"
    REPAIR_GENERATION_FAILED = "REPAIR_GENERATION_FAILED"


class RepairCompleteness(str, Enum):
    FULLY_ADDRESSED_SELECTED_ROOTS = "FULLY_ADDRESSED_SELECTED_ROOTS"
    PARTIALLY_ADDRESSED_SELECTED_ROOTS = "PARTIALLY_ADDRESSED_SELECTED_ROOTS"
    NO_SUPPORTED_REPAIR = "NO_SUPPORTED_REPAIR"


class EditOperation(str, Enum):
    REPLACE_STATIC_SCALAR = "REPLACE_STATIC_SCALAR"
    RENAME_MAPPING_KEY = "RENAME_MAPPING_KEY"
    UPDATE_MAPPING_VALUE = "UPDATE_MAPPING_VALUE"
    ADD_DECLARATION = "ADD_DECLARATION"
    REMOVE_DECLARATION = "REMOVE_DECLARATION"
    UPDATE_SQL_IDENTIFIER = "UPDATE_SQL_IDENTIFIER"
    UPDATE_SQL_OUTPUT_ALIAS = "UPDATE_SQL_OUTPUT_ALIAS"
    UPDATE_DBT_COLUMN_NAME = "UPDATE_DBT_COLUMN_NAME"
    UPDATE_CONTRACT_FIELD = "UPDATE_CONTRACT_FIELD"
    UPDATE_CONTRACT_TYPE = "UPDATE_CONTRACT_TYPE"
    UPDATE_QUALITY_REFERENCE = "UPDATE_QUALITY_REFERENCE"
    UPDATE_DAG_STATIC_ARGUMENT = "UPDATE_DAG_STATIC_ARGUMENT"
    UPDATE_PIPELINE_CONFIG_REFERENCE = "UPDATE_PIPELINE_CONFIG_REFERENCE"
    UPDATE_MODEL_FILE_REFERENCE = "UPDATE_MODEL_FILE_REFERENCE"
    REMOVE_STALE_STATIC_REFERENCE = "REMOVE_STALE_STATIC_REFERENCE"


@dataclass(frozen=True, order=True)
class ProposalMetadataItem:
    key: str
    value: str


@dataclass(frozen=True)
class RepairRepositoryIdentity:
    repository_name: str
    repository_namespace: str | None = None
    repository_fingerprint: str | None = None


@dataclass(frozen=True)
class RepairGenerationProposal:
    proposal_id: str
    repair_analysis_id: str
    operation: RepairOperation
    predecessor_analysis_id: str
    predecessor_manifest_fingerprint: str
    repository_identity: RepairRepositoryIdentity
    base_revision: str
    head_revision: str
    repair_mode: RepairMode
    target_root_cause_ids: tuple[str, ...] = ()
    target_logical_change_group_ids: tuple[str, ...] = ()
    scenario_id: str | None = None
    description: str | None = None
    proposal_metadata: tuple[ProposalMetadataItem, ...] = ()


@dataclass(frozen=True)
class RepairAnalysisIdentity:
    repair_analysis_id: str
    proposal_id: str
    predecessor_analysis_id: str
    predecessor_manifest_fingerprint: str
    predecessor_analysis_fingerprint: str
    repository_fingerprint: str
    base_commit: str
    head_commit: str
    source_snapshot_id: str
    source_snapshot_fingerprint: str
    proposal_fingerprint: str
    engine_version: str = REPAIR_ENGINE_VERSION
    scenario_id: str | None = None


@dataclass(frozen=True)
class RepairabilityClassification:
    root_cause_id: str
    root_type: str
    repairability: RepairabilityState
    repairability_rule_id: str
    supporting_evidence: tuple[str, ...]
    required_preconditions: tuple[str, ...]
    reason: str
    eligible_file_categories: tuple[str, ...]
    remaining_uncertainty: tuple[str, ...]
    logical_change_group_id: str | None = None


@dataclass(frozen=True)
class RepairAction:
    repair_action_id: str
    repair_rule_id: str
    root_cause_id: str
    logical_change_group_id: str | None
    target_file_change_id: str
    target_path: str
    file_category: str
    current_evidence: dict[str, Any]
    intended_future_evidence: dict[str, Any]
    edit_operation: EditOperation
    expected_changed_identities: tuple[str, ...]
    dependency_actions: tuple[str, ...]
    confidence: str
    preconditions: tuple[str, ...]
    static_validation_requirements: tuple[str, ...]
    remaining_evidence_requirements: tuple[str, ...]
    human_explanation: str
    target_location: str | None = None


@dataclass(frozen=True)
class RepairPlan:
    repair_analysis_id: str
    predecessor_analysis_id: str
    selected_root_cause_ids: tuple[str, ...]
    classifications: tuple[RepairabilityClassification, ...]
    repair_actions: tuple[RepairAction, ...]
    non_repairable_root_ids: tuple[str, ...]
    blocked_root_ids: tuple[str, ...]
    affected_files: tuple[str, ...]
    edit_dependencies: tuple[dict[str, str], ...]
    application_order: tuple[str, ...]
    expected_repository_coherence_improvement: str
    expected_compatibility_limitations: tuple[str, ...]
    required_human_decisions: tuple[str, ...]
    required_phase_7_validations: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class RepairRule:
    repair_rule_id: str
    supported_root_types: tuple[str, ...]
    supported_file_categories: tuple[str, ...]
    required_evidence: tuple[str, ...]
    preconditions: tuple[str, ...]
    edit_operation: EditOperation
    editor_name: str
    post_generation_static_checks: tuple[str, ...]
    remaining_evidence_requirements: tuple[str, ...]
    explanation_template: str
    conditional: bool = False


@dataclass(frozen=True)
class RepairGenerationResult:
    identity: RepairAnalysisIdentity
    certification_status: str
    repair_disposition: RepairDisposition
    completeness: RepairCompleteness
    repair_actions: tuple[dict[str, Any], ...]
    affected_files: tuple[str, ...]
    projected_closed_roots: tuple[str, ...]
    remaining_findings: tuple[dict[str, Any], ...]
    projected_coherence: str
    semantic_fingerprint: str
    patch_manifest: dict[str, Any]
    artifact_manifest: dict[str, Any]
    patch_paths: tuple[Path, ...]
    candidate_file_paths: tuple[Path, ...]
    output_dir: Path
    artifact_paths: tuple[Path, ...]
    artifacts: dict[str, dict[str, Any]]
