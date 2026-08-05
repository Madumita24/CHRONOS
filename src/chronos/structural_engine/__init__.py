"""Generalized CHRONOS structural-change analysis public API."""

from .engine import ARTIFACT_FILENAMES, analyze_structural_change
from .errors import (
    CertificationError,
    OutputSafetyError,
    ProposalValidationError,
    StructuralEngineError,
    TargetResolutionError,
)
from .models import (
    GENERALIZED_ARTIFACT_SCHEMA_VERSION,
    GENERALIZED_ENGINE_VERSION,
    AnalysisIdentity,
    ResolvedField,
    StructuralAnalysisResult,
)
from .proposals import (
    FieldDeleteProposal,
    FieldRenameProposal,
    FieldTypeChangeProposal,
    Proposal,
    StructuralChangeProposal,
    StructuralOperation,
    parse_proposal,
)

__all__ = [
    "ARTIFACT_FILENAMES",
    "GENERALIZED_ARTIFACT_SCHEMA_VERSION",
    "GENERALIZED_ENGINE_VERSION",
    "AnalysisIdentity",
    "CertificationError",
    "FieldDeleteProposal",
    "FieldRenameProposal",
    "FieldTypeChangeProposal",
    "OutputSafetyError",
    "Proposal",
    "ProposalValidationError",
    "ResolvedField",
    "StructuralAnalysisResult",
    "StructuralChangeProposal",
    "StructuralEngineError",
    "StructuralOperation",
    "TargetResolutionError",
    "analyze_structural_change",
    "parse_proposal",
]
