"""Errors raised by CHRONOS Phase 3.6 certification."""


class Phase3CertificationError(ValueError):
    """Base class for Phase 3 certification failures."""


class Phase3CertificationInputError(Phase3CertificationError):
    """An authoritative certification input could not be loaded."""


class Phase3CertificationSerializationError(Phase3CertificationError):
    """A certification artifact is malformed or was tampered with."""


class Phase3CertificationValidationError(Phase3CertificationError):
    """A certification result is internally inconsistent."""
