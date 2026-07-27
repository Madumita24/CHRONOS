"""Immutable domain models for CHRONOS Phase 2.2 proposal validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


VALIDATOR_SCHEMA_VERSION = "1.0"


class ProposalValidationState(str, Enum):
    VALID = "valid"
    INVALID = "invalid"
    STALE_BASELINE = "stale_baseline"
    UNAVAILABLE = "unavailable"


class ValidationFindingSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ValidationFindingCode(str, Enum):
    SNAPSHOT_FINGERPRINT_MISMATCH = "snapshot_fingerprint_mismatch"
    DEMONSTRATION_MISMATCH = "demonstration_mismatch"
    TARGET_DATASET_MISMATCH = "target_dataset_mismatch"
    TARGET_DATASET_NOT_FOUND = "target_dataset_not_found"
    TARGET_DATASET_DUPLICATE = "target_dataset_duplicate"
    TARGET_FIELD_NOT_FOUND = "target_field_not_found"
    TARGET_FIELD_DUPLICATE = "target_field_duplicate"
    TARGET_FIELD_PARENT_MISMATCH = "target_field_parent_mismatch"
    BEFORE_STATE_MISMATCH = "before_state_mismatch"
    FIELD_NAME_COLLISION = "field_name_collision"
    RENAME_NOT_ADMISSIBLE = "rename_not_admissible"
    UNSUPPORTED_PROPOSAL_TYPE = "unsupported_proposal_type"
    MALFORMED_PROPOSAL = "malformed_proposal"
    SNAPSHOT_VALIDATION_FAILURE = "snapshot_validation_failure"
    NO_ADDITIONAL_REQUESTED_MUTATION = (
        "no_additional_requested_mutation"
    )


class PreconditionStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    NOT_EVALUATED = "not_evaluated"


@dataclass(frozen=True)
class ProposalValidationFinding:
    code: ValidationFindingCode
    severity: ValidationFindingSeverity
    message: str
    expected: str | None = None
    observed: str | None = None
    affected_key: str | None = None


@dataclass(frozen=True)
class PreconditionResult:
    name: str
    status: PreconditionStatus
    expected: str
    observed: str


@dataclass(frozen=True)
class ValidatedTarget:
    dataset_urn: str
    field_path: str
    dataset_occurrences: int
    field_occurrences: int
    field_parent_matches: bool | None

    @property
    def machine_key(self) -> tuple[str, str]:
        return (self.dataset_urn, self.field_path)


@dataclass(frozen=True)
class ValidatedBeforeState:
    claimed_field_path: str
    observed_field_path: str | None
    claimed_field_name: str
    observed_field_name: str | None
    claimed_native_type: str
    observed_native_type: str | None
    claimed_normalized_type: str
    observed_normalized_type: str | None
    matches: bool


@dataclass(frozen=True)
class ValidatedRequestedAfterState:
    field_path: str
    field_name: str
    source_schema_occurrences: int
    additional_requested_mutation: bool


@dataclass(frozen=True)
class ProposalValidationResult:
    proposal_id: str | None
    proposal_fingerprint: str | None
    snapshot_id: str | None
    snapshot_fingerprint: str | None
    validation_state: ProposalValidationState
    validated_target: ValidatedTarget | None
    validated_before_state: ValidatedBeforeState | None
    requested_after_state: ValidatedRequestedAfterState | None
    findings: tuple[ProposalValidationFinding, ...]
    preconditions: tuple[PreconditionResult, ...]
    validated_at: str
    validator_schema_version: str = VALIDATOR_SCHEMA_VERSION
    semantic_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        if self.validator_schema_version != VALIDATOR_SCHEMA_VERSION:
            raise ValueError(
                "Unsupported proposal validator schema version: "
                f"{self.validator_schema_version!r}."
            )
        if not isinstance(self.validation_state, ProposalValidationState):
            raise ValueError("Validation state must be typed.")
        if not isinstance(self.findings, tuple):
            raise ValueError("Validation findings must be an immutable tuple.")
        if not isinstance(self.preconditions, tuple):
            raise ValueError("Preconditions must be an immutable tuple.")
        try:
            timestamp = datetime.fromisoformat(self.validated_at)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "Validation timestamp must be ISO-8601."
            ) from exc
        if timestamp.tzinfo is None:
            raise ValueError("Validation timestamp must include a timezone.")
        for value, label in (
            (self.proposal_fingerprint, "proposal fingerprint"),
            (self.snapshot_fingerprint, "snapshot fingerprint"),
        ):
            if value is not None and not _is_sha256_fingerprint(value):
                raise ValueError(f"{label} is not canonical sha256.")
        has_error = any(
            item.severity is ValidationFindingSeverity.ERROR
            for item in self.findings
        )
        if self.validation_state is ProposalValidationState.VALID and has_error:
            raise ValueError("A VALID result cannot contain ERROR findings.")
        from .serialization import validation_result_semantic_fingerprint

        object.__setattr__(
            self,
            "semantic_fingerprint",
            validation_result_semantic_fingerprint(self),
        )

    def to_dict(self, *, include_volatile: bool = True) -> dict[str, Any]:
        from .serialization import validation_result_to_dict

        return validation_result_to_dict(
            self,
            include_volatile=include_volatile,
        )

    def to_json(self) -> str:
        from .serialization import validation_result_to_json

        return validation_result_to_json(self, include_volatile=True)

    def semantic_json(self) -> str:
        from .serialization import validation_result_to_json

        return validation_result_to_json(self, include_volatile=False)

    @classmethod
    def from_json(cls, value: str) -> ProposalValidationResult:
        from .serialization import validation_result_from_json

        return validation_result_from_json(value)

    def semantically_equals(self, other: object) -> bool:
        return (
            isinstance(other, ProposalValidationResult)
            and self.semantic_fingerprint == other.semantic_fingerprint
            and self.semantic_json() == other.semantic_json()
        )

    def summary(self) -> str:
        preconditions = {item.name: item for item in self.preconditions}

        def observed(name: str) -> str:
            item = preconditions.get(name)
            return item.observed if item is not None else "NOT EVALUATED"

        requested = (
            self.requested_after_state.field_path
            if self.requested_after_state is not None
            else "UNAVAILABLE"
        )
        return "\n".join(
            (
                f"Proposal: {self.proposal_id or 'UNAVAILABLE'}",
                f"Baseline: {observed('baseline_fingerprint')}",
                f"Demonstration: {observed('demonstration_identity')}",
                f"Target dataset: {observed('target_dataset')}",
                f"Target field: {observed('target_field')}",
                f"Before state: {observed('before_state')}",
                f"Requested field: {requested}",
                (
                    "Source-schema collision: "
                    f"{observed('source_schema_collision')}"
                ),
                f"Result: {self.validation_state.name}",
            )
        )


def _is_sha256_fingerprint(value: object) -> bool:
    if not isinstance(value, str) or not value.startswith("sha256:"):
        return False
    digest = value.removeprefix("sha256:")
    return len(digest) == 64 and all(
        character in "0123456789abcdef" for character in digest
    )
