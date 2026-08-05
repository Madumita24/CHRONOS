"""Errors raised by deterministic semantic SQL analysis."""


class SemanticEngineError(ValueError):
    """Base class for bounded user-facing semantic analysis failures."""


class SemanticProposalError(SemanticEngineError):
    """The semantic proposal is malformed or inconsistent."""


class UnsafeCodeInputError(SemanticEngineError):
    """A code or manifest reference is outside the safe repository boundary."""


class UnsupportedDbtError(SemanticEngineError):
    """Raw dbt input cannot be resolved without executing templates."""


class SqlParseError(SemanticEngineError):
    """SQL is invalid or outside the supported single-model boundary."""


class SemanticResolutionError(SemanticEngineError):
    """A model, relation, or column cannot be resolved safely."""


class SemanticCertificationError(SemanticEngineError):
    """A generated semantic package failed a certification invariant."""
