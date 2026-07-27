"""Public proposal-validation API for CHRONOS Phase 2.2."""

from .errors import (
    ProposalValidationError,
    ProposalValidationSerializationError,
)
from .models import (
    VALIDATOR_SCHEMA_VERSION,
    PreconditionResult,
    PreconditionStatus,
    ProposalValidationFinding,
    ProposalValidationResult,
    ProposalValidationState,
    ValidatedBeforeState,
    ValidatedRequestedAfterState,
    ValidatedTarget,
    ValidationFindingCode,
    ValidationFindingSeverity,
)
from .serialization import (
    export_validation_result,
    load_validation_result,
    validation_result_from_json,
    validation_result_semantic_fingerprint,
    validation_result_to_dict,
    validation_result_to_json,
)
from .validator import validate_proposal

__all__ = [
    "VALIDATOR_SCHEMA_VERSION",
    "PreconditionResult",
    "PreconditionStatus",
    "ProposalValidationError",
    "ProposalValidationFinding",
    "ProposalValidationResult",
    "ProposalValidationSerializationError",
    "ProposalValidationState",
    "ValidatedBeforeState",
    "ValidatedRequestedAfterState",
    "ValidatedTarget",
    "ValidationFindingCode",
    "ValidationFindingSeverity",
    "export_validation_result",
    "load_validation_result",
    "validate_proposal",
    "validation_result_from_json",
    "validation_result_semantic_fingerprint",
    "validation_result_to_dict",
    "validation_result_to_json",
]
