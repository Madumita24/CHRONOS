"""Errors raised by CHRONOS Phase 3.5 explanation generation."""


class ExplanationError(ValueError):
    """Base class for deterministic explanation failures."""


class ExplanationEntryPreconditionError(ExplanationError):
    """An authoritative explanation prerequisite failed closed."""


class ExplanationValidationError(ExplanationError):
    """An explanation bundle is inconsistent with its evidence."""


class ExplanationSerializationError(ExplanationError):
    """Serialized explanation content is invalid or tampered."""
