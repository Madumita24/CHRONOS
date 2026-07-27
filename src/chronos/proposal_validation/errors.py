"""Errors raised by CHRONOS Phase 2.2 proposal validation."""


class ProposalValidationError(ValueError):
    """Base class for validation-result domain failures."""


class ProposalValidationSerializationError(ProposalValidationError):
    """A validation result cannot be safely serialized or reloaded."""
