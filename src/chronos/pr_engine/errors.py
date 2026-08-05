"""Typed bounded failures for Phase 6.3 PR analysis."""


class PullRequestEngineError(ValueError):
    """Base class for expected PR analysis failures."""


class PullRequestProposalError(PullRequestEngineError):
    """The strict PR proposal is invalid."""


class RepositoryIntakeError(PullRequestEngineError):
    """The Git repository or exported bundle is unsafe or invalid."""


class FileSafetyError(PullRequestEngineError):
    """A changed file violates the bounded analysis policy."""


class FileParseError(PullRequestEngineError):
    """A supported file cannot be safely parsed."""


class PullRequestResolutionError(PullRequestEngineError):
    """A required code-to-metadata identity is ambiguous or inconsistent."""


class PullRequestCertificationError(PullRequestEngineError):
    """The composite package failed deterministic certification."""
