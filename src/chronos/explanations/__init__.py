"""Public CHRONOS Phase 3.5 explanation API."""

from .builder import (
    build_explanation_bundle,
    build_explanation_bundle_from_artifacts,
    validate_explanation_bundle,
)
from .errors import (
    ExplanationEntryPreconditionError,
    ExplanationError,
    ExplanationSerializationError,
    ExplanationValidationError,
)
from .models import (
    EXPLANATION_BUNDLE_SCHEMA_VERSION,
    ArtifactEvidenceReference,
    DatasetExplanation,
    EvidenceChain,
    ExplanationBundle,
    ExplanationClassification,
    ExplanationStep,
    ExplanationStepType,
    ExplanationValidationState,
    FieldExplanation,
    PathExplanation,
    RelationshipExplanation,
    SourceExplanation,
    UncertaintyRecord,
)
from .serialization import (
    explanation_from_json,
    explanation_semantic_fingerprint,
    explanation_to_dict,
    explanation_to_json,
    export_explanation_bundle,
    load_explanation_bundle,
)

__all__ = [
    "EXPLANATION_BUNDLE_SCHEMA_VERSION",
    "ArtifactEvidenceReference",
    "DatasetExplanation",
    "EvidenceChain",
    "ExplanationBundle",
    "ExplanationClassification",
    "ExplanationEntryPreconditionError",
    "ExplanationError",
    "ExplanationSerializationError",
    "ExplanationStep",
    "ExplanationStepType",
    "ExplanationValidationError",
    "ExplanationValidationState",
    "FieldExplanation",
    "PathExplanation",
    "RelationshipExplanation",
    "SourceExplanation",
    "UncertaintyRecord",
    "build_explanation_bundle",
    "build_explanation_bundle_from_artifacts",
    "explanation_from_json",
    "explanation_semantic_fingerprint",
    "explanation_to_dict",
    "explanation_to_json",
    "export_explanation_bundle",
    "load_explanation_bundle",
    "validate_explanation_bundle",
]
