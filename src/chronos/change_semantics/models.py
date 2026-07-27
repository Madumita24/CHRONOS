"""Immutable models for the CHRONOS Phase 2.3 semantic contract."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from chronos.proposal import ChangeType


CONTRACT_SCHEMA_VERSION = "1.0"
SemanticValue = str | int | bool | None | tuple[str, ...]


class SemanticCategory(str, Enum):
    CHANGED = "changed"
    UNCHANGED_BY_PROPOSAL = "unchanged_by_proposal"
    UNKNOWN_CONSEQUENCE = "unknown_consequence"
    PRECONDITION = "precondition"


class IdentityClassification(str, Enum):
    CERTIFIED_CURRENT = "certified_current"
    COUNTERFACTUAL_CANDIDATE = "counterfactual_candidate"


class ConsequenceStatus(str, Enum):
    UNKNOWN = "unknown"


class EvaluationStatus(str, Enum):
    NOT_EVALUATED = "not_evaluated"


class PreconditionStatus(str, Enum):
    SATISFIED = "satisfied"


class RuleDisposition(str, Enum):
    ALLOWED = "allowed"
    REQUIRED = "required"
    FORBIDDEN = "forbidden"


class SemanticRuleCode(str, Enum):
    CREATE_COUNTERFACTUAL_REPRESENTATION = (
        "create_counterfactual_representation"
    )
    RENAME_TARGET_SOURCE_IDENTITY = "rename_target_source_identity"
    PRESERVE_UNCHANGED_SOURCE_PROPERTIES = (
        "preserve_unchanged_source_properties"
    )
    PRESERVE_CURRENT_SNAPSHOT = "preserve_current_snapshot"
    MUTATE_CURRENT_SNAPSHOT = "mutate_current_snapshot"
    CHANGE_UNRELATED_FIELDS = "change_unrelated_fields"
    CHANGE_DATASET_IDENTITY = "change_dataset_identity"
    CHANGE_SOURCE_TYPES = "change_source_types"
    DELETE_CURRENT_EVIDENCE = "delete_current_evidence"
    AUTOMATIC_DOWNSTREAM_RENAME = "automatic_downstream_rename"
    INFER_DOWNSTREAM_COMPATIBILITY = "infer_downstream_compatibility"
    WRITE_DATAHUB = "write_datahub"
    PRESERVE_EVIDENCE_PROVENANCE = "preserve_evidence_provenance"
    REINTERPRET_CURRENT_EVIDENCE_AS_COUNTERFACTUAL = (
        "reinterpret_current_evidence_as_counterfactual"
    )


@dataclass(frozen=True)
class FieldMachineIdentity:
    dataset_urn: str
    field_path: str
    schema_field_urn: str | None
    classification: IdentityClassification

    @property
    def machine_key(self) -> tuple[str, str]:
        return (self.dataset_urn, self.field_path)


@dataclass(frozen=True)
class ChangedProperty:
    property_name: str
    before: SemanticValue
    after: SemanticValue
    category: SemanticCategory = field(
        default=SemanticCategory.CHANGED,
        init=False,
    )


@dataclass(frozen=True)
class UnchangedProperty:
    property_name: str
    value: SemanticValue
    category: SemanticCategory = field(
        default=SemanticCategory.UNCHANGED_BY_PROPOSAL,
        init=False,
    )


@dataclass(frozen=True)
class UnknownConsequence:
    consequence: str
    status: ConsequenceStatus = ConsequenceStatus.UNKNOWN
    evaluation: EvaluationStatus = EvaluationStatus.NOT_EVALUATED
    category: SemanticCategory = field(
        default=SemanticCategory.UNKNOWN_CONSEQUENCE,
        init=False,
    )


@dataclass(frozen=True)
class ContractPrecondition:
    precondition: str
    status: PreconditionStatus
    expected: str
    observed: str
    category: SemanticCategory = field(
        default=SemanticCategory.PRECONDITION,
        init=False,
    )


@dataclass(frozen=True)
class SemanticRule:
    code: SemanticRuleCode
    disposition: RuleDisposition
    statement: str


@dataclass(frozen=True)
class SourceSchemaSemanticContract:
    current_field_count: int
    counterfactual_candidate_field_count: int
    current_field_path: str
    counterfactual_candidate_field_path: str
    unchanged_field_paths: tuple[str, ...]
    transformed_schema_materialized: bool


@dataclass(frozen=True)
class ChangeSemanticContract:
    proposal_id: str
    proposal_fingerprint: str
    validation_fingerprint: str
    baseline_snapshot_fingerprint: str
    change_type: ChangeType
    current_target: FieldMachineIdentity
    counterfactual_candidate: FieldMachineIdentity
    changed_properties: tuple[ChangedProperty, ...]
    unchanged_properties: tuple[UnchangedProperty, ...]
    unknown_consequences: tuple[UnknownConsequence, ...]
    preconditions: tuple[ContractPrecondition, ...]
    semantic_rules: tuple[SemanticRule, ...]
    source_schema_contract: SourceSchemaSemanticContract
    created_at: str
    contract_schema_version: str = CONTRACT_SCHEMA_VERSION
    semantic_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        if self.contract_schema_version != CONTRACT_SCHEMA_VERSION:
            raise ValueError(
                "Unsupported semantic-contract schema version: "
                f"{self.contract_schema_version!r}."
            )
        if self.change_type is not ChangeType.FIELD_RENAME:
            raise ValueError("Only FIELD_RENAME semantic contracts are valid.")
        try:
            timestamp = datetime.fromisoformat(self.created_at)
        except (TypeError, ValueError) as exc:
            raise ValueError("Contract created_at must be ISO-8601.") from exc
        if timestamp.tzinfo is None:
            raise ValueError("Contract created_at must include a timezone.")
        for value, label in (
            (self.proposal_fingerprint, "proposal fingerprint"),
            (self.validation_fingerprint, "validation fingerprint"),
            (self.baseline_snapshot_fingerprint, "snapshot fingerprint"),
        ):
            if not _is_sha256_fingerprint(value):
                raise ValueError(f"{label} is not canonical sha256.")
        if self.current_target.dataset_urn != (
            self.counterfactual_candidate.dataset_urn
        ):
            raise ValueError("FIELD_RENAME must preserve the Dataset URN.")
        if self.current_target.field_path == (
            self.counterfactual_candidate.field_path
        ):
            raise ValueError("Current and candidate field paths must differ.")
        if self.counterfactual_candidate.schema_field_urn is not None:
            raise ValueError(
                "A counterfactual candidate cannot claim a schema-field URN."
            )
        if self.source_schema_contract.transformed_schema_materialized:
            raise ValueError("Phase 2.3 cannot materialize a transformed schema.")
        from .serialization import contract_semantic_fingerprint

        object.__setattr__(
            self,
            "semantic_fingerprint",
            contract_semantic_fingerprint(self),
        )

    def to_dict(self, *, include_volatile: bool = True) -> dict[str, Any]:
        from .serialization import contract_to_dict

        return contract_to_dict(self, include_volatile=include_volatile)

    def to_json(self) -> str:
        from .serialization import contract_to_json

        return contract_to_json(self, include_volatile=True)

    def semantic_json(self) -> str:
        from .serialization import contract_to_json

        return contract_to_json(self, include_volatile=False)

    @classmethod
    def from_json(cls, value: str) -> ChangeSemanticContract:
        from .serialization import contract_from_json

        return contract_from_json(value)

    def semantically_equals(self, other: object) -> bool:
        return (
            isinstance(other, ChangeSemanticContract)
            and self.semantic_fingerprint == other.semantic_fingerprint
            and self.semantic_json() == other.semantic_json()
        )

    def summary(self) -> str:
        unchanged_names = ", ".join(
            item.property_name for item in self.unchanged_properties
        )
        return "\n".join(
            (
                f"Operation: {self.change_type.name}",
                (
                    "Target: "
                    f"{self.current_target.dataset_urn} / "
                    f"{self.current_target.field_path}"
                ),
                (
                    "Changed: field path/name "
                    f"{self.current_target.field_path} -> "
                    f"{self.counterfactual_candidate.field_path}"
                ),
                f"Unchanged by proposal: {unchanged_names}",
                "Unknown consequences: NOT_EVALUATED",
                (
                    "Future application: must create a new "
                    "counterfactual representation"
                ),
                "Current snapshot mutation: FORBIDDEN",
                "Automatic downstream rename: FORBIDDEN",
            )
        )


def _is_sha256_fingerprint(value: object) -> bool:
    if not isinstance(value, str) or not value.startswith("sha256:"):
        return False
    digest = value.removeprefix("sha256:")
    return len(digest) == 64 and all(
        character in "0123456789abcdef" for character in digest
    )
