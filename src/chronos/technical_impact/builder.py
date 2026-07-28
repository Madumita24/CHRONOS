"""Deterministic Phase 4.1 technical-impact derivation."""

from __future__ import annotations

import hashlib
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from chronos.change_semantics import ChangeSemanticContract, load_contract
from chronos.compatibility_evaluation import (
    CompatibilityEvaluationResult,
    CompatibilityState,
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
    CANONICAL_DEMONSTRATION_ID,
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

from .errors import TechnicalImpactEntryError, TechnicalImpactValidationError
from .models import (
    TECHNICAL_IMPACT_SCHEMA_VERSION,
    DatasetTechnicalImpactSummary,
    FieldTechnicalImpact,
    ImpactArtifactReference,
    ImpactCausalChain,
    PathTechnicalImpact,
    RelationshipTechnicalImpact,
    SourceChangeImpact,
    SourceTechnicalRole,
    TechnicalImpactAggregateMetrics,
    TechnicalImpactAnalysis,
    TechnicalImpactCause,
    TechnicalImpactReasonCode,
    TechnicalImpactState,
    TechnicalImpactValidationState,
)


Clock = Callable[[], datetime]
_CURRENT = FieldMachineKey(CANONICAL_DATASET_URN, "order_total")
_CANDIDATE = FieldMachineKey(CANONICAL_DATASET_URN, "order_amount")
_CAUSE_ID = "technical-impact-cause-source-rename-semantics"
_CHAIN_ID = "technical-impact-chain-chronos-demo-001"


def derive_technical_impact_state(
    compatibility_state: CompatibilityState,
) -> tuple[TechnicalImpactState, tuple[TechnicalImpactReasonCode, ...]]:
    """Map certified compatibility to technical consequence without context."""
    if compatibility_state is CompatibilityState.INCOMPATIBLE:
        return (
            TechnicalImpactState.CONFIRMED_IMPACT,
            (
                TechnicalImpactReasonCode.CONFIRMED_INCOMPATIBLE_DEPENDENCY,
            ),
        )
    if compatibility_state is CompatibilityState.UNKNOWN:
        return (
            TechnicalImpactState.UNRESOLVED_IMPACT,
            (
                TechnicalImpactReasonCode.SOURCE_BOUNDARY_UNRESOLVED,
                TechnicalImpactReasonCode.INSUFFICIENT_EVIDENCE,
            ),
        )
    if compatibility_state is CompatibilityState.CONDITIONALLY_COMPATIBLE:
        return (
            TechnicalImpactState.POTENTIAL_IMPACT,
            (
                TechnicalImpactReasonCode.DEPENDS_ON_UNRESOLVED_UPSTREAM,
                TechnicalImpactReasonCode.CONDITIONAL_LOCAL_CONTINUITY,
            ),
        )
    if compatibility_state is CompatibilityState.COMPATIBLE:
        return (
            TechnicalImpactState.NO_DEMONSTRATED_IMPACT,
            (
                TechnicalImpactReasonCode.COMPATIBILITY_CONFIRMED,
                TechnicalImpactReasonCode.NO_TECHNICAL_CONSEQUENCE_OBSERVED,
            ),
        )
    raise TechnicalImpactValidationError(
        f"Unsupported compatibility state: {compatibility_state!r}."
    )


def derive_technical_impact(
    snapshot: CurrentMetadataSnapshot,
    proposal: ChangeProposal,
    validation: ProposalValidationResult,
    contract: ChangeSemanticContract,
    phase2: Phase2CertificationResult,
    source_state: CounterfactualSourceState,
    graph: FutureMetadataGraph,
    propagation: DependencyPropagationResult,
    compatibility: CompatibilityEvaluationResult,
    explanations: ExplanationBundle,
    phase3: Phase3CertificationResult,
    *,
    input_artifact_hashes: tuple[InputArtifactHash, ...],
    clock: Clock | None = None,
) -> TechnicalImpactAnalysis:
    _require_entry(
        snapshot,
        proposal,
        validation,
        contract,
        phase2,
        source_state,
        graph,
        propagation,
        compatibility,
        explanations,
        phase3,
        input_artifact_hashes,
    )
    graph_relationships = {
        item.relationship_id: item for item in graph.relationship_registry
    }
    propagation_relationships = {
        item.relationship_id: item
        for item in propagation.relationship_exposure_registry
    }
    compatibility_relationships = {
        item.relationship_id: item
        for item in compatibility.relationship_evaluations
    }
    propagation_paths = {
        item.path_id: item for item in propagation.path_registry
    }
    compatibility_paths = {
        item.path_id: item for item in compatibility.path_evaluations
    }
    compatibility_fields = {
        item.field_key: item for item in compatibility.field_evaluations
    }
    propagation_fields = {
        item.field_key: item
        for item in propagation.field_exposure_registry
    }
    explanation_relationships = {
        item.relationship_id: item
        for item in explanations.relationship_explanations
    }
    explanation_paths = {
        item.path_id: item for item in explanations.path_explanations
    }
    explanation_fields = {
        item.field_key: item for item in explanations.field_explanations
    }

    source_edge = next(
        item
        for item in compatibility.relationship_evaluations
        if item.upstream_field == _CANDIDATE
    )
    references = _artifact_references(
        snapshot,
        proposal,
        validation,
        contract,
        phase2,
        source_state,
        graph,
        propagation,
        compatibility,
        explanations,
        phase3,
    )
    chain = ImpactCausalChain(
        chain_id=_CHAIN_ID,
        cause_id=_CAUSE_ID,
        ordered_references=references,
    )
    source_change = SourceChangeImpact(
        current_field=_CURRENT,
        candidate_field=_CANDIDATE,
        role=SourceTechnicalRole.CHANGE_ORIGIN,
        proposal_id=proposal.proposal_id,
        human_explanation=(
            "The certified proposal changes the source identity from "
            "orders.order_total to orders.order_amount. This is the change "
            "origin, not a downstream technical-impact record."
        ),
        causal_chain_id=_CHAIN_ID,
    )

    relationship_impacts: list[RelationshipTechnicalImpact] = []
    for item in sorted(
        compatibility.relationship_evaluations,
        key=lambda value: value.relationship_id,
    ):
        state, reasons = derive_technical_impact_state(
            item.compatibility_state
        )
        is_root = item.relationship_id == source_edge.relationship_id
        if is_root:
            human = (
                "The source boundary is dependency-exposed, but available "
                "evidence cannot determine whether the Spark export accepts "
                "the renamed field. Technical impact is UNRESOLVED_IMPACT; "
                "no failure is confirmed."
            )
        elif state is TechnicalImpactState.POTENTIAL_IMPACT:
            human = (
                "Local relationship continuity is conditional, while usable "
                "upstream input depends on the unresolved source boundary. "
                "Technical impact is POTENTIAL_IMPACT, not a confirmed failure."
            )
        else:
            human = _relationship_human(state)
        relationship_impacts.append(
            RelationshipTechnicalImpact(
                relationship_id=item.relationship_id,
                upstream_field=item.upstream_field,
                downstream_field=item.downstream_field,
                exposure_state=(
                    propagation_relationships[item.relationship_id].exposure_state
                ),
                compatibility_state=item.compatibility_state,
                technical_impact_state=state,
                reason_codes=reasons,
                supporting_compatibility_record_id=item.relationship_id,
                supporting_path_ids=item.supporting_path_ids,
                upstream_cause_ids=(_CAUSE_ID,),
                evidence_strength=item.evidence_strength,
                current_provenance_ids=item.current_provenance_ids,
                counterfactual_provenance_ids=(
                    item.counterfactual_provenance_ids
                ),
                explanation_relationship_id=(
                    explanation_relationships[item.relationship_id].relationship_id
                ),
                human_explanation=human,
                causal_chain_id=_CHAIN_ID,
            )
        )
    relationship_impacts_by_id = {
        item.relationship_id: item for item in relationship_impacts
    }

    path_impacts: list[PathTechnicalImpact] = []
    for item in sorted(
        compatibility.path_evaluations,
        key=lambda value: value.path_id,
    ):
        state, reasons = derive_technical_impact_state(
            item.compatibility_state
        )
        path = propagation_paths[item.path_id]
        path_impacts.append(
            PathTechnicalImpact(
                path_id=item.path_id,
                ordered_relationship_ids=item.relationship_ids,
                target_field=item.target_field,
                depth=item.depth,
                compatibility_state=item.compatibility_state,
                technical_impact_state=state,
                reason_codes=reasons,
                relationship_impact_states=tuple(
                    relationship_impacts_by_id[value].technical_impact_state
                    for value in item.relationship_ids
                ),
                uncertain_or_blocking_relationship_ids=tuple(
                    dict.fromkeys(
                        item.blocking_relationship_ids
                        + item.uncertain_relationship_ids
                    )
                ),
                cause_ids=(_CAUSE_ID,),
                current_provenance_ids=item.current_provenance_ids,
                counterfactual_provenance_ids=(
                    item.counterfactual_provenance_ids
                ),
                explanation_path_id=explanation_paths[item.path_id].path_id,
                human_explanation=(
                    f"This {item.depth}-edge path requires the unresolved "
                    "source boundary, so technical impact remains "
                    f"{state.value.upper()}; no path failure is confirmed."
                ),
                causal_chain_id=_CHAIN_ID,
            )
        )
    path_impacts_by_id = {item.path_id: item for item in path_impacts}

    field_impacts: list[FieldTechnicalImpact] = []
    for item in sorted(
        compatibility.field_evaluations,
        key=lambda value: value.field_key.text,
    ):
        state, reasons = derive_technical_impact_state(
            item.compatibility_state
        )
        path_states = tuple(
            path_impacts_by_id[value].technical_impact_state
            for value in item.supporting_path_ids
        )
        field_impacts.append(
            FieldTechnicalImpact(
                field_key=item.field_key,
                dataset_urn=item.field_key.dataset_urn,
                exposure_state=propagation_fields[item.field_key].exposure_state,
                compatibility_state=item.compatibility_state,
                technical_impact_state=state,
                minimum_depth=item.minimum_depth,
                path_count=len(item.supporting_path_ids),
                supporting_path_ids=item.supporting_path_ids,
                supporting_path_impact_states=path_states,
                uncertain_or_blocking_relationship_ids=(
                    explanation_fields[
                        item.field_key
                    ].uncertain_or_blocking_relationship_ids
                ),
                reason_codes=reasons,
                cause_ids=(_CAUSE_ID,),
                current_provenance_ids=item.current_provenance_ids,
                counterfactual_provenance_ids=(
                    item.counterfactual_provenance_ids
                ),
                explanation_field_key=explanation_fields[item.field_key].field_key,
                human_explanation=(
                    f"This downstream field is exposed through "
                    f"{len(item.supporting_path_ids)} distinct path(s). Its "
                    f"technical impact is {state.value.upper()} because every "
                    "supporting path inherits the same unresolved source "
                    "boundary; path count and depth do not determine impact."
                ),
                causal_chain_id=_CHAIN_ID,
            )
        )
    field_impacts_by_key = {
        item.field_key: item for item in field_impacts
    }

    dataset_summaries: list[DatasetTechnicalImpactSummary] = []
    for item in sorted(
        compatibility.dataset_summaries,
        key=lambda value: value.dataset_urn,
    ):
        records = tuple(
            field_impacts_by_key[value] for value in item.exposed_field_keys
        )
        counts = Counter(value.technical_impact_state for value in records)
        dataset_state = _roll_up_dataset_state(counts)
        dataset_summaries.append(
            DatasetTechnicalImpactSummary(
                dataset_urn=item.dataset_urn,
                exposed_field_keys=item.exposed_field_keys,
                confirmed_impacted_fields=counts[
                    TechnicalImpactState.CONFIRMED_IMPACT
                ],
                potential_impacted_fields=counts[
                    TechnicalImpactState.POTENTIAL_IMPACT
                ],
                unresolved_impacted_fields=counts[
                    TechnicalImpactState.UNRESOLVED_IMPACT
                ],
                no_demonstrated_impact_fields=counts[
                    TechnicalImpactState.NO_DEMONSTRATED_IMPACT
                ],
                technical_impact_state=dataset_state,
                cause_ids=(_CAUSE_ID,),
                human_explanation=(
                    f"This technical-only Dataset summary contains "
                    f"{len(records)} exposed field(s): "
                    f"{counts[TechnicalImpactState.CONFIRMED_IMPACT]} confirmed, "
                    f"{counts[TechnicalImpactState.POTENTIAL_IMPACT]} potential, "
                    f"{counts[TechnicalImpactState.UNRESOLVED_IMPACT]} unresolved, "
                    f"and {counts[TechnicalImpactState.NO_DEMONSTRATED_IMPACT]} "
                    "with no demonstrated impact."
                ),
                causal_chain_id=_CHAIN_ID,
            )
        )

    cause = TechnicalImpactCause(
        cause_id=_CAUSE_ID,
        root_relationship_id=source_edge.relationship_id,
        upstream_field=source_edge.upstream_field,
        downstream_field=source_edge.downstream_field,
        impact_state=TechnicalImpactState.UNRESOLVED_IMPACT,
        reason_codes=(
            TechnicalImpactReasonCode.SOURCE_BOUNDARY_UNRESOLVED,
            TechnicalImpactReasonCode.INSUFFICIENT_EVIDENCE,
        ),
        compatibility_reason=source_edge.reason_code,
        evidence_strength=source_edge.evidence_strength,
        affected_relationship_ids=tuple(
            item.relationship_id for item in relationship_impacts
        ),
        affected_path_ids=tuple(item.path_id for item in path_impacts),
        affected_field_keys=tuple(item.field_key for item in field_impacts),
        affected_dataset_urns=tuple(
            item.dataset_urn for item in dataset_summaries
        ),
        human_explanation=(
            "One unresolved technical cause represents whether the Spark "
            "export accepts or adapts to the renamed PostgreSQL input. "
            "Downstream records reference this shared cause rather than "
            "presenting independent failures."
        ),
        causal_chain_id=_CHAIN_ID,
    )
    aggregate = _aggregate(
        (cause,),
        tuple(relationship_impacts),
        tuple(path_impacts),
        tuple(field_impacts),
        tuple(dataset_summaries),
    )
    narrative = _render_narrative(
        source_change,
        aggregate,
        cause,
    )
    result = TechnicalImpactAnalysis(
        schema_version=TECHNICAL_IMPACT_SCHEMA_VERSION,
        demonstration_id=CANONICAL_DEMONSTRATION_ID,
        proposal_id=proposal.proposal_id,
        phase_3_certification_fingerprint=phase3.semantic_fingerprint,
        source_change=source_change,
        technical_impact_causes=(cause,),
        relationship_impacts=tuple(relationship_impacts),
        path_impacts=tuple(path_impacts),
        field_impacts=tuple(field_impacts),
        dataset_summaries=tuple(dataset_summaries),
        causal_chains=(chain,),
        aggregate_metrics=aggregate,
        canonical_narrative=narrative,
        warnings=(),
        input_artifact_hashes=input_artifact_hashes,
        created_at=_timestamp(clock),
        validation_state=TechnicalImpactValidationState.VALID,
    )
    validate_technical_impact(
        result,
        source_state,
        graph,
        propagation,
        compatibility,
        explanations,
        phase3,
    )
    return result


def derive_technical_impact_from_artifacts(
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
    *,
    clock: Clock | None = None,
) -> TechnicalImpactAnalysis:
    paths = (
        ("current_metadata_snapshot.json", Path(snapshot_path)),
        ("change_proposal.json", Path(proposal_path)),
        ("change_proposal_validation.json", Path(validation_path)),
        ("change_semantic_contract.json", Path(contract_path)),
        ("phase_2_certification.json", Path(phase2_path)),
        ("counterfactual_source_state.json", Path(source_state_path)),
        ("future_metadata_graph.json", Path(graph_path)),
        ("dependency_propagation.json", Path(propagation_path)),
        ("compatibility_evaluation.json", Path(compatibility_path)),
        ("explanation_bundle.json", Path(explanations_path)),
        ("phase_3_certification.json", Path(phase3_path)),
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
    after_load = {name: _file_hash(path) for name, path in paths}
    hashes = tuple(
        InputArtifactHash(name, before[name], after_load[name])
        for name, _ in paths
    )
    result = derive_technical_impact(
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
        input_artifact_hashes=hashes,
        clock=clock,
    )
    if {name: _file_hash(path) for name, path in paths} != before:
        raise TechnicalImpactValidationError(
            "An authoritative input changed during technical-impact derivation."
        )
    return result


def validate_technical_impact(
    result: TechnicalImpactAnalysis,
    source_state: CounterfactualSourceState,
    graph: FutureMetadataGraph,
    propagation: DependencyPropagationResult,
    compatibility: CompatibilityEvaluationResult,
    explanations: ExplanationBundle,
    phase3: Phase3CertificationResult,
) -> None:
    issues: list[str] = []

    def require(condition: bool, message: str) -> None:
        if not condition:
            issues.append(message)

    require(
        result.phase_3_certification_fingerprint == phase3.semantic_fingerprint,
        "Phase 3 certification reference mismatch",
    )
    require(
        result.source_change.current_field == _CURRENT
        and result.source_change.candidate_field == _CANDIDATE
        and result.source_change.role is SourceTechnicalRole.CHANGE_ORIGIN,
        "Source change origin mismatch",
    )
    comp_relationships = {
        item.relationship_id: item
        for item in compatibility.relationship_evaluations
    }
    prop_relationships = {
        item.relationship_id: item
        for item in propagation.relationship_exposure_registry
    }
    rel_impacts = {
        item.relationship_id: item for item in result.relationship_impacts
    }
    require(set(rel_impacts) == set(comp_relationships), "Relationship scope mismatch")
    for key, impact in rel_impacts.items():
        if key not in comp_relationships or key not in prop_relationships:
            issues.append(f"Dangling relationship impact: {key}")
            continue
        expected_state, expected_reasons = derive_technical_impact_state(
            comp_relationships[key].compatibility_state
        )
        require(
            impact.compatibility_state
            == comp_relationships[key].compatibility_state
            and impact.exposure_state == prop_relationships[key].exposure_state
            and impact.technical_impact_state == expected_state
            and impact.reason_codes == expected_reasons
            and impact.upstream_field == comp_relationships[key].upstream_field
            and impact.downstream_field == comp_relationships[key].downstream_field
            and impact.supporting_compatibility_record_id == key
            and impact.explanation_relationship_id == key,
            f"Relationship impact changed certified evidence: {key}",
        )
    comp_paths = {item.path_id: item for item in compatibility.path_evaluations}
    prop_paths = {item.path_id: item for item in propagation.path_registry}
    path_impacts = {item.path_id: item for item in result.path_impacts}
    require(set(path_impacts) == set(comp_paths), "Path impact scope mismatch")
    for key, impact in path_impacts.items():
        if key not in comp_paths or key not in prop_paths:
            issues.append(f"Dangling path impact: {key}")
            continue
        expected_state, expected_reasons = derive_technical_impact_state(
            comp_paths[key].compatibility_state
        )
        require(
            impact.ordered_relationship_ids == comp_paths[key].relationship_ids
            and impact.target_field == prop_paths[key].target_field
            and impact.depth == prop_paths[key].depth
            and impact.technical_impact_state == expected_state
            and impact.reason_codes == expected_reasons
            and all(value in rel_impacts for value in impact.ordered_relationship_ids)
            and impact.explanation_path_id == key,
            f"Path impact mismatch: {key}",
        )
    comp_fields = {
        item.field_key: item for item in compatibility.field_evaluations
    }
    prop_fields = {
        item.field_key: item for item in propagation.field_exposure_registry
    }
    field_impacts = {item.field_key: item for item in result.field_impacts}
    require(set(field_impacts) == set(comp_fields), "Field impact scope mismatch")
    require(_CANDIDATE not in field_impacts, "Source counted as downstream impact")
    for key, impact in field_impacts.items():
        if key not in comp_fields or key not in prop_fields:
            issues.append(f"Dangling field impact: {key.text}")
            continue
        expected_state, expected_reasons = derive_technical_impact_state(
            comp_fields[key].compatibility_state
        )
        require(
            impact.supporting_path_ids == comp_fields[key].supporting_path_ids
            and impact.path_count == len(set(impact.supporting_path_ids))
            and impact.minimum_depth == prop_fields[key].minimum_depth
            and impact.exposure_state == prop_fields[key].exposure_state
            and impact.technical_impact_state == expected_state
            and impact.reason_codes == expected_reasons
            and all(value in path_impacts for value in impact.supporting_path_ids)
            and impact.explanation_field_key == key,
            f"Field impact mismatch: {key.text}",
        )
    datasets = {item.dataset_urn: item for item in result.dataset_summaries}
    require(len(datasets) == 20, "Dataset summary count mismatch")
    for item in datasets.values():
        if any(key not in field_impacts for key in item.exposed_field_keys):
            issues.append(f"Dangling Dataset field: {item.dataset_urn}")
            continue
        records = tuple(field_impacts[key] for key in item.exposed_field_keys)
        counts = Counter(value.technical_impact_state for value in records)
        require(
            item.confirmed_impacted_fields
            == counts[TechnicalImpactState.CONFIRMED_IMPACT]
            and item.potential_impacted_fields
            == counts[TechnicalImpactState.POTENTIAL_IMPACT]
            and item.unresolved_impacted_fields
            == counts[TechnicalImpactState.UNRESOLVED_IMPACT]
            and item.no_demonstrated_impact_fields
            == counts[TechnicalImpactState.NO_DEMONSTRATED_IMPACT]
            and item.technical_impact_state == _roll_up_dataset_state(counts),
            f"Dataset aggregation mismatch: {item.dataset_urn}",
        )
    require(
        len(result.relationship_impacts) == 27
        and len(result.path_impacts) == 48
        and len(result.field_impacts) == 25
        and len(result.dataset_summaries) == 20
        and len(result.technical_impact_causes) >= 1,
        "Canonical technical-impact counts mismatch",
    )
    known_provenance = {
        item.provenance_id for item in graph.provenance_registry
    }
    referenced_provenance = {
        value
        for registry in (
            result.relationship_impacts,
            result.path_impacts,
            result.field_impacts,
        )
        for item in registry
        for value in (
            item.current_provenance_ids
            + item.counterfactual_provenance_ids
        )
    }
    require(
        referenced_provenance.issubset(known_provenance),
        "Dangling technical-impact provenance",
    )
    cause_ids = {item.cause_id for item in result.technical_impact_causes}
    require(
        len(cause_ids) == len(result.technical_impact_causes),
        "Duplicate impact cause",
    )
    root = result.technical_impact_causes[0]
    require(
        set(root.affected_relationship_ids) == set(rel_impacts)
        and set(root.affected_path_ids) == set(path_impacts)
        and set(root.affected_field_keys) == set(field_impacts)
        and set(root.affected_dataset_urns) == set(datasets),
        "Root-cause consolidation mismatch",
    )
    expected_reference_fingerprints = {
        item.artifact_name: item.semantic_fingerprint
        for item in phase3.input_artifact_identities
    }
    expected_reference_fingerprints["phase_3_certification.json"] = (
        phase3.semantic_fingerprint
    )
    require(
        any(
            {
                reference.artifact_name: reference.semantic_fingerprint
                for reference in chain.ordered_references
            }
            == expected_reference_fingerprints
            for chain in result.causal_chains
        ),
        "Causal-chain artifact closure mismatch",
    )
    forbidden = (
        "fields are broken",
        "deployment is unsafe",
        "high risk",
        "fix spark",
        "notify the",
    )
    text = result.to_json().lower()
    require(
        all(value not in text for value in forbidden),
        "Unsupported later-phase conclusion exists",
    )
    expected_narrative = _render_narrative(
        result.source_change,
        result.aggregate_metrics,
        root,
    )
    require(
        result.canonical_narrative == expected_narrative,
        "Canonical narrative is not derived from typed evidence",
    )
    if issues:
        raise TechnicalImpactValidationError("; ".join(issues))


def _require_entry(
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
    hashes: tuple[InputArtifactHash, ...],
) -> None:
    try:
        validate_phase3_certification(phase3)
        validate_counterfactual_source_state(
            source, snapshot, proposal, validation, contract, phase2
        )
        validate_future_metadata_graph(
            graph,
            snapshot,
            proposal,
            validation,
            contract,
            phase2,
            source,
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
    except ValueError as exc:
        raise TechnicalImpactEntryError(
            "Certified Phase 3 entry validation failed."
        ) from exc
    if (
        snapshot.validation_result.state is not SnapshotValidationState.VALID
        or phase2.certification_state is not Phase2CertificationState.CERTIFIED
        or phase3.certification_status
        is not Phase3CertificationStatus.CERTIFIED
        or phase3_certification_semantic_fingerprint(phase3)
        != phase3.semantic_fingerprint
        or proposal.change_type is not ChangeType.FIELD_RENAME
    ):
        raise TechnicalImpactEntryError(
            "A required certification state or fingerprint is invalid."
        )
    semantic_objects = (
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
    )
    expected_names = tuple(
        item.artifact_name for item in phase3.input_artifact_identities
    )
    hash_by_name = {item.artifact_name: item for item in hashes}
    if len(hashes) != 11 or any(not item.unchanged for item in hashes):
        raise TechnicalImpactEntryError(
            "All eleven technical-impact inputs must remain unchanged."
        )
    for identity, obj in zip(
        phase3.input_artifact_identities,
        semantic_objects,
    ):
        if (
            identity.semantic_fingerprint != obj.semantic_fingerprint
            or identity.artifact_name not in hash_by_name
            or identity.physical_sha256
            != hash_by_name[identity.artifact_name].before_sha256
        ):
            raise TechnicalImpactEntryError(
                "Phase 3 predecessor identity or physical hash mismatch."
            )
    if tuple(hash_by_name)[:10] != expected_names:
        raise TechnicalImpactEntryError(
            "Phase 3 predecessor artifact ordering mismatch."
        )


def _artifact_references(
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
) -> tuple[ImpactArtifactReference, ...]:
    return tuple(
        ImpactArtifactReference(name, obj.semantic_fingerprint, object_id)
        for name, obj, object_id in (
            (
                "current_metadata_snapshot.json",
                snapshot,
                snapshot.metadata.snapshot_id,
            ),
            ("change_proposal.json", proposal, proposal.proposal_id),
            (
                "change_proposal_validation.json",
                validation,
                validation.proposal_id,
            ),
            ("change_semantic_contract.json", contract, contract.proposal_id),
            (
                "phase_2_certification.json",
                phase2,
                phase2.demonstration_id,
            ),
            ("counterfactual_source_state.json", source, _CANDIDATE.text),
            ("future_metadata_graph.json", graph, graph.demonstration_id),
            (
                "dependency_propagation.json",
                propagation,
                propagation.source_candidate_field.text,
            ),
            (
                "compatibility_evaluation.json",
                compatibility,
                compatibility.proposal_id,
            ),
            (
                "explanation_bundle.json",
                explanations,
                explanations.demonstration_id,
            ),
            (
                "phase_3_certification.json",
                phase3,
                phase3.demonstration_id,
            ),
        )
    )


def _aggregate(
    causes: tuple[TechnicalImpactCause, ...],
    relationships: tuple[RelationshipTechnicalImpact, ...],
    paths: tuple[PathTechnicalImpact, ...],
    fields_: tuple[FieldTechnicalImpact, ...],
    datasets: tuple[DatasetTechnicalImpactSummary, ...],
) -> TechnicalImpactAggregateMetrics:
    relationship_counts = Counter(
        item.technical_impact_state for item in relationships
    )
    path_counts = Counter(item.technical_impact_state for item in paths)
    field_counts = Counter(item.technical_impact_state for item in fields_)
    return TechnicalImpactAggregateMetrics(
        technical_impact_causes=len(causes),
        confirmed_impacted_relationships=relationship_counts[
            TechnicalImpactState.CONFIRMED_IMPACT
        ],
        potential_impacted_relationships=relationship_counts[
            TechnicalImpactState.POTENTIAL_IMPACT
        ],
        unresolved_relationships=relationship_counts[
            TechnicalImpactState.UNRESOLVED_IMPACT
        ],
        no_demonstrated_impact_relationships=relationship_counts[
            TechnicalImpactState.NO_DEMONSTRATED_IMPACT
        ],
        confirmed_impacted_paths=path_counts[
            TechnicalImpactState.CONFIRMED_IMPACT
        ],
        potential_impacted_paths=path_counts[
            TechnicalImpactState.POTENTIAL_IMPACT
        ],
        unresolved_paths=path_counts[
            TechnicalImpactState.UNRESOLVED_IMPACT
        ],
        no_demonstrated_impact_paths=path_counts[
            TechnicalImpactState.NO_DEMONSTRATED_IMPACT
        ],
        confirmed_impacted_fields=field_counts[
            TechnicalImpactState.CONFIRMED_IMPACT
        ],
        potential_impacted_fields=field_counts[
            TechnicalImpactState.POTENTIAL_IMPACT
        ],
        unresolved_fields=field_counts[
            TechnicalImpactState.UNRESOLVED_IMPACT
        ],
        no_demonstrated_impact_fields=field_counts[
            TechnicalImpactState.NO_DEMONSTRATED_IMPACT
        ],
        downstream_dataset_summaries=len(datasets),
    )


def _roll_up_dataset_state(
    counts: Counter[TechnicalImpactState],
) -> TechnicalImpactState:
    for state in (
        TechnicalImpactState.CONFIRMED_IMPACT,
        TechnicalImpactState.UNRESOLVED_IMPACT,
        TechnicalImpactState.POTENTIAL_IMPACT,
        TechnicalImpactState.NO_DEMONSTRATED_IMPACT,
    ):
        if counts[state]:
            return state
    raise TechnicalImpactValidationError(
        "Dataset technical-impact summary has no evaluated fields."
    )


def _render_narrative(
    source: SourceChangeImpact,
    aggregate: TechnicalImpactAggregateMetrics,
    cause: TechnicalImpactCause,
) -> str:
    return (
        f"The proposed rename changes PostgreSQL "
        f"orders.{source.current_field.field_path} to "
        f"{source.candidate_field.field_path}. CHRONOS identified "
        f"{aggregate.unresolved_fields} downstream fields across "
        f"{aggregate.downstream_dataset_summaries} datasets that depend on "
        "this source. The first dependency boundary, from PostgreSQL "
        f"{cause.upstream_field.field_path} to S3 "
        f"{cause.downstream_field.field_path}, cannot be verified from "
        "available transform or query metadata. Therefore CHRONOS has not "
        "confirmed downstream breakage. The downstream dependency cone "
        "inherits technical uncertainty from this single unresolved source "
        "boundary."
    )


def _relationship_human(state: TechnicalImpactState) -> str:
    if state is TechnicalImpactState.CONFIRMED_IMPACT:
        return (
            "Explicit incompatibility establishes CONFIRMED_IMPACT for this "
            "technical dependency."
        )
    if state is TechnicalImpactState.NO_DEMONSTRATED_IMPACT:
        return (
            "Certified compatibility establishes NO_DEMONSTRATED_IMPACT "
            "within the modeled technical change."
        )
    return f"Technical impact is {state.value.upper()}."


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _timestamp(clock: Clock | None) -> str:
    value = (clock or (lambda: datetime.now(timezone.utc)))()
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()
