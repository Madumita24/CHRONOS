"""Errors raised by CHRONOS Phase 4.3 severity and criticality analysis."""


class SeverityCriticalityError(ValueError):
    """Base Phase 4.3 error."""


class SeverityCriticalityEntryError(SeverityCriticalityError):
    """A certified prerequisite failed closed."""


class SeverityCriticalityValidationError(SeverityCriticalityError):
    """A derived severity package violated an invariant."""


class SeverityCriticalitySerializationError(SeverityCriticalityError):
    """Serialized Phase 4.3 data is invalid."""
