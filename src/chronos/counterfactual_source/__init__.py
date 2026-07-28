"""Public CHRONOS Phase 3.1 counterfactual source-state API."""

from .errors import (
    CounterfactualSourceStateError,
    CounterfactualSourceStateSerializationError,
    CounterfactualSourceStateValidationError,
    Phase3EntryPreconditionError,
)
from .materializer import (
    materialize_counterfactual_source_state,
    materialize_source_state_from_artifacts,
    validate_counterfactual_source_state,
)
from .models import (
    CANONICAL_DATASET_URN,
    COUNTERFACTUAL_SOURCE_SCHEMA_VERSION,
    CandidateSourceField,
    CandidateSourceSchema,
    CounterfactualDatasetIdentity,
    CounterfactualSourceState,
    CurrentSourceSchemaReference,
    FieldIdentityMapping,
    FieldMappingClassification,
    InputArtifactHash,
    SourceFieldIdentity,
    SourceStateClassification,
    TransformationSummary,
)
from .serialization import (
    export_source_state,
    load_source_state,
    source_state_from_json,
    source_state_semantic_fingerprint,
    source_state_to_dict,
    source_state_to_json,
)

__all__ = [
    "CANONICAL_DATASET_URN",
    "COUNTERFACTUAL_SOURCE_SCHEMA_VERSION",
    "CandidateSourceField",
    "CandidateSourceSchema",
    "CounterfactualDatasetIdentity",
    "CounterfactualSourceState",
    "CounterfactualSourceStateError",
    "CounterfactualSourceStateSerializationError",
    "CounterfactualSourceStateValidationError",
    "CurrentSourceSchemaReference",
    "FieldIdentityMapping",
    "FieldMappingClassification",
    "InputArtifactHash",
    "Phase3EntryPreconditionError",
    "SourceFieldIdentity",
    "SourceStateClassification",
    "TransformationSummary",
    "export_source_state",
    "load_source_state",
    "materialize_counterfactual_source_state",
    "materialize_source_state_from_artifacts",
    "source_state_from_json",
    "source_state_semantic_fingerprint",
    "source_state_to_dict",
    "source_state_to_json",
    "validate_counterfactual_source_state",
]
