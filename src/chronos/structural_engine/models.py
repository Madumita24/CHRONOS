"""Public models for generalized structural-change analysis."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .proposals import StructuralOperation


GENERALIZED_ENGINE_VERSION = "6.1.0"
GENERALIZED_ARTIFACT_SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class AnalysisIdentity:
    analysis_id: str
    proposal_id: str
    operation: StructuralOperation
    dataset_urn: str
    current_field_path: str
    source_snapshot_fingerprint: str
    proposal_fingerprint: str
    source_snapshot_id: str
    engine_version: str
    scenario_id: str | None = None
    created_at: str | None = None


@dataclass(frozen=True)
class ResolvedField:
    dataset_urn: str
    field_path: str
    field_name: str
    native_type: str | None
    normalized_type: str
    position: int
    schema_field_urn: str | None

    @property
    def key(self) -> str:
        return f"{self.dataset_urn}|{self.field_path}"


@dataclass(frozen=True)
class StructuralAnalysisResult:
    identity: AnalysisIdentity
    disposition: str
    decision_certainty: str
    certification_status: str
    semantic_fingerprint: str
    output_dir: Path
    artifact_paths: tuple[Path, ...]
    artifacts: dict[str, dict[str, Any]]
    manifest: dict[str, Any]
    key_summary: dict[str, Any]
