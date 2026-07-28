"""Immutable CHRONOS Phase 4.5 certification models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


PHASE4_CERTIFICATION_SCHEMA_VERSION = "1.0"


class Phase4CertificationStatus(str, Enum):
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
    TECHNICAL_IMPACT = "technical_impact"
    BUSINESS_CONTEXT = "business_context"
    CRITICALITY = "criticality"
    BREADTH = "breadth"
    SEVERITY = "severity"
    DECISION = "decision"
    BLOCKING_EVIDENCE = "blocking_evidence"
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
class InputSemanticFingerprint:
    artifact_name: str
    semantic_fingerprint: str


@dataclass(frozen=True)
class ArtifactImmutabilityEvidence:
    artifact_name: str
    before_sha256: str
    after_sha256: str

    @property
    def unchanged(self) -> bool:
        return self.before_sha256 == self.after_sha256


@dataclass(frozen=True)
class Phase4SemanticFingerprints:
    technical_impact: str
    business_context: str
    severity_criticality: str
    impact_synthesis: str


@dataclass(frozen=True)
class CertificationCheck:
    check_id: str
    category: CertificationCheckCategory
    description: str
    status: CertificationCheckStatus
    failure_severity: CertificationFailureSeverity
    expected: str
    observed: str
    evidence_references: tuple[str, ...]


@dataclass(frozen=True)
class TechnicalBaseline:
    change_origins: int
    technical_root_causes: int
    relationship_impacts: int
    path_impacts: int
    downstream_fields: int
    downstream_datasets: int
    confirmed_downstream_failures: int
    potential_relationships: int
    unresolved_relationships: int
    unresolved_paths: int
    unresolved_fields: int
    root_cause_id: str
    root_relationship_id: str


@dataclass(frozen=True)
class ContextBaseline:
    technical_scope_datasets: int
    unique_context_assets: int
    scoped_context_relationships: int
    field_to_context_mappings: int
    context_categories: tuple[str, ...]
    unresolved_context_references: int


@dataclass(frozen=True)
class SeverityDistribution:
    critical: int
    high: int
    moderate: int
    low: int
    undetermined: int


@dataclass(frozen=True)
class SeverityBaseline:
    technical_consequence: str
    technical_certainty: str
    context_criticality: str
    breadth: str
    sensitivity: str
    severity_if_realized: str
    breadth_rule_id: str
    severity_rule_id: str
    severity_rule_count: int
    field_distribution: SeverityDistribution
    dataset_distribution: SeverityDistribution


@dataclass(frozen=True)
class DecisionBaseline:
    disposition: str
    decision_certainty: str
    technical_certainty: str
    decision_rule_id: str
    decision_reason_codes: tuple[str, ...]
    confirmed_broken_fields: int
    technically_unresolved_fields: int
    connected_context_assets: int
    blocking_questions: int
    required_evidence: int
    representative_paths: int


@dataclass(frozen=True)
class Phase4CertificationResult:
    schema_version: str
    demonstration_id: str
    proposal_id: str
    certification_status: Phase4CertificationStatus
    certified_at: str
    input_artifact_identities: tuple[InputArtifactIdentity, ...]
    input_semantic_fingerprints: tuple[
        InputSemanticFingerprint, ...
    ]
    phase_4_semantic_fingerprints: Phase4SemanticFingerprints
    certification_checks: tuple[CertificationCheck, ...]
    technical_baseline: TechnicalBaseline
    context_baseline: ContextBaseline
    severity_baseline: SeverityBaseline
    decision_baseline: DecisionBaseline
    blocking_question_ids: tuple[str, ...]
    warnings: tuple[str, ...]
    scope_statement: str
    artifact_immutability: tuple[ArtifactImmutabilityEvidence, ...]
    semantic_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        if self.schema_version != PHASE4_CERTIFICATION_SCHEMA_VERSION:
            raise ValueError("Unsupported Phase 4 certification schema.")
        if self.demonstration_id != "CHRONOS-DEMO-001":
            raise ValueError("Phase 4 certification demonstration invalid.")
        if self.proposal_id != "CHRONOS-DEMO-001-PROPOSAL-001":
            raise ValueError("Phase 4 certification proposal invalid.")
        try:
            timestamp = datetime.fromisoformat(self.certified_at)
        except (TypeError, ValueError) as exc:
            raise ValueError("certified_at must be ISO-8601.") from exc
        if timestamp.tzinfo is None:
            raise ValueError("certified_at must include timezone.")
        if (
            len(self.input_artifact_identities) != 15
            or len(self.input_semantic_fingerprints) != 15
            or len(self.artifact_immutability) != 15
        ):
            raise ValueError(
                "Phase 4 certification requires fifteen immutable inputs."
            )
        for values, attribute in (
            (self.input_artifact_identities, "artifact_name"),
            (self.input_semantic_fingerprints, "artifact_name"),
            (self.artifact_immutability, "artifact_name"),
            (self.certification_checks, "check_id"),
        ):
            keys = tuple(getattr(item, attribute) for item in values)
            if len(keys) != len(set(keys)):
                raise ValueError(
                    f"Duplicate Phase 4 certification {attribute}."
                )
        for identity in self.input_artifact_identities:
            if (
                not _is_sha256_fingerprint(identity.semantic_fingerprint)
                or not _is_sha256_digest(identity.physical_sha256)
            ):
                raise ValueError("Invalid certification input identity.")
        for item in self.input_semantic_fingerprints:
            if not _is_sha256_fingerprint(item.semantic_fingerprint):
                raise ValueError("Invalid input semantic fingerprint.")
        for value in (
            self.phase_4_semantic_fingerprints.technical_impact,
            self.phase_4_semantic_fingerprints.business_context,
            self.phase_4_semantic_fingerprints.severity_criticality,
            self.phase_4_semantic_fingerprints.impact_synthesis,
        ):
            if not _is_sha256_fingerprint(value):
                raise ValueError("Invalid Phase 4 semantic fingerprint.")
        failed = tuple(
            item
            for item in self.certification_checks
            if item.status is CertificationCheckStatus.FAIL
        )
        if (
            self.certification_status is Phase4CertificationStatus.CERTIFIED
            and failed
        ):
            raise ValueError("CERTIFIED cannot contain failed checks.")
        if (
            self.certification_status is Phase4CertificationStatus.FAILED
            and not failed
        ):
            raise ValueError("FAILED requires a failed check.")
        if (
            self.certification_status is Phase4CertificationStatus.CERTIFIED
            and any(
                not item.unchanged for item in self.artifact_immutability
            )
        ):
            raise ValueError("CERTIFIED inputs must be byte-identical.")
        if not self.scope_statement:
            raise ValueError("Certification scope statement is required.")
        from .serialization import phase4_certification_semantic_fingerprint

        object.__setattr__(
            self,
            "semantic_fingerprint",
            phase4_certification_semantic_fingerprint(self),
        )

    def to_dict(self, *, include_volatile: bool = True) -> dict[str, Any]:
        from .serialization import phase4_certification_to_dict

        return phase4_certification_to_dict(
            self, include_volatile=include_volatile
        )

    def to_json(self) -> str:
        from .serialization import phase4_certification_to_json

        return phase4_certification_to_json(
            self, include_volatile=True
        )

    def semantic_json(self) -> str:
        from .serialization import phase4_certification_to_json

        return phase4_certification_to_json(
            self, include_volatile=False
        )

    @classmethod
    def from_json(cls, value: str) -> Phase4CertificationResult:
        from .serialization import phase4_certification_from_json

        return phase4_certification_from_json(value)

    def semantically_equals(self, other: object) -> bool:
        return (
            isinstance(other, Phase4CertificationResult)
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
