"""Immutable contracts for deterministic multi-file pull-request analysis."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any


PR_ENGINE_VERSION = "6.3.0"
PR_ARTIFACT_SCHEMA_VERSION = "1.0"
MAX_CHANGED_FILES = 200
MAX_FILE_BYTES = 1_048_576


class PullRequestOperation(str, Enum):
    MULTI_FILE_PR_CHANGE = "MULTI_FILE_PR_CHANGE"


class IntakeMode(str, Enum):
    LOCAL_GIT_RANGE = "LOCAL_GIT_RANGE"
    EXPORTED_PR_BUNDLE = "EXPORTED_PR_BUNDLE"


class FileStatus(str, Enum):
    ADDED = "ADDED"
    MODIFIED = "MODIFIED"
    DELETED = "DELETED"
    RENAMED = "RENAMED"
    COPIED = "COPIED"
    UNSUPPORTED = "UNSUPPORTED"


class FileCategory(str, Enum):
    SQL_MODEL = "SQL_MODEL"
    DBT_MODEL = "DBT_MODEL"
    DBT_SCHEMA = "DBT_SCHEMA"
    SCHEMA_CONTRACT = "SCHEMA_CONTRACT"
    PIPELINE_DAG = "PIPELINE_DAG"
    PIPELINE_CONFIG = "PIPELINE_CONFIG"
    QUALITY_CONFIG = "QUALITY_CONFIG"
    DOCUMENTATION_ONLY = "DOCUMENTATION_ONLY"
    UNSUPPORTED = "UNSUPPORTED"


class CoherenceState(str, Enum):
    COHERENT = "COHERENT"
    PARTIALLY_COHERENT = "PARTIALLY_COHERENT"
    INCONSISTENT = "INCONSISTENT"
    UNRESOLVED = "UNRESOLVED"


class ClaimResolutionState(str, Enum):
    RESOLVED = "RESOLVED"
    COUNTERFACTUAL = "COUNTERFACTUAL"
    AMBIGUOUS = "AMBIGUOUS"
    NOT_FOUND = "NOT_FOUND"
    INSUFFICIENT_METADATA = "INSUFFICIENT_METADATA"


@dataclass(frozen=True, order=True)
class ProposalMetadataItem:
    key: str
    value: str


@dataclass(frozen=True)
class RepositoryIdentityInput:
    repository_name: str
    repository_namespace: str | None = None


@dataclass(frozen=True)
class FileModelMapping:
    path: str
    model_dataset_urn: str
    model_relation: str
    sql_dialect: str
    dbt_manifest_path: str | None = None


@dataclass(frozen=True)
class PullRequestAnalysisProposal:
    proposal_id: str
    analysis_id: str
    operation: PullRequestOperation
    source_snapshot_fingerprint: str
    repository_identity: RepositoryIdentityInput
    base_revision: str
    head_revision: str
    intake_mode: IntakeMode
    source_snapshot_id: str | None = None
    pull_request_number: int | None = None
    scenario_id: str | None = None
    title: str | None = None
    description: str | None = None
    created_at: str | None = None
    proposal_metadata: tuple[ProposalMetadataItem, ...] = ()
    file_model_mappings: tuple[FileModelMapping, ...] = ()


@dataclass(frozen=True)
class PullRequestAnalysisIdentity:
    analysis_id: str
    proposal_id: str
    operation: PullRequestOperation
    intake_mode: IntakeMode
    repository_fingerprint: str
    base_commit: str
    head_commit: str
    source_snapshot_id: str
    source_snapshot_fingerprint: str
    proposal_fingerprint: str
    engine_version: str
    scenario_id: str | None = None
    created_at: str | None = None


@dataclass(frozen=True)
class ChangedFile:
    file_change_id: str
    base_path: str | None
    head_path: str | None
    status: FileStatus
    category: FileCategory
    base_content_fingerprint: str | None
    head_content_fingerprint: str | None
    base_size: int
    head_size: int
    binary: bool
    parser_assignment: str
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class FilePayload:
    record: ChangedFile
    base_content: str | None
    head_content: str | None


@dataclass(frozen=True)
class PullRequestInput:
    repository_identity: dict[str, Any]
    base_commit: str
    head_commit: str
    files: tuple[FilePayload, ...]
    intake_warnings: tuple[str, ...]


@dataclass(frozen=True)
class PullRequestAnalysisResult:
    identity: PullRequestAnalysisIdentity
    repository_identity: dict[str, Any]
    certification_status: str
    disposition: str
    decision_certainty: str
    coherence_state: CoherenceState
    semantic_fingerprint: str
    changed_file_summary: dict[str, Any]
    logical_change_groups: tuple[dict[str, Any], ...]
    root_causes: tuple[dict[str, Any], ...]
    conflicts: tuple[dict[str, Any], ...]
    key_findings: tuple[dict[str, Any], ...]
    future_graph_summary: dict[str, Any]
    output_dir: Path
    artifact_paths: tuple[Path, ...]
    artifacts: dict[str, dict[str, Any]]
    manifest: dict[str, Any]
