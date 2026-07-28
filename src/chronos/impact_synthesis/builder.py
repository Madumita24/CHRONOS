"""Offline deterministic CHRONOS Phase 4.4 impact synthesis."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from chronos.business_context import (
    BusinessContextPropagation,
    ContextAssetRecord,
    ContextAssetType,
    ContextCategory,
    load_business_context,
    validate_business_context,
)
from chronos.change_semantics import load_contract
from chronos.compatibility_evaluation import (
    load_compatibility_evaluation,
    validate_compatibility_evaluation,
)
from chronos.counterfactual_source import (
    InputArtifactHash,
    load_source_state,
    validate_counterfactual_source_state,
)
from chronos.dependency_propagation import (
    load_dependency_propagation,
    validate_dependency_propagation,
)
from chronos.explanations import (
    ExplanationBundle,
    load_explanation_bundle,
    validate_explanation_bundle,
)
from chronos.future_graph import (
    load_future_graph,
    validate_future_metadata_graph,
)
from chronos.phase2_certification import (
    Phase2CertificationState,
    load_certification,
)
from chronos.phase3_certification import (
    Phase3CertificationResult,
    Phase3CertificationStatus,
    load_phase3_certification,
    phase3_certification_semantic_fingerprint,
    validate_phase3_certification,
)
from chronos.proposal import ChangeType, load_proposal
from chronos.proposal_validation import load_validation_result
from chronos.severity_criticality import (
    SeverityCriticalityAnalysis,
    SeverityCriticalityValidationState,
    load_severity_analysis,
    derive_severity_if_realized,
    validate_severity_criticality,
)
from chronos.snapshot import (
    FieldMachineKey,
    SnapshotValidationState,
    load_snapshot,
)
from chronos.technical_impact import (
    TechnicalImpactAnalysis,
    load_technical_impact,
    validate_technical_impact,
)

from .errors import (
    ImpactSynthesisEntryError,
    ImpactSynthesisValidationError,
)
from .models import (
    IMPACT_SYNTHESIS_SCHEMA_VERSION,
    BlockingQuestion,
    BlockingQuestionResolutionState,
    ChangeReviewAssessment,
    ContextHighlight,
    ContextHighlightKind,
    DecisionEvidence,
    DecisionEvidenceType,
    DecisionReason,
    DecisionReasonCode,
    DecisionRuleInputs,
    ImpactSynthesis,
    ImpactSynthesisSummary,
    ImpactSynthesisValidationState,
    RepresentativeEvidencePath,
    RepresentativePathKind,
    RequiredEvidence,
    RequiredEvidenceState,
)
from .rules import DEFAULT_DECISION_RULES, evaluate_decision


Clock = Callable[[], datetime]
_CAUSE_ID = "technical-impact-cause-source-rename-semantics"
_PROPOSAL_ID = "CHRONOS-DEMO-001-PROPOSAL-001"
_NAMES = (
    "current_metadata_snapshot.json",
    "change_proposal.json",
    "change_proposal_validation.json",
    "change_semantic_contract.json",
    "phase_2_certification.json",
    "counterfactual_source_state.json",
    "future_metadata_graph.json",
    "dependency_propagation.json",
    "compatibility_evaluation.json",
    "explanation_bundle.json",
    "phase_3_certification.json",
    "technical_impact_analysis.json",
    "business_context_propagation.json",
    "severity_criticality_analysis.json",
)


@dataclass(frozen=True)
class _Components:
    scope: ImpactSynthesisSummary
    evidence: tuple[DecisionEvidence, ...]
    reasons: tuple[DecisionReason, ...]
    required: tuple[RequiredEvidence, ...]
    questions: tuple[BlockingQuestion, ...]
    paths: tuple[RepresentativeEvidencePath, ...]
    highlights: tuple[ContextHighlight, ...]
    profile: DecisionRuleInputs
    narrative: str
    known: tuple[str, ...]
    unknown: tuple[str, ...]
    warnings: tuple[str, ...]


def synthesize_impact(
    phase3: Phase3CertificationResult,
    technical: TechnicalImpactAnalysis,
    context: BusinessContextPropagation,
    severity: SeverityCriticalityAnalysis,
    explanations: ExplanationBundle,
    *,
    input_artifact_hashes: tuple[InputArtifactHash, ...],
    clock: Clock | None = None,
) -> ImpactSynthesis:
    """Create one assessment from already-materialized predecessor state."""
    _require_high_level_entry(
        phase3, technical, context, severity, explanations,
        input_artifact_hashes,
    )
    components = _derive_components(
        phase3, technical, context, severity, explanations
    )
    selected = evaluate_decision(components.profile)
    reason_ids = tuple(item.reason_id for item in components.reasons)
    question_ids = tuple(item.question_id for item in components.questions)
    required_ids = tuple(
        item.required_evidence_id for item in components.required
    )
    assessment = ChangeReviewAssessment(
        disposition=selected.disposition,
        decision_certainty=selected.decision_certainty,
        technical_consequence=components.profile.technical_consequence,
        impact_certainty=components.profile.impact_certainty,
        criticality=components.profile.criticality,
        breadth=components.profile.breadth,
        severity_if_realized=components.profile.severity_if_realized,
        root_cause_ids=tuple(
            item.cause_id for item in technical.technical_impact_causes
        ),
        decision_rule_id=selected.rule_id,
        selected_rule_inputs=selected.inputs,
        decision_reason_ids=reason_ids,
        blocking_question_ids=question_ids,
        required_evidence_ids=required_ids,
        scope_summary=components.scope,
        narrative=_narrative(
            selected.disposition.value,
            selected.decision_certainty.value,
            components,
        ),
    )
    result = ImpactSynthesis(
        schema_version=IMPACT_SYNTHESIS_SCHEMA_VERSION,
        demonstration_id=technical.demonstration_id,
        proposal_id=technical.proposal_id,
        operation="field_rename",
        phase_3_certification_fingerprint=phase3.semantic_fingerprint,
        technical_impact_fingerprint=technical.semantic_fingerprint,
        business_context_fingerprint=context.semantic_fingerprint,
        severity_criticality_fingerprint=severity.semantic_fingerprint,
        source_change=technical.source_change,
        root_causes=assessment.root_cause_ids,
        decision_rule_registry=DEFAULT_DECISION_RULES,
        decision_evidence=components.evidence,
        decision_reasons=components.reasons,
        blocking_questions=components.questions,
        required_evidence=components.required,
        representative_evidence_paths=components.paths,
        context_highlights=components.highlights,
        scope_summary=components.scope,
        change_severity_profile=components.profile,
        decision_disposition=selected.disposition,
        decision_certainty=selected.decision_certainty,
        decision_rule_id=selected.rule_id,
        decision_reason_codes=selected.reason_codes,
        assessment=assessment,
        what_we_know=components.known,
        what_we_do_not_know=components.unknown,
        warnings=components.warnings,
        input_artifact_hashes=input_artifact_hashes,
        created_at=_timestamp(clock),
        validation_state=ImpactSynthesisValidationState.VALID,
    )
    validate_impact_synthesis(
        result, phase3, technical, context, severity, explanations
    )
    return result


def synthesize_impact_from_artifacts(
    snapshot_path: str | Path,
    proposal_path: str | Path,
    validation_path: str | Path,
    contract_path: str | Path,
    phase2_path: str | Path,
    source_state_path: str | Path,
    graph_path: str | Path,
    propagation_path: str | Path,
    compatibility_path: str | Path,
    explanations_path: str | Path,
    phase3_path: str | Path,
    technical_path: str | Path,
    context_path: str | Path,
    severity_path: str | Path,
    *,
    clock: Clock | None = None,
) -> ImpactSynthesis:
    """Load, validate, hash, and synthesize the fourteen local inputs."""
    supplied = (
        snapshot_path,
        proposal_path,
        validation_path,
        contract_path,
        phase2_path,
        source_state_path,
        graph_path,
        propagation_path,
        compatibility_path,
        explanations_path,
        phase3_path,
        technical_path,
        context_path,
        severity_path,
    )
    paths = tuple(
        (name, Path(path)) for name, path in zip(_NAMES, supplied)
    )
    before = {name: _file_hash(path) for name, path in paths}
    snapshot = load_snapshot(snapshot_path)
    proposal = load_proposal(proposal_path)
    validation = load_validation_result(validation_path)
    contract = load_contract(contract_path)
    phase2 = load_certification(phase2_path)
    source = load_source_state(source_state_path)
    graph = load_future_graph(graph_path)
    propagation = load_dependency_propagation(propagation_path)
    compatibility = load_compatibility_evaluation(compatibility_path)
    explanations = load_explanation_bundle(explanations_path)
    phase3 = load_phase3_certification(phase3_path)
    technical = load_technical_impact(technical_path)
    context = load_business_context(context_path)
    severity = load_severity_analysis(severity_path)
    after_load = {name: _file_hash(path) for name, path in paths}
    hashes = tuple(
        InputArtifactHash(name, before[name], after_load[name])
        for name, _ in paths
    )
    try:
        validate_phase3_certification(phase3)
        validate_counterfactual_source_state(
            source, snapshot, proposal, validation, contract, phase2
        )
        validate_future_metadata_graph(
            graph, snapshot, proposal, validation, contract, phase2, source
        )
        validate_dependency_propagation(propagation, graph)
        validate_compatibility_evaluation(
            compatibility, graph, propagation
        )
        validate_explanation_bundle(
            explanations,
            snapshot,
            source,
            graph,
            propagation,
            compatibility,
        )
        validate_technical_impact(
            technical,
            source,
            graph,
            propagation,
            compatibility,
            explanations,
            phase3,
        )
        validate_business_context(
            context, snapshot, graph, technical, phase3
        )
        validate_severity_criticality(
            severity, snapshot, graph, technical, context, phase3
        )
    except ValueError as exc:
        raise ImpactSynthesisEntryError(
            "Certified Phase 4.4 entry validation failed."
        ) from exc
    if (
        snapshot.validation_result.state is not SnapshotValidationState.VALID
        or phase2.certification_state
        is not Phase2CertificationState.CERTIFIED
        or phase3.certification_status
        is not Phase3CertificationStatus.CERTIFIED
        or proposal.change_type is not ChangeType.FIELD_RENAME
        or proposal.demonstration_id != "CHRONOS-DEMO-001"
        or proposal.proposal_id != _PROPOSAL_ID
    ):
        raise ImpactSynthesisEntryError(
            "Required certification or canonical identity is invalid."
        )
    _validate_physical_closure(
        hashes, phase3, technical, context, severity
    )
    result = synthesize_impact(
        phase3,
        technical,
        context,
        severity,
        explanations,
        input_artifact_hashes=hashes,
        clock=clock,
    )
    if {name: _file_hash(path) for name, path in paths} != before:
        raise ImpactSynthesisValidationError(
            "An authoritative input changed during impact synthesis."
        )
    return result


def validate_impact_synthesis(
    result: ImpactSynthesis,
    phase3: Phase3CertificationResult,
    technical: TechnicalImpactAnalysis,
    context: BusinessContextPropagation,
    severity: SeverityCriticalityAnalysis,
    explanations: ExplanationBundle,
) -> None:
    """Fail closed unless the assessment reproduces from predecessors."""
    issues: list[str] = []

    def require(condition: bool, message: str) -> None:
        if not condition:
            issues.append(message)

    require(
        result.phase_3_certification_fingerprint
        == phase3.semantic_fingerprint,
        "Phase 3 certification fingerprint mismatch",
    )
    require(
        result.technical_impact_fingerprint
        == technical.semantic_fingerprint,
        "Phase 4.1 fingerprint mismatch",
    )
    require(
        result.business_context_fingerprint
        == context.semantic_fingerprint,
        "Phase 4.2 fingerprint mismatch",
    )
    require(
        result.severity_criticality_fingerprint
        == severity.semantic_fingerprint,
        "Phase 4.3 fingerprint mismatch",
    )
    require(
        result.source_change == technical.source_change,
        "Source transition mismatch",
    )
    expected = _derive_components(
        phase3, technical, context, severity, explanations
    )
    for actual, wanted, label in (
        (result.scope_summary, expected.scope, "scope"),
        (result.decision_evidence, expected.evidence, "evidence"),
        (result.decision_reasons, expected.reasons, "reasons"),
        (result.required_evidence, expected.required, "required evidence"),
        (result.blocking_questions, expected.questions, "questions"),
        (
            result.representative_evidence_paths,
            expected.paths,
            "representative paths",
        ),
        (result.context_highlights, expected.highlights, "highlights"),
        (result.change_severity_profile, expected.profile, "profile"),
        (result.what_we_know, expected.known, "known facts"),
        (result.what_we_do_not_know, expected.unknown, "unknown facts"),
    ):
        require(actual == wanted, f"Derived {label} mismatch")
    selected = evaluate_decision(
        result.change_severity_profile,
        rules=result.decision_rule_registry,
    )
    require(
        result.decision_rule_registry == DEFAULT_DECISION_RULES,
        "Decision rule registry mismatch",
    )
    require(
        selected.rule_id == result.decision_rule_id
        and selected.disposition is result.decision_disposition
        and selected.decision_certainty is result.decision_certainty
        and selected.reason_codes == result.decision_reason_codes,
        "Selected rule is not reproducible",
    )
    require(
        result.assessment.narrative
        == _narrative(
            selected.disposition.value,
            selected.decision_certainty.value,
            expected,
        ),
        "Narrative is not derived from typed evidence",
    )
    require(
        result.root_causes == (_CAUSE_ID,),
        "Root technical cause was not preserved",
    )
    require(
        all(item.unchanged for item in result.input_artifact_hashes)
        and tuple(
            item.artifact_name for item in result.input_artifact_hashes
        )
        == _NAMES,
        "Input immutability closure is invalid",
    )
    serialized = result.to_json().lower()
    forbidden = (
        "auto_deploy",
        "auto_fix",
        "auto_rollback",
        "sql patch",
        "spark patch",
        "dbt patch",
        "migration plan",
        "repair proposal",
        "remediation order",
        "notification priority",
        "failure probability",
        "risk score",
        "expected loss",
    )
    require(
        not any(term in serialized for term in forbidden),
        "Unsupported repair, workflow, probability, or score introduced",
    )
    if issues:
        raise ImpactSynthesisValidationError("; ".join(issues))


def _require_high_level_entry(
    phase3: Phase3CertificationResult,
    technical: TechnicalImpactAnalysis,
    context: BusinessContextPropagation,
    severity: SeverityCriticalityAnalysis,
    explanations: ExplanationBundle,
    hashes: tuple[InputArtifactHash, ...],
) -> None:
    if (
        phase3.certification_status
        is not Phase3CertificationStatus.CERTIFIED
        or phase3_certification_semantic_fingerprint(phase3)
        != phase3.semantic_fingerprint
        or technical.validation_state.value != "valid"
        or context.validation_state.value != "valid"
        or severity.validation_state
        is not SeverityCriticalityValidationState.VALID
        or technical.phase_3_certification_fingerprint
        != phase3.semantic_fingerprint
        or context.phase_3_certification_fingerprint
        != phase3.semantic_fingerprint
        or severity.phase_3_certification_fingerprint
        != phase3.semantic_fingerprint
        or context.technical_impact_fingerprint
        != technical.semantic_fingerprint
        or severity.technical_impact_fingerprint
        != technical.semantic_fingerprint
        or severity.business_context_fingerprint
        != context.semantic_fingerprint
        or technical.demonstration_id != "CHRONOS-DEMO-001"
        or technical.proposal_id != _PROPOSAL_ID
        or context.demonstration_id != technical.demonstration_id
        or context.proposal_id != technical.proposal_id
        or severity.demonstration_id != technical.demonstration_id
        or severity.proposal_id != technical.proposal_id
        or explanations.demonstration_id != technical.demonstration_id
    ):
        raise ImpactSynthesisEntryError(
            "A predecessor validation, fingerprint, or identity is invalid."
        )
    profile = severity.change_level_profile
    metrics = technical.aggregate_metrics
    context_metrics = context.aggregate_metrics
    causes = tuple(
        item.cause_id for item in technical.technical_impact_causes
    )
    if (
        causes != (_CAUSE_ID,)
        or profile.root_cause_ids != (_CAUSE_ID,)
        or metrics.confirmed_impacted_fields != 0
        or metrics.unresolved_fields != 25
        or metrics.unresolved_paths != 48
        or metrics.downstream_dataset_summaries != 20
        or context_metrics.total_unique_context_assets != 66
        or context_metrics.scoped_context_relationships != 211
        or context_metrics.total_technical_to_context_mappings != 257
        or len(hashes) != len(_NAMES)
        or tuple(item.artifact_name for item in hashes) != _NAMES
        or any(not item.unchanged for item in hashes)
    ):
        raise ImpactSynthesisEntryError(
            "Certified technical, context, severity, or hash scope mismatch."
        )
    criticality = next(
        (
            item
            for item in severity.criticality_evidence
            if item.evidence_id == profile.criticality_evidence_id
        ),
        None,
    )
    breadth = next(
        (
            item
            for item in severity.breadth_metrics
            if item.breadth_metrics_id == profile.breadth_metrics_id
        ),
        None,
    )
    try:
        reproduced_severity = derive_severity_if_realized(
            profile.technical_consequence,
            profile.context_criticality,
            profile.exposure_breadth,
            profile.evidence_certainty,
            rules=severity.severity_rule_registry,
        )
    except ValueError as exc:
        raise ImpactSynthesisEntryError(
            "Phase 4.3 decision inputs are not reproducible."
        ) from exc
    if (
        criticality is None
        or criticality.criticality is not profile.context_criticality
        or breadth is None
        or breadth.exposure_breadth is not profile.exposure_breadth
        or reproduced_severity.rule_id != profile.severity_rule_id
        or reproduced_severity.severity_if_realized
        is not profile.severity_if_realized
        or reproduced_severity.inputs != profile.severity_rule_inputs
    ):
        raise ImpactSynthesisEntryError(
            "Phase 4.3 profile semantics are internally inconsistent."
        )


def _derive_components(
    phase3: Phase3CertificationResult,
    technical: TechnicalImpactAnalysis,
    context: BusinessContextPropagation,
    severity: SeverityCriticalityAnalysis,
    explanations: ExplanationBundle,
) -> _Components:
    profile = severity.change_level_profile
    metrics = technical.aggregate_metrics
    context_metrics = context.aggregate_metrics
    scope = ImpactSynthesisSummary(
        changed_source_fields=1,
        technical_root_causes=len(technical.technical_impact_causes),
        confirmed_downstream_failures=metrics.confirmed_impacted_fields,
        potential_downstream_fields=metrics.potential_impacted_fields,
        unresolved_downstream_fields=metrics.unresolved_fields,
        no_demonstrated_impact_fields=(
            metrics.no_demonstrated_impact_fields
        ),
        downstream_datasets=metrics.downstream_dataset_summaries,
        technical_relationships=len(technical.relationship_impacts),
        unresolved_relationships=metrics.unresolved_relationships,
        dependency_paths=len(technical.path_impacts),
        unresolved_paths=metrics.unresolved_paths,
        context_assets=context_metrics.total_unique_context_assets,
        context_relationships=(
            context_metrics.scoped_context_relationships
        ),
        field_to_context_mappings=(
            context_metrics.total_technical_to_context_mappings
        ),
        breadth=profile.exposure_breadth,
        criticality=profile.context_criticality,
        severity_if_realized=profile.severity_if_realized,
        technical_certainty=profile.evidence_certainty,
        downstream_field_keys=tuple(
            sorted(
                (item.field_key for item in technical.field_impacts),
                key=_field_key,
            )
        ),
        downstream_dataset_urns=tuple(
            sorted(item.dataset_urn for item in technical.dataset_summaries)
        ),
        technical_relationship_ids=tuple(
            sorted(
                item.relationship_id
                for item in technical.relationship_impacts
            )
        ),
        dependency_path_ids=tuple(
            sorted(item.path_id for item in technical.path_impacts)
        ),
        context_asset_ids=tuple(
            sorted(item.asset_id for item in context.context_asset_registry)
        ),
    )
    rule_inputs = DecisionRuleInputs(
        technical_consequence=profile.technical_consequence,
        impact_certainty=profile.evidence_certainty,
        severity_if_realized=profile.severity_if_realized,
        breadth=profile.exposure_breadth,
        criticality=profile.context_criticality,
        has_explicit_conditions=False,
    )
    evidence = _decision_evidence(
        phase3, technical, context, severity, explanations
    )
    selected = evaluate_decision(rule_inputs)
    reasons = _decision_reasons(selected.reason_codes)
    required = _required_evidence(explanations)
    questions = _blocking_questions(
        technical, explanations, required, selected.disposition.value
    )
    paths = _representative_paths(technical, context)
    highlights = _context_highlights(severity, context)
    known = (
        "The certified proposal renames the PostgreSQL orders field "
        "order_total to order_amount.",
        f"{metrics.unresolved_fields} downstream fields depend on the "
        "source boundary.",
        f"{metrics.downstream_dataset_summaries} downstream Datasets are "
        "in the technical cone.",
        f"{metrics.unresolved_paths} modeled dependency paths remain "
        "unresolved.",
        "Captured metadata is insufficient to establish source-boundary "
        "compatibility.",
        f"Dependency reach is {profile.exposure_breadth.value}.",
        "The potential consequence is "
        f"{profile.severity_if_realized.value} if the unresolved technical "
        "condition materializes.",
    )
    unknown = (
        "Whether the Spark export accepts PostgreSQL orders.order_amount.",
        "Whether the pipeline adapts the renamed source field.",
        "Whether execution would succeed after the proposed rename.",
    )
    warnings = (
        "Explicit business-criticality metadata is absent; "
        "ELEVATED_CONTEXT is derived from certified connected context.",
        "WIDESPREAD describes reach only and is not independently a block.",
        "HIGH is severity if realized, not probability or confirmed impact.",
    )
    return _Components(
        scope=scope,
        evidence=evidence,
        reasons=reasons,
        required=required,
        questions=questions,
        paths=paths,
        highlights=highlights,
        profile=rule_inputs,
        narrative="",
        known=known,
        unknown=unknown,
        warnings=warnings,
    )


def _decision_evidence(
    phase3: Phase3CertificationResult,
    technical: TechnicalImpactAnalysis,
    context: BusinessContextPropagation,
    severity: SeverityCriticalityAnalysis,
    explanations: ExplanationBundle,
) -> tuple[DecisionEvidence, ...]:
    cause_ids = tuple(
        item.cause_id for item in technical.technical_impact_causes
    )
    uncertainty_ids = tuple(
        item.uncertainty_id for item in explanations.uncertainties
    )
    return (
        DecisionEvidence(
            "decision-evidence-technical-scope",
            DecisionEvidenceType.TECHNICAL_FINDING,
            "technical_impact_analysis.json",
            technical.semantic_fingerprint,
            cause_ids
            + tuple(
                sorted(
                    item.path_id for item in technical.path_impacts
                )
            ),
            "One unresolved source boundary reaches 25 downstream fields "
            "across 20 Datasets and 48 modeled paths; no downstream "
            "failure is confirmed.",
        ),
        DecisionEvidence(
            "decision-evidence-context-scope",
            DecisionEvidenceType.BUSINESS_CONTEXT,
            "business_context_propagation.json",
            context.semantic_fingerprint,
            tuple(
                sorted(
                    item.asset_id
                    for item in context.context_asset_registry
                )
            ),
            "Sixty-six context assets are connected to the unresolved "
            "technical cone through 211 scoped context relationships.",
        ),
        DecisionEvidence(
            "decision-evidence-severity-profile",
            DecisionEvidenceType.SEVERITY_PROFILE,
            "severity_criticality_analysis.json",
            severity.semantic_fingerprint,
            (severity.change_level_profile.subject_id,),
            "The certified profile is unresolved, widespread, elevated "
            "context, with high severity if realized.",
        ),
        DecisionEvidence(
            "decision-evidence-compatibility-gap",
            DecisionEvidenceType.EXPLANATION_EVIDENCE,
            "explanation_bundle.json",
            explanations.semantic_fingerprint,
            uncertainty_ids,
            "Captured evidence does not establish whether the first Spark "
            "export boundary accepts or adapts to the renamed field.",
        ),
        DecisionEvidence(
            "decision-evidence-certification",
            DecisionEvidenceType.COMPATIBILITY_EVIDENCE,
            "phase_3_certification.json",
            phase3.semantic_fingerprint,
            tuple(
                item.check_id for item in phase3.certification_checks
            ),
            "Phase 3 certified the compatibility and explanation evidence "
            "used by the Phase 4 analyses.",
        ),
    )


def _decision_reasons(
    reason_codes: tuple[DecisionReasonCode, ...],
) -> tuple[DecisionReason, ...]:
    definitions = {
        DecisionReasonCode.UNRESOLVED_SOURCE_COMPATIBILITY: (
            "The first downstream Spark boundary remains unresolved.",
            (
                "decision-evidence-technical-scope",
                "decision-evidence-compatibility-gap",
            ),
        ),
        DecisionReasonCode.MATERIAL_SEVERITY_IF_REALIZED: (
            "The potential consequence is high if the unresolved "
            "condition materializes.",
            ("decision-evidence-severity-profile",),
        ),
        DecisionReasonCode.WIDESPREAD_DEPENDENCY_REACH: (
            "The unresolved boundary feeds a widespread dependency cone.",
            (
                "decision-evidence-technical-scope",
                "decision-evidence-context-scope",
            ),
        ),
        DecisionReasonCode.MISSING_EXECUTION_EVIDENCE: (
            "Execution and mapping evidence required to resolve the "
            "boundary is absent.",
            ("decision-evidence-compatibility-gap",),
        ),
        DecisionReasonCode.CONFIRMED_INCOMPATIBILITY: (
            "Certified evidence establishes an incompatible dependency.",
            ("decision-evidence-technical-scope",),
        ),
        DecisionReasonCode.NO_DEMONSTRATED_TECHNICAL_IMPACT: (
            "Certified evidence demonstrates no technical consequence.",
            ("decision-evidence-technical-scope",),
        ),
        DecisionReasonCode.ADEQUATE_COMPATIBILITY_EVIDENCE: (
            "Compatibility evidence is adequate for the conclusion.",
            ("decision-evidence-certification",),
        ),
        DecisionReasonCode.CONDITIONAL_APPROVAL_REQUIREMENTS: (
            "Proceeding is supported only under explicit verifiable "
            "conditions.",
            ("decision-evidence-technical-scope",),
        ),
    }
    return tuple(
        DecisionReason(
            reason_id=f"decision-reason-{code.value}",
            reason_code=code,
            statement=definitions[code][0],
            evidence_ids=definitions[code][1],
        )
        for code in reason_codes
    )


def _required_evidence(
    explanations: ExplanationBundle,
) -> tuple[RequiredEvidence, ...]:
    records: list[RequiredEvidence] = []
    for uncertainty in sorted(
        explanations.uncertainties, key=lambda item: item.uncertainty_id
    ):
        for evidence_class in sorted(uncertainty.missing_evidence_types):
            records.append(
                RequiredEvidence(
                    required_evidence_id=(
                        "required-evidence-" + evidence_class.replace("_", "-")
                    ),
                    evidence_class=evidence_class,
                    subject=uncertainty.subject,
                    reason=(
                        "Required to determine whether the unresolved "
                        "source boundary is compatible or incompatible."
                    ),
                    state=(
                        RequiredEvidenceState
                        .REQUIRED_FOR_DECISION_RESOLUTION
                    ),
                    source_uncertainty_id=uncertainty.uncertainty_id,
                )
            )
    return tuple(records)


def _blocking_questions(
    technical: TechnicalImpactAnalysis,
    explanations: ExplanationBundle,
    required: tuple[RequiredEvidence, ...],
    disposition: str,
) -> tuple[BlockingQuestion, ...]:
    if disposition != "hold_for_review":
        return ()
    uncertainty = explanations.uncertainties[0]
    cause = technical.technical_impact_causes[0]
    return (
        BlockingQuestion(
            question_id="blocking-question-spark-export-rename-compatibility",
            question=(
                "Does the Spark export mapping accept or adapt to "
                "PostgreSQL orders.order_amount after order_total is "
                "renamed?"
            ),
            subject=uncertainty.subject,
            reason=uncertainty.human_explanation,
            root_cause_id=cause.cause_id,
            affected_field_keys=tuple(
                sorted(uncertainty.affected_field_keys, key=_field_key)
            ),
            affected_dataset_urns=tuple(
                sorted(
                    {
                        item.dataset_urn
                        for item in uncertainty.affected_field_keys
                    }
                )
            ),
            affected_path_ids=tuple(
                sorted(uncertainty.affected_path_ids)
            ),
            required_evidence_ids=tuple(
                item.required_evidence_id for item in required
            ),
            resolution_state=BlockingQuestionResolutionState.UNRESOLVED,
        ),
    )


def _representative_paths(
    technical: TechnicalImpactAnalysis,
    context: BusinessContextPropagation,
) -> tuple[RepresentativeEvidencePath, ...]:
    paths = sorted(
        technical.path_impacts, key=lambda item: (item.depth, item.path_id)
    )
    short = paths[0]
    deep = sorted(
        paths, key=lambda item: (-item.depth, item.path_id)
    )[0]
    fields = {
        item.field_key: item for item in technical.field_impacts
    }
    multipath_candidates = tuple(
        path
        for path in paths
        if fields[path.target_field].path_count > 1
        and path.path_id not in {short.path_id, deep.path_id}
    )
    multipath = multipath_candidates[0]
    selected = (
        (RepresentativePathKind.SHORT, short),
        (RepresentativePathKind.DEEP, deep),
        (RepresentativePathKind.MULTIPATH, multipath),
    )
    root_relationship = technical.technical_impact_causes[
        0
    ].root_relationship_id
    result: list[RepresentativeEvidencePath] = []
    for kind, path in selected:
        mappings = sorted(
            (
                item
                for item in context.technical_to_context_mappings
                if item.technical_field_key == path.target_field
                and path.path_id in item.supporting_path_ids
            ),
            key=lambda item: (
                _context_rank(item.context_category),
                item.context_asset_id,
                item.mapping_id,
            ),
        )
        if not mappings:
            mappings = sorted(
                (
                    item
                    for item in context.technical_to_context_mappings
                    if item.technical_field_key == path.target_field
                ),
                key=lambda item: (
                    _context_rank(item.context_category),
                    item.context_asset_id,
                    item.mapping_id,
                ),
            )
        mapping = mappings[0]
        result.append(
            RepresentativeEvidencePath(
                representative_path_id=(
                    f"representative-path-{kind.value}"
                ),
                kind=kind,
                technical_path_id=path.path_id,
                source_field=technical.source_change.candidate_field,
                unresolved_boundary_relationship_id=root_relationship,
                ordered_relationship_ids=path.ordered_relationship_ids,
                downstream_field=path.target_field,
                downstream_dataset_urn=path.target_field.dataset_urn,
                context_mapping_id=mapping.mapping_id,
                context_asset_id=mapping.context_asset_id,
                explanation=(
                    f"Representative {kind.value} path from the renamed "
                    "source through the unresolved boundary to a downstream "
                    "field, Dataset, and connected context asset."
                ),
            )
        )
    return tuple(result)


def _context_highlights(
    severity: SeverityCriticalityAnalysis,
    context: BusinessContextPropagation,
) -> tuple[ContextHighlight, ...]:
    assets = tuple(context.context_asset_registry)
    dataset_ids = tuple(
        item.dataset_urn
        for item in sorted(
            severity.dataset_assessments,
            key=lambda item: (
                _severity_rank(item.severity_if_realized.value),
                item.dataset_urn,
            ),
        )[:3]
    )
    highlights: list[ContextHighlight] = [
        ContextHighlight(
            highlight_id=f"context-highlight-dataset-{index}",
            kind=ContextHighlightKind.TECHNICAL_DATASET,
            subject_id=dataset,
            display_name=None,
            selection_basis=(
                "First three Datasets by severity-if-realized rank, then "
                "Dataset URN."
            ),
            supporting_dataset_urns=(dataset,),
            supporting_field_keys=tuple(
                sorted(
                    (
                        item.field_key
                        for item in severity.field_assessments
                        if item.dataset_urn == dataset
                    ),
                    key=_field_key,
                )
            ),
        )
        for index, dataset in enumerate(dataset_ids, start=1)
    ]
    groups = (
        (
            ContextHighlightKind.BI_CONSUMER,
            lambda asset: asset.category is ContextCategory.BI,
            2,
        ),
        (
            ContextHighlightKind.DATA_PRODUCT,
            lambda asset: asset.category is ContextCategory.DATA_PRODUCT,
            2,
        ),
        (
            ContextHighlightKind.PIPELINE_CONTEXT,
            lambda asset: asset.category is ContextCategory.PIPELINE,
            2,
        ),
        (
            ContextHighlightKind.ASSOCIATED_OWNER,
            lambda asset: (
                asset.category is ContextCategory.OWNERSHIP
                and bool(set(asset.supporting_dataset_urns) & set(dataset_ids))
            ),
            2,
        ),
    )
    for kind, predicate, limit in groups:
        selected = sorted(
            (asset for asset in assets if predicate(asset)),
            key=lambda asset: asset.asset_id,
        )[:limit]
        for index, asset in enumerate(selected, start=1):
            highlights.append(
                _asset_highlight(kind, index, asset)
            )
    return tuple(highlights)


def _asset_highlight(
    kind: ContextHighlightKind,
    index: int,
    asset: ContextAssetRecord,
) -> ContextHighlight:
    return ContextHighlight(
        highlight_id=f"context-highlight-{kind.value}-{index}",
        kind=kind,
        subject_id=asset.asset_id,
        display_name=asset.display_name,
        selection_basis=(
            "First two certified connected assets by category and asset ID; "
            "owners must support a highlighted Dataset."
        ),
        supporting_dataset_urns=tuple(
            sorted(asset.supporting_dataset_urns)
        ),
        supporting_field_keys=tuple(
            sorted(asset.supporting_field_keys, key=_field_key)
        ),
    )


def _narrative(
    disposition: str,
    decision_certainty: str,
    components: _Components,
) -> str:
    scope = components.scope
    headline = disposition.replace("_", " ").upper()
    return (
        f"CHRONOS recommends {headline}. "
        "The proposed rename has not been proven incompatible. "
        "The first Spark export dependency remains unresolved because "
        "captured metadata does not show whether it accepts or adapts to "
        "the renamed source field. One unresolved source boundary causes "
        f"uncertainty across {scope.unresolved_downstream_fields} "
        f"downstream fields, {scope.downstream_datasets} Datasets, and all "
        f"{scope.unresolved_paths} modeled paths. "
        f"The connected scope is {scope.breadth.value}; "
        f"{scope.context_assets} context assets are connected to the "
        "unresolved technical cone. The potential consequence is "
        f"{scope.severity_if_realized.value} if the unresolved technical "
        "condition materializes. The recommendation has "
        f"{decision_certainty} decision certainty because the rule "
        "deterministically requires compatibility evidence before "
        "approval; this does not assert a confirmed failure."
    )


def _validate_physical_closure(
    hashes: tuple[InputArtifactHash, ...],
    phase3: Phase3CertificationResult,
    technical: TechnicalImpactAnalysis,
    context: BusinessContextPropagation,
    severity: SeverityCriticalityAnalysis,
) -> None:
    by_name = {item.artifact_name: item for item in hashes}
    if (
        len(hashes) != len(_NAMES)
        or tuple(item.artifact_name for item in hashes) != _NAMES
        or any(not item.unchanged for item in hashes)
    ):
        raise ImpactSynthesisEntryError(
            "All fourteen local inputs must remain unchanged."
        )
    for identity in phase3.input_artifact_identities:
        observed = by_name.get(identity.artifact_name)
        if (
            observed is None
            or observed.before_sha256 != identity.physical_sha256
        ):
            raise ImpactSynthesisEntryError(
                "Phase 3 physical artifact identity mismatch."
            )
    for predecessor, count, label in (
        (technical.input_artifact_hashes, 11, "Phase 4.1"),
        (context.input_artifact_hashes, 12, "Phase 4.2"),
        (severity.input_artifact_hashes, 13, "Phase 4.3"),
    ):
        recorded = {item.artifact_name: item for item in predecessor}
        for name in _NAMES[:count]:
            if (
                name not in recorded
                or not recorded[name].unchanged
                or recorded[name].before_sha256
                != by_name[name].before_sha256
            ):
                raise ImpactSynthesisEntryError(
                    f"{label} physical predecessor identity mismatch."
                )


def _field_key(value: FieldMachineKey) -> tuple[str, str]:
    return value.dataset_urn, value.field_path


def _context_rank(category: ContextCategory) -> int:
    ranks = {
        ContextCategory.BI: 0,
        ContextCategory.DATA_PRODUCT: 1,
        ContextCategory.PIPELINE: 2,
    }
    return ranks.get(category, 9)


def _severity_rank(value: str) -> int:
    return {
        "critical": 0,
        "high": 1,
        "moderate": 2,
        "low": 3,
        "undetermined": 4,
    }[value]


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _timestamp(clock: Clock | None) -> str:
    value = clock() if clock is not None else datetime.now(timezone.utc)
    if value.tzinfo is None:
        raise ImpactSynthesisValidationError(
            "Clock must return timezone-aware values."
        )
    return value.isoformat()
