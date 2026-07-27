"""Immutable result models for CHRONOS Phase 2.4 certification."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


CERTIFIER_SCHEMA_VERSION = "1.0"


class Phase2CertificationState(str, Enum):
    CERTIFIED = "certified"
    NOT_CERTIFIED = "not_certified"


class CertificationCheckStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"


class CertificationFindingSeverity(str, Enum):
    BLOCKING = "blocking"


class CertificationFindingCode(str, Enum):
    ARTIFACT_CHAIN = "artifact_chain"
    DEMONSTRATION_IDENTITY = "demonstration_identity"
    TARGET_IDENTITY = "target_identity"
    BEFORE_STATE = "before_state"
    REQUESTED_STATE = "requested_state"
    VALIDATION_RESULT = "validation_result"
    SEMANTIC_CONTRACT = "semantic_contract"
    SCHEMA_CARDINALITY = "schema_cardinality"
    NON_PROPAGATION = "non_propagation"
    STATE_BOUNDARY = "state_boundary"
    IMMUTABILITY = "immutability"
    DETERMINISM = "determinism"
    SECRET_AUDIT = "secret_audit"
    FORBIDDEN_SEMANTICS = "forbidden_semantics"
    STRUCTURAL_INTEGRITY = "structural_integrity"
    ARTIFACT_HASH = "artifact_hash"


@dataclass(frozen=True)
class CertificationCheck:
    name: str
    status: CertificationCheckStatus
    expected: str
    observed: str


@dataclass(frozen=True)
class CertificationFinding:
    code: CertificationFindingCode
    severity: CertificationFindingSeverity
    message: str
    check_name: str


@dataclass(frozen=True)
class ArtifactHashEvidence:
    artifact_name: str
    before_sha256: str
    after_sha256: str


@dataclass(frozen=True)
class Phase2CertificationResult:
    demonstration_id: str
    certification_state: Phase2CertificationState
    snapshot_fingerprint: str
    proposal_fingerprint: str
    validation_fingerprint: str
    semantic_contract_fingerprint: str
    checks: tuple[CertificationCheck, ...]
    findings: tuple[CertificationFinding, ...]
    warnings: tuple[str, ...]
    artifact_hashes: tuple[ArtifactHashEvidence, ...]
    certified_at: str
    certifier_schema_version: str = CERTIFIER_SCHEMA_VERSION
    semantic_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        if self.certifier_schema_version != CERTIFIER_SCHEMA_VERSION:
            raise ValueError(
                "Unsupported Phase 2 certifier schema version: "
                f"{self.certifier_schema_version!r}."
            )
        if not isinstance(self.certification_state, Phase2CertificationState):
            raise ValueError("Certification state must be typed.")
        try:
            timestamp = datetime.fromisoformat(self.certified_at)
        except (TypeError, ValueError) as exc:
            raise ValueError("certified_at must be ISO-8601.") from exc
        if timestamp.tzinfo is None:
            raise ValueError("certified_at must include a timezone.")
        for value, label in (
            (self.snapshot_fingerprint, "snapshot fingerprint"),
            (self.proposal_fingerprint, "proposal fingerprint"),
            (self.validation_fingerprint, "validation fingerprint"),
            (
                self.semantic_contract_fingerprint,
                "semantic-contract fingerprint",
            ),
        ):
            if not _is_sha256_fingerprint(value):
                raise ValueError(f"{label} is not canonical sha256.")
        failed = any(
            item.status is CertificationCheckStatus.FAIL
            for item in self.checks
        )
        if (
            self.certification_state is Phase2CertificationState.CERTIFIED
            and (failed or self.findings)
        ):
            raise ValueError(
                "CERTIFIED cannot contain failed checks or findings."
            )
        if (
            self.certification_state
            is Phase2CertificationState.NOT_CERTIFIED
            and not failed
        ):
            raise ValueError("NOT_CERTIFIED requires a failed check.")
        from .serialization import certification_semantic_fingerprint

        object.__setattr__(
            self,
            "semantic_fingerprint",
            certification_semantic_fingerprint(self),
        )

    def to_dict(self, *, include_volatile: bool = True) -> dict[str, Any]:
        from .serialization import certification_to_dict

        return certification_to_dict(self, include_volatile=include_volatile)

    def to_json(self) -> str:
        from .serialization import certification_to_json

        return certification_to_json(self, include_volatile=True)

    def semantic_json(self) -> str:
        from .serialization import certification_to_json

        return certification_to_json(self, include_volatile=False)

    @classmethod
    def from_json(cls, value: str) -> Phase2CertificationResult:
        from .serialization import certification_from_json

        return certification_from_json(value)

    def semantically_equals(self, other: object) -> bool:
        return (
            isinstance(other, Phase2CertificationResult)
            and self.semantic_fingerprint == other.semantic_fingerprint
            and self.semantic_json() == other.semantic_json()
        )

    def summary(self) -> str:
        passed = sum(
            item.status is CertificationCheckStatus.PASS
            for item in self.checks
        )
        failed = len(self.checks) - passed
        return "\n".join(
            (
                f"Demonstration: {self.demonstration_id}",
                f"Checks passed: {passed}",
                f"Checks failed: {failed}",
                f"Blocking findings: {len(self.findings)}",
                f"Warnings: {len(self.warnings)}",
                f"Final status: {self.certification_state.name}",
            )
        )


def _is_sha256_fingerprint(value: object) -> bool:
    if not isinstance(value, str) or not value.startswith("sha256:"):
        return False
    digest = value.removeprefix("sha256:")
    return len(digest) == 64 and all(
        character in "0123456789abcdef" for character in digest
    )
