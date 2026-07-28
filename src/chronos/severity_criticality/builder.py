"""Deterministic CHRONOS Phase 4.3 severity and criticality derivation."""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

from chronos.business_context import (
    BusinessContextPropagation,
    ContextAssetRecord,
    ContextAssetType,
    ContextCategory,
    ContextResolutionState,
    TechnicalToContextMapping,
    load_business_context,
    validate_business_context,
)
from chronos.change_semantics import ChangeSemanticContract, load_contract
from chronos.compatibility_evaluation import (
    CompatibilityEvaluationResult,
    load_compatibility_evaluation,
    validate_compatibility_evaluation,
)
from chronos.counterfactual_source import (
    CounterfactualSourceState,
    InputArtifactHash,
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
from chronos.phase2_certification import (
    Phase2CertificationResult,
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
from chronos.proposal import (
    CANONICAL_DATASET_URN,
    ChangeProposal,
    ChangeType,
    load_proposal,
)
from chronos.proposal_validation import (
    ProposalValidationResult,
    load_validation_result,
)
from chronos.snapshot import (
    CurrentMetadataSnapshot,
    FieldMachineKey,
    SnapshotValidationState,
    load_snapshot,
)
from chronos.technical_impact import (
    FieldTechnicalImpact,
    TechnicalImpactAnalysis,
    TechnicalImpactState,
    load_technical_impact,
    validate_technical_impact,
)

from .errors import (
    SeverityCriticalityEntryError,
    SeverityCriticalityValidationError,
)
from .models import (
    SEVERITY_CRITICALITY_SCHEMA_VERSION,
    AssessmentSubjectType,
    BreadthMetrics,
    ChangeLevelSeverityProfile,
    ContextAssetSignificanceAssessment,
    ContextCriticality,
    ContextSignificance,
    CriticalityEvidence,
    CriticalityReasonCode,
    DatasetSeverityAssessment,
    EvidenceCertainty,
    ExposureBreadth,
    FieldSeverityAssessment,
    MissingEvidence,
    MissingEvidenceClass,
    RootCauseReference,
    SensitivityEvidence,
    SensitivityState,
    SeverityCriticalityAggregateMetrics,
    SeverityCriticalityAnalysis,
    SeverityCriticalityValidationState,
    SeverityIfRealized,
    SeverityReasonCode,
    TechnicalConsequence,
)
from .rules import (
    DEFAULT_BREADTH_RULES,
    DEFAULT_SEVERITY_RULES,
    derive_breadth,
    derive_context_criticality,
    derive_severity_if_realized,
)


Clock = Callable[[], datetime]
_CURRENT = FieldMachineKey(CANONICAL_DATASET_URN, "order_total")
_CANDIDATE = FieldMachineKey(CANONICAL_DATASET_URN, "order_amount")
_PROPOSAL_ID = "CHRONOS-DEMO-001-PROPOSAL-001"
_CAUSE_ID = "technical-impact-cause-source-rename-semantics"
_PII_TAG = "urn:li:tag:b2fd91.PII_Data"
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
)
_EXPLICIT_CRITICALITY_SEMANTICS = {
    "business.criticality": frozenset(
        {"critical", "mission_critical", "tier_1"}
    ),
    "business.importanceTier": frozenset({"tier_1"}),
}
_MISSING_CLASSES = tuple(MissingEvidenceClass)


@dataclass(frozen=True)
class _SubjectBundle:
    criticality: CriticalityEvidence
    breadth: BreadthMetrics
    sensitivity: SensitivityEvidence
    missing: MissingEvidence
    mapping_ids: tuple[str, ...]
    asset_ids: tuple[str, ...]
    relationship_ids: tuple[str, ...]
    field_keys: tuple[FieldMachineKey, ...]
    dataset_urns: tuple[str, ...]
    path_ids: tuple[str, ...]
    provenance_ids: tuple[str, ...]


@dataclass(frozen=True)
class _Components:
    root_causes: tuple[RootCauseReference, ...]
    field_assessments: tuple[FieldSeverityAssessment, ...]
    dataset_assessments: tuple[DatasetSeverityAssessment, ...]
    context_asset_assessments: tuple[
        ContextAssetSignificanceAssessment,
        ...,
    ]
    change_level_profile: ChangeLevelSeverityProfile
    criticality_evidence: tuple[CriticalityEvidence, ...]
    breadth_metrics: tuple[BreadthMetrics, ...]
    sensitivity_evidence: tuple[SensitivityEvidence, ...]
    missing_evidence: tuple[MissingEvidence, ...]
    aggregate_metrics: SeverityCriticalityAggregateMetrics


def assess_severity_criticality(
    snapshot: CurrentMetadataSnapshot,
    proposal: ChangeProposal,
    proposal_validation: ProposalValidationResult,
    contract: ChangeSemanticContract,
    phase2: Phase2CertificationResult,
    source_state: CounterfactualSourceState,
    graph: FutureMetadataGraph,
    propagation: DependencyPropagationResult,
    compatibility: CompatibilityEvaluationResult,
    explanations: ExplanationBundle,
    phase3: Phase3CertificationResult,
    technical_impact: TechnicalImpactAnalysis,
    business_context: BusinessContextPropagation,
    *,
    input_artifact_hashes: tuple[InputArtifactHash, ...],
    clock: Clock | None = None,
) -> SeverityCriticalityAnalysis:
    _require_entry(
        snapshot,
        proposal,
        proposal_validation,
        contract,
        phase2,
        source_state,
        graph,
        propagation,
        compatibility,
        explanations,
        phase3,
        technical_impact,
        business_context,
        input_artifact_hashes,
    )
    components = _derive_components(technical_impact, business_context)
    result = SeverityCriticalityAnalysis(
        schema_version=SEVERITY_CRITICALITY_SCHEMA_VERSION,
        demonstration_id=technical_impact.demonstration_id,
        proposal_id=technical_impact.proposal_id,
        phase_3_certification_fingerprint=phase3.semantic_fingerprint,
        technical_impact_fingerprint=technical_impact.semantic_fingerprint,
        business_context_fingerprint=business_context.semantic_fingerprint,
        root_causes=components.root_causes,
        severity_rule_registry=DEFAULT_SEVERITY_RULES,
        breadth_rule_registry=DEFAULT_BREADTH_RULES,
        field_assessments=components.field_assessments,
        dataset_assessments=components.dataset_assessments,
        context_asset_assessments=(
            components.context_asset_assessments
        ),
        change_level_profile=components.change_level_profile,
        criticality_evidence=components.criticality_evidence,
        breadth_metrics=components.breadth_metrics,
        sensitivity_evidence=components.sensitivity_evidence,
        missing_evidence=components.missing_evidence,
        aggregate_metrics=components.aggregate_metrics,
        canonical_narrative=_canonical_narrative(
            components.change_level_profile,
            components.aggregate_metrics,
        ),
        warnings=(),
        input_artifact_hashes=input_artifact_hashes,
        created_at=_timestamp(clock),
        validation_state=SeverityCriticalityValidationState.VALID,
    )
    validate_severity_criticality(
        result,
        snapshot,
        graph,
        technical_impact,
        business_context,
        phase3,
    )
    return result


def assess_severity_criticality_from_artifacts(
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
    technical_impact_path: str | Path,
    business_context_path: str | Path,
    *,
    clock: Clock | None = None,
) -> SeverityCriticalityAnalysis:
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
                source_state_path,
                graph_path,
                propagation_path,
                compatibility_path,
                explanations_path,
                phase3_path,
                technical_impact_path,
                business_context_path,
            ),
        )
    )
    before = {name: _file_hash(path) for name, path in paths}
    snapshot = load_snapshot(snapshot_path)
    proposal = load_proposal(proposal_path)
    proposal_validation = load_validation_result(validation_path)
    contract = load_contract(contract_path)
    phase2 = load_certification(phase2_path)
    source_state = load_source_state(source_state_path)
    graph = load_future_graph(graph_path)
    propagation = load_dependency_propagation(propagation_path)
    compatibility = load_compatibility_evaluation(compatibility_path)
    explanations = load_explanation_bundle(explanations_path)
    phase3 = load_phase3_certification(phase3_path)
    technical_impact = load_technical_impact(technical_impact_path)
    business_context = load_business_context(business_context_path)
    after_load = {name: _file_hash(path) for name, path in paths}
    hashes = tuple(
        InputArtifactHash(name, before[name], after_load[name])
        for name, _ in paths
    )
    result = assess_severity_criticality(
        snapshot,
        proposal,
        proposal_validation,
        contract,
        phase2,
        source_state,
        graph,
        propagation,
        compatibility,
        explanations,
        phase3,
        technical_impact,
        business_context,
        input_artifact_hashes=hashes,
        clock=clock,
    )
    if {name: _file_hash(path) for name, path in paths} != before:
        raise SeverityCriticalityValidationError(
            "An authoritative input changed during severity derivation."
        )
    return result


def validate_severity_criticality(
    result: SeverityCriticalityAnalysis,
    snapshot: CurrentMetadataSnapshot,
    graph: FutureMetadataGraph,
    technical_impact: TechnicalImpactAnalysis,
    business_context: BusinessContextPropagation,
    phase3: Phase3CertificationResult,
) -> None:
    issues: list[str] = []

    def require(condition: bool, message: str) -> None:
        if not condition:
            issues.append(message)

    require(
        result.phase_3_certification_fingerprint
        == phase3.semantic_fingerprint,
        "Phase 3 certification reference mismatch",
    )
    require(
        result.technical_impact_fingerprint
        == technical_impact.semantic_fingerprint,
        "Phase 4.1 technical-impact reference mismatch",
    )
    require(
        result.business_context_fingerprint
        == business_context.semantic_fingerprint,
        "Phase 4.2 business-context reference mismatch",
    )
    expected = _derive_components(technical_impact, business_context)
    for actual, wanted, label in (
        (result.root_causes, expected.root_causes, "root causes"),
        (
            result.field_assessments,
            expected.field_assessments,
            "field assessments",
        ),
        (
            result.dataset_assessments,
            expected.dataset_assessments,
            "Dataset assessments",
        ),
        (
            result.context_asset_assessments,
            expected.context_asset_assessments,
            "context asset assessments",
        ),
        (
            result.change_level_profile,
            expected.change_level_profile,
            "change-level profile",
        ),
        (
            result.criticality_evidence,
            expected.criticality_evidence,
            "criticality evidence",
        ),
        (
            result.breadth_metrics,
            expected.breadth_metrics,
            "breadth metrics",
        ),
        (
            result.sensitivity_evidence,
            expected.sensitivity_evidence,
            "sensitivity evidence",
        ),
        (
            result.missing_evidence,
            expected.missing_evidence,
            "missing evidence",
        ),
        (
            result.aggregate_metrics,
            expected.aggregate_metrics,
            "aggregate metrics",
        ),
    ):
        require(actual == wanted, f"Derived {label} mismatch")
    require(
        result.severity_rule_registry == DEFAULT_SEVERITY_RULES,
        "Severity rule registry mismatch",
    )
    require(
        result.breadth_rule_registry == DEFAULT_BREADTH_RULES,
        "Breadth rule registry mismatch",
    )
    field_states = {
        item.field_key: item.technical_impact_state
        for item in technical_impact.field_impacts
    }
    require(
        all(
            item.technical_impact_state is field_states.get(item.field_key)
            for item in result.field_assessments
        ),
        "A Phase 4.1 technical state was mutated",
    )
    context_ids = {
        item.asset_id for item in business_context.context_asset_registry
    }
    require(
        {
            item.context_asset_id
            for item in result.context_asset_assessments
        }
        == context_ids,
        "Phase 4.2 context asset scope mismatch",
    )
    for assessment in (
        tuple(result.field_assessments)
        + tuple(result.dataset_assessments)
        + (result.change_level_profile,)
    ):
        reproduced = derive_severity_if_realized(
            assessment.severity_rule_inputs.technical_consequence,
            assessment.severity_rule_inputs.context_criticality,
            assessment.severity_rule_inputs.exposure_breadth,
            assessment.severity_rule_inputs.evidence_certainty,
            rules=result.severity_rule_registry,
        )
        require(
            reproduced.rule_id == assessment.severity_rule_id
            and reproduced.severity_if_realized
            is assessment.severity_if_realized
            and reproduced.reason_codes
            == assessment.severity_reason_codes,
            f"Severity rule result is not reproducible: {assessment}",
        )
    for metrics in result.breadth_metrics:
        reproduced_state, reproduced_rule = derive_breadth(
            supporting_datasets=metrics.supporting_datasets,
            consumer_assets=metrics.consumer_assets,
            context_assets=metrics.unique_context_assets,
            rules=result.breadth_rule_registry,
        )
        require(
            reproduced_state is metrics.exposure_breadth
            and reproduced_rule == metrics.breadth_rule_id,
            f"Breadth rule result is not reproducible: "
            f"{metrics.breadth_metrics_id}",
        )
    require(
        result.canonical_narrative
        == _canonical_narrative(
            result.change_level_profile,
            result.aggregate_metrics,
        ),
        "Canonical narrative is not derived from typed evidence",
    )
    require(
        len(result.input_artifact_hashes) == len(_NAMES)
        and tuple(
            item.artifact_name for item in result.input_artifact_hashes
        )
        == _NAMES
        and all(item.unchanged for item in result.input_artifact_hashes),
        "Phase 4.3 input immutability evidence is invalid",
    )
    require(
        len(result.field_assessments) == 25
        and len(result.dataset_assessments) == 20
        and len(result.context_asset_assessments) == 66,
        "Canonical assessment scope mismatch",
    )
    snapshot_relationships = {
        item.relationship_id for item in snapshot.relationships
    }
    require(
        all(
            relationship_id in snapshot_relationships
            for evidence in result.criticality_evidence
            for relationship_id in (
                evidence.supporting_context_relationship_ids
            )
        ),
        "Criticality evidence lacks certified current provenance",
    )
    graph_context_ids = {
        item.current_relationship_id
        for item in graph.context_relationship_registry
    }
    require(
        all(
            relationship_id in graph_context_ids
            for evidence in result.criticality_evidence
            for relationship_id in (
                evidence.supporting_context_relationship_ids
            )
        ),
        "Criticality evidence lacks Future Graph provenance",
    )
    serialized = result.to_json().lower()
    for phrase in (
        "safe_to_deploy",
        "do_not_deploy",
        "deployment_recommendation",
        "repair_recommendation",
        "remediation_sequence",
        "owner_notification",
        "probability_of_failure",
        "likelihood_percentage",
        "expected_loss",
        "risk_score",
    ):
        require(phrase not in serialized, f"Unsupported concept: {phrase}")
    if issues:
        raise SeverityCriticalityValidationError("; ".join(issues))


def _require_entry(
    snapshot: CurrentMetadataSnapshot,
    proposal: ChangeProposal,
    proposal_validation: ProposalValidationResult,
    contract: ChangeSemanticContract,
    phase2: Phase2CertificationResult,
    source_state: CounterfactualSourceState,
    graph: FutureMetadataGraph,
    propagation: DependencyPropagationResult,
    compatibility: CompatibilityEvaluationResult,
    explanations: ExplanationBundle,
    phase3: Phase3CertificationResult,
    technical_impact: TechnicalImpactAnalysis,
    business_context: BusinessContextPropagation,
    hashes: tuple[InputArtifactHash, ...],
) -> None:
    try:
        validate_phase3_certification(phase3)
        validate_counterfactual_source_state(
            source_state,
            snapshot,
            proposal,
            proposal_validation,
            contract,
            phase2,
        )
        validate_future_metadata_graph(
            graph,
            snapshot,
            proposal,
            proposal_validation,
            contract,
            phase2,
            source_state,
        )
        validate_dependency_propagation(propagation, graph)
        validate_compatibility_evaluation(
            compatibility,
            graph,
            propagation,
        )
        validate_explanation_bundle(
            explanations,
            snapshot,
            source_state,
            graph,
            propagation,
            compatibility,
        )
        validate_technical_impact(
            technical_impact,
            source_state,
            graph,
            propagation,
            compatibility,
            explanations,
            phase3,
        )
        validate_business_context(
            business_context,
            snapshot,
            graph,
            technical_impact,
            phase3,
        )
    except ValueError as exc:
        raise SeverityCriticalityEntryError(
            "Certified Phase 4.3 entry validation failed."
        ) from exc
    if (
        snapshot.validation_result.state is not SnapshotValidationState.VALID
        or phase2.certification_state
        is not Phase2CertificationState.CERTIFIED
        or phase3.certification_status
        is not Phase3CertificationStatus.CERTIFIED
        or phase3_certification_semantic_fingerprint(phase3)
        != phase3.semantic_fingerprint
        or proposal.change_type is not ChangeType.FIELD_RENAME
        or proposal.demonstration_id != "CHRONOS-DEMO-001"
        or proposal.proposal_id != _PROPOSAL_ID
        or proposal.change.target.dataset_urn != CANONICAL_DATASET_URN
        or proposal.change.before.field_path != _CURRENT.field_path
        or proposal.change.requested_after.field_path
        != _CANDIDATE.field_path
        or technical_impact.source_change.current_field != _CURRENT
        or technical_impact.source_change.candidate_field != _CANDIDATE
        or technical_impact.phase_3_certification_fingerprint
        != phase3.semantic_fingerprint
        or business_context.phase_3_certification_fingerprint
        != phase3.semantic_fingerprint
        or business_context.technical_impact_fingerprint
        != technical_impact.semantic_fingerprint
    ):
        raise SeverityCriticalityEntryError(
            "A required certification, identity, or source transition "
            "is invalid."
        )
    if (
        len(technical_impact.field_impacts) != 25
        or len(technical_impact.dataset_summaries) != 20
        or len(business_context.context_asset_registry) != 66
        or len(business_context.context_link_registry) != 211
        or len(business_context.technical_to_context_mappings) != 257
        or {item.cause_id for item in technical_impact.technical_impact_causes}
        != {_CAUSE_ID}
    ):
        raise SeverityCriticalityEntryError(
            "The certified Phase 4 baseline scope is invalid."
        )
    if (
        len(hashes) != len(_NAMES)
        or tuple(item.artifact_name for item in hashes) != _NAMES
        or any(not item.unchanged for item in hashes)
    ):
        raise SeverityCriticalityEntryError(
            "All thirteen Phase 4.3 inputs must remain unchanged."
        )
    hash_by_name = {item.artifact_name: item for item in hashes}
    semantic_objects = (
        snapshot,
        proposal,
        proposal_validation,
        contract,
        phase2,
        source_state,
        graph,
        propagation,
        compatibility,
        explanations,
    )
    for identity, obj in zip(
        phase3.input_artifact_identities,
        semantic_objects,
    ):
        observed = hash_by_name.get(identity.artifact_name)
        if (
            identity.semantic_fingerprint != obj.semantic_fingerprint
            or observed is None
            or identity.physical_sha256 != observed.before_sha256
        ):
            raise SeverityCriticalityEntryError(
                "Phase 3 predecessor identity or hash mismatch."
            )
    for predecessor_hashes, names, label in (
        (
            technical_impact.input_artifact_hashes,
            _NAMES[:11],
            "Phase 4.1",
        ),
        (
            business_context.input_artifact_hashes,
            _NAMES[:12],
            "Phase 4.2",
        ),
    ):
        recorded_by_name = {
            item.artifact_name: item for item in predecessor_hashes
        }
        for name in names:
            recorded = recorded_by_name.get(name)
            observed = hash_by_name[name]
            if (
                recorded is None
                or not recorded.unchanged
                or recorded.before_sha256 != observed.before_sha256
            ):
                raise SeverityCriticalityEntryError(
                    f"{label} predecessor physical hash mismatch."
                )


def _derive_components(
    technical: TechnicalImpactAnalysis,
    context: BusinessContextPropagation,
) -> _Components:
    field_by_key = {
        item.field_key: item for item in technical.field_impacts
    }
    asset_by_id = {
        item.asset_id: item for item in context.context_asset_registry
    }
    mappings = context.technical_to_context_mappings
    bundles: list[_SubjectBundle] = []
    field_assessments: list[FieldSeverityAssessment] = []
    for field in sorted(
        technical.field_impacts,
        key=lambda item: item.field_key.text,
    ):
        subject_mappings = tuple(
            item
            for item in mappings
            if item.technical_field_key == field.field_key
        )
        bundle = _subject_bundle(
            AssessmentSubjectType.FIELD,
            field.field_key.text,
            subject_mappings,
            context,
            field_keys=(field.field_key,),
            dataset_urns=(field.dataset_urn,),
            path_ids=field.supporting_path_ids,
        )
        bundles.append(bundle)
        consequence = _technical_consequence(
            field.technical_impact_state
        )
        certainty = _certainty((consequence,))
        rule = derive_severity_if_realized(
            consequence,
            bundle.criticality.criticality,
            bundle.breadth.exposure_breadth,
            certainty,
        )
        field_assessments.append(
            FieldSeverityAssessment(
                field_key=field.field_key,
                dataset_urn=field.dataset_urn,
                technical_impact_state=field.technical_impact_state,
                technical_consequence=consequence,
                root_cause_ids=field.cause_ids,
                context_mapping_ids=bundle.mapping_ids,
                criticality_evidence_id=bundle.criticality.evidence_id,
                breadth_metrics_id=bundle.breadth.breadth_metrics_id,
                sensitivity_evidence_id=(
                    bundle.sensitivity.sensitivity_evidence_id
                ),
                evidence_certainty=certainty,
                severity_if_realized=rule.severity_if_realized,
                severity_rule_id=rule.rule_id,
                severity_rule_inputs=rule.inputs,
                criticality_reason_codes=(
                    bundle.criticality.reason_codes
                ),
                severity_reason_codes=rule.reason_codes,
                missing_evidence_id=bundle.missing.missing_evidence_id,
                provenance_ids=_ordered_unique(
                    (
                        technical.semantic_fingerprint,
                        context.semantic_fingerprint,
                    )
                    + field.current_provenance_ids
                    + field.counterfactual_provenance_ids
                    + bundle.provenance_ids
                ),
                explanation=_severity_explanation(
                    field.field_key.text,
                    consequence,
                    bundle.criticality.criticality,
                    bundle.breadth.exposure_breadth,
                    certainty,
                    rule.severity_if_realized,
                ),
            )
        )
    dataset_assessments: list[DatasetSeverityAssessment] = []
    for dataset in sorted(
        technical.dataset_summaries,
        key=lambda item: item.dataset_urn,
    ):
        fields = tuple(
            sorted(
                (
                    field_by_key[value]
                    for value in dataset.exposed_field_keys
                ),
                key=lambda item: item.field_key.text,
            )
        )
        subject_mappings = tuple(
            item
            for item in mappings
            if item.dataset_urn == dataset.dataset_urn
        )
        paths = tuple(
            sorted(
                {
                    value
                    for item in fields
                    for value in item.supporting_path_ids
                }
            )
        )
        bundle = _subject_bundle(
            AssessmentSubjectType.DATASET,
            dataset.dataset_urn,
            subject_mappings,
            context,
            field_keys=tuple(item.field_key for item in fields),
            dataset_urns=(dataset.dataset_urn,),
            path_ids=paths,
        )
        bundles.append(bundle)
        consequences = tuple(
            _technical_consequence(item.technical_impact_state)
            for item in fields
        )
        consequence = _rollup_consequence(consequences)
        certainty = _certainty(consequences)
        rule = derive_severity_if_realized(
            consequence,
            bundle.criticality.criticality,
            bundle.breadth.exposure_breadth,
            certainty,
        )
        counts = Counter(item.technical_impact_state for item in fields)
        dataset_assessments.append(
            DatasetSeverityAssessment(
                dataset_urn=dataset.dataset_urn,
                field_keys=tuple(item.field_key for item in fields),
                confirmed_fields=counts[
                    TechnicalImpactState.CONFIRMED_IMPACT
                ],
                potential_fields=counts[
                    TechnicalImpactState.POTENTIAL_IMPACT
                ],
                unresolved_fields=counts[
                    TechnicalImpactState.UNRESOLVED_IMPACT
                ],
                no_demonstrated_fields=counts[
                    TechnicalImpactState.NO_DEMONSTRATED_IMPACT
                ],
                technical_consequence=consequence,
                root_cause_ids=dataset.cause_ids,
                context_asset_ids=bundle.asset_ids,
                context_mapping_ids=bundle.mapping_ids,
                criticality_evidence_id=bundle.criticality.evidence_id,
                breadth_metrics_id=bundle.breadth.breadth_metrics_id,
                sensitivity_evidence_id=(
                    bundle.sensitivity.sensitivity_evidence_id
                ),
                evidence_certainty=certainty,
                severity_if_realized=rule.severity_if_realized,
                severity_rule_id=rule.rule_id,
                severity_rule_inputs=rule.inputs,
                criticality_reason_codes=(
                    bundle.criticality.reason_codes
                ),
                severity_reason_codes=rule.reason_codes,
                missing_evidence_id=bundle.missing.missing_evidence_id,
                provenance_ids=_ordered_unique(
                    (
                        technical.semantic_fingerprint,
                        context.semantic_fingerprint,
                    )
                    + bundle.provenance_ids
                ),
                explanation=_severity_explanation(
                    dataset.dataset_urn,
                    consequence,
                    bundle.criticality.criticality,
                    bundle.breadth.exposure_breadth,
                    certainty,
                    rule.severity_if_realized,
                ),
            )
        )
    context_assessments: list[ContextAssetSignificanceAssessment] = []
    for asset in context.context_asset_registry:
        subject_mappings = tuple(
            item for item in mappings if item.context_asset_id == asset.asset_id
        )
        fields = tuple(
            sorted(
                {item.technical_field_key for item in subject_mappings},
                key=lambda item: item.text,
            )
        )
        datasets = tuple(
            sorted({item.dataset_urn for item in subject_mappings})
        )
        paths = tuple(
            sorted(
                {
                    value
                    for item in subject_mappings
                    for value in item.supporting_path_ids
                }
            )
        )
        bundle = _subject_bundle(
            AssessmentSubjectType.CONTEXT_ASSET,
            asset.asset_id,
            subject_mappings,
            context,
            field_keys=fields,
            dataset_urns=datasets,
            path_ids=paths,
            subject_asset=asset,
        )
        bundles.append(bundle)
        consequences = tuple(
            sorted(
                {
                    _technical_consequence(
                        field_by_key[item].technical_impact_state
                    )
                    for item in fields
                },
                key=lambda item: item.value,
            )
        )
        context_assessments.append(
            ContextAssetSignificanceAssessment(
                context_asset_id=asset.asset_id,
                context_category=asset.category,
                context_asset_type=asset.asset_type,
                context_significance=_context_significance(asset.category),
                linked_technical_consequences=consequences,
                supporting_dataset_urns=datasets,
                supporting_field_keys=fields,
                root_cause_ids=asset.root_technical_cause_ids,
                context_mapping_ids=bundle.mapping_ids,
                criticality_evidence_id=bundle.criticality.evidence_id,
                breadth_metrics_id=bundle.breadth.breadth_metrics_id,
                sensitivity_evidence_id=(
                    bundle.sensitivity.sensitivity_evidence_id
                ),
                evidence_certainty=_certainty(consequences),
                missing_evidence_id=bundle.missing.missing_evidence_id,
                provenance_ids=_ordered_unique(
                    (
                        technical.semantic_fingerprint,
                        context.semantic_fingerprint,
                    )
                    + asset.current_evidence_ids
                    + asset.future_graph_provenance_ids
                    + bundle.provenance_ids
                ),
                explanation=(
                    f"{asset.asset_id} is represented as "
                    f"{_context_significance(asset.category).value}. It is "
                    "contextually linked to technical evidence without being "
                    "assigned a technical failure state."
                ),
            )
        )
    all_fields = tuple(
        item.field_key for item in technical.field_impacts
    )
    all_datasets = tuple(
        item.dataset_urn for item in technical.dataset_summaries
    )
    all_paths = tuple(item.path_id for item in technical.path_impacts)
    change_bundle = _subject_bundle(
        AssessmentSubjectType.CHANGE,
        technical.proposal_id,
        mappings,
        context,
        field_keys=all_fields,
        dataset_urns=all_datasets,
        path_ids=all_paths,
    )
    bundles.append(change_bundle)
    change_consequences = tuple(
        _technical_consequence(item.technical_impact_state)
        for item in technical.field_impacts
    )
    change_consequence = _rollup_consequence(change_consequences)
    change_certainty = _certainty(change_consequences)
    change_rule = derive_severity_if_realized(
        change_consequence,
        change_bundle.criticality.criticality,
        change_bundle.breadth.exposure_breadth,
        change_certainty,
    )
    change_profile = ChangeLevelSeverityProfile(
        subject_id=technical.proposal_id,
        technical_consequence=change_consequence,
        context_criticality=change_bundle.criticality.criticality,
        exposure_breadth=change_bundle.breadth.exposure_breadth,
        sensitivity_state=change_bundle.sensitivity.sensitivity_state,
        evidence_certainty=change_certainty,
        severity_if_realized=change_rule.severity_if_realized,
        root_cause_ids=tuple(
            item.cause_id for item in technical.technical_impact_causes
        ),
        criticality_evidence_id=change_bundle.criticality.evidence_id,
        breadth_metrics_id=change_bundle.breadth.breadth_metrics_id,
        sensitivity_evidence_id=(
            change_bundle.sensitivity.sensitivity_evidence_id
        ),
        missing_evidence_id=change_bundle.missing.missing_evidence_id,
        severity_rule_id=change_rule.rule_id,
        severity_rule_inputs=change_rule.inputs,
        criticality_reason_codes=change_bundle.criticality.reason_codes,
        severity_reason_codes=change_rule.reason_codes,
        explanation=_severity_explanation(
            "the proposed field rename",
            change_consequence,
            change_bundle.criticality.criticality,
            change_bundle.breadth.exposure_breadth,
            change_certainty,
            change_rule.severity_if_realized,
        ),
        provenance_ids=_ordered_unique(
            (
                technical.semantic_fingerprint,
                context.semantic_fingerprint,
            )
            + change_bundle.provenance_ids
        ),
    )
    roots = tuple(
        RootCauseReference(
            cause_id=item.cause_id,
            root_relationship_id=item.root_relationship_id,
            technical_consequence=_technical_consequence(
                item.impact_state
            ),
            evidence_certainty=_certainty(
                (_technical_consequence(item.impact_state),)
            ),
            source_evidence_strength=item.evidence_strength.value,
            phase_4_1_technical_impact_fingerprint=(
                technical.semantic_fingerprint
            ),
        )
        for item in technical.technical_impact_causes
    )
    criticality_evidence = tuple(
        sorted(
            (item.criticality for item in bundles),
            key=lambda item: item.evidence_id,
        )
    )
    breadth_metrics = tuple(
        sorted(
            (item.breadth for item in bundles),
            key=lambda item: item.breadth_metrics_id,
        )
    )
    sensitivity_evidence = tuple(
        sorted(
            (item.sensitivity for item in bundles),
            key=lambda item: item.sensitivity_evidence_id,
        )
    )
    missing_evidence = tuple(
        sorted(
            (item.missing for item in bundles),
            key=lambda item: item.missing_evidence_id,
        )
    )
    aggregate = _aggregate(
        tuple(field_assessments),
        tuple(dataset_assessments),
        tuple(context_assessments),
        criticality_evidence,
        sensitivity_evidence,
        context,
    )
    return _Components(
        root_causes=roots,
        field_assessments=tuple(field_assessments),
        dataset_assessments=tuple(dataset_assessments),
        context_asset_assessments=tuple(context_assessments),
        change_level_profile=change_profile,
        criticality_evidence=criticality_evidence,
        breadth_metrics=breadth_metrics,
        sensitivity_evidence=sensitivity_evidence,
        missing_evidence=missing_evidence,
        aggregate_metrics=aggregate,
    )


def _subject_bundle(
    subject_type: AssessmentSubjectType,
    subject_id: str,
    mappings: tuple[TechnicalToContextMapping, ...],
    context: BusinessContextPropagation,
    *,
    field_keys: tuple[FieldMachineKey, ...],
    dataset_urns: tuple[str, ...],
    path_ids: tuple[str, ...],
    subject_asset: ContextAssetRecord | None = None,
) -> _SubjectBundle:
    asset_by_id = {
        item.asset_id: item for item in context.context_asset_registry
    }
    link_by_id = {
        item.context_relationship_id: item
        for item in context.context_link_registry
    }
    asset_ids = tuple(
        sorted({item.context_asset_id for item in mappings})
    )
    if subject_asset is not None and subject_asset.asset_id not in asset_ids:
        asset_ids = tuple(sorted(asset_ids + (subject_asset.asset_id,)))
    assets = tuple(asset_by_id[item] for item in asset_ids)
    relationship_ids = tuple(
        sorted({item.context_relationship_id for item in mappings})
    )
    categories = {item.category.value for item in assets}
    pii_tags = tuple(
        sorted(item.asset_id for item in assets if item.asset_id == _PII_TAG)
    )
    unresolved_tags = tuple(
        sorted(
            item.asset_id
            for item in assets
            if item.category is ContextCategory.TAG
            and item.resolution_state is ContextResolutionState.UNRESOLVED
        )
    )
    if pii_tags:
        sensitivity_state = SensitivityState.PII
        sensitivity_explanation = (
            "Exact certified PII_Data tag identity is present. This is a "
            "sensitivity signal only."
        )
    elif unresolved_tags:
        sensitivity_state = SensitivityState.SENSITIVITY_UNKNOWN
        sensitivity_explanation = (
            "An unresolved certified tag is present, so its sensitivity "
            "semantics remain unknown."
        )
    else:
        sensitivity_state = (
            SensitivityState.NO_CERTIFIED_SENSITIVITY_SIGNAL
        )
        sensitivity_explanation = (
            "No exact certified sensitivity classification is linked."
        )
    explicit_identity, explicit_value = _explicit_criticality(
        relationship_ids,
        link_by_id,
    )
    criticality_state, criticality_reasons = derive_context_criticality(
        explicit_designation=explicit_identity is not None,
        context_categories=categories,
        supporting_datasets=len(set(dataset_urns)),
        sensitivity_state=sensitivity_state,
    )
    consumers = sum(
        item.category
        in (
            ContextCategory.DATA_PRODUCT,
            ContextCategory.PIPELINE,
            ContextCategory.BI,
        )
        for item in assets
    )
    breadth_state, breadth_rule_id = derive_breadth(
        supporting_datasets=len(set(dataset_urns)),
        consumer_assets=consumers,
        context_assets=len(assets),
    )
    evidence_id = _record_id("criticality", subject_type, subject_id)
    breadth_id = _record_id("breadth", subject_type, subject_id)
    sensitivity_id = _record_id("sensitivity", subject_type, subject_id)
    missing_id = _record_id("missing", subject_type, subject_id)
    provenance = _ordered_unique(
        (context.semantic_fingerprint,)
        + tuple(item.mapping_id for item in mappings)
        + relationship_ids
    )
    criticality = CriticalityEvidence(
        evidence_id=evidence_id,
        subject_type=subject_type,
        subject_id=subject_id,
        criticality=criticality_state,
        reason_codes=criticality_reasons,
        explicit_semantic_identity=explicit_identity,
        explicit_semantic_value=explicit_value,
        supporting_context_asset_ids=asset_ids,
        supporting_context_relationship_ids=relationship_ids,
        explanation=_criticality_explanation(
            criticality_state,
            explicit_identity,
        ),
        provenance_ids=provenance,
    )
    breadth = BreadthMetrics(
        breadth_metrics_id=breadth_id,
        subject_type=subject_type,
        subject_id=subject_id,
        supporting_technical_fields=len(set(field_keys)),
        supporting_datasets=len(set(dataset_urns)),
        context_relationship_count=len(relationship_ids),
        unique_context_assets=len(assets),
        owners=_category_count(assets, ContextCategory.OWNERSHIP),
        domains=_category_count(assets, ContextCategory.DOMAIN),
        data_products=_category_count(
            assets,
            ContextCategory.DATA_PRODUCT,
        ),
        documents=_category_count(assets, ContextCategory.DOCUMENT),
        pipeline_assets=_category_count(
            assets,
            ContextCategory.PIPELINE,
        ),
        bi_assets=_category_count(assets, ContextCategory.BI),
        charts=sum(
            item.asset_type is ContextAssetType.CHART for item in assets
        ),
        dashboards=sum(
            item.asset_type is ContextAssetType.DASHBOARD
            for item in assets
        ),
        supporting_technical_paths=len(set(path_ids)),
        exposure_breadth=breadth_state,
        breadth_rule_id=breadth_rule_id,
        supporting_context_asset_ids=asset_ids,
        supporting_path_ids=tuple(sorted(set(path_ids))),
    )
    sensitivity = SensitivityEvidence(
        sensitivity_evidence_id=sensitivity_id,
        subject_type=subject_type,
        subject_id=subject_id,
        sensitivity_state=sensitivity_state,
        supporting_tag_ids=tuple(sorted(set(pii_tags + unresolved_tags))),
        explanation=sensitivity_explanation,
        provenance_ids=provenance,
    )
    missing_classes = (
        ()
        if explicit_identity is not None
        else _MISSING_CLASSES
    )
    missing = MissingEvidence(
        missing_evidence_id=missing_id,
        subject_type=subject_type,
        subject_id=subject_id,
        missing_classes=missing_classes,
        explanation=(
            "No certified explicit business criticality tier, "
            "criticality-bearing SLA class, production tier, asset "
            "importance, or consumer criticality designation is present."
            if missing_classes
            else "Explicit criticality metadata is present."
        ),
    )
    return _SubjectBundle(
        criticality=criticality,
        breadth=breadth,
        sensitivity=sensitivity,
        missing=missing,
        mapping_ids=tuple(sorted(item.mapping_id for item in mappings)),
        asset_ids=asset_ids,
        relationship_ids=relationship_ids,
        field_keys=tuple(sorted(set(field_keys), key=lambda item: item.text)),
        dataset_urns=tuple(sorted(set(dataset_urns))),
        path_ids=tuple(sorted(set(path_ids))),
        provenance_ids=provenance,
    )


def _explicit_criticality(
    relationship_ids: tuple[str, ...],
    link_by_id: dict[str, object],
) -> tuple[str | None, str | None]:
    for relationship_id in relationship_ids:
        link = link_by_id[relationship_id]
        if link.context_category is not ContextCategory.STRUCTURED_PROPERTY:
            continue
        attributes = {
            item.name: item.values for item in link.attributes
        }
        qualified_names = attributes.get("qualified_name", ())
        values = attributes.get("values", ())
        for qualified_name in qualified_names:
            recognized = _EXPLICIT_CRITICALITY_SEMANTICS.get(
                str(qualified_name)
            )
            if recognized is None:
                continue
            for value in values:
                normalized = str(value).strip().lower()
                if normalized in recognized:
                    return str(qualified_name), str(value)
    return None, None


def _technical_consequence(
    state: TechnicalImpactState,
) -> TechnicalConsequence:
    return TechnicalConsequence(state.value)


def _rollup_consequence(
    values: Iterable[TechnicalConsequence],
) -> TechnicalConsequence:
    states = set(values)
    if TechnicalConsequence.CONFIRMED_IMPACT in states:
        return TechnicalConsequence.CONFIRMED_IMPACT
    if TechnicalConsequence.UNRESOLVED_IMPACT in states:
        return TechnicalConsequence.UNRESOLVED_IMPACT
    if TechnicalConsequence.POTENTIAL_IMPACT in states:
        return TechnicalConsequence.POTENTIAL_IMPACT
    return TechnicalConsequence.NO_DEMONSTRATED_IMPACT


def _certainty(
    values: Iterable[TechnicalConsequence],
) -> EvidenceCertainty:
    states = set(values)
    if not states:
        return EvidenceCertainty.INSUFFICIENT
    if TechnicalConsequence.UNRESOLVED_IMPACT in states:
        return EvidenceCertainty.UNRESOLVED
    if TechnicalConsequence.POTENTIAL_IMPACT in states:
        return EvidenceCertainty.CONDITIONAL
    return EvidenceCertainty.ESTABLISHED


def _context_significance(
    category: ContextCategory,
) -> ContextSignificance:
    return {
        ContextCategory.OWNERSHIP: ContextSignificance.ACCOUNTABILITY,
        ContextCategory.DOMAIN: (
            ContextSignificance.ORGANIZATIONAL_GROUPING
        ),
        ContextCategory.TAG: ContextSignificance.CLASSIFICATION,
        ContextCategory.GLOSSARY: ContextSignificance.BUSINESS_SEMANTICS,
        ContextCategory.STRUCTURED_PROPERTY: (
            ContextSignificance.CONFIGURED_METADATA
        ),
        ContextCategory.DATA_PRODUCT: (
            ContextSignificance.PRODUCT_GROUPING
        ),
        ContextCategory.DOCUMENT: (
            ContextSignificance.DOCUMENTATION_CONTEXT
        ),
        ContextCategory.PIPELINE: (
            ContextSignificance.OPERATIONAL_DEPENDENCY_CONTEXT
        ),
        ContextCategory.BI: ContextSignificance.CONSUMER_FACING_CONTEXT,
    }[category]


def _aggregate(
    field_assessments: tuple[FieldSeverityAssessment, ...],
    dataset_assessments: tuple[DatasetSeverityAssessment, ...],
    context_assessments: tuple[
        ContextAssetSignificanceAssessment,
        ...,
    ],
    criticality: tuple[CriticalityEvidence, ...],
    sensitivity: tuple[SensitivityEvidence, ...],
    context: BusinessContextPropagation,
) -> SeverityCriticalityAggregateMetrics:
    criticality_counts = Counter(item.criticality for item in criticality)
    sensitivity_counts = Counter(
        item.sensitivity_state for item in sensitivity
    )
    field_counts = Counter(
        item.severity_if_realized for item in field_assessments
    )
    dataset_counts = Counter(
        item.severity_if_realized for item in dataset_assessments
    )
    return SeverityCriticalityAggregateMetrics(
        field_assessments=len(field_assessments),
        dataset_assessments=len(dataset_assessments),
        context_asset_assessments=len(context_assessments),
        explicitly_critical_subjects=criticality_counts[
            ContextCriticality.EXPLICITLY_CRITICAL
        ],
        elevated_context_subjects=criticality_counts[
            ContextCriticality.ELEVATED_CONTEXT
        ],
        standard_context_subjects=criticality_counts[
            ContextCriticality.STANDARD_CONTEXT
        ],
        criticality_unknown_subjects=criticality_counts[
            ContextCriticality.CRITICALITY_UNKNOWN
        ],
        pii_sensitive_subjects=sensitivity_counts[SensitivityState.PII],
        sensitivity_unknown_subjects=sensitivity_counts[
            SensitivityState.SENSITIVITY_UNKNOWN
        ],
        critical_severity_fields=field_counts[SeverityIfRealized.CRITICAL],
        high_severity_fields=field_counts[SeverityIfRealized.HIGH],
        moderate_severity_fields=field_counts[
            SeverityIfRealized.MODERATE
        ],
        low_severity_fields=field_counts[SeverityIfRealized.LOW],
        undetermined_severity_fields=field_counts[
            SeverityIfRealized.UNDETERMINED
        ],
        critical_severity_datasets=dataset_counts[
            SeverityIfRealized.CRITICAL
        ],
        high_severity_datasets=dataset_counts[SeverityIfRealized.HIGH],
        moderate_severity_datasets=dataset_counts[
            SeverityIfRealized.MODERATE
        ],
        low_severity_datasets=dataset_counts[SeverityIfRealized.LOW],
        undetermined_severity_datasets=dataset_counts[
            SeverityIfRealized.UNDETERMINED
        ],
        unique_context_assets=len(context.context_asset_registry),
        context_relationships=len(context.context_link_registry),
        technical_to_context_mappings=len(
            context.technical_to_context_mappings
        ),
    )


def _criticality_explanation(
    state: ContextCriticality,
    explicit_identity: str | None,
) -> str:
    if state is ContextCriticality.EXPLICITLY_CRITICAL:
        return (
            f"Exact recognized criticality semantic {explicit_identity} "
            "explicitly identifies criticality."
        )
    if state is ContextCriticality.ELEVATED_CONTEXT:
        return (
            "Certified BI consumer context is combined with another context "
            "category, but no explicit criticality designation exists."
        )
    if state is ContextCriticality.STANDARD_CONTEXT:
        return (
            "Certified context exists without a recognized explicit or "
            "combined elevated criticality signal."
        )
    return (
        "Available certified context is insufficient to classify "
        "criticality."
    )


def _severity_explanation(
    subject_id: str,
    consequence: TechnicalConsequence,
    criticality: ContextCriticality,
    breadth: ExposureBreadth,
    certainty: EvidenceCertainty,
    severity: SeverityIfRealized,
) -> str:
    return (
        f"{subject_id} has technical consequence {consequence.value}, "
        f"context criticality {criticality.value}, and structural breadth "
        f"{breadth.value}. Severity-if-realized is {severity.value}; impact "
        f"certainty remains {certainty.value}."
    )


def _canonical_narrative(
    profile: ChangeLevelSeverityProfile,
    metrics: SeverityCriticalityAggregateMetrics,
) -> str:
    return (
        "CHRONOS has not confirmed that the source rename causes failure. "
        "The first Spark boundary remains technically unresolved. If that "
        f"boundary fails, the dependency cone reaches "
        f"{metrics.field_assessments} downstream fields across "
        f"{metrics.dataset_assessments} datasets and connects to "
        f"{metrics.unique_context_assets} unique certified context assets. "
        f"Structural breadth is {profile.exposure_breadth.value}, "
        f"severity-if-realized is {profile.severity_if_realized.value}, and "
        f"impact certainty remains {profile.evidence_certainty.value}. "
        "These dimensions are not a probability or a final decision."
    )


def _category_count(
    assets: tuple[ContextAssetRecord, ...],
    category: ContextCategory,
) -> int:
    return sum(item.category is category for item in assets)


def _record_id(
    prefix: str,
    subject_type: AssessmentSubjectType,
    subject_id: str,
) -> str:
    payload = (
        f"{prefix}\x1f{subject_type.value}\x1f{subject_id}"
    ).encode("utf-8")
    return f"{prefix}-" + hashlib.sha256(payload).hexdigest()[:24]


def _ordered_unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _timestamp(clock: Clock | None) -> str:
    value = clock() if clock is not None else datetime.now(timezone.utc)
    if value.tzinfo is None:
        raise SeverityCriticalityValidationError(
            "Phase 4.3 clock must return a timezone-aware datetime."
        )
    return value.isoformat()
