"""Errors for CHRONOS Phase 2.4 package certification."""


class Phase2CertificationError(ValueError):
    """Base class for Phase 2 certification failures."""


class Phase2CertificationSerializationError(Phase2CertificationError):
    """A certification result cannot be safely serialized or reloaded."""
