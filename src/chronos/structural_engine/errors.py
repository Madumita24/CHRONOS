"""Errors raised by the generalized structural-change engine."""


class StructuralEngineError(ValueError):
    """Base class for safe, user-actionable analysis failures."""


class ProposalValidationError(StructuralEngineError):
    """The proposal is malformed or semantically invalid."""


class TargetResolutionError(StructuralEngineError):
    """The proposal target cannot be resolved exactly once."""


class OutputSafetyError(StructuralEngineError):
    """The requested artifact location is unsafe or already populated."""


class CertificationError(StructuralEngineError):
    """The generated analysis does not satisfy certification invariants."""
