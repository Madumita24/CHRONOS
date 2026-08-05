"""Immutable public contracts for Phase 6.2 semantic analysis."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, TypeAlias


SEMANTIC_ENGINE_VERSION = "6.2.0"
SEMANTIC_ARTIFACT_SCHEMA_VERSION = "1.0"
SQL_PARSER_NAME = "sqlglot"
SQL_PARSER_VERSION = "30.13.0"


class SemanticOperation(str, Enum):
    SEMANTIC_CODE_CHANGE = "SEMANTIC_CODE_CHANGE"


class ResolutionState(str, Enum):
    RESOLVED = "RESOLVED"
    AMBIGUOUS = "AMBIGUOUS"
    NOT_FOUND = "NOT_FOUND"
    INSUFFICIENT_METADATA = "INSUFFICIENT_METADATA"


class OutputMappingState(str, Enum):
    RESOLVED_CURRENT_OUTPUT = "RESOLVED_CURRENT_OUTPUT"
    COUNTERFACTUAL_OUTPUT = "COUNTERFACTUAL_OUTPUT"
    REMOVED_OUTPUT = "REMOVED_OUTPUT"
    NEW_OUTPUT = "NEW_OUTPUT"
    UNRESOLVED_OUTPUT = "UNRESOLVED_OUTPUT"
    IDENTITY_PRESERVED_SEMANTICS_CHANGED = (
        "IDENTITY_PRESERVED_SEMANTICS_CHANGED"
    )


class SemanticCompatibilityState(str, Enum):
    SEMANTICALLY_COMPATIBLE = "SEMANTICALLY_COMPATIBLE"
    SEMANTICALLY_CHANGED = "SEMANTICALLY_CHANGED"
    SEMANTIC_COMPATIBILITY_UNKNOWN = "SEMANTIC_COMPATIBILITY_UNKNOWN"
    SEMANTICALLY_INCOMPATIBLE = "SEMANTICALLY_INCOMPATIBLE"


class DeltaType(str, Enum):
    AGGREGATION_CHANGE = "AGGREGATION_CHANGE"
    FILTER_CHANGE = "FILTER_CHANGE"
    JOIN_TYPE_CHANGE = "JOIN_TYPE_CHANGE"
    JOIN_PREDICATE_CHANGE = "JOIN_PREDICATE_CHANGE"
    JOINED_RELATION_CHANGE = "JOINED_RELATION_CHANGE"
    DERIVED_EXPRESSION_CHANGE = "DERIVED_EXPRESSION_CHANGE"
    OUTPUT_COLUMN_RENAME = "OUTPUT_COLUMN_RENAME"
    OUTPUT_COLUMN_ADDED = "OUTPUT_COLUMN_ADDED"
    OUTPUT_COLUMN_REMOVED = "OUTPUT_COLUMN_REMOVED"
    OUTPUT_ORDER_CHANGE = "OUTPUT_ORDER_CHANGE"


class DeltaScope(str, Enum):
    OUTPUT_FIELD = "OUTPUT_FIELD"
    MODEL_WIDE = "MODEL_WIDE"
    STRUCTURAL = "STRUCTURAL"


class EvidenceClass(str, Enum):
    OBSERVED_DATAHUB_EVIDENCE = "OBSERVED_DATAHUB_EVIDENCE"
    CODE_DERIVED_EVIDENCE = "CODE_DERIVED_EVIDENCE"
    COUNTERFACTUAL_DERIVATION = "COUNTERFACTUAL_DERIVATION"
    MISSING_EVIDENCE = "MISSING_EVIDENCE"
    DECISION_EVIDENCE = "DECISION_EVIDENCE"


@dataclass(frozen=True, order=True)
class MetadataItem:
    key: str
    value: str


@dataclass(frozen=True)
class SemanticCodeChangeProposal:
    proposal_id: str
    analysis_id: str
    operation: SemanticOperation
    model_dataset_urn: str
    sql_dialect: str
    before_code_reference: str
    after_code_reference: str
    source_snapshot_fingerprint: str
    source_snapshot_id: str | None = None
    dbt_manifest_reference: str | None = None
    scenario_id: str | None = None
    model_relation: str | None = None
    description: str | None = None
    created_at: str | None = None
    proposal_metadata: tuple[MetadataItem, ...] = ()


@dataclass(frozen=True)
class SemanticAnalysisIdentity:
    analysis_id: str
    proposal_id: str
    operation: SemanticOperation
    model_dataset_urn: str
    sql_dialect: str
    parser_name: str
    parser_version: str
    engine_version: str
    source_snapshot_id: str
    source_snapshot_fingerprint: str
    proposal_fingerprint: str
    before_content_fingerprint: str
    after_content_fingerprint: str
    scenario_id: str | None = None
    created_at: str | None = None


@dataclass(frozen=True, order=True)
class ColumnReference:
    name: str
    qualifier: str | None
    normalized: str


@dataclass(frozen=True)
class AggregationContract:
    function: str
    distinct: bool
    input_references: tuple[ColumnReference, ...]
    normalized_expression: str


@dataclass(frozen=True)
class OutputColumnContract:
    ordinal: int
    output_name: str
    normalized_expression: str
    expression_fingerprint: str
    input_columns: tuple[ColumnReference, ...]
    source_relations: tuple[str, ...]
    aggregations: tuple[AggregationContract, ...]
    functions: tuple[str, ...]
    literals: tuple[str, ...]
    operators: tuple[str, ...]
    has_case: bool
    has_window: bool
    data_type_state: str
    lineage_derivation: str


@dataclass(frozen=True)
class RelationContract:
    qualified_name: str
    alias: str
    is_cte: bool


@dataclass(frozen=True)
class JoinContract:
    ordinal: int
    join_type: str
    relation: RelationContract
    normalized_predicate: str | None
    predicate_columns: tuple[ColumnReference, ...]


@dataclass(frozen=True)
class ParsedModel:
    statement_type: str
    dialect: str
    parser_name: str
    parser_version: str
    canonical_sql: str
    canonical_ast_fingerprint: str
    ctes: tuple[str, ...]
    source_relations: tuple[RelationContract, ...]
    output_columns: tuple[OutputColumnContract, ...]
    filter_predicate: str | None
    filter_columns: tuple[ColumnReference, ...]
    filter_literals: tuple[str, ...]
    filter_operators: tuple[str, ...]
    joins: tuple[JoinContract, ...]
    grouping: tuple[str, ...]
    ordering: tuple[str, ...]
    windows: tuple[str, ...]
    unresolved_stars: tuple[str, ...]


@dataclass(frozen=True)
class SemanticDelta:
    delta_id: str
    delta_type: DeltaType
    scope: DeltaScope
    affected_model_urn: str
    affected_output_field: str | None
    before_representation: Any
    after_representation: Any
    input_references: tuple[str, ...]
    evidence_references: tuple[str, ...]
    certainty: str
    change_components: tuple[str, ...]
    explanation: str


@dataclass(frozen=True)
class AggregationChange(SemanticDelta):
    pass


@dataclass(frozen=True)
class FilterChange(SemanticDelta):
    pass


@dataclass(frozen=True)
class JoinTypeChange(SemanticDelta):
    pass


@dataclass(frozen=True)
class JoinPredicateChange(SemanticDelta):
    pass


@dataclass(frozen=True)
class JoinedRelationChange(SemanticDelta):
    pass


@dataclass(frozen=True)
class DerivedExpressionChange(SemanticDelta):
    pass


@dataclass(frozen=True)
class OutputColumnRename(SemanticDelta):
    pass


@dataclass(frozen=True)
class OutputColumnAdded(SemanticDelta):
    pass


@dataclass(frozen=True)
class OutputColumnRemoved(SemanticDelta):
    pass


@dataclass(frozen=True)
class OutputOrderChange(SemanticDelta):
    pass


Delta: TypeAlias = (
    AggregationChange
    | FilterChange
    | JoinTypeChange
    | JoinPredicateChange
    | JoinedRelationChange
    | DerivedExpressionChange
    | OutputColumnRename
    | OutputColumnAdded
    | OutputColumnRemoved
    | OutputOrderChange
)


@dataclass(frozen=True)
class SemanticAnalysisResult:
    identity: SemanticAnalysisIdentity
    certification_status: str
    disposition: str
    decision_certainty: str
    semantic_compatibility: SemanticCompatibilityState
    semantic_fingerprint: str
    detected_deltas: tuple[Delta, ...]
    resolved_model: dict[str, Any]
    affected_outputs: tuple[str, ...]
    output_dir: Path
    artifact_paths: tuple[Path, ...]
    artifacts: dict[str, dict[str, Any]]
    manifest: dict[str, Any]
    key_summary: dict[str, Any]
