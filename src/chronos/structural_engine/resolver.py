"""Snapshot-backed target resolution with exact-match semantics."""

from __future__ import annotations

from chronos.snapshot import CurrentMetadataSnapshot

from .errors import ProposalValidationError, TargetResolutionError
from .models import ResolvedField
from .proposals import Proposal


def resolve_target(
    snapshot: CurrentMetadataSnapshot,
    proposal: Proposal,
) -> ResolvedField:
    if not _is_dataset_urn(proposal.dataset_urn):
        raise ProposalValidationError(
            "dataset_urn must be a canonical DataHub dataset URN."
        )
    if not _is_field_path(proposal.current_field_path):
        raise ProposalValidationError("current_field_path is malformed.")
    if proposal.source_snapshot_fingerprint != snapshot.semantic_fingerprint:
        raise ProposalValidationError(
            "Proposal source_snapshot_fingerprint does not match the supplied snapshot."
        )
    if (
        proposal.source_snapshot_id is not None
        and proposal.source_snapshot_id != snapshot.metadata.snapshot_id
    ):
        raise ProposalValidationError(
            "Proposal source_snapshot_id does not match the supplied snapshot."
        )
    if proposal.dataset_urn != snapshot.source_schema.dataset_urn:
        raise TargetResolutionError(
            "Structural changes must target the supplied snapshot source schema dataset."
        )
    matches = tuple(
        item
        for item in snapshot.source_schema.fields
        if item.field_path == proposal.current_field_path
    )
    if len(matches) != 1:
        raise TargetResolutionError(
            "Target field must resolve exactly once in the source schema; "
            f"resolved {len(matches)} matches."
        )
    field = matches[0]
    leaf_name = field.field_path.rsplit(".", 1)[-1]
    if field.field_name not in {field.field_path, leaf_name}:
        raise TargetResolutionError(
            "Resolved schema field has inconsistent field_name and field_path identity."
        )
    return ResolvedField(
        dataset_urn=proposal.dataset_urn,
        field_path=field.field_path,
        field_name=field.field_name,
        native_type=field.native_type,
        normalized_type=field.normalized_type,
        position=field.position,
        schema_field_urn=field.schema_field_urn,
    )


def _is_dataset_urn(value: str) -> bool:
    return (
        isinstance(value, str)
        and value.startswith("urn:li:dataset:(")
        and value.endswith(")")
        and value.count(",") >= 2
    )


def _is_field_path(value: str) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and value == value.strip()
        and not value.startswith(".")
        and not value.endswith(".")
        and ".." not in value
        and not any(character.isspace() for character in value)
    )
