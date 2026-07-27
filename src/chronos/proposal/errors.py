"""Narrow structural errors for CHRONOS Phase 2.1 proposals."""

from __future__ import annotations


class ChangeProposalError(ValueError):
    """Base class for proposal-domain failures."""


class InvalidChangeProposal(ChangeProposalError):
    """The proposal envelope is structurally invalid."""


class UnsupportedChangeType(ChangeProposalError):
    """The requested operation is not supported by Phase 2.1."""


class InvalidChangeTarget(ChangeProposalError):
    """The target lacks an exact schema-field machine identity."""


class InvalidFieldRename(ChangeProposalError):
    """A FIELD_RENAME payload is incomplete or meaningless."""


class InvalidProposalSnapshotReference(ChangeProposalError):
    """The certified-current-snapshot reference is malformed."""


class ProposalSerializationError(ChangeProposalError):
    """A proposal artifact cannot be safely serialized or reloaded."""
