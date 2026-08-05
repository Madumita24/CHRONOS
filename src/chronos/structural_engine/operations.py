"""Operation adapters for structural counterfactual source state."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import replace

from chronos.snapshot import CurrentMetadataSnapshot, SnapshotSchemaField

from .errors import ProposalValidationError
from .models import ResolvedField
from .resolver import _is_field_path
from .proposals import (
    FieldDeleteProposal,
    FieldRenameProposal,
    FieldTypeChangeProposal,
    Proposal,
    StructuralOperation,
)


SUPPORTED_NORMALIZED_TYPES = {
    "ARRAY",
    "BINARY",
    "BOOLEAN",
    "DATE",
    "DATETIME",
    "NUMBER",
    "STRING",
    "STRUCT",
    "TIME",
    "UNKNOWN",
}


class OperationAdapter(ABC):
    operation: StructuralOperation

    @abstractmethod
    def validate(
        self,
        snapshot: CurrentMetadataSnapshot,
        target: ResolvedField,
        proposal: Proposal,
    ) -> None:
        """Validate operation semantics against resolved snapshot state."""

    @abstractmethod
    def project_fields(
        self,
        snapshot: CurrentMetadataSnapshot,
        target: ResolvedField,
        proposal: Proposal,
    ) -> tuple[SnapshotSchemaField, ...]:
        """Return the projected source schema fields."""

    @abstractmethod
    def projected_field_path(self, proposal: Proposal) -> str | None:
        """Return future path, or None when the field is removed."""

    @abstractmethod
    def root_state(self) -> str:
        """Return the projected root graph state."""


class FieldRenameAdapter(OperationAdapter):
    operation = StructuralOperation.FIELD_RENAME

    def validate(self, snapshot, target, proposal) -> None:
        assert isinstance(proposal, FieldRenameProposal)
        if proposal.proposed_field_path == target.field_path:
            raise ProposalValidationError("Rename must change the field path.")
        if not _is_field_path(proposal.proposed_field_path):
            raise ProposalValidationError("proposed_field_path is malformed.")
        if any(
            field.field_path == proposal.proposed_field_path
            for field in snapshot.source_schema.fields
        ):
            raise ProposalValidationError(
                "proposed_field_path already exists in the source schema."
            )

    def project_fields(self, snapshot, target, proposal):
        assert isinstance(proposal, FieldRenameProposal)
        return tuple(
            replace(
                field,
                field_path=proposal.proposed_field_path,
                field_name=proposal.proposed_field_path.rsplit(".", 1)[-1],
                schema_field_urn=None,
            )
            if field.field_path == target.field_path
            else field
            for field in snapshot.source_schema.fields
        )

    def projected_field_path(self, proposal):
        assert isinstance(proposal, FieldRenameProposal)
        return proposal.proposed_field_path

    def root_state(self) -> str:
        return "renamed"


class FieldDeleteAdapter(OperationAdapter):
    operation = StructuralOperation.FIELD_DELETE

    def validate(self, snapshot, target, proposal) -> None:
        assert isinstance(proposal, FieldDeleteProposal)

    def project_fields(self, snapshot, target, proposal):
        assert isinstance(proposal, FieldDeleteProposal)
        return tuple(
            field
            for field in snapshot.source_schema.fields
            if field.field_path != target.field_path
        )

    def projected_field_path(self, proposal):
        assert isinstance(proposal, FieldDeleteProposal)
        return None

    def root_state(self) -> str:
        return "removed"


class FieldTypeChangeAdapter(OperationAdapter):
    operation = StructuralOperation.FIELD_TYPE_CHANGE

    def validate(self, snapshot, target, proposal) -> None:
        assert isinstance(proposal, FieldTypeChangeProposal)
        normalized = proposal.proposed_normalized_type.upper()
        if normalized not in SUPPORTED_NORMALIZED_TYPES:
            raise ProposalValidationError(
                "proposed_normalized_type is not a supported normalized type family."
            )
        if (
            proposal.proposed_native_type == target.native_type
            and normalized == target.normalized_type.upper()
        ):
            raise ProposalValidationError("Type change must change the effective type.")

    def project_fields(self, snapshot, target, proposal):
        assert isinstance(proposal, FieldTypeChangeProposal)
        return tuple(
            replace(
                field,
                native_type=proposal.proposed_native_type,
                normalized_type=proposal.proposed_normalized_type.upper(),
                datahub_type=proposal.proposed_normalized_type.upper(),
                schema_field_urn=None,
            )
            if field.field_path == target.field_path
            else field
            for field in snapshot.source_schema.fields
        )

    def projected_field_path(self, proposal):
        assert isinstance(proposal, FieldTypeChangeProposal)
        return proposal.current_field_path

    def root_state(self) -> str:
        return "type_changed"


_ADAPTERS: dict[StructuralOperation, OperationAdapter] = {
    StructuralOperation.FIELD_RENAME: FieldRenameAdapter(),
    StructuralOperation.FIELD_DELETE: FieldDeleteAdapter(),
    StructuralOperation.FIELD_TYPE_CHANGE: FieldTypeChangeAdapter(),
}


def get_adapter(proposal: Proposal) -> OperationAdapter:
    return _ADAPTERS[proposal.operation]
