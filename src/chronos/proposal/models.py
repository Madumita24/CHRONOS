"""Immutable Change Proposal domain model for CHRONOS Phase 2.1."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from chronos.resolution.models import CanonicalEntityType

from .errors import (
    InvalidChangeProposal,
    InvalidChangeTarget,
    InvalidFieldRename,
    InvalidProposalSnapshotReference,
    UnsupportedChangeType,
)


PROPOSAL_SCHEMA_VERSION = "1.0"


class ChangeType(str, Enum):
    FIELD_RENAME = "field_rename"


class ProposalLifecycleState(str, Enum):
    DRAFT = "draft"
    STRUCTURALLY_VALID = "structurally_valid"


class ProposalSource(str, Enum):
    CANONICAL_DEMO = "canonical_demo"


class ProposalInformationClassification(str, Enum):
    PROPOSED = "proposed"


@dataclass(frozen=True)
class SchemaFieldTarget:
    dataset_urn: str
    field_path: str
    display_identity: str | None = None
    platform: str | None = None
    environment: str | None = None
    entity_type: CanonicalEntityType = field(
        default=CanonicalEntityType.SCHEMA_FIELD,
        init=False,
    )

    def __post_init__(self) -> None:
        _require_exact(self.dataset_urn, "target dataset URN", InvalidChangeTarget)
        if not (
            self.dataset_urn.startswith("urn:li:dataset:(")
            and self.dataset_urn.endswith(")")
        ):
            raise InvalidChangeTarget(
                "Target dataset URN must be a DataHub Dataset URN."
            )
        _require_exact(self.field_path, "target field path", InvalidChangeTarget)
        _optional_exact(
            self.display_identity,
            "target display identity",
            InvalidChangeTarget,
        )
        _optional_exact(self.platform, "target platform", InvalidChangeTarget)
        _optional_exact(
            self.environment,
            "target environment",
            InvalidChangeTarget,
        )

    @property
    def machine_key(self) -> tuple[str, str]:
        return (self.dataset_urn, self.field_path)


@dataclass(frozen=True)
class ClaimedFieldState:
    field_path: str
    field_name: str
    native_type: str
    normalized_type: str

    def __post_init__(self) -> None:
        _require_exact(
            self.field_path,
            "before field path",
            InvalidFieldRename,
        )
        _require_exact(
            self.field_name,
            "before field name",
            InvalidFieldRename,
        )
        _require_exact(
            self.native_type,
            "before native type",
            InvalidFieldRename,
        )
        _require_exact(
            self.normalized_type,
            "before normalized type",
            InvalidFieldRename,
        )


@dataclass(frozen=True)
class RequestedFieldState:
    field_path: str
    field_name: str

    def __post_init__(self) -> None:
        _require_exact(
            self.field_path,
            "requested-after field path",
            InvalidFieldRename,
        )
        _require_exact(
            self.field_name,
            "requested-after field name",
            InvalidFieldRename,
        )


@dataclass(frozen=True)
class FieldRenameChange:
    target: SchemaFieldTarget
    before: ClaimedFieldState
    requested_after: RequestedFieldState

    def __post_init__(self) -> None:
        if not isinstance(self.target, SchemaFieldTarget):
            raise InvalidFieldRename(
                "FIELD_RENAME target must be a SchemaFieldTarget."
            )
        if not isinstance(self.before, ClaimedFieldState):
            raise InvalidFieldRename(
                "FIELD_RENAME before state must be ClaimedFieldState."
            )
        if not isinstance(self.requested_after, RequestedFieldState):
            raise InvalidFieldRename(
                "FIELD_RENAME requested-after state must be "
                "RequestedFieldState."
            )
        if self.target.field_path != self.before.field_path:
            raise InvalidFieldRename(
                "Target field path must exactly match the claimed before path."
            )
        if self.before.field_path == self.requested_after.field_path:
            raise InvalidFieldRename(
                "Requested-after field path must differ from the before path."
            )
        if self.before.field_name == self.requested_after.field_name:
            raise InvalidFieldRename(
                "Requested-after field name must differ from the before name."
            )


@dataclass(frozen=True)
class ProposalSnapshotReference:
    semantic_fingerprint: str
    snapshot_id: str | None = None
    snapshot_schema_version: str | None = None

    def __post_init__(self) -> None:
        _require_exact(
            self.semantic_fingerprint,
            "snapshot semantic fingerprint",
            InvalidProposalSnapshotReference,
        )
        prefix = "sha256:"
        digest = self.semantic_fingerprint[len(prefix) :]
        if not (
            self.semantic_fingerprint.startswith(prefix)
            and len(digest) == 64
            and all(character in "0123456789abcdef" for character in digest)
        ):
            raise InvalidProposalSnapshotReference(
                "Snapshot fingerprint must use the canonical sha256 format."
            )
        _optional_exact(
            self.snapshot_id,
            "snapshot ID",
            InvalidProposalSnapshotReference,
        )
        _optional_exact(
            self.snapshot_schema_version,
            "snapshot schema version",
            InvalidProposalSnapshotReference,
        )


@dataclass(frozen=True)
class ProposalProvenance:
    source: ProposalSource
    created_by: str | None = None
    source_reference: str | None = None
    classification: ProposalInformationClassification = (
        ProposalInformationClassification.PROPOSED
    )

    def __post_init__(self) -> None:
        if not isinstance(self.source, ProposalSource):
            raise InvalidChangeProposal("Proposal source is unsupported.")
        if self.classification is not ProposalInformationClassification.PROPOSED:
            raise InvalidChangeProposal(
                "Phase 2.1 proposal information must be classified proposed."
            )
        _optional_exact(
            self.created_by,
            "proposal created_by",
            InvalidChangeProposal,
        )
        _optional_exact(
            self.source_reference,
            "proposal source reference",
            InvalidChangeProposal,
        )


@dataclass(frozen=True)
class ChangeProposal:
    proposal_id: str
    demonstration_id: str
    change_type: ChangeType
    change: FieldRenameChange
    snapshot_reference: ProposalSnapshotReference
    lifecycle_state: ProposalLifecycleState
    created_at: str
    provenance: ProposalProvenance
    description: str | None = None
    rationale: str | None = None
    proposal_schema_version: str = PROPOSAL_SCHEMA_VERSION
    semantic_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        validate_change_proposal(self)
        from .serialization import proposal_semantic_fingerprint

        object.__setattr__(
            self,
            "semantic_fingerprint",
            proposal_semantic_fingerprint(self),
        )

    def to_dict(self, *, include_volatile: bool = True) -> dict[str, Any]:
        from .serialization import proposal_to_dict

        return proposal_to_dict(self, include_volatile=include_volatile)

    def to_json(self) -> str:
        from .serialization import proposal_to_json

        return proposal_to_json(self, include_volatile=True)

    def semantic_json(self) -> str:
        from .serialization import proposal_to_json

        return proposal_to_json(self, include_volatile=False)

    @classmethod
    def from_json(cls, value: str) -> ChangeProposal:
        from .serialization import proposal_from_json

        return proposal_from_json(value)

    def semantically_equals(self, other: object) -> bool:
        return (
            isinstance(other, ChangeProposal)
            and self.semantic_fingerprint == other.semantic_fingerprint
            and self.semantic_json() == other.semantic_json()
        )

    def summary(self) -> str:
        target = (
            self.change.target.display_identity
            or (
                f"{self.change.target.dataset_urn} / "
                f"{self.change.target.field_path}"
            )
        )
        return "\n".join(
            (
                f"Proposal: {self.proposal_id}",
                f"Operation: {self.change_type.name}",
                f"Target: {target}",
                (
                    "Requested change: "
                    f"{self.change.before.field_path} -> "
                    f"{self.change.requested_after.field_path}"
                ),
                (
                    "Baseline: "
                    f"{self.snapshot_reference.semantic_fingerprint}"
                ),
                f"State: {self.lifecycle_state.name}",
            )
        )


def validate_change_proposal(proposal: ChangeProposal) -> None:
    """Perform intrinsic validation only; never inspect current metadata."""

    _require_exact(
        proposal.proposal_id,
        "proposal ID",
        InvalidChangeProposal,
    )
    _require_exact(
        proposal.demonstration_id,
        "demonstration ID",
        InvalidChangeProposal,
    )
    if proposal.proposal_schema_version != PROPOSAL_SCHEMA_VERSION:
        raise InvalidChangeProposal(
            "Unsupported proposal schema version: "
            f"{proposal.proposal_schema_version!r}."
        )
    if not isinstance(proposal.change_type, ChangeType):
        raise UnsupportedChangeType(
            f"Unsupported change type: {proposal.change_type!r}."
        )
    if proposal.change_type is not ChangeType.FIELD_RENAME:
        raise UnsupportedChangeType(
            f"Unsupported change type: {proposal.change_type.value}."
        )
    if not isinstance(proposal.change, FieldRenameChange):
        raise InvalidFieldRename(
            "FIELD_RENAME requires a FieldRenameChange payload."
        )
    if not isinstance(proposal.snapshot_reference, ProposalSnapshotReference):
        raise InvalidProposalSnapshotReference(
            "Proposal snapshot reference is required."
        )
    if not isinstance(proposal.lifecycle_state, ProposalLifecycleState):
        raise InvalidChangeProposal("Proposal lifecycle state is unsupported.")
    if not isinstance(proposal.provenance, ProposalProvenance):
        raise InvalidChangeProposal("Proposal provenance is required.")
    _require_timestamp(proposal.created_at)
    _optional_exact(
        proposal.description,
        "proposal description",
        InvalidChangeProposal,
    )
    _optional_exact(
        proposal.rationale,
        "proposal rationale",
        InvalidChangeProposal,
    )


def _require_timestamp(value: str) -> None:
    _require_exact(value, "proposal created_at", InvalidChangeProposal)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise InvalidChangeProposal(
            "Proposal created_at must be an ISO-8601 timestamp."
        ) from exc
    if parsed.tzinfo is None:
        raise InvalidChangeProposal(
            "Proposal created_at must include a timezone."
        )


def _require_exact(
    value: object,
    label: str,
    error_type: type[ValueError],
) -> None:
    if not isinstance(value, str) or not value:
        raise error_type(f"{label} must be a non-empty string.")
    if not value.strip():
        raise error_type(f"{label} must not be whitespace-only.")
    if value != value.strip():
        raise error_type(
            f"{label} must not contain leading or trailing whitespace."
        )


def _optional_exact(
    value: object | None,
    label: str,
    error_type: type[ValueError],
) -> None:
    if value is not None:
        _require_exact(value, label, error_type)
