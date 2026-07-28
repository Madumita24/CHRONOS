"""Immutable models for CHRONOS Phase 3.6 certification."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


PHASE3_CERTIFICATION_SCHEMA_VERSION = "1.0"


class Phase3CertificationStatus(str, Enum):
    CERTIFIED = "certified"
    FAILED = "failed"


class CertificationCheckStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"


class CertificationFailureSeverity(str, Enum):
    BLOCKING = "blocking"


class CertificationCheckCategory(str, Enum):
    PREREQUISITE = "prerequisite"
    CROSS_REFERENCE = "cross_reference"
    SOURCE_STATE = "source_state"
    GRAPH_INTEGRITY = "graph_integrity"
    PATH_INTEGRITY = "path_integrity"
    PROPAGATION = "propagation"
    COMPATIBILITY = "compatibility"
    EXPLANATION = "explanation"
    PROVENANCE = "provenance"
    IMMUTABILITY = "immutability"
    DETERMINISM = "determinism"
    SECURITY = "security"
    SCOPE = "scope"


@dataclass(frozen=True)
class InputArtifactIdentity:
    artifact_name: str
    object_id: str
    semantic_fingerprint: str
    physical_sha256: str


@dataclass(frozen=True)
class ArtifactImmutabilityEvidence:
    artifact_name: str
    before_sha256: str
    after_sha256: str

    @property
    def unchanged(self) -> bool:
        return self.before_sha256 == self.after_sha256


@dataclass(frozen=True)
class Phase3SemanticFingerprints:
    counterfactual_source: str
    future_graph: str
    dependency_propagation: str
    compatibility_evaluation: str
    explanation_bundle: str


@dataclass(frozen=True)
class CertificationCheck:
    check_id: str
    category: CertificationCheckCategory
    description: str
    status: CertificationCheckStatus
    severity_if_failed: CertificationFailureSeverity
    evidence: tuple[str, ...]
    expected_value: str
    observed_value: str


@dataclass(frozen=True)
class Phase3SummaryMetrics:
    datasets: int
    active_future_fields: int
    changed_source_fields: int
    downstream_fields: int
    downstream_datasets: int
    structural_relationships: int
    mapping_groups: int
    supporting_paths: int
    maximum_shortest_exposure_depth: int
    maximum_stored_path_depth: int
    root_uncertainties: int
    conditionally_compatible_relationships: int
    unknown_relationships: int
    unknown_paths: int


@dataclass(frozen=True)
class Phase3CertificationResult:
    schema_version: str
    demonstration_id: str
    certification_status: Phase3CertificationStatus
    certified_at: str
    input_artifact_identities: tuple[InputArtifactIdentity, ...]
    phase_3_semantic_fingerprints: Phase3SemanticFingerprints
    certification_checks: tuple[CertificationCheck, ...]
    warnings: tuple[str, ...]
    summary_metrics: Phase3SummaryMetrics
    artifact_immutability: tuple[ArtifactImmutabilityEvidence, ...]
    scope_statement: str
    semantic_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        if self.schema_version != PHASE3_CERTIFICATION_SCHEMA_VERSION:
            raise ValueError("Unsupported Phase 3 certification schema.")
        if self.demonstration_id != "CHRONOS-DEMO-001":
            raise ValueError("Phase 3 demonstration identity is invalid.")
        try:
            timestamp = datetime.fromisoformat(self.certified_at)
        except (TypeError, ValueError) as exc:
            raise ValueError("certified_at must be ISO-8601.") from exc
        if timestamp.tzinfo is None:
            raise ValueError("certified_at must include a timezone.")
        if len(self.input_artifact_identities) != 10:
            raise ValueError("Phase 3 certification requires ten inputs.")
        artifact_names = tuple(
            item.artifact_name for item in self.input_artifact_identities
        )
        if len(set(artifact_names)) != len(artifact_names):
            raise ValueError("Duplicate certification input artifact.")
        for item in self.input_artifact_identities:
            if not _is_sha256_fingerprint(item.semantic_fingerprint):
                raise ValueError("Invalid input semantic fingerprint.")
            if not _is_sha256_digest(item.physical_sha256):
                raise ValueError("Invalid input physical hash.")
        for value in (
            self.phase_3_semantic_fingerprints.counterfactual_source,
            self.phase_3_semantic_fingerprints.future_graph,
            self.phase_3_semantic_fingerprints.dependency_propagation,
            self.phase_3_semantic_fingerprints.compatibility_evaluation,
            self.phase_3_semantic_fingerprints.explanation_bundle,
        ):
            if not _is_sha256_fingerprint(value):
                raise ValueError("Invalid Phase 3 semantic fingerprint.")
        check_ids = tuple(item.check_id for item in self.certification_checks)
        if len(check_ids) != len(set(check_ids)):
            raise ValueError("Duplicate Phase 3 certification check ID.")
        failed = tuple(
            item
            for item in self.certification_checks
            if item.status is CertificationCheckStatus.FAIL
        )
        if (
            self.certification_status is Phase3CertificationStatus.CERTIFIED
            and failed
        ):
            raise ValueError("CERTIFIED cannot contain failed checks.")
        if (
            self.certification_status is Phase3CertificationStatus.FAILED
            and not failed
        ):
            raise ValueError("FAILED requires at least one failed check.")
        if len(self.artifact_immutability) != 10:
            raise ValueError("Immutability evidence must cover ten inputs.")
        if (
            self.certification_status is Phase3CertificationStatus.CERTIFIED
            and any(not item.unchanged for item in self.artifact_immutability)
        ):
            raise ValueError("CERTIFIED inputs must be immutable.")
        if not self.scope_statement:
            raise ValueError("Certification scope statement is required.")
        from .serialization import phase3_certification_semantic_fingerprint

        object.__setattr__(
            self,
            "semantic_fingerprint",
            phase3_certification_semantic_fingerprint(self),
        )

    def to_dict(self, *, include_volatile: bool = True) -> dict[str, Any]:
        from .serialization import phase3_certification_to_dict

        return phase3_certification_to_dict(
            self,
            include_volatile=include_volatile,
        )

    def to_json(self) -> str:
        from .serialization import phase3_certification_to_json

        return phase3_certification_to_json(self, include_volatile=True)

    def semantic_json(self) -> str:
        from .serialization import phase3_certification_to_json

        return phase3_certification_to_json(self, include_volatile=False)

    @classmethod
    def from_json(cls, value: str) -> Phase3CertificationResult:
        from .serialization import phase3_certification_from_json

        return phase3_certification_from_json(value)

    def semantically_equals(self, other: object) -> bool:
        return (
            isinstance(other, Phase3CertificationResult)
            and self.semantic_fingerprint == other.semantic_fingerprint
            and self.semantic_json() == other.semantic_json()
        )


def _is_sha256_fingerprint(value: object) -> bool:
    return (
        isinstance(value, str)
        and value.startswith("sha256:")
        and _is_sha256_digest(value.removeprefix("sha256:"))
    )


def _is_sha256_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )
