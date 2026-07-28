"""Errors raised by CHRONOS Phase 3.4 compatibility evaluation."""


class CompatibilityEvaluationError(ValueError):
    """Base class for deterministic compatibility failures."""


class CompatibilityEntryPreconditionError(CompatibilityEvaluationError):
    """An authoritative Phase 3.4 prerequisite failed closed."""


class CompatibilityValidationError(CompatibilityEvaluationError):
    """A compatibility result is internally inconsistent."""


class CompatibilitySerializationError(CompatibilityEvaluationError):
    """Serialized compatibility content is invalid or tampered."""
