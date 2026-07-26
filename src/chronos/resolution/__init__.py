"""Public Phase 1.2 canonical identity resolution API."""

from .models import (
    CanonicalDatasetIdentity,
    CanonicalEntityType,
    CanonicalSchemaFieldIdentity,
    DatasetResolutionResult,
    FieldResolutionResult,
    ResolutionEvidence,
    ResolutionState,
    ResolvedDatasetIdentity,
    ResolvedSchemaFieldIdentity,
)
from .resolver import CanonicalEntityResolver
from .session import ResolutionSession, create_resolution_session

__all__ = [
    "CanonicalDatasetIdentity",
    "CanonicalEntityResolver",
    "CanonicalEntityType",
    "CanonicalSchemaFieldIdentity",
    "DatasetResolutionResult",
    "FieldResolutionResult",
    "ResolutionEvidence",
    "ResolutionSession",
    "ResolutionState",
    "ResolvedDatasetIdentity",
    "ResolvedSchemaFieldIdentity",
    "create_resolution_session",
]
