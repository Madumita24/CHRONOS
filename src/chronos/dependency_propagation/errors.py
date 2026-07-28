"""Errors raised by CHRONOS Phase 3.3 dependency propagation."""


class DependencyPropagationError(ValueError):
    """Base class for deterministic propagation failures."""


class DependencyPropagationEntryPreconditionError(
    DependencyPropagationError
):
    """An authoritative Phase 3.3 input failed closed."""


class DependencyPropagationValidationError(DependencyPropagationError):
    """The propagated dependency state is internally inconsistent."""


class DependencyPropagationSerializationError(DependencyPropagationError):
    """A serialized propagation result is invalid or tampered."""
