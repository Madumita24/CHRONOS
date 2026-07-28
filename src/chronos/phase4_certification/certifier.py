"""Offline certification of the complete CHRONOS Phase 4 chain."""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import fields, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Iterable

from chronos.business_context import (
    BusinessContextPropagation,
    ContextCategory,
    business_context_semantic_fingerprint,
    load_business_context,
    propagate_business_context_from_artifacts,
    validate_business_context,
)
from chronos.change_semantics import (
    ChangeSemanticContract,
    load_contract,
)
from chronos.compatibility_evaluation import (
    CompatibilityEvaluationResult,
    CompatibilityState,
    EvidenceStrength,
    load_compatibility_evaluation,
    validate_compatibility_evaluation,
)
from chronos.counterfactual_source import (
    CounterfactualSourceState,
    load_source_state,
    validate_counterfactual_source_state,
)
from chronos.dependency_propagation import (
    DependencyPropagationResult,
    load_dependency_propagation,
    validate_dependency_propagation,
)
from chronos.explanations import (
    ExplanationBundle,
    load_explanation_bundle,
    validate_explanation_bundle,
)
from chronos.future_graph import (
    FutureMetadataGraph,
    load_future_graph,
    validate_future_metadata_graph,
)
from chronos.impact_synthesis import (
    DecisionCertainty,
    DecisionDisposition,
    ImpactSynthesis,
    evaluate_decision,
    impact_synthesis_semantic_fingerprint,
    load_impact_synthesis,
    synthesize_impact_from_artifacts,
    validate_impact_synthesis,
)
from chronos.phase2_certification import (
    Phase2CertificationResult,
    Phase2CertificationState,
    certification_semantic_fingerprint,
    load_certification,
)
from chronos.phase3_certification import (
    Phase3CertificationResult,
    Phase3CertificationStatus,
    load_phase3_certification,
    phase3_certification_semantic_fingerprint,
    validate_phase3_certification,
)
from chronos.proposal import (
    ChangeProposal,
    ChangeType,
    load_proposal,
)
from chronos.proposal_validation import (
    ProposalValidationResult,
    load_validation_result,
)
from chronos.severity_criticality import (
    ContextCriticality,
    EvidenceCertainty,
    ExposureBreadth,
    SensitivityState,
    SeverityCriticalityAnalysis,
    SeverityIfRealized,
    TechnicalConsequence,
    assess_severity_criticality_from_artifacts,
    derive_breadth,
    derive_severity_if_realized,
    load_severity_analysis,
    severity_semantic_fingerprint,
    validate_severity_criticality,
)
from chronos.snapshot import (
    CurrentMetadataSnapshot,
    FieldMachineKey,
    SnapshotValidationState,
    contains_secret,
    load_snapshot,
    semantic_fingerprint as snapshot_semantic_fingerprint,
    validate_snapshot,
)
from chronos.technical_impact import (
    TechnicalImpactAnalysis,
    TechnicalImpactState,
    derive_technical_impact_from_artifacts,
    load_technical_impact,
    technical_impact_semantic_fingerprint,
    validate_technical_impact,
)

from .errors import (
    Phase4CertificationInputError,
    Phase4CertificationValidationError,
)
from .models import (
    PHASE4_CERTIFICATION_SCHEMA_VERSION,
    ArtifactImmutabilityEvidence,
    CertificationCheck,
    CertificationCheckCategory,
    CertificationCheckStatus,
    CertificationFailureSeverity,
    ContextBaseline,
    DecisionBaseline,
    InputArtifactIdentity,
    InputSemanticFingerprint,
    Phase4CertificationResult,
    Phase4CertificationStatus,
    Phase4SemanticFingerprints,
    SeverityBaseline,
    SeverityDistribution,
    TechnicalBaseline,
)


Clock = Callable[[], datetime]
_CURRENT_PATH = "order_total"
_CANDIDATE_PATH = "order_amount"
_CAUSE_ID = "technical-impact-cause-source-rename-semantics"
_ROOT_RELATIONSHIP = "future-lineage-68f7e0269dbea7279911b809"
_ACCEPTED_PHASE3 = (
    "sha256:91ddc335c903db0e5685d50cbcc17a99450f5d3518a7451352eb239ef1475965"
)
_ACCEPTED_PHASE4 = Phase4SemanticFingerprints(
    technical_impact=(
        "sha256:b99dcaa245c077c43939bbe7e79131f57fce58a00a1661ae3a374e40ae00e0ef"
    ),
    business_context=(
        "sha256:18d6c6774d5421b04aa6480e2487b469bc4e45afae9418d15865b8cc5d05edf0"
    ),
    severity_criticality=(
        "sha256:84eaf9129915e7985ecbf9edc71d1e10815bf897195aeea1dc60c85aa099de0a"
    ),
    impact_synthesis=(
        "sha256:630cff0fdc4cbe53ce4b42df275f24362a9954d4a5123d541617d629c9b32cc3"
    ),
)
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
    "impact_synthesis.json",
)
_SCOPE_STATEMENT = (
    "Phase 4 certification validates and freezes the read-only technical "
    "impact, business context, severity/criticality, and impact-synthesis "
    "outputs for Phase 5 consumption. Phase 5 may consume these certified "
    "outputs and must not independently re-derive their semantics. This "
    "certification performs no metadata retrieval, repair generation, "
    "external inspection, DataHub access, frontend construction, or change "
    "to any predecessor artifact."
)


def certify_phase4(
    snapshot: CurrentMetadataSnapshot,
    proposal: ChangeProposal,
    validation: ProposalValidationResult,
    contract: ChangeSemanticContract,
    phase2: Phase2CertificationResult,
    source: CounterfactualSourceState,
    graph: FutureMetadataGraph,
    propagation: DependencyPropagationResult,
    compatibility: CompatibilityEvaluationResult,
    explanations: ExplanationBundle,
    phase3: Phase3CertificationResult,
    technical: TechnicalImpactAnalysis,
    context: BusinessContextPropagation,
    severity: SeverityCriticalityAnalysis,
    synthesis: ImpactSynthesis,
    *,
    input_artifact_identities: tuple[InputArtifactIdentity, ...],
    artifact_immutability: tuple[ArtifactImmutabilityEvidence, ...],
    reconstructed_fingerprints: Phase4SemanticFingerprints,
    clock: Clock | None = None,
) -> Phase4CertificationResult:
    """Certify existing Phase 4 evidence without changing conclusions."""
    checks: list[CertificationCheck] = []

    def check(
        check_id: str,
        category: CertificationCheckCategory,
        description: str,
        condition: bool,
        expected: object,
        observed: object,
        evidence: Iterable[object] = (),
    ) -> None:
        checks.append(
            CertificationCheck(
                check_id=check_id,
                category=category,
                description=description,
                status=(
                    CertificationCheckStatus.PASS
                    if condition
                    else CertificationCheckStatus.FAIL
                ),
                failure_severity=CertificationFailureSeverity.BLOCKING,
                expected=_text(expected),
                observed=_text(observed),
                evidence_references=tuple(
                    _text(item) for item in evidence
                ),
            )
        )

    phase4_fingerprints = _phase4_fingerprints(
        technical, context, severity, synthesis
    )
    technical_baseline = _technical_baseline(technical)
    context_baseline = _context_baseline(context, technical)
    severity_baseline = _severity_baseline(severity)
    decision_baseline = _decision_baseline(synthesis)

    phase1_validation = validate_snapshot(snapshot)
    validators = (
        (
            "technical_impact",
            _passes(
                validate_technical_impact,
                technical,
                source,
                graph,
                propagation,
                compatibility,
                explanations,
                phase3,
            ),
        ),
        (
            "business_context",
            _passes(
                validate_business_context,
                context,
                snapshot,
                graph,
                technical,
                phase3,
            ),
        ),
        (
            "severity_criticality",
            _passes(
                validate_severity_criticality,
                severity,
                snapshot,
                graph,
                technical,
                context,
                phase3,
            ),
        ),
        (
            "impact_synthesis",
            _passes(
                validate_impact_synthesis,
                synthesis,
                phase3,
                technical,
                context,
                severity,
                explanations,
            ),
        ),
    )
    check(
        "prerequisite.phase_1",
        CertificationCheckCategory.PREREQUISITE,
        "Phase 1 embedded certification remains valid and reproducible.",
        (
            phase1_validation.state is SnapshotValidationState.VALID
            and snapshot.validation_result.state
            is SnapshotValidationState.VALID
            and snapshot_semantic_fingerprint(snapshot)
            == snapshot.semantic_fingerprint
        ),
        "valid and reproducible",
        (
            phase1_validation.state.value,
            snapshot.semantic_fingerprint,
        ),
        (snapshot.metadata.snapshot_id,),
    )
    check(
        "prerequisite.phase_2",
        CertificationCheckCategory.PREREQUISITE,
        "Phase 2 certification remains certified and reproducible.",
        (
            phase2.certification_state
            is Phase2CertificationState.CERTIFIED
            and certification_semantic_fingerprint(phase2)
            == phase2.semantic_fingerprint
        ),
        "certified and reproducible",
        (phase2.certification_state.value, phase2.semantic_fingerprint),
        (phase2.demonstration_id,),
    )
    check(
        "prerequisite.phase_3",
        CertificationCheckCategory.PREREQUISITE,
        "Phase 3 remains independently certified.",
        (
            phase3.certification_status
            is Phase3CertificationStatus.CERTIFIED
            and _passes(validate_phase3_certification, phase3)
            and phase3_certification_semantic_fingerprint(phase3)
            == phase3.semantic_fingerprint
            and phase3.semantic_fingerprint == _ACCEPTED_PHASE3
        ),
        _ACCEPTED_PHASE3,
        phase3.semantic_fingerprint,
        (phase3.demonstration_id,),
    )
    for name, valid in validators:
        check(
            f"prerequisite.phase_4_public_validator.{name}",
            CertificationCheckCategory.PREREQUISITE,
            f"The public {name} validator passes.",
            valid,
            True,
            valid,
            (name,),
        )

    demonstrations = (
        snapshot.metadata.demonstration_id,
        proposal.demonstration_id,
        phase2.demonstration_id,
        source.demonstration_id,
        graph.demonstration_id,
        propagation.demonstration_id,
        compatibility.demonstration_id,
        explanations.demonstration_id,
        phase3.demonstration_id,
        technical.demonstration_id,
        context.demonstration_id,
        severity.demonstration_id,
        synthesis.demonstration_id,
    )
    proposal_ids = (
        proposal.proposal_id,
        validation.proposal_id,
        contract.proposal_id,
        compatibility.proposal_id,
        technical.proposal_id,
        context.proposal_id,
        severity.proposal_id,
        synthesis.proposal_id,
    )
    check(
        "cross_reference.demonstration_identity",
        CertificationCheckCategory.CROSS_REFERENCE,
        "All artifacts share the canonical demonstration identity.",
        set(demonstrations) == {"CHRONOS-DEMO-001"},
        "CHRONOS-DEMO-001",
        tuple(sorted(set(demonstrations))),
    )
    check(
        "cross_reference.proposal_identity",
        CertificationCheckCategory.CROSS_REFERENCE,
        "All proposal-bearing artifacts share one proposal identity.",
        set(proposal_ids) == {"CHRONOS-DEMO-001-PROPOSAL-001"},
        "CHRONOS-DEMO-001-PROPOSAL-001",
        tuple(sorted(set(proposal_ids))),
    )
    source_transitions = (
        (
            source.current_source_schema_reference.target_field.field_path,
            next(
                item.field_path
                for item in source.candidate_source_schema.fields
                if item.field_path == _CANDIDATE_PATH
            ),
        ),
        (
            technical.source_change.current_field.field_path,
            technical.source_change.candidate_field.field_path,
        ),
        (
            synthesis.source_change.current_field.field_path,
            synthesis.source_change.candidate_field.field_path,
        ),
    )
    check(
        "cross_reference.source_transition",
        CertificationCheckCategory.CROSS_REFERENCE,
        "Every source transition resolves to order_total -> order_amount.",
        set(source_transitions)
        == {(_CURRENT_PATH, _CANDIDATE_PATH)},
        (_CURRENT_PATH, _CANDIDATE_PATH),
        source_transitions,
    )
    chain_valid = (
        technical.phase_3_certification_fingerprint
        == phase3.semantic_fingerprint
        and context.phase_3_certification_fingerprint
        == phase3.semantic_fingerprint
        and context.technical_impact_fingerprint
        == technical.semantic_fingerprint
        and severity.phase_3_certification_fingerprint
        == phase3.semantic_fingerprint
        and severity.technical_impact_fingerprint
        == technical.semantic_fingerprint
        and severity.business_context_fingerprint
        == context.semantic_fingerprint
        and synthesis.phase_3_certification_fingerprint
        == phase3.semantic_fingerprint
        and synthesis.technical_impact_fingerprint
        == technical.semantic_fingerprint
        and synthesis.business_context_fingerprint
        == context.semantic_fingerprint
        and synthesis.severity_criticality_fingerprint
        == severity.semantic_fingerprint
    )
    check(
        "cross_reference.complete_artifact_chain",
        CertificationCheckCategory.CROSS_REFERENCE,
        "The Phase 4 chain references exact semantic predecessors.",
        chain_valid,
        True,
        chain_valid,
        tuple(item.semantic_fingerprint for item in input_artifact_identities),
    )
    check(
        "cross_reference.acceptance_fingerprints",
        CertificationCheckCategory.CROSS_REFERENCE,
        "Phase 4 fingerprints equal the acceptance references.",
        phase4_fingerprints == _ACCEPTED_PHASE4,
        _ACCEPTED_PHASE4,
        phase4_fingerprints,
    )
    phase3_metrics = phase3.summary_metrics
    observed_phase3 = (
        phase3_metrics.datasets,
        phase3_metrics.active_future_fields,
        phase3_metrics.changed_source_fields,
        phase3_metrics.downstream_fields,
        phase3_metrics.downstream_datasets,
        phase3_metrics.structural_relationships,
        phase3_metrics.mapping_groups,
        phase3_metrics.supporting_paths,
        phase3_metrics.maximum_shortest_exposure_depth,
        phase3_metrics.root_uncertainties,
        phase3_metrics.conditionally_compatible_relationships,
        phase3_metrics.unknown_relationships,
        phase3_metrics.unknown_paths,
    )
    check(
        "cross_reference.phase_3_frozen_baseline",
        CertificationCheckCategory.CROSS_REFERENCE,
        "The frozen Phase 3 baseline remains unchanged.",
        observed_phase3
        == (21, 26, 1, 25, 20, 27, 28, 48, 5, 1, 26, 1, 48),
        (21, 26, 1, 25, 20, 27, 28, 48, 5, 1, 26, 1, 48),
        observed_phase3,
    )

    technical_expected = TechnicalBaseline(
        1,
        1,
        27,
        48,
        25,
        20,
        0,
        26,
        1,
        48,
        25,
        _CAUSE_ID,
        _ROOT_RELATIONSHIP,
    )
    check(
        "technical_impact.frozen_baseline",
        CertificationCheckCategory.TECHNICAL_IMPACT,
        "Phase 4.1 records reproduce the frozen technical baseline.",
        technical_baseline == technical_expected,
        technical_expected,
        technical_baseline,
    )
    relationship_distribution = Counter(
        item.technical_impact_state.value
        for item in technical.relationship_impacts
    )
    path_distribution = Counter(
        item.technical_impact_state.value
        for item in technical.path_impacts
    )
    field_distribution = Counter(
        item.technical_impact_state.value
        for item in technical.field_impacts
    )
    check(
        "technical_impact.distributions",
        CertificationCheckCategory.TECHNICAL_IMPACT,
        "Relationship, path, and field states retain canonical counts.",
        (
            relationship_distribution
            == Counter({"potential_impact": 26, "unresolved_impact": 1})
            and path_distribution == Counter({"unresolved_impact": 48})
            and field_distribution == Counter({"unresolved_impact": 25})
        ),
        (
            {"potential_impact": 26, "unresolved_impact": 1},
            {"unresolved_impact": 48},
            {"unresolved_impact": 25},
        ),
        (
            dict(relationship_distribution),
            dict(path_distribution),
            dict(field_distribution),
        ),
    )
    cause = technical.technical_impact_causes[0]
    root_relationship = next(
        item
        for item in technical.relationship_impacts
        if item.relationship_id == cause.root_relationship_id
    )
    check(
        "technical_impact.root_cause",
        CertificationCheckCategory.TECHNICAL_IMPACT,
        "One unresolved source-rename root cause retains exact boundary.",
        (
            cause.cause_id == _CAUSE_ID
            and cause.root_relationship_id == _ROOT_RELATIONSHIP
            and cause.upstream_field.field_path == _CANDIDATE_PATH
            and cause.downstream_field.field_path == _CURRENT_PATH
            and cause.compatibility_reason.value
            == "source_rename_semantics_unknown"
            and cause.evidence_strength is EvidenceStrength.INSUFFICIENT
            and cause.impact_state
            is TechnicalImpactState.UNRESOLVED_IMPACT
            and root_relationship.compatibility_state
            is CompatibilityState.UNKNOWN
            and all(
                item.cause_ids == (_CAUSE_ID,)
                for item in technical.field_impacts
            )
        ),
        (
            _CAUSE_ID,
            _ROOT_RELATIONSHIP,
            "unknown",
            "insufficient",
            "unresolved_impact",
        ),
        (
            cause.cause_id,
            cause.root_relationship_id,
            root_relationship.compatibility_state.value,
            cause.evidence_strength.value,
            cause.impact_state.value,
        ),
    )

    expected_categories = tuple(
        sorted(item.value for item in ContextCategory)
    )
    observed_categories = tuple(
        sorted({item.category.value for item in context.context_asset_registry})
    )
    context_expected = ContextBaseline(
        20, 66, 211, 257, expected_categories, 1
    )
    check(
        "business_context.frozen_baseline",
        CertificationCheckCategory.BUSINESS_CONTEXT,
        "Phase 4.2 records reproduce the frozen context baseline.",
        context_baseline == context_expected,
        context_expected,
        context_baseline,
    )
    asset_ids = {
        item.asset_id for item in context.context_asset_registry
    }
    relationship_ids = {
        item.context_relationship_id
        for item in context.context_link_registry
    }
    technical_fields = {
        item.field_key for item in technical.field_impacts
    }
    mapping_integrity = all(
        item.technical_field_key in technical_fields
        and item.technical_field_key.dataset_urn == item.dataset_urn
        and item.context_relationship_id in relationship_ids
        and item.context_asset_id in asset_ids
        for item in context.technical_to_context_mappings
    )
    check(
        "business_context.scope_anchors",
        CertificationCheckCategory.BUSINESS_CONTEXT,
        "Every context mapping resolves through field, Dataset, relationship, and asset.",
        mapping_integrity
        and all(
            item.supporting_field_keys
            and item.supporting_dataset_urns
            for item in context.context_asset_registry
        ),
        True,
        mapping_integrity,
    )
    check(
        "business_context.identity_deduplication",
        CertificationCheckCategory.BUSINESS_CONTEXT,
        "Unique assets remain distinct from mapping multiplicity.",
        (
            len(asset_ids) == len(context.context_asset_registry) == 66
            and len(context.technical_to_context_mappings) == 257
        ),
        (66, 257),
        (
            len(asset_ids),
            len(context.technical_to_context_mappings),
        ),
    )
    check(
        "business_context.category_integrity",
        CertificationCheckCategory.BUSINESS_CONTEXT,
        "All nine context categories remain semantically distinct.",
        observed_categories == expected_categories,
        expected_categories,
        observed_categories,
    )
    check(
        "business_context.technical_state_preserved",
        CertificationCheckCategory.BUSINESS_CONTEXT,
        "Context propagation does not change Phase 4.1 technical states.",
        all(
            item.technical_impact_state
            is TechnicalImpactState.UNRESOLVED_IMPACT
            for item in context.technical_to_context_mappings
        ),
        "all unresolved_impact",
        Counter(
            item.technical_impact_state.value
            for item in context.technical_to_context_mappings
        ),
    )

    profile = severity.change_level_profile
    dimensions = (
        profile.technical_consequence.value,
        profile.context_criticality.value,
        profile.exposure_breadth.value,
        profile.sensitivity_state.value,
        profile.evidence_certainty.value,
        profile.severity_if_realized.value,
    )
    check(
        "criticality.dimension_separation",
        CertificationCheckCategory.CRITICALITY,
        "Technical, criticality, breadth, sensitivity, certainty, and severity dimensions remain distinct.",
        dimensions
        == (
            "unresolved_impact",
            "elevated_context",
            "widespread",
            "pii",
            "unresolved",
            "high",
        ),
        (
            "unresolved_impact",
            "elevated_context",
            "widespread",
            "pii",
            "unresolved",
            "high",
        ),
        dimensions,
    )
    explicit_criticality = tuple(
        item
        for item in severity.criticality_evidence
        if item.explicit_semantic_identity is not None
    )
    check(
        "criticality.elevated_not_explicit",
        CertificationCheckCategory.CRITICALITY,
        "ELEVATED_CONTEXT is not explicit or mission-critical metadata.",
        (
            profile.context_criticality
            is ContextCriticality.ELEVATED_CONTEXT
            and not explicit_criticality
        ),
        ("elevated_context", 0),
        (profile.context_criticality.value, len(explicit_criticality)),
    )
    check(
        "criticality.sensitivity_separation",
        CertificationCheckCategory.CRITICALITY,
        "PII sensitivity does not become explicit criticality or independently select severity.",
        (
            profile.sensitivity_state is SensitivityState.PII
            and profile.context_criticality
            is not ContextCriticality.EXPLICITLY_CRITICAL
            and "sensitivity_state"
            not in {
                item.name
                for item in fields(profile.severity_rule_inputs)
            }
        ),
        True,
        (
            profile.sensitivity_state.value,
            profile.context_criticality.value,
        ),
    )
    change_breadth = next(
        item
        for item in severity.breadth_metrics
        if item.breadth_metrics_id == profile.breadth_metrics_id
    )
    replayed_breadth, breadth_rule = derive_breadth(
        supporting_datasets=change_breadth.supporting_datasets,
        consumer_assets=change_breadth.consumer_assets,
        context_assets=change_breadth.unique_context_assets,
        rules=severity.breadth_rule_registry,
    )
    check(
        "breadth.change_level_replay",
        CertificationCheckCategory.BREADTH,
        "Change-level breadth replays from serialized counts and rules.",
        (
            replayed_breadth is ExposureBreadth.WIDESPREAD
            and breadth_rule == "breadth-widespread-multi-channel"
            and breadth_rule == change_breadth.breadth_rule_id
        ),
        ("widespread", "breadth-widespread-multi-channel"),
        (replayed_breadth.value, breadth_rule),
    )
    breadth_only_block = any(
        rule.result.value == "high"
        and len(rule.technical_conditions)
        == len(TechnicalConsequence)
        for rule in severity.severity_rule_registry
    )
    check(
        "breadth.not_severity_or_block",
        CertificationCheckCategory.BREADTH,
        "No severity rule derives HIGH from breadth alone.",
        not breadth_only_block,
        False,
        breadth_only_block,
    )

    registry_valid = (
        len(severity.severity_rule_registry) == 11
        and len(
            {item.rule_id for item in severity.severity_rule_registry}
        )
        == 11
        and len(
            {item.precedence for item in severity.severity_rule_registry}
        )
        == 11
        and all(
            item.technical_conditions
            and item.criticality_conditions
            and item.breadth_conditions
            and item.certainty_conditions
            and item.description
            for item in severity.severity_rule_registry
        )
    )
    check(
        "severity.rule_registry",
        CertificationCheckCategory.SEVERITY,
        "The complete eleven-rule registry is typed and unambiguous.",
        registry_valid,
        True,
        registry_valid,
    )
    field_replay = _severity_assessments_replay(
        severity.field_assessments, severity
    )
    dataset_replay = _severity_assessments_replay(
        severity.dataset_assessments, severity
    )
    change_replay = _severity_assessments_replay((profile,), severity)
    check(
        "severity.rule_replay",
        CertificationCheckCategory.SEVERITY,
        "Every field, Dataset, and change assessment replays exactly.",
        field_replay and dataset_replay and change_replay,
        True,
        (field_replay, dataset_replay, change_replay),
    )
    severity_expected = SeverityBaseline(
        "unresolved_impact",
        "unresolved",
        "elevated_context",
        "widespread",
        "pii",
        "high",
        "breadth-widespread-multi-channel",
        "severity-unresolved-or-potential-elevated-broad",
        11,
        SeverityDistribution(0, 3, 6, 16, 0),
        SeverityDistribution(0, 3, 4, 13, 0),
    )
    check(
        "severity.frozen_baseline",
        CertificationCheckCategory.SEVERITY,
        "Phase 4.3 reproduces canonical profile and distributions.",
        severity_baseline == severity_expected,
        severity_expected,
        severity_baseline,
    )
    check(
        "severity.certainty_preserved",
        CertificationCheckCategory.SEVERITY,
        "Every field and Dataset certainty remains UNRESOLVED.",
        all(
            item.evidence_certainty is EvidenceCertainty.UNRESOLVED
            for item in (
                *severity.field_assessments,
                *severity.dataset_assessments,
            )
        ),
        "all unresolved",
        Counter(
            item.evidence_certainty.value
            for item in (
                *severity.field_assessments,
                *severity.dataset_assessments,
            )
        ),
    )
    context_model_fields = {
        item.name
        for item in fields(severity.context_asset_assessments[0])
    }
    check(
        "severity.context_assets_remain_context",
        CertificationCheckCategory.SEVERITY,
        "Context assessments contain no failure, probability, repair, or realized-severity state.",
        not context_model_fields
        & {
            "technical_failure_state",
            "severity_if_realized",
            "failure_probability",
            "repair_priority",
        },
        "no prohibited technical or repair fields",
        tuple(sorted(context_model_fields)),
    )

    decision_inputs_match = (
        synthesis.change_severity_profile.technical_consequence
        is profile.technical_consequence
        and synthesis.change_severity_profile.impact_certainty
        is profile.evidence_certainty
        and synthesis.change_severity_profile.severity_if_realized
        is profile.severity_if_realized
        and synthesis.change_severity_profile.breadth
        is profile.exposure_breadth
        and synthesis.change_severity_profile.criticality
        is profile.context_criticality
        and not synthesis.change_severity_profile.has_explicit_conditions
    )
    check(
        "decision.inputs_match_phase_4_3",
        CertificationCheckCategory.DECISION,
        "Phase 4.4 uses exactly the certified Phase 4.3 profile.",
        decision_inputs_match,
        True,
        decision_inputs_match,
    )
    decision_registry_valid = (
        len(
            {
                item.rule_id
                for item in synthesis.decision_rule_registry
            }
        )
        == len(synthesis.decision_rule_registry)
        and len(
            {
                item.precedence
                for item in synthesis.decision_rule_registry
            }
        )
        == len(synthesis.decision_rule_registry)
        and all(
            item.technical_consequence_conditions
            and item.impact_certainty_conditions
            and item.severity_if_realized_conditions
            and item.breadth_conditions
            and item.criticality_conditions
            and item.reason_codes
            and item.description
            for item in synthesis.decision_rule_registry
        )
    )
    selected = evaluate_decision(
        synthesis.change_severity_profile,
        rules=synthesis.decision_rule_registry,
    )
    check(
        "decision.rule_registry_and_replay",
        CertificationCheckCategory.DECISION,
        "The typed decision registry is unambiguous and canonical selection replays.",
        (
            decision_registry_valid
            and selected.rule_id
            == "decision-hold-unresolved-material-broad"
            and selected.disposition
            is DecisionDisposition.HOLD_FOR_REVIEW
            and selected.decision_certainty
            is DecisionCertainty.HIGH_CONFIDENCE
            and selected.rule_id == synthesis.decision_rule_id
            and selected.reason_codes
            == synthesis.decision_reason_codes
        ),
        (
            "decision-hold-unresolved-material-broad",
            "hold_for_review",
            "high_confidence",
        ),
        (
            selected.rule_id,
            selected.disposition.value,
            selected.decision_certainty.value,
        ),
    )
    decision_expected = DecisionBaseline(
        "hold_for_review",
        "high_confidence",
        "unresolved",
        "decision-hold-unresolved-material-broad",
        (
            "unresolved_source_compatibility",
            "material_severity_if_realized",
            "widespread_dependency_reach",
            "missing_execution_evidence",
        ),
        0,
        25,
        66,
        1,
        4,
        3,
    )
    check(
        "decision.frozen_baseline",
        CertificationCheckCategory.DECISION,
        "Phase 4.4 reproduces the frozen decision baseline.",
        decision_baseline == decision_expected,
        decision_expected,
        decision_baseline,
    )
    narrative = synthesis.assessment.narrative.lower()
    check(
        "decision.certainty_and_failure_integrity",
        CertificationCheckCategory.DECISION,
        "High decision confidence remains separate from unresolved technical certainty and zero confirmed failures.",
        (
            synthesis.decision_certainty
            is DecisionCertainty.HIGH_CONFIDENCE
            and synthesis.change_severity_profile.impact_certainty
            is EvidenceCertainty.UNRESOLVED
            and synthesis.scope_summary.confirmed_downstream_failures == 0
            and "not been proven incompatible" in narrative
            and "does not assert a confirmed failure" in narrative
            and "25 broken" not in narrative
            and "20 broken" not in narrative
            and "48 failed" not in narrative
            and "66 impacted assets" not in narrative
        ),
        True,
        True,
    )
    reasons_resolve = all(
        reason.evidence_ids
        and set(reason.evidence_ids)
        <= {item.evidence_id for item in synthesis.decision_evidence}
        for reason in synthesis.decision_reasons
    )
    check(
        "decision.reason_evidence",
        CertificationCheckCategory.DECISION,
        "Every canonical decision reason resolves to typed evidence.",
        reasons_resolve
        and tuple(
            item.reason_code.value for item in synthesis.decision_reasons
        )
        == decision_expected.decision_reason_codes,
        decision_expected.decision_reason_codes,
        tuple(
            item.reason_code.value for item in synthesis.decision_reasons
        ),
    )
    known = " ".join(synthesis.what_we_know).lower()
    unknown = " ".join(synthesis.what_we_do_not_know).lower()
    check(
        "decision.known_unknown_audit",
        CertificationCheckCategory.DECISION,
        "Known and unresolved facts remain supported and separate.",
        (
            all(
                term in known
                for term in (
                    "renames",
                    "25 downstream fields",
                    "20 downstream datasets",
                    "48 modeled dependency paths",
                    "insufficient",
                    "widespread",
                    "high if",
                )
            )
            and all(
                term in unknown
                for term in (
                    "spark export accepts",
                    "pipeline adapts",
                    "execution would succeed",
                )
            )
        ),
        True,
        True,
    )

    questions = synthesis.blocking_questions
    required_classes = {
        item.evidence_class for item in synthesis.required_evidence
    }
    question_valid = (
        len(questions) == 1
        and questions[0].question_id
        == "blocking-question-spark-export-rename-compatibility"
        and questions[0].root_cause_id == _CAUSE_ID
        and questions[0].subject == _ROOT_RELATIONSHIP
        and len(questions[0].affected_field_keys) == 25
        and len(questions[0].affected_dataset_urns) == 20
        and len(questions[0].affected_path_ids) == 48
        and questions[0].resolution_state.value == "unresolved"
    )
    check(
        "blocking_evidence.question",
        CertificationCheckCategory.BLOCKING_EVIDENCE,
        "The canonical blocking question and all affected scope resolve.",
        question_valid,
        True,
        question_valid,
        tuple(item.question_id for item in questions),
    )
    expected_evidence_classes = {
        "spark_transformation_configuration",
        "input_column_reference_query_or_code",
        "explicit_rename_mapping",
        "validated_execution_result",
    }
    check(
        "blocking_evidence.required_evidence",
        CertificationCheckCategory.BLOCKING_EVIDENCE,
        "Four unresolved evidence classes remain requirements, not repairs.",
        (
            required_classes == expected_evidence_classes
            and all(
                item.state.value
                == "required_for_decision_resolution"
                for item in synthesis.required_evidence
            )
        ),
        tuple(sorted(expected_evidence_classes)),
        tuple(sorted(required_classes)),
    )

    technical_path_ids = {
        item.path_id for item in technical.path_impacts
    }
    technical_relationship_ids = {
        item.relationship_id for item in technical.relationship_impacts
    }
    context_mapping_ids = {
        item.mapping_id for item in context.technical_to_context_mappings
    }
    context_assets = {
        item.asset_id for item in context.context_asset_registry
    }
    representative_valid = (
        {item.kind.value for item in synthesis.representative_evidence_paths}
        == {"short", "deep", "multipath"}
        and all(
            item.technical_path_id in technical_path_ids
            and set(item.ordered_relationship_ids)
            <= technical_relationship_ids
            and item.context_mapping_id in context_mapping_ids
            and item.context_asset_id in context_assets
            for item in synthesis.representative_evidence_paths
        )
    )
    check(
        "provenance.representative_paths",
        CertificationCheckCategory.PROVENANCE,
        "Short, deep, and multipath evidence examples resolve completely.",
        representative_valid,
        True,
        representative_valid,
    )
    highlight_valid = all(
        item.subject_id in context_assets
        or item.kind.value == "technical_dataset"
        and item.subject_id
        in {
            summary.dataset_urn for summary in technical.dataset_summaries
        }
        for item in synthesis.context_highlights
    ) and all(
        "highest risk" not in item.selection_basis.lower()
        and "most likely" not in item.selection_basis.lower()
        and "notification" not in item.selection_basis.lower()
        for item in synthesis.context_highlights
    )
    check(
        "provenance.context_highlights",
        CertificationCheckCategory.PROVENANCE,
        "Context highlights resolve and retain non-risk selection semantics.",
        highlight_valid,
        True,
        highlight_valid,
    )
    phase3_chain_names = {
        item.artifact_name for item in phase3.input_artifact_identities
    }
    full_provenance = (
        phase3_chain_names == set(_NAMES[:10])
        and mapping_integrity
        and representative_valid
        and reasons_resolve
        and question_valid
    )
    check(
        "provenance.recursive_closure",
        CertificationCheckCategory.PROVENANCE,
        "Decision, severity, context, technical, Phase 3, proposal, and current-state provenance closes.",
        full_provenance,
        True,
        full_provenance,
    )

    immutable = (
        len(artifact_immutability) == 15
        and all(item.unchanged for item in artifact_immutability)
    )
    check(
        "immutability.all_inputs",
        CertificationCheckCategory.IMMUTABILITY,
        "All fifteen authoritative inputs remain byte-identical.",
        immutable,
        True,
        immutable,
        tuple(item.artifact_name for item in artifact_immutability),
    )
    check(
        "determinism.phase_4_reconstruction",
        CertificationCheckCategory.DETERMINISM,
        "Independent Phase 4.1-4.4 reconstruction is semantically identical.",
        reconstructed_fingerprints == phase4_fingerprints,
        phase4_fingerprints,
        reconstructed_fingerprints,
    )
    round_trips = all(
        obj.__class__.from_json(obj.to_json()).semantically_equals(obj)
        for obj in (technical, context, severity, synthesis)
    )
    check(
        "determinism.serialization_round_trips",
        CertificationCheckCategory.DETERMINISM,
        "Every Phase 4 artifact round-trips without semantic drift.",
        round_trips,
        True,
        round_trips,
    )

    objects = (
        snapshot,
        proposal,
        validation,
        contract,
        phase2,
        source,
        graph,
        propagation,
        compatibility,
        explanations,
        phase3,
        technical,
        context,
        severity,
        synthesis,
    )
    secret_free = all(
        not contains_secret(obj.to_dict()) for obj in objects
    )
    check(
        "security.credential_scan",
        CertificationCheckCategory.SECURITY,
        "All certification inputs contain no credential-shaped content.",
        secret_free,
        True,
        secret_free,
    )
    prohibited_fields = {
        "risk_score",
        "failure_probability",
        "expected_loss",
        "repair_recommendation",
        "notification_priority",
        "llm_disposition",
        "automatic_fix",
    }
    observed_fields = _collect_field_names(
        (technical, context, severity, synthesis)
    )
    check(
        "scope.prohibited_semantics",
        CertificationCheckCategory.SCOPE,
        "Phase 4 contains no repair, score, probability, notification, or LLM-authority fields.",
        not prohibited_fields & observed_fields,
        (),
        tuple(sorted(prohibited_fields & observed_fields)),
    )
    check(
        "scope.semantic_layer_separation",
        CertificationCheckCategory.SCOPE,
        "Current, proposal, counterfactual, exposure, compatibility, impact, context, severity, certainty, and disposition layers remain distinct.",
        (
            source.state_classification.value == "counterfactual"
            and proposal.change_type is ChangeType.FIELD_RENAME
            and cause.impact_state
            is TechnicalImpactState.UNRESOLVED_IMPACT
            and profile.context_criticality
            is ContextCriticality.ELEVATED_CONTEXT
            and synthesis.decision_disposition
            is DecisionDisposition.HOLD_FOR_REVIEW
        ),
        True,
        True,
    )
    check(
        "scope.frontend_consumption_boundary",
        CertificationCheckCategory.SCOPE,
        "Certification exposes frozen read-only outputs without frontend construction.",
        (
            "Phase 5" in _SCOPE_STATEMENT
            and "must not independently re-derive" in _SCOPE_STATEMENT
            and "frontend construction" in _SCOPE_STATEMENT
        ),
        True,
        True,
    )

    status = (
        Phase4CertificationStatus.CERTIFIED
        if all(
            item.status is CertificationCheckStatus.PASS
            for item in checks
        )
        else Phase4CertificationStatus.FAILED
    )
    warnings = (
        "Explicit business-criticality metadata remains absent.",
        "HIGH remains severity if realized, not probability.",
        "WIDESPREAD remains breadth, not an independent block.",
        "HOLD_FOR_REVIEW is not a confirmed failure or permanent ban.",
    )
    result = Phase4CertificationResult(
        schema_version=PHASE4_CERTIFICATION_SCHEMA_VERSION,
        demonstration_id=technical.demonstration_id,
        proposal_id=technical.proposal_id,
        certification_status=status,
        certified_at=_timestamp(clock),
        input_artifact_identities=input_artifact_identities,
        input_semantic_fingerprints=tuple(
            InputSemanticFingerprint(
                item.artifact_name, item.semantic_fingerprint
            )
            for item in input_artifact_identities
        ),
        phase_4_semantic_fingerprints=phase4_fingerprints,
        certification_checks=tuple(checks),
        technical_baseline=technical_baseline,
        context_baseline=context_baseline,
        severity_baseline=severity_baseline,
        decision_baseline=decision_baseline,
        blocking_question_ids=tuple(
            item.question_id for item in synthesis.blocking_questions
        ),
        warnings=warnings,
        scope_statement=_SCOPE_STATEMENT,
        artifact_immutability=artifact_immutability,
    )
    if status is Phase4CertificationStatus.CERTIFIED:
        validate_phase4_certification(result)
    return result


def certify_phase4_from_artifacts(
    snapshot_path: str | Path,
    proposal_path: str | Path,
    validation_path: str | Path,
    contract_path: str | Path,
    phase2_path: str | Path,
    source_path: str | Path,
    graph_path: str | Path,
    propagation_path: str | Path,
    compatibility_path: str | Path,
    explanations_path: str | Path,
    phase3_path: str | Path,
    technical_path: str | Path,
    context_path: str | Path,
    severity_path: str | Path,
    synthesis_path: str | Path,
    *,
    clock: Clock | None = None,
) -> Phase4CertificationResult:
    """Load, reconstruct, and certify fifteen immutable local artifacts."""
    paths = tuple(
        (name, Path(path))
        for name, path in zip(
            _NAMES,
            (
                snapshot_path,
                proposal_path,
                validation_path,
                contract_path,
                phase2_path,
                source_path,
                graph_path,
                propagation_path,
                compatibility_path,
                explanations_path,
                phase3_path,
                technical_path,
                context_path,
                severity_path,
                synthesis_path,
            ),
        )
    )
    before = {name: _file_hash(path) for name, path in paths}
    try:
        objects = (
            load_snapshot(snapshot_path),
            load_proposal(proposal_path),
            load_validation_result(validation_path),
            load_contract(contract_path),
            load_certification(phase2_path),
            load_source_state(source_path),
            load_future_graph(graph_path),
            load_dependency_propagation(propagation_path),
            load_compatibility_evaluation(compatibility_path),
            load_explanation_bundle(explanations_path),
            load_phase3_certification(phase3_path),
            load_technical_impact(technical_path),
            load_business_context(context_path),
            load_severity_analysis(severity_path),
            load_impact_synthesis(synthesis_path),
        )
    except Exception as exc:
        raise Phase4CertificationInputError(
            "A Phase 4 certification input failed closed during loading."
        ) from exc
    after_load = {name: _file_hash(path) for name, path in paths}
    if after_load != before:
        raise Phase4CertificationInputError(
            "A certification input changed during loading."
        )
    reconstructed = _reconstruct_phase4(
        tuple(path for _, path in paths)
    )
    after_reconstruction = {
        name: _file_hash(path) for name, path in paths
    }
    semantic_values = tuple(
        obj.semantic_fingerprint for obj in objects
    )
    object_ids = (
        objects[0].metadata.snapshot_id,
        objects[1].proposal_id,
        objects[2].proposal_id,
        objects[3].proposal_id,
        objects[4].demonstration_id,
        objects[5].demonstration_id,
        objects[6].demonstration_id,
        objects[7].demonstration_id,
        objects[8].proposal_id,
        objects[9].demonstration_id,
        objects[10].demonstration_id,
        objects[11].proposal_id,
        objects[12].proposal_id,
        objects[13].proposal_id,
        objects[14].proposal_id,
    )
    identities = tuple(
        InputArtifactIdentity(
            artifact_name=name,
            object_id=object_id,
            semantic_fingerprint=semantic_value,
            physical_sha256=before[name],
        )
        for (name, _), object_id, semantic_value in zip(
            paths, object_ids, semantic_values
        )
    )
    immutability = tuple(
        ArtifactImmutabilityEvidence(
            name, before[name], after_reconstruction[name]
        )
        for name, _ in paths
    )
    result = certify_phase4(
        *objects,
        input_artifact_identities=identities,
        artifact_immutability=immutability,
        reconstructed_fingerprints=reconstructed,
        clock=clock,
    )
    if {name: _file_hash(path) for name, path in paths} != before:
        raise Phase4CertificationInputError(
            "A predecessor artifact changed during certification."
        )
    return result


def validate_phase4_certification(
    result: Phase4CertificationResult,
) -> None:
    """Fail closed when a Phase 4 certification contradicts itself."""
    issues: list[str] = []
    if result.certification_status is not Phase4CertificationStatus.CERTIFIED:
        issues.append("Phase 4 status is not CERTIFIED")
    if any(
        item.status is not CertificationCheckStatus.PASS
        for item in result.certification_checks
    ):
        issues.append("One or more Phase 4 certification checks failed")
    if {
        item.category for item in result.certification_checks
    } != set(CertificationCheckCategory):
        issues.append("Certification check categories are incomplete")
    if any(not item.unchanged for item in result.artifact_immutability):
        issues.append("An authoritative input changed")
    if result.phase_4_semantic_fingerprints != _ACCEPTED_PHASE4:
        issues.append("Phase 4 acceptance fingerprint mismatch")
    if result.technical_baseline != TechnicalBaseline(
        1, 1, 27, 48, 25, 20, 0, 26, 1, 48, 25, _CAUSE_ID,
        _ROOT_RELATIONSHIP,
    ):
        issues.append("Frozen technical baseline mismatch")
    if result.context_baseline != ContextBaseline(
        20,
        66,
        211,
        257,
        tuple(sorted(item.value for item in ContextCategory)),
        1,
    ):
        issues.append("Frozen context baseline mismatch")
    if result.severity_baseline != SeverityBaseline(
        "unresolved_impact",
        "unresolved",
        "elevated_context",
        "widespread",
        "pii",
        "high",
        "breadth-widespread-multi-channel",
        "severity-unresolved-or-potential-elevated-broad",
        11,
        SeverityDistribution(0, 3, 6, 16, 0),
        SeverityDistribution(0, 3, 4, 13, 0),
    ):
        issues.append("Frozen severity baseline mismatch")
    if result.decision_baseline != DecisionBaseline(
        "hold_for_review",
        "high_confidence",
        "unresolved",
        "decision-hold-unresolved-material-broad",
        (
            "unresolved_source_compatibility",
            "material_severity_if_realized",
            "widespread_dependency_reach",
            "missing_execution_evidence",
        ),
        0,
        25,
        66,
        1,
        4,
        3,
    ):
        issues.append("Frozen decision baseline mismatch")
    if result.blocking_question_ids != (
        "blocking-question-spark-export-rename-compatibility",
    ):
        issues.append("Blocking question baseline mismatch")
    if contains_secret(result.to_dict()):
        issues.append("Certification contains credential-shaped content")
    if issues:
        raise Phase4CertificationValidationError("; ".join(issues))


def _reconstruct_phase4(
    paths: tuple[Path, ...],
) -> Phase4SemanticFingerprints:
    fixed = lambda hour: lambda: datetime(
        2026, 7, 28, hour, tzinfo=timezone.utc
    )
    technical = derive_technical_impact_from_artifacts(
        *paths[:11], clock=fixed(1)
    )
    context = propagate_business_context_from_artifacts(
        *paths[:12], clock=fixed(2)
    )
    severity = assess_severity_criticality_from_artifacts(
        *paths[:13], clock=fixed(3)
    )
    synthesis = synthesize_impact_from_artifacts(
        *paths[:14], clock=fixed(4)
    )
    return _phase4_fingerprints(
        technical, context, severity, synthesis
    )


def _phase4_fingerprints(
    technical: TechnicalImpactAnalysis,
    context: BusinessContextPropagation,
    severity: SeverityCriticalityAnalysis,
    synthesis: ImpactSynthesis,
) -> Phase4SemanticFingerprints:
    return Phase4SemanticFingerprints(
        technical_impact=technical_impact_semantic_fingerprint(technical),
        business_context=business_context_semantic_fingerprint(context),
        severity_criticality=severity_semantic_fingerprint(severity),
        impact_synthesis=impact_synthesis_semantic_fingerprint(synthesis),
    )


def _technical_baseline(
    technical: TechnicalImpactAnalysis,
) -> TechnicalBaseline:
    metrics = technical.aggregate_metrics
    cause = technical.technical_impact_causes[0]
    return TechnicalBaseline(
        change_origins=1,
        technical_root_causes=len(technical.technical_impact_causes),
        relationship_impacts=len(technical.relationship_impacts),
        path_impacts=len(technical.path_impacts),
        downstream_fields=len(technical.field_impacts),
        downstream_datasets=len(technical.dataset_summaries),
        confirmed_downstream_failures=metrics.confirmed_impacted_fields,
        potential_relationships=metrics.potential_impacted_relationships,
        unresolved_relationships=metrics.unresolved_relationships,
        unresolved_paths=metrics.unresolved_paths,
        unresolved_fields=metrics.unresolved_fields,
        root_cause_id=cause.cause_id,
        root_relationship_id=cause.root_relationship_id,
    )


def _context_baseline(
    context: BusinessContextPropagation,
    technical: TechnicalImpactAnalysis,
) -> ContextBaseline:
    metrics = context.aggregate_metrics
    return ContextBaseline(
        technical_scope_datasets=len(technical.dataset_summaries),
        unique_context_assets=len(context.context_asset_registry),
        scoped_context_relationships=len(context.context_link_registry),
        field_to_context_mappings=len(
            context.technical_to_context_mappings
        ),
        context_categories=tuple(
            sorted(
                {
                    item.category.value
                    for item in context.context_asset_registry
                }
            )
        ),
        unresolved_context_references=len(
            context.unresolved_context_references
        ),
    )


def _severity_baseline(
    severity: SeverityCriticalityAnalysis,
) -> SeverityBaseline:
    profile = severity.change_level_profile
    breadth = next(
        item
        for item in severity.breadth_metrics
        if item.breadth_metrics_id == profile.breadth_metrics_id
    )
    return SeverityBaseline(
        technical_consequence=profile.technical_consequence.value,
        technical_certainty=profile.evidence_certainty.value,
        context_criticality=profile.context_criticality.value,
        breadth=profile.exposure_breadth.value,
        sensitivity=profile.sensitivity_state.value,
        severity_if_realized=profile.severity_if_realized.value,
        breadth_rule_id=breadth.breadth_rule_id,
        severity_rule_id=profile.severity_rule_id,
        severity_rule_count=len(severity.severity_rule_registry),
        field_distribution=_severity_distribution(
            item.severity_if_realized
            for item in severity.field_assessments
        ),
        dataset_distribution=_severity_distribution(
            item.severity_if_realized
            for item in severity.dataset_assessments
        ),
    )


def _severity_distribution(
    values: Iterable[SeverityIfRealized],
) -> SeverityDistribution:
    counts = Counter(item.value for item in values)
    return SeverityDistribution(
        critical=counts["critical"],
        high=counts["high"],
        moderate=counts["moderate"],
        low=counts["low"],
        undetermined=counts["undetermined"],
    )


def _decision_baseline(synthesis: ImpactSynthesis) -> DecisionBaseline:
    return DecisionBaseline(
        disposition=synthesis.decision_disposition.value,
        decision_certainty=synthesis.decision_certainty.value,
        technical_certainty=(
            synthesis.change_severity_profile.impact_certainty.value
        ),
        decision_rule_id=synthesis.decision_rule_id,
        decision_reason_codes=tuple(
            item.value for item in synthesis.decision_reason_codes
        ),
        confirmed_broken_fields=(
            synthesis.scope_summary.confirmed_downstream_failures
        ),
        technically_unresolved_fields=(
            synthesis.scope_summary.unresolved_downstream_fields
        ),
        connected_context_assets=synthesis.scope_summary.context_assets,
        blocking_questions=len(synthesis.blocking_questions),
        required_evidence=len(synthesis.required_evidence),
        representative_paths=len(synthesis.representative_evidence_paths),
    )


def _severity_assessments_replay(
    assessments: Iterable[Any],
    severity: SeverityCriticalityAnalysis,
) -> bool:
    for assessment in assessments:
        replay = derive_severity_if_realized(
            assessment.severity_rule_inputs.technical_consequence,
            assessment.severity_rule_inputs.context_criticality,
            assessment.severity_rule_inputs.exposure_breadth,
            assessment.severity_rule_inputs.evidence_certainty,
            rules=severity.severity_rule_registry,
        )
        if (
            replay.rule_id != assessment.severity_rule_id
            or replay.severity_if_realized
            is not assessment.severity_if_realized
            or replay.reason_codes != assessment.severity_reason_codes
        ):
            return False
    return True


def _collect_field_names(roots: Iterable[Any]) -> set[str]:
    names: set[str] = set()

    def visit(value: Any) -> None:
        if is_dataclass(value):
            for item in fields(value):
                names.add(item.name)
                visit(getattr(value, item.name))
        elif isinstance(value, (tuple, list)):
            for item in value:
                visit(item)
        elif isinstance(value, dict):
            names.update(str(key) for key in value)
            for item in value.values():
                visit(item)

    for root in roots:
        visit(root)
    return names


def _passes(function: Callable[..., Any], *args: Any) -> bool:
    try:
        function(*args)
    except Exception:
        return False
    return True


def _text(value: object) -> str:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return repr(value)
    if isinstance(value, Counter):
        return repr(dict(value))
    return str(value)


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _timestamp(clock: Clock | None) -> str:
    value = (clock or (lambda: datetime.now(timezone.utc)))()
    if value.tzinfo is None:
        raise Phase4CertificationInputError(
            "Certification clock must include a timezone."
        )
    return value.astimezone(timezone.utc).isoformat()
