"""Deterministic CHRONOS Phase 4.4 decision rules."""

from __future__ import annotations

from .errors import ImpactSynthesisValidationError
from .models import (
    DecisionCertainty,
    DecisionDisposition,
    DecisionReasonCode,
    DecisionRule,
    DecisionRuleInputs,
    DecisionRuleResult,
)
from chronos.severity_criticality import (
    ContextCriticality,
    EvidenceCertainty,
    ExposureBreadth,
    SeverityIfRealized,
    TechnicalConsequence,
)


_ALL_CRITICALITY = tuple(ContextCriticality)
_ALL_BREADTH = tuple(ExposureBreadth)
_MATERIAL = (SeverityIfRealized.HIGH, SeverityIfRealized.CRITICAL)
_LIMITED = (SeverityIfRealized.LOW, SeverityIfRealized.MODERATE)


DEFAULT_DECISION_RULES = (
    DecisionRule(
        rule_id="decision-block-confirmed-material-incompatibility",
        precedence=10,
        technical_consequence_conditions=(
            TechnicalConsequence.CONFIRMED_IMPACT,
        ),
        impact_certainty_conditions=(EvidenceCertainty.ESTABLISHED,),
        severity_if_realized_conditions=_MATERIAL,
        breadth_conditions=_ALL_BREADTH,
        criticality_conditions=_ALL_CRITICALITY,
        requires_explicit_conditions=None,
        resulting_disposition=(
            DecisionDisposition.BLOCK_CONFIRMED_INCOMPATIBILITY
        ),
        decision_certainty=DecisionCertainty.HIGH_CONFIDENCE,
        reason_codes=(
            DecisionReasonCode.CONFIRMED_INCOMPATIBILITY,
            DecisionReasonCode.MATERIAL_SEVERITY_IF_REALIZED,
        ),
        description=(
            "Established incompatibility with material confirmed "
            "consequence requires a block."
        ),
    ),
    DecisionRule(
        rule_id="decision-hold-unresolved-material-broad",
        precedence=20,
        technical_consequence_conditions=(
            TechnicalConsequence.UNRESOLVED_IMPACT,
        ),
        impact_certainty_conditions=(EvidenceCertainty.UNRESOLVED,),
        severity_if_realized_conditions=_MATERIAL,
        breadth_conditions=(
            ExposureBreadth.BROAD,
            ExposureBreadth.WIDESPREAD,
        ),
        criticality_conditions=_ALL_CRITICALITY,
        requires_explicit_conditions=None,
        resulting_disposition=DecisionDisposition.HOLD_FOR_REVIEW,
        decision_certainty=DecisionCertainty.HIGH_CONFIDENCE,
        reason_codes=(
            DecisionReasonCode.UNRESOLVED_SOURCE_COMPATIBILITY,
            DecisionReasonCode.MATERIAL_SEVERITY_IF_REALIZED,
            DecisionReasonCode.WIDESPREAD_DEPENDENCY_REACH,
            DecisionReasonCode.MISSING_EXECUTION_EVIDENCE,
        ),
        description=(
            "Unresolved compatibility with material potential consequence "
            "and broad reach requires review before approval."
        ),
    ),
    DecisionRule(
        rule_id="decision-proceed-with-explicit-conditions",
        precedence=30,
        technical_consequence_conditions=(
            TechnicalConsequence.POTENTIAL_IMPACT,
        ),
        impact_certainty_conditions=(EvidenceCertainty.CONDITIONAL,),
        severity_if_realized_conditions=_LIMITED,
        breadth_conditions=_ALL_BREADTH,
        criticality_conditions=_ALL_CRITICALITY,
        requires_explicit_conditions=True,
        resulting_disposition=(
            DecisionDisposition.PROCEED_WITH_CONDITIONS
        ),
        decision_certainty=DecisionCertainty.SUPPORTED,
        reason_codes=(
            DecisionReasonCode.CONDITIONAL_APPROVAL_REQUIREMENTS,
        ),
        description=(
            "A limited conditional consequence may proceed only when "
            "explicit, verifiable conditions are recorded."
        ),
    ),
    DecisionRule(
        rule_id="decision-proceed-no-demonstrated-impact",
        precedence=40,
        technical_consequence_conditions=(
            TechnicalConsequence.NO_DEMONSTRATED_IMPACT,
        ),
        impact_certainty_conditions=(EvidenceCertainty.ESTABLISHED,),
        severity_if_realized_conditions=tuple(SeverityIfRealized),
        breadth_conditions=_ALL_BREADTH,
        criticality_conditions=_ALL_CRITICALITY,
        requires_explicit_conditions=None,
        resulting_disposition=DecisionDisposition.PROCEED,
        decision_certainty=DecisionCertainty.HIGH_CONFIDENCE,
        reason_codes=(
            DecisionReasonCode.NO_DEMONSTRATED_TECHNICAL_IMPACT,
            DecisionReasonCode.ADEQUATE_COMPATIBILITY_EVIDENCE,
        ),
        description=(
            "Adequate evidence showing no demonstrated technical "
            "consequence supports proceeding regardless of context size."
        ),
    ),
)


def evaluate_decision(
    inputs: DecisionRuleInputs,
    *,
    rules: tuple[DecisionRule, ...] = DEFAULT_DECISION_RULES,
) -> DecisionRuleResult:
    """Select exactly one highest-precedence matching rule."""
    matches = tuple(rule for rule in rules if _matches(rule, inputs))
    if not matches:
        raise ImpactSynthesisValidationError(
            "No decision rule matches the supplied evidence."
        )
    best_precedence = min(rule.precedence for rule in matches)
    winners = tuple(
        rule for rule in matches if rule.precedence == best_precedence
    )
    if len(winners) != 1:
        raise ImpactSynthesisValidationError(
            "Equal-precedence decision rules conflict."
        )
    rule = winners[0]
    return DecisionRuleResult(
        rule_id=rule.rule_id,
        inputs=inputs,
        disposition=rule.resulting_disposition,
        decision_certainty=rule.decision_certainty,
        reason_codes=rule.reason_codes,
    )


def _matches(rule: DecisionRule, inputs: DecisionRuleInputs) -> bool:
    condition_match = (
        inputs.technical_consequence
        in rule.technical_consequence_conditions
        and inputs.impact_certainty
        in rule.impact_certainty_conditions
        and inputs.severity_if_realized
        in rule.severity_if_realized_conditions
        and inputs.breadth in rule.breadth_conditions
        and inputs.criticality in rule.criticality_conditions
    )
    explicit_match = (
        rule.requires_explicit_conditions is None
        or rule.requires_explicit_conditions
        == inputs.has_explicit_conditions
    )
    return condition_match and explicit_match
