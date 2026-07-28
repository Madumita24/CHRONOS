"""Explicit deterministic Phase 4.3 criticality, breadth, and severity rules."""

from __future__ import annotations

from collections.abc import Iterable

from .errors import SeverityCriticalityValidationError
from .models import (
    BreadthRule,
    ContextCriticality,
    CriticalityReasonCode,
    EvidenceCertainty,
    ExposureBreadth,
    SensitivityState,
    SeverityIfRealized,
    SeverityReasonCode,
    SeverityRule,
    SeverityRuleInputs,
    SeverityRuleResult,
    TechnicalConsequence,
)


_ALL_CERTAINTIES = tuple(EvidenceCertainty)
_ALL_BREADTH = tuple(ExposureBreadth)
_REALIZED_TECHNICAL = (
    TechnicalConsequence.UNRESOLVED_IMPACT,
    TechnicalConsequence.POTENTIAL_IMPACT,
)
_BROAD = (ExposureBreadth.BROAD, ExposureBreadth.WIDESPREAD)
_NARROW = (ExposureBreadth.LOCAL, ExposureBreadth.LIMITED)


DEFAULT_BREADTH_RULES = (
    BreadthRule(
        rule_id="breadth-widespread-multi-channel",
        precedence=10,
        minimum_datasets=10,
        minimum_consumer_assets=10,
        minimum_context_assets=10,
        result=ExposureBreadth.WIDESPREAD,
        description=(
            "Double-digit Dataset reach plus double-digit certified "
            "consumer assets is structurally widespread."
        ),
    ),
    BreadthRule(
        rule_id="breadth-broad-multi-dataset",
        precedence=20,
        minimum_datasets=2,
        minimum_consumer_assets=0,
        minimum_context_assets=1,
        result=ExposureBreadth.BROAD,
        description=(
            "Reach across multiple Datasets is structurally broad."
        ),
    ),
    BreadthRule(
        rule_id="breadth-broad-multi-consumer",
        precedence=21,
        minimum_datasets=1,
        minimum_consumer_assets=3,
        minimum_context_assets=3,
        result=ExposureBreadth.BROAD,
        description=(
            "One Dataset reaching at least three certified consumer assets "
            "has broad consumer breadth."
        ),
    ),
    BreadthRule(
        rule_id="breadth-limited-context",
        precedence=30,
        minimum_datasets=1,
        minimum_consumer_assets=0,
        minimum_context_assets=1,
        result=ExposureBreadth.LIMITED,
        description=(
            "A single Dataset with certified context has limited breadth."
        ),
    ),
    BreadthRule(
        rule_id="breadth-local",
        precedence=40,
        minimum_datasets=0,
        minimum_consumer_assets=0,
        minimum_context_assets=0,
        result=ExposureBreadth.LOCAL,
        description=(
            "A subject without certified contextual reach remains local."
        ),
    ),
)


DEFAULT_SEVERITY_RULES = (
    SeverityRule(
        rule_id="severity-no-demonstrated-impact",
        precedence=10,
        technical_conditions=(
            TechnicalConsequence.NO_DEMONSTRATED_IMPACT,
        ),
        criticality_conditions=tuple(ContextCriticality),
        breadth_conditions=_ALL_BREADTH,
        certainty_conditions=_ALL_CERTAINTIES,
        result=SeverityIfRealized.UNDETERMINED,
        description=(
            "Context alone cannot create severity when no technical "
            "consequence is demonstrated."
        ),
    ),
    SeverityRule(
        rule_id="severity-confirmed-explicit-critical-broad",
        precedence=20,
        technical_conditions=(TechnicalConsequence.CONFIRMED_IMPACT,),
        criticality_conditions=(
            ContextCriticality.EXPLICITLY_CRITICAL,
        ),
        breadth_conditions=_BROAD,
        certainty_conditions=_ALL_CERTAINTIES,
        result=SeverityIfRealized.CRITICAL,
        description=(
            "A confirmed consequence with explicit criticality and broad "
            "reach is critical if realized."
        ),
    ),
    SeverityRule(
        rule_id="severity-confirmed-explicit-critical-narrow",
        precedence=21,
        technical_conditions=(TechnicalConsequence.CONFIRMED_IMPACT,),
        criticality_conditions=(
            ContextCriticality.EXPLICITLY_CRITICAL,
        ),
        breadth_conditions=_NARROW,
        certainty_conditions=_ALL_CERTAINTIES,
        result=SeverityIfRealized.HIGH,
        description=(
            "A confirmed consequence with explicit criticality is high even "
            "when reach is narrow."
        ),
    ),
    SeverityRule(
        rule_id="severity-confirmed-elevated",
        precedence=22,
        technical_conditions=(TechnicalConsequence.CONFIRMED_IMPACT,),
        criticality_conditions=(ContextCriticality.ELEVATED_CONTEXT,),
        breadth_conditions=_ALL_BREADTH,
        certainty_conditions=_ALL_CERTAINTIES,
        result=SeverityIfRealized.HIGH,
        description=(
            "A confirmed consequence with combined consumer and contextual "
            "reach is high if realized."
        ),
    ),
    SeverityRule(
        rule_id="severity-confirmed-standard-or-unknown",
        precedence=23,
        technical_conditions=(TechnicalConsequence.CONFIRMED_IMPACT,),
        criticality_conditions=(
            ContextCriticality.STANDARD_CONTEXT,
            ContextCriticality.CRITICALITY_UNKNOWN,
        ),
        breadth_conditions=_ALL_BREADTH,
        certainty_conditions=_ALL_CERTAINTIES,
        result=SeverityIfRealized.MODERATE,
        description=(
            "A confirmed consequence without elevated or explicit "
            "criticality is moderate if realized."
        ),
    ),
    SeverityRule(
        rule_id="severity-unresolved-or-potential-explicit",
        precedence=30,
        technical_conditions=_REALIZED_TECHNICAL,
        criticality_conditions=(
            ContextCriticality.EXPLICITLY_CRITICAL,
        ),
        breadth_conditions=_ALL_BREADTH,
        certainty_conditions=_ALL_CERTAINTIES,
        result=SeverityIfRealized.HIGH,
        description=(
            "An unresolved or potential consequence connected to explicit "
            "criticality has high severity if it materializes."
        ),
    ),
    SeverityRule(
        rule_id="severity-unresolved-or-potential-elevated-broad",
        precedence=31,
        technical_conditions=_REALIZED_TECHNICAL,
        criticality_conditions=(ContextCriticality.ELEVATED_CONTEXT,),
        breadth_conditions=_BROAD,
        certainty_conditions=_ALL_CERTAINTIES,
        result=SeverityIfRealized.HIGH,
        description=(
            "An unresolved or potential consequence with elevated, broad "
            "context has high severity if it materializes."
        ),
    ),
    SeverityRule(
        rule_id="severity-unresolved-or-potential-elevated-narrow",
        precedence=32,
        technical_conditions=_REALIZED_TECHNICAL,
        criticality_conditions=(ContextCriticality.ELEVATED_CONTEXT,),
        breadth_conditions=_NARROW,
        certainty_conditions=_ALL_CERTAINTIES,
        result=SeverityIfRealized.MODERATE,
        description=(
            "Elevated but narrow unresolved or potential consequence is "
            "moderate if realized."
        ),
    ),
    SeverityRule(
        rule_id="severity-unresolved-or-potential-standard-broad",
        precedence=33,
        technical_conditions=_REALIZED_TECHNICAL,
        criticality_conditions=(
            ContextCriticality.STANDARD_CONTEXT,
            ContextCriticality.CRITICALITY_UNKNOWN,
        ),
        breadth_conditions=_BROAD,
        certainty_conditions=_ALL_CERTAINTIES,
        result=SeverityIfRealized.MODERATE,
        description=(
            "Broad reach without explicit or elevated criticality supports "
            "moderate severity if realized."
        ),
    ),
    SeverityRule(
        rule_id="severity-unresolved-or-potential-standard-narrow",
        precedence=34,
        technical_conditions=_REALIZED_TECHNICAL,
        criticality_conditions=(ContextCriticality.STANDARD_CONTEXT,),
        breadth_conditions=_NARROW,
        certainty_conditions=_ALL_CERTAINTIES,
        result=SeverityIfRealized.LOW,
        description=(
            "Standard narrow context supports low severity if an unresolved "
            "or potential consequence materializes."
        ),
    ),
    SeverityRule(
        rule_id="severity-unresolved-or-potential-unknown-narrow",
        precedence=35,
        technical_conditions=_REALIZED_TECHNICAL,
        criticality_conditions=(ContextCriticality.CRITICALITY_UNKNOWN,),
        breadth_conditions=_NARROW,
        certainty_conditions=_ALL_CERTAINTIES,
        result=SeverityIfRealized.UNDETERMINED,
        description=(
            "Narrow reach with unknown criticality cannot justify realized "
            "severity."
        ),
    ),
)


def derive_context_criticality(
    *,
    explicit_designation: bool,
    context_categories: Iterable[str],
    supporting_datasets: int,
    sensitivity_state: SensitivityState,
) -> tuple[ContextCriticality, tuple[CriticalityReasonCode, ...]]:
    categories = set(context_categories)
    reasons: list[CriticalityReasonCode] = []
    if explicit_designation:
        reasons.append(
            CriticalityReasonCode.EXPLICIT_CRITICALITY_METADATA
        )
        state = ContextCriticality.EXPLICITLY_CRITICAL
    elif not categories:
        reasons.extend(
            (
                CriticalityReasonCode.NO_EXPLICIT_CRITICALITY_METADATA,
                CriticalityReasonCode.CRITICALITY_EVIDENCE_INSUFFICIENT,
            )
        )
        state = ContextCriticality.CRITICALITY_UNKNOWN
    elif "bi" in categories and len(categories) >= 2:
        reasons.extend(
            (
                CriticalityReasonCode.CONSUMER_REACH_PRESENT,
                CriticalityReasonCode.BI_CONTEXT_PRESENT,
                CriticalityReasonCode.NO_EXPLICIT_CRITICALITY_METADATA,
            )
        )
        state = ContextCriticality.ELEVATED_CONTEXT
    else:
        reasons.append(
            CriticalityReasonCode.NO_EXPLICIT_CRITICALITY_METADATA
        )
        state = ContextCriticality.STANDARD_CONTEXT
    if supporting_datasets > 1:
        reasons.append(CriticalityReasonCode.MULTI_DATASET_CONTEXT)
    if "data_product" in categories:
        reasons.append(
            CriticalityReasonCode.DATA_PRODUCT_CONTEXT_PRESENT
        )
    if "pipeline" in categories:
        reasons.append(CriticalityReasonCode.PIPELINE_CONTEXT_PRESENT)
    if "bi" in categories and CriticalityReasonCode.BI_CONTEXT_PRESENT not in reasons:
        reasons.append(CriticalityReasonCode.BI_CONTEXT_PRESENT)
    if sensitivity_state is SensitivityState.PII:
        reasons.append(
            CriticalityReasonCode.SENSITIVITY_CLASSIFICATION_PRESENT
        )
    return state, tuple(dict.fromkeys(reasons))


def derive_breadth(
    *,
    supporting_datasets: int,
    consumer_assets: int,
    context_assets: int,
    rules: tuple[BreadthRule, ...] = DEFAULT_BREADTH_RULES,
) -> tuple[ExposureBreadth, str]:
    matching = tuple(
        rule
        for rule in rules
        if supporting_datasets >= rule.minimum_datasets
        and consumer_assets >= rule.minimum_consumer_assets
        and context_assets >= rule.minimum_context_assets
    )
    if not matching:
        raise SeverityCriticalityValidationError(
            "Breadth rule registry does not cover the recorded inputs."
        )
    minimum = min(item.precedence for item in matching)
    selected = tuple(
        item for item in matching if item.precedence == minimum
    )
    if len(selected) != 1:
        raise SeverityCriticalityValidationError(
            "Breadth rule precedence is ambiguous."
        )
    return selected[0].result, selected[0].rule_id


def derive_severity_if_realized(
    technical_consequence: TechnicalConsequence,
    context_criticality: ContextCriticality,
    exposure_breadth: ExposureBreadth,
    evidence_certainty: EvidenceCertainty,
    *,
    rules: tuple[SeverityRule, ...] = DEFAULT_SEVERITY_RULES,
) -> SeverityRuleResult:
    inputs = SeverityRuleInputs(
        technical_consequence=technical_consequence,
        context_criticality=context_criticality,
        exposure_breadth=exposure_breadth,
        evidence_certainty=evidence_certainty,
    )
    matching = tuple(
        rule
        for rule in rules
        if technical_consequence in rule.technical_conditions
        and context_criticality in rule.criticality_conditions
        and exposure_breadth in rule.breadth_conditions
        and evidence_certainty in rule.certainty_conditions
    )
    if not matching:
        raise SeverityCriticalityValidationError(
            "Severity rule registry does not cover the recorded inputs."
        )
    minimum = min(item.precedence for item in matching)
    selected = tuple(
        item for item in matching if item.precedence == minimum
    )
    if len(selected) != 1:
        raise SeverityCriticalityValidationError(
            "Severity rule precedence is ambiguous."
        )
    rule = selected[0]
    return SeverityRuleResult(
        rule_id=rule.rule_id,
        inputs=inputs,
        severity_if_realized=rule.result,
        reason_codes=_severity_reasons(inputs),
    )


def _severity_reasons(
    inputs: SeverityRuleInputs,
) -> tuple[SeverityReasonCode, ...]:
    reasons: list[SeverityReasonCode] = []
    if inputs.technical_consequence is TechnicalConsequence.CONFIRMED_IMPACT:
        reasons.append(
            SeverityReasonCode.CONFIRMED_TECHNICAL_FAILURE
        )
    elif (
        inputs.technical_consequence
        is TechnicalConsequence.UNRESOLVED_IMPACT
    ):
        reasons.append(
            SeverityReasonCode.UNRESOLVED_TECHNICAL_BOUNDARY
        )
    elif (
        inputs.technical_consequence
        is TechnicalConsequence.POTENTIAL_IMPACT
    ):
        reasons.append(
            SeverityReasonCode.POTENTIAL_DOWNSTREAM_CONSEQUENCE
        )
    else:
        reasons.append(
            SeverityReasonCode.NO_DEMONSTRATED_TECHNICAL_IMPACT
        )
    if inputs.context_criticality is ContextCriticality.EXPLICITLY_CRITICAL:
        reasons.append(SeverityReasonCode.EXPLICIT_CRITICAL_ASSET)
    else:
        reasons.append(SeverityReasonCode.CRITICALITY_NOT_EXPLICIT)
    if inputs.exposure_breadth in _BROAD:
        reasons.append(SeverityReasonCode.BROAD_CONSUMER_REACH)
    else:
        reasons.append(SeverityReasonCode.LIMITED_CONSUMER_REACH)
    if inputs.evidence_certainty is EvidenceCertainty.UNRESOLVED:
        reasons.append(SeverityReasonCode.CERTAINTY_UNRESOLVED)
    elif inputs.evidence_certainty is EvidenceCertainty.CONDITIONAL:
        reasons.append(SeverityReasonCode.CERTAINTY_CONDITIONAL)
    return tuple(reasons)
