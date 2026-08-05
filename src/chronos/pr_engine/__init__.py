"""Public deterministic Phase 6.3 multi-file PR analysis API."""

from .engine import (
    PR_ARTIFACT_FILENAMES,
    analyze_pull_request,
    analyze_pull_request_bundle,
)
from .errors import (
    FileParseError,
    FileSafetyError,
    PullRequestCertificationError,
    PullRequestEngineError,
    PullRequestProposalError,
    PullRequestResolutionError,
    RepositoryIntakeError,
)
from .models import (
    CoherenceState,
    FileCategory,
    FileStatus,
    IntakeMode,
    PullRequestAnalysisProposal,
    PullRequestAnalysisResult,
    PullRequestOperation,
)
from .proposals import parse_pr_proposal

__all__ = [
    "PR_ARTIFACT_FILENAMES", "CoherenceState", "FileCategory", "FileParseError",
    "FileSafetyError", "FileStatus", "IntakeMode", "PullRequestAnalysisProposal",
    "PullRequestAnalysisResult", "PullRequestCertificationError", "PullRequestEngineError",
    "PullRequestOperation", "PullRequestProposalError", "PullRequestResolutionError",
    "RepositoryIntakeError", "analyze_pull_request", "analyze_pull_request_bundle",
    "parse_pr_proposal",
]
