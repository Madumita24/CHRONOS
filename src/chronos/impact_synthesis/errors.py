"""CHRONOS Phase 4.4 impact-synthesis failures."""


class ImpactSynthesisError(Exception):
    """Base Phase 4.4 error."""


class ImpactSynthesisEntryError(ImpactSynthesisError):
    """A certified predecessor or identity precondition failed."""


class ImpactSynthesisValidationError(ImpactSynthesisError):
    """Derived decision state is inconsistent or unsupported."""


class ImpactSynthesisSerializationError(ImpactSynthesisError):
    """Serialized Phase 4.4 state is invalid."""
