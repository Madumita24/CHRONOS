"""Explicit conservative compatibility rules for Level 1 operations."""

from __future__ import annotations

from dataclasses import dataclass

from chronos.compatibility_evaluation import CompatibilityState, EvidenceStrength

from .proposals import FieldTypeChangeProposal, Proposal, StructuralOperation


@dataclass(frozen=True)
class CompatibilityRule:
    rule_id: str
    operation: str
    required_evidence: tuple[str, ...]
    inputs: tuple[str, ...]
    result: CompatibilityState
    reason_code: str
    evidence_strength: EvidenceStrength
    explanation_template: str


COMPATIBILITY_RULES = (
    CompatibilityRule(
        rule_id="compatibility-no-active-downstream-dependency",
        operation="*",
        required_evidence=("certified_future_graph",),
        inputs=("downstream_relationship_count=0",),
        result=CompatibilityState.COMPATIBLE,
        reason_code="NO_ACTIVE_DOWNSTREAM_DEPENDENCY",
        evidence_strength=EvidenceStrength.DERIVED,
        explanation_template="No active downstream dependency is present in the supplied snapshot.",
    ),
    CompatibilityRule(
        rule_id="compatibility-rename-without-execution-evidence",
        operation=StructuralOperation.FIELD_RENAME.value,
        required_evidence=(
            "explicit_rename_mapping",
            "transformation_or_query_semantics",
            "execution_validation",
        ),
        inputs=("active_downstream_dependency=true", "explicit_adaptation_evidence=false"),
        result=CompatibilityState.UNKNOWN,
        reason_code="SOURCE_RENAME_SEMANTICS_UNKNOWN",
        evidence_strength=EvidenceStrength.INSUFFICIENT,
        explanation_template="The first consumer boundary has no certified rename-adaptation evidence.",
    ),
    CompatibilityRule(
        rule_id="compatibility-delete-active-dependency",
        operation=StructuralOperation.FIELD_DELETE.value,
        required_evidence=("certified_field_lineage", "certified_future_deletion"),
        inputs=("active_downstream_dependency=true", "certified_replacement=false"),
        result=CompatibilityState.INCOMPATIBLE,
        reason_code="SOURCE_FIELD_REMOVED_WITH_ACTIVE_DEPENDENCY",
        evidence_strength=EvidenceStrength.DERIVED,
        explanation_template="A certified current field dependency has no active future source field.",
    ),
    CompatibilityRule(
        rule_id="compatibility-type-documented-widening",
        operation=StructuralOperation.FIELD_TYPE_CHANGE.value,
        required_evidence=("current_type", "proposed_type", "documented_widening_rule"),
        inputs=("same_normalized_family=true", "documented_safe_widening=true"),
        result=CompatibilityState.CONDITIONALLY_COMPATIBLE,
        reason_code="DOCUMENTED_PRIMITIVE_TYPE_WIDENING",
        evidence_strength=EvidenceStrength.DERIVED,
        explanation_template="The primitive type change matches a documented widening rule.",
    ),
    CompatibilityRule(
        rule_id="compatibility-type-without-consumer-expectations",
        operation=StructuralOperation.FIELD_TYPE_CHANGE.value,
        required_evidence=(
            "downstream_expected_type",
            "cast_or_conversion_semantics",
            "contract_or_execution_validation",
        ),
        inputs=("active_downstream_dependency=true", "consumer_type_evidence=false"),
        result=CompatibilityState.UNKNOWN,
        reason_code="DOWNSTREAM_TYPE_EXPECTATIONS_UNKNOWN",
        evidence_strength=EvidenceStrength.INSUFFICIENT,
        explanation_template="The supplied snapshot does not certify downstream accepted types.",
    ),
)


def evaluate_root_compatibility(
    proposal: Proposal,
    *,
    current_native_type: str | None,
    current_normalized_type: str,
    has_dependencies: bool,
) -> CompatibilityRule:
    if not has_dependencies:
        return COMPATIBILITY_RULES[0]
    if proposal.operation is StructuralOperation.FIELD_RENAME:
        return COMPATIBILITY_RULES[1]
    if proposal.operation is StructuralOperation.FIELD_DELETE:
        return COMPATIBILITY_RULES[2]
    assert isinstance(proposal, FieldTypeChangeProposal)
    current_family = current_normalized_type.upper()
    future_family = proposal.proposed_normalized_type.upper()
    native_pair = (
        (current_native_type or "").upper(),
        proposal.proposed_native_type.upper(),
    )
    safe_widenings = {
        ("SMALLINT", "INTEGER"),
        ("INTEGER", "BIGINT"),
        ("REAL", "DOUBLE PRECISION"),
        ("FLOAT", "DOUBLE PRECISION"),
    }
    if current_family == future_family and native_pair in safe_widenings:
        return COMPATIBILITY_RULES[3]
    return COMPATIBILITY_RULES[4]
