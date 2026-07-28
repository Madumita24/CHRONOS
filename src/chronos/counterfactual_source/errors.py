"""Errors for CHRONOS Phase 3.1 counterfactual source state."""


class CounterfactualSourceStateError(ValueError):
    """Base class for Phase 3.1 source-state failures."""


class Phase3EntryPreconditionError(CounterfactualSourceStateError):
    """Certified entry artifacts do not authorize materialization."""


class CounterfactualSourceStateValidationError(
    CounterfactualSourceStateError
):
    """A candidate source state violates the Phase 3.1 contract."""


class CounterfactualSourceStateSerializationError(
    CounterfactualSourceStateError
):
    """A candidate source-state artifact cannot be serialized or loaded."""
