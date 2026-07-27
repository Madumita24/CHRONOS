"""Public change-semantics API for CHRONOS Phase 2.3."""

from .builder import (
    build_change_semantic_contract,
    build_contract_from_artifacts,
)
from .errors import (
    ChangeSemanticContractError,
    ChangeSemanticContractSerializationError,
    SemanticContractPreconditionError,
)
from .models import (
    CONTRACT_SCHEMA_VERSION,
    ChangeSemanticContract,
    ChangedProperty,
    ConsequenceStatus,
    ContractPrecondition,
    EvaluationStatus,
    FieldMachineIdentity,
    IdentityClassification,
    PreconditionStatus,
    RuleDisposition,
    SemanticCategory,
    SemanticRule,
    SemanticRuleCode,
    SourceSchemaSemanticContract,
    UnchangedProperty,
    UnknownConsequence,
)
from .serialization import (
    contract_from_json,
    contract_semantic_fingerprint,
    contract_to_dict,
    contract_to_json,
    export_contract,
    load_contract,
)

__all__ = [
    "CONTRACT_SCHEMA_VERSION",
    "ChangeSemanticContract",
    "ChangeSemanticContractError",
    "ChangeSemanticContractSerializationError",
    "ChangedProperty",
    "ConsequenceStatus",
    "ContractPrecondition",
    "EvaluationStatus",
    "FieldMachineIdentity",
    "IdentityClassification",
    "PreconditionStatus",
    "RuleDisposition",
    "SemanticCategory",
    "SemanticContractPreconditionError",
    "SemanticRule",
    "SemanticRuleCode",
    "SourceSchemaSemanticContract",
    "UnchangedProperty",
    "UnknownConsequence",
    "build_change_semantic_contract",
    "build_contract_from_artifacts",
    "contract_from_json",
    "contract_semantic_fingerprint",
    "contract_to_dict",
    "contract_to_json",
    "export_contract",
    "load_contract",
]
