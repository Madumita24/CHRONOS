"""Errors raised by CHRONOS Phase 2.3 change semantics."""


class ChangeSemanticContractError(ValueError):
    """Base class for semantic-contract failures."""


class SemanticContractPreconditionError(ChangeSemanticContractError):
    """Certified inputs do not satisfy contract-construction preconditions."""


class ChangeSemanticContractSerializationError(ChangeSemanticContractError):
    """A semantic contract cannot be safely serialized or reloaded."""
