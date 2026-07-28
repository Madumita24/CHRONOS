"""CHRONOS Phase 4.5 certification failures."""


class Phase4CertificationError(Exception):
    """Base Phase 4 certification error."""


class Phase4CertificationInputError(Phase4CertificationError):
    """An authoritative certification input failed closed."""


class Phase4CertificationValidationError(Phase4CertificationError):
    """A certification result contradicts its certified invariants."""


class Phase4CertificationSerializationError(Phase4CertificationError):
    """Serialized Phase 4 certification content is invalid."""
