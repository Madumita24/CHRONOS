"""Errors raised by CHRONOS Phase 4.1 technical-impact derivation."""


class TechnicalImpactError(ValueError):
    """Base class for Phase 4.1 failures."""


class TechnicalImpactEntryError(TechnicalImpactError):
    """The certified Phase 3 entry boundary failed closed."""


class TechnicalImpactValidationError(TechnicalImpactError):
    """A technical-impact result contradicts certified evidence."""


class TechnicalImpactSerializationError(TechnicalImpactError):
    """Serialized technical-impact content is malformed or tampered."""
