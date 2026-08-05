"""Explicit semantic compatibility and evidence registry."""

from __future__ import annotations

from dataclasses import dataclass

from .models import DeltaType, SemanticCompatibilityState


@dataclass(frozen=True)
class SemanticCompatibilityRule:
    rule_id: str
    delta_type: str
    required_evidence: tuple[str, ...]
    result: SemanticCompatibilityState
    evidence_certainty: str
    reason_code: str
    explanation_template: str


SEMANTIC_COMPATIBILITY_RULES = (
    SemanticCompatibilityRule(
        rule_id="semantic-compatible-no-delta",
        delta_type="NO_SEMANTIC_CHANGE",
        required_evidence=("canonical_ast_equivalence",),
        result=SemanticCompatibilityState.SEMANTICALLY_COMPATIBLE,
        evidence_certainty="ESTABLISHED",
        reason_code="NO_SEMANTIC_CHANGE",
        explanation_template="Canonical parsed model contracts are semantically equivalent within the supported boundary.",
    ),
    SemanticCompatibilityRule(
        rule_id="semantic-aggregation-definition-unresolved",
        delta_type=DeltaType.AGGREGATION_CHANGE.value,
        required_evidence=(
            "approved_metric_definition",
            "model_owner_or_contract_approval",
            "downstream_semantic_tests",
            "execution_comparison",
        ),
        result=SemanticCompatibilityState.SEMANTIC_COMPATIBILITY_UNKNOWN,
        evidence_certainty="UNRESOLVED",
        reason_code="AGGREGATION_DEFINITION_CHANGED_WITHOUT_APPROVAL",
        explanation_template="Aggregation meaning changed without certified approval or execution evidence.",
    ),
    SemanticCompatibilityRule(
        rule_id="semantic-filter-population-unresolved",
        delta_type=DeltaType.FILTER_CHANGE.value,
        required_evidence=(
            "certified_population_contract",
            "row_count_comparison",
            "downstream_consumer_test",
        ),
        result=SemanticCompatibilityState.SEMANTIC_COMPATIBILITY_UNKNOWN,
        evidence_certainty="UNRESOLVED",
        reason_code="ROW_SET_DEFINITION_CHANGED_WITHOUT_CONTRACT",
        explanation_template="The model population changed without a certified expected-population contract.",
    ),
    SemanticCompatibilityRule(
        rule_id="semantic-join-behavior-unresolved",
        delta_type="JOIN_CHANGE",
        required_evidence=(
            "cardinality_comparison",
            "null_rate_comparison",
            "uniqueness_validation",
            "consumer_contract",
        ),
        result=SemanticCompatibilityState.SEMANTIC_COMPATIBILITY_UNKNOWN,
        evidence_certainty="UNRESOLVED",
        reason_code="JOIN_BEHAVIOR_CHANGED_WITHOUT_EXECUTION_EVIDENCE",
        explanation_template="Join behavior changed without certified row-preservation or cardinality evidence.",
    ),
    SemanticCompatibilityRule(
        rule_id="semantic-derived-definition-unresolved",
        delta_type=DeltaType.DERIVED_EXPRESSION_CHANGE.value,
        required_evidence=(
            "approved_business_definition",
            "semantic_test",
            "execution_comparison",
        ),
        result=SemanticCompatibilityState.SEMANTIC_COMPATIBILITY_UNKNOWN,
        evidence_certainty="UNRESOLVED",
        reason_code="DERIVED_DEFINITION_CHANGED_WITHOUT_APPROVAL",
        explanation_template="The derived field definition changed without certified business-definition evidence.",
    ),
)


def rule_for_delta(delta_type: DeltaType) -> SemanticCompatibilityRule:
    if delta_type in {
        DeltaType.JOIN_TYPE_CHANGE,
        DeltaType.JOIN_PREDICATE_CHANGE,
        DeltaType.JOINED_RELATION_CHANGE,
    }:
        key = "JOIN_CHANGE"
    else:
        key = delta_type.value
    return next(item for item in SEMANTIC_COMPATIBILITY_RULES if item.delta_type == key)


def no_change_rule() -> SemanticCompatibilityRule:
    return SEMANTIC_COMPATIBILITY_RULES[0]
