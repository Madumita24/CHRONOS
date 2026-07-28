"""Public CHRONOS Phase 3.3 dependency propagation API."""

from .builder import (
    TraversalPath,
    enumerate_dependency_paths,
    propagate_dependencies,
    propagate_dependencies_from_artifacts,
    shortest_dependency_depths,
    validate_dependency_propagation,
)
from .errors import (
    DependencyPropagationEntryPreconditionError,
    DependencyPropagationError,
    DependencyPropagationSerializationError,
    DependencyPropagationValidationError,
)
from .models import (
    DEPENDENCY_PROPAGATION_SCHEMA_VERSION,
    DatasetExposureRecord,
    DatasetExposureState,
    DependencyPathRecord,
    DependencyPropagationResult,
    FieldExposureRecord,
    FieldExposureState,
    PropagationSummary,
    PropagationValidationState,
    RelationshipExposureRecord,
    RelationshipExposureState,
)
from .serialization import (
    export_dependency_propagation,
    load_dependency_propagation,
    propagation_from_json,
    propagation_semantic_fingerprint,
    propagation_to_dict,
    propagation_to_json,
)

__all__ = [
    "DEPENDENCY_PROPAGATION_SCHEMA_VERSION",
    "DatasetExposureRecord",
    "DatasetExposureState",
    "DependencyPathRecord",
    "DependencyPropagationEntryPreconditionError",
    "DependencyPropagationError",
    "DependencyPropagationResult",
    "DependencyPropagationSerializationError",
    "DependencyPropagationValidationError",
    "FieldExposureRecord",
    "FieldExposureState",
    "PropagationSummary",
    "PropagationValidationState",
    "RelationshipExposureRecord",
    "RelationshipExposureState",
    "TraversalPath",
    "enumerate_dependency_paths",
    "export_dependency_propagation",
    "load_dependency_propagation",
    "propagate_dependencies",
    "propagate_dependencies_from_artifacts",
    "propagation_from_json",
    "propagation_semantic_fingerprint",
    "propagation_to_dict",
    "propagation_to_json",
    "shortest_dependency_depths",
    "validate_dependency_propagation",
]
