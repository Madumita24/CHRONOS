"""Errors for CHRONOS Phase 3.2 Future Graph construction."""


class FutureGraphError(ValueError):
    """Base class for Phase 3.2 failures."""


class FutureGraphEntryPreconditionError(FutureGraphError):
    """Authoritative artifacts do not permit Future Graph construction."""


class FutureGraphValidationError(FutureGraphError):
    """A Future Graph violates structural Phase 3.2 invariants."""


class FutureGraphSerializationError(FutureGraphError):
    """A Future Graph artifact cannot be serialized or loaded."""
