"""Strict, immutable proposal union for supported structural changes."""

from __future__ import annotations

from dataclasses import dataclass, fields
from enum import Enum
from typing import Any, Mapping, TypeAlias

from .errors import ProposalValidationError


class StructuralOperation(str, Enum):
    FIELD_RENAME = "FIELD_RENAME"
    FIELD_DELETE = "FIELD_DELETE"
    FIELD_TYPE_CHANGE = "FIELD_TYPE_CHANGE"


@dataclass(frozen=True, order=True)
class ProposalMetadataItem:
    key: str
    value: str


@dataclass(frozen=True)
class StructuralChangeProposal:
    proposal_id: str
    analysis_id: str
    operation: StructuralOperation
    dataset_urn: str
    current_field_path: str
    source_snapshot_fingerprint: str
    source_snapshot_id: str | None = None
    description: str | None = None
    created_at: str | None = None
    proposal_metadata: tuple[ProposalMetadataItem, ...] = ()


@dataclass(frozen=True)
class FieldRenameProposal(StructuralChangeProposal):
    proposed_field_path: str = ""


@dataclass(frozen=True)
class FieldDeleteProposal(StructuralChangeProposal):
    pass


@dataclass(frozen=True)
class FieldTypeChangeProposal(StructuralChangeProposal):
    proposed_native_type: str = ""
    proposed_normalized_type: str = ""
    precision: int | None = None
    scale: int | None = None
    length: int | None = None


Proposal: TypeAlias = (
    FieldRenameProposal | FieldDeleteProposal | FieldTypeChangeProposal
)


_COMMON_KEYS = {
    "proposal_id",
    "analysis_id",
    "operation",
    "dataset_urn",
    "current_field_path",
    "source_snapshot_fingerprint",
    "source_snapshot_id",
    "description",
    "created_at",
    "proposal_metadata",
}
_REQUIRED_COMMON_KEYS = {
    "proposal_id",
    "analysis_id",
    "operation",
    "dataset_urn",
    "current_field_path",
    "source_snapshot_fingerprint",
}
_OPERATION_KEYS = {
    StructuralOperation.FIELD_RENAME: {"proposed_field_path"},
    StructuralOperation.FIELD_DELETE: set(),
    StructuralOperation.FIELD_TYPE_CHANGE: {
        "proposed_native_type",
        "proposed_normalized_type",
        "precision",
        "scale",
        "length",
    },
}
_OPERATION_REQUIRED_KEYS = {
    StructuralOperation.FIELD_RENAME: {"proposed_field_path"},
    StructuralOperation.FIELD_DELETE: set(),
    StructuralOperation.FIELD_TYPE_CHANGE: {
        "proposed_native_type",
        "proposed_normalized_type",
    },
}
_PROPOSAL_TYPES = {
    StructuralOperation.FIELD_RENAME: FieldRenameProposal,
    StructuralOperation.FIELD_DELETE: FieldDeleteProposal,
    StructuralOperation.FIELD_TYPE_CHANGE: FieldTypeChangeProposal,
}


def parse_proposal(value: Mapping[str, Any]) -> Proposal:
    """Parse a JSON object without coercion or unknown-key acceptance."""
    if not isinstance(value, Mapping):
        raise ProposalValidationError("Proposal must be a JSON object.")
    raw_operation = value.get("operation")
    try:
        operation = StructuralOperation(raw_operation)
    except (TypeError, ValueError) as exc:
        supported = ", ".join(item.value for item in StructuralOperation)
        raise ProposalValidationError(
            f"Unsupported operation {raw_operation!r}; expected one of {supported}."
        ) from exc

    allowed = _COMMON_KEYS | _OPERATION_KEYS[operation]
    required = _REQUIRED_COMMON_KEYS | _OPERATION_REQUIRED_KEYS[operation]
    unknown = sorted(set(value) - allowed)
    missing = sorted(required - set(value))
    if unknown:
        raise ProposalValidationError(
            f"Unknown proposal properties: {', '.join(unknown)}."
        )
    if missing:
        raise ProposalValidationError(
            f"Missing proposal properties: {', '.join(missing)}."
        )

    kwargs = dict(value)
    kwargs["operation"] = operation
    kwargs["proposal_metadata"] = _parse_metadata(
        kwargs.get("proposal_metadata", {})
    )
    proposal_type = _PROPOSAL_TYPES[operation]
    instance = proposal_type(**kwargs)
    _validate_scalar_types(instance)
    return instance


def proposal_to_dict(proposal: Proposal, *, semantic: bool = False) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for item in fields(proposal):
        if semantic and item.name == "created_at":
            continue
        value = getattr(proposal, item.name)
        if isinstance(value, Enum):
            value = value.value
        elif item.name == "proposal_metadata":
            value = {entry.key: entry.value for entry in value}
        if value is not None:
            result[item.name] = value
    return result


def _parse_metadata(value: Any) -> tuple[ProposalMetadataItem, ...]:
    if not isinstance(value, Mapping):
        raise ProposalValidationError("proposal_metadata must be a JSON object.")
    if not all(isinstance(key, str) and isinstance(item, str) for key, item in value.items()):
        raise ProposalValidationError(
            "proposal_metadata keys and values must be strings."
        )
    return tuple(
        ProposalMetadataItem(key=key, value=value[key]) for key in sorted(value)
    )


def _validate_scalar_types(proposal: Proposal) -> None:
    required_strings = (
        proposal.proposal_id,
        proposal.analysis_id,
        proposal.dataset_urn,
        proposal.current_field_path,
        proposal.source_snapshot_fingerprint,
    )
    if any(not isinstance(value, str) or not value.strip() for value in required_strings):
        raise ProposalValidationError("Required string properties must be non-empty.")
    optional_strings = (
        proposal.source_snapshot_id,
        proposal.description,
        proposal.created_at,
    )
    if any(value is not None and not isinstance(value, str) for value in optional_strings):
        raise ProposalValidationError("Optional textual properties must be strings.")
    if isinstance(proposal, FieldRenameProposal):
        if not isinstance(proposal.proposed_field_path, str) or not proposal.proposed_field_path.strip():
            raise ProposalValidationError("proposed_field_path must be non-empty.")
    if isinstance(proposal, FieldTypeChangeProposal):
        if not isinstance(proposal.proposed_native_type, str) or not proposal.proposed_native_type.strip():
            raise ProposalValidationError("proposed_native_type must be non-empty.")
        if not isinstance(proposal.proposed_normalized_type, str) or not proposal.proposed_normalized_type.strip():
            raise ProposalValidationError("proposed_normalized_type must be non-empty.")
        for name in ("precision", "scale", "length"):
            number = getattr(proposal, name)
            if number is not None and (not isinstance(number, int) or isinstance(number, bool) or number < 0):
                raise ProposalValidationError(f"{name} must be a non-negative integer.")
