"""Errors raised by CHRONOS Phase 4.2 business-context propagation."""


class BusinessContextError(ValueError):
    """Base Phase 4.2 error."""


class BusinessContextEntryError(BusinessContextError):
    """A certified prerequisite failed closed."""


class BusinessContextValidationError(BusinessContextError):
    """A derived business-context package violated an invariant."""


class BusinessContextSerializationError(BusinessContextError):
    """Serialized Phase 4.2 data is invalid."""
