"""Deterministic Phase 3.5 evidence and explanation projection."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

from chronos.change_semantics import ChangeSemanticContract, load_contract
from chronos.compatibility_evaluation import (
    CompatibilityEvaluationResult,
    CompatibilityReasonCode,
    CompatibilityState,
    CompatibilityValidationState,
    load_compatibility_evaluation,
    compatibility_semantic_fingerprint,
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
    propagation_semantic_fingerprint,
    validate_dependency_propagation,
)
from chronos.future_graph import (
    FutureMetadataGraph,
    load_future_graph,
    future_graph_semantic_fingerprint,
    validate_future_metadata_graph,
)
from chronos.phase2_certification import (
    Phase2CertificationResult,
    Phase2CertificationState,
    load_certification,
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
    load_snapshot,
)

from .errors import (
    ExplanationEntryPreconditionError,
    ExplanationValidationError,
)
from .models import (
    EXPLANATION_BUNDLE_SCHEMA_VERSION,
    ArtifactEvidenceReference,
    DatasetExplanation,
    EvidenceChain,
    ExplanationBundle,
    ExplanationClassification,
    ExplanationStep,
    ExplanationStepType,
    ExplanationValidationState,
    FieldExplanation,
    PathExplanation,
    RelationshipExplanation,
    SourceExplanation,
    UncertaintyRecord,
)


Clock = Callable[[], datetime]
_CURRENT = FieldMachineKey(CANONICAL_DATASET_URN, "order_total")
_CANDIDATE = FieldMachineKey(CANONICAL_DATASET_URN, "order_amount")
_CHAIN_ID = "evidence-chain-chronos-demo-001"
_ROOT_UNCERTAINTY = "uncertainty-source-rename-boundary"


def build_explanation_bundle(
    snapshot: CurrentMetadataSnapshot,
    proposal: ChangeProposal,
    validation: ProposalValidationResult,
    contract: ChangeSemanticContract,
    certification: Phase2CertificationResult,
    source_state: CounterfactualSourceState,
    future_graph: FutureMetadataGraph,
    propagation: DependencyPropagationResult,
    compatibility: CompatibilityEvaluationResult,
    *,
    input_artifact_hashes: tuple[InputArtifactHash, ...],
    clock: Clock | None = None,
) -> ExplanationBundle:
    _require_preconditions(
        snapshot,
        proposal,
        validation,
        contract,
        certification,
        source_state,
        future_graph,
        propagation,
        compatibility,
        input_artifact_hashes,
    )
    graph_relationships = {
        item.relationship_id: item
        for item in future_graph.relationship_registry
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
    graph_fields = {item.key: item for item in future_graph.field_registry}

    chain = EvidenceChain(
        chain_id=_CHAIN_ID,
        references=(
            ArtifactEvidenceReference(
                "current_metadata_snapshot.json",
                snapshot.semantic_fingerprint,
                snapshot.metadata.snapshot_id,
            ),
            ArtifactEvidenceReference(
                "change_proposal.json",
                proposal.semantic_fingerprint,
                proposal.proposal_id,
            ),
            ArtifactEvidenceReference(
                "change_proposal_validation.json",
                validation.semantic_fingerprint,
                proposal.proposal_id,
            ),
            ArtifactEvidenceReference(
                "change_semantic_contract.json",
                contract.semantic_fingerprint,
                proposal.proposal_id,
            ),
            ArtifactEvidenceReference(
                "phase_2_certification.json",
                certification.semantic_fingerprint,
                proposal.proposal_id,
            ),
            ArtifactEvidenceReference(
                "counterfactual_source_state.json",
                source_state.semantic_fingerprint,
                _CANDIDATE.text,
            ),
            ArtifactEvidenceReference(
                "future_metadata_graph.json",
                future_graph.semantic_fingerprint,
                _CANDIDATE.text,
            ),
            ArtifactEvidenceReference(
                "dependency_propagation.json",
                propagation.semantic_fingerprint,
                _CANDIDATE.text,
            ),
            ArtifactEvidenceReference(
                "compatibility_evaluation.json",
                compatibility.semantic_fingerprint,
                proposal.proposal_id,
            ),
        ),
    )
    current_field = snapshot.field_by_key()[_CURRENT]
    source_steps = (
        _step(
            "source-current",
            ExplanationStepType.CURRENT_FACT,
            _CURRENT.text,
            "CURRENT_SOURCE_CERTIFIED",
            (
                "DataHub currently records PostgreSQL orders.order_total as "
                "DOUBLE PRECISION / Number, nullable=true, part_of_key=false."
            ),
            "current_metadata_snapshot.json",
            _CURRENT.text,
            current_field.evidence_ids,
            ExplanationClassification.VERIFIED_CURRENT,
        ),
        _step(
            "source-proposal",
            ExplanationStepType.PROPOSED_CHANGE,
            _CURRENT.text,
            "FIELD_RENAME_PROPOSED",
            "The certified proposal renames order_total to order_amount.",
            "change_proposal.json",
            proposal.proposal_id,
            (),
            ExplanationClassification.PROPOSED,
        ),
        _step(
            "source-counterfactual",
            ExplanationStepType.COUNTERFACTUAL_DERIVATION,
            _CANDIDATE.text,
            "SOURCE_IDENTITY_PROJECTED",
            (
                "CHRONOS projects PostgreSQL orders.order_amount while "
                "preserving Dataset identity, type, nullability, and key state."
            ),
            "counterfactual_source_state.json",
            _CANDIDATE.text,
            source_state.candidate_source_schema.current_evidence_ids,
            ExplanationClassification.COUNTERFACTUAL,
        ),
    )
    source_explanation = SourceExplanation(
        current_field=_CURRENT,
        candidate_field=_CANDIDATE,
        current_native_type=current_field.native_type,
        current_normalized_type=current_field.normalized_type,
        nullable=current_field.nullable,
        is_part_of_key=current_field.is_part_of_key,
        preserved_properties=(
            "dataset_identity",
            "native_type",
            "normalized_type",
            "nullable",
            "is_part_of_key",
        ),
        steps=source_steps,
        human_explanation=" ".join(item.human_statement for item in source_steps),
        evidence_chain_id=_CHAIN_ID,
    )

    source_edge = next(
        item
        for item in compatibility.relationship_evaluations
        if item.upstream_field == _CANDIDATE
    )
    uncertainty = UncertaintyRecord(
        uncertainty_id=_ROOT_UNCERTAINTY,
        subject=source_edge.relationship_id,
        reason_code=CompatibilityReasonCode.SOURCE_RENAME_SEMANTICS_UNKNOWN,
        missing_evidence_types=(
            "spark_transformation_configuration",
            "input_column_reference_query_or_code",
            "explicit_rename_mapping",
            "validated_execution_result",
        ),
        affected_relationship_ids=tuple(
            item.relationship_id
            for item in compatibility.relationship_evaluations
        ),
        affected_path_ids=tuple(
            item.path_id for item in compatibility.path_evaluations
        ),
        affected_field_keys=tuple(
            item.field_key for item in compatibility.field_evaluations
        ),
        upstream_uncertainty_ids=(),
        human_explanation=(
            "CHRONOS cannot determine whether the Spark export accepts the "
            "renamed input because captured metadata contains neither transform "
            "nor query semantics for that boundary."
        ),
        evidence_chain_id=_CHAIN_ID,
    )

    relationship_explanations: list[RelationshipExplanation] = []
    for evaluated in sorted(
        compatibility.relationship_evaluations,
        key=lambda item: item.relationship_id,
    ):
        graph_record = graph_relationships[evaluated.relationship_id]
        exposure = propagation_relationships[evaluated.relationship_id]
        is_source = evaluated.relationship_id == source_edge.relationship_id
        current_statement = (
            f"DataHub currently records {graph_record.current_upstream.text} "
            f"feeding {graph_record.current_downstream.text}."
        )
        structural_statement = (
            f"CHRONOS projects {graph_record.upstream.text} feeding "
            f"{graph_record.downstream.text} as counterfactual structure."
        )
        if is_source:
            evidence_statement = (
                "CHRONOS cannot determine whether the Spark export accepts "
                "order_amount: transform and query evidence are absent; lineage "
                "confidence 0.5 is provenance only and does not establish "
                "candidate compatibility."
            )
        else:
            evidence_statement = (
                "The proposal does not directly change the local endpoint "
                "identities. Local structural continuity is conditional on "
                "upstream availability and is not end-to-end compatibility."
            )
        steps = (
            _step(
                f"relationship-{evaluated.relationship_id}-current",
                ExplanationStepType.CURRENT_FACT,
                evaluated.relationship_id,
                "CURRENT_LINEAGE_RECORDED",
                current_statement,
                "current_metadata_snapshot.json",
                graph_record.current_edge_id,
                graph_record.current_evidence_ids,
                ExplanationClassification.VERIFIED_CURRENT,
            ),
            _step(
                f"relationship-{evaluated.relationship_id}-structure",
                ExplanationStepType.STRUCTURAL_DEPENDENCY,
                evaluated.relationship_id,
                "COUNTERFACTUAL_STRUCTURE_PROJECTED",
                structural_statement,
                "future_metadata_graph.json",
                evaluated.relationship_id,
                evaluated.counterfactual_provenance_ids,
                ExplanationClassification.COUNTERFACTUAL,
            ),
            _step(
                f"relationship-{evaluated.relationship_id}-exposure",
                ExplanationStepType.DEPENDENCY_EXPOSURE,
                evaluated.relationship_id,
                evaluated.exposure_state.value.upper(),
                f"Phase 3.3 classifies this edge {evaluated.exposure_state.value}.",
                "dependency_propagation.json",
                evaluated.relationship_id,
                evaluated.current_provenance_ids,
                ExplanationClassification.DERIVED,
            ),
            _step(
                f"relationship-{evaluated.relationship_id}-evidence",
                (
                    ExplanationStepType.COMPATIBILITY_UNCERTAINTY
                    if is_source
                    else ExplanationStepType.COMPATIBILITY_EVIDENCE
                ),
                evaluated.relationship_id,
                evaluated.reason_code.value.upper(),
                evidence_statement,
                "compatibility_evaluation.json",
                evaluated.relationship_id,
                evaluated.current_provenance_ids
                + evaluated.counterfactual_provenance_ids,
                (
                    ExplanationClassification.INSUFFICIENT
                    if is_source
                    else ExplanationClassification.DERIVED
                ),
            ),
            _step(
                f"relationship-{evaluated.relationship_id}-conclusion",
                ExplanationStepType.CONCLUSION,
                evaluated.relationship_id,
                evaluated.compatibility_state.value.upper(),
                (
                    "The existing Phase 3.4 relationship conclusion is "
                    f"{evaluated.compatibility_state.value.upper()}."
                ),
                "compatibility_evaluation.json",
                evaluated.relationship_id,
                (),
                ExplanationClassification.CONCLUSION,
            ),
        )
        relationship_explanations.append(
            RelationshipExplanation(
                relationship_id=evaluated.relationship_id,
                current_upstream=graph_record.current_upstream,
                current_downstream=graph_record.current_downstream,
                candidate_upstream=evaluated.upstream_field,
                candidate_downstream=evaluated.downstream_field,
                exposure_state=exposure.exposure_state,
                compatibility_state=evaluated.compatibility_state,
                evidence_strength=evaluated.evidence_strength,
                reason_codes=(evaluated.reason_code,),
                transform_operations=evaluated.transform_operations,
                query_evidence=evaluated.query_evidence,
                lineage_confidence_provenance=(
                    evaluated.lineage_confidence_provenance
                ),
                mapping_group_ids=evaluated.mapping_group_ids,
                uncertainty_ids=(_ROOT_UNCERTAINTY,),
                steps=steps,
                human_explanation=" ".join(
                    item.human_statement for item in steps
                ),
                evidence_chain_id=_CHAIN_ID,
            )
        )

    path_explanations: list[PathExplanation] = []
    for evaluated in sorted(
        compatibility.path_evaluations,
        key=lambda item: item.path_id,
    ):
        source = propagation_paths[evaluated.path_id]
        unresolved_ids = set(
            evaluated.blocking_relationship_ids
            + evaluated.uncertain_relationship_ids
        )
        first = next(
            (
                relationship_id
                for relationship_id in evaluated.relationship_ids
                if relationship_id in unresolved_ids
            ),
            None,
        )
        steps = (
            _step(
                f"path-{evaluated.path_id}-structure",
                ExplanationStepType.STRUCTURAL_DEPENDENCY,
                evaluated.path_id,
                "ORDERED_STRUCTURAL_PATH",
                (
                    f"CHRONOS projects a {evaluated.depth}-edge structural path "
                    f"to {evaluated.target_field.text}."
                ),
                "dependency_propagation.json",
                evaluated.path_id,
                source.current_provenance_ids
                + source.counterfactual_provenance_ids,
                ExplanationClassification.COUNTERFACTUAL,
            ),
            _step(
                f"path-{evaluated.path_id}-uncertainty",
                ExplanationStepType.COMPATIBILITY_UNCERTAINTY,
                evaluated.path_id,
                evaluated.reason_codes[0].value.upper(),
                (
                    f"The first uncertain or blocking edge is {first}."
                    if first is not None
                    else "No uncertain or blocking edge is present."
                ),
                "compatibility_evaluation.json",
                evaluated.path_id,
                (),
                ExplanationClassification.INSUFFICIENT,
            ),
            _step(
                f"path-{evaluated.path_id}-conclusion",
                ExplanationStepType.CONCLUSION,
                evaluated.path_id,
                evaluated.compatibility_state.value.upper(),
                (
                    "The existing Phase 3.4 end-to-end path conclusion is "
                    f"{evaluated.compatibility_state.value.upper()}."
                ),
                "compatibility_evaluation.json",
                evaluated.path_id,
                (),
                ExplanationClassification.CONCLUSION,
            ),
        )
        path_explanations.append(
            PathExplanation(
                path_id=evaluated.path_id,
                ordered_fields=source.node_keys,
                ordered_relationship_ids=evaluated.relationship_ids,
                depth=evaluated.depth,
                edge_compatibility_states=(
                    evaluated.edge_compatibility_states
                ),
                first_uncertain_or_blocking_relationship_id=first,
                compatibility_state=evaluated.compatibility_state,
                reason_codes=evaluated.reason_codes,
                uncertainty_ids=(_ROOT_UNCERTAINTY,),
                steps=steps,
                human_explanation=" ".join(
                    item.human_statement for item in steps
                ),
                current_provenance_ids=evaluated.current_provenance_ids,
                counterfactual_provenance_ids=(
                    evaluated.counterfactual_provenance_ids
                ),
                evidence_chain_id=_CHAIN_ID,
            )
        )
    paths_by_id = {item.path_id: item for item in path_explanations}

    field_explanations: list[FieldExplanation] = []
    for evaluated in compatibility.field_evaluations:
        exposure = propagation_fields[evaluated.field_key]
        paths = tuple(paths_by_id[value] for value in evaluated.supporting_path_ids)
        first_edges = {
            item.first_uncertain_or_blocking_relationship_id for item in paths
        }
        path_states = {item.compatibility_state for item in paths}
        graph_field = graph_fields[evaluated.field_key]
        steps = (
            _step(
                f"field-{evaluated.field_key.text}-exposure",
                ExplanationStepType.DEPENDENCY_EXPOSURE,
                evaluated.field_key.text,
                evaluated.exposure_state.value.upper(),
                (
                    f"Phase 3.3 exposes this field at minimum depth "
                    f"{evaluated.minimum_depth} through "
                    f"{evaluated.supporting_path_count} path(s)."
                ),
                "dependency_propagation.json",
                evaluated.field_key.text,
                exposure.current_provenance_ids,
                ExplanationClassification.DERIVED,
            ),
            _step(
                f"field-{evaluated.field_key.text}-uncertainty",
                ExplanationStepType.COMPATIBILITY_UNCERTAINTY,
                evaluated.field_key.text,
                evaluated.reason_codes[0].value.upper(),
                (
                    f"All {len(paths)} supporting path(s) retain the unresolved "
                    "source boundary."
                ),
                "compatibility_evaluation.json",
                evaluated.field_key.text,
                evaluated.current_provenance_ids,
                ExplanationClassification.INSUFFICIENT,
            ),
            _step(
                f"field-{evaluated.field_key.text}-conclusion",
                ExplanationStepType.CONCLUSION,
                evaluated.field_key.text,
                evaluated.compatibility_state.value.upper(),
                (
                    "The existing Phase 3.4 field conclusion is "
                    f"{evaluated.compatibility_state.value.upper()}."
                ),
                "compatibility_evaluation.json",
                evaluated.field_key.text,
                (),
                ExplanationClassification.CONCLUSION,
            ),
        )
        field_explanations.append(
            FieldExplanation(
                field_key=evaluated.field_key,
                platform=graph_field.platform,
                dataset_urn=evaluated.field_key.dataset_urn,
                minimum_depth=evaluated.minimum_depth,
                exposure_state=evaluated.exposure_state,
                supporting_path_ids=evaluated.supporting_path_ids,
                incoming_relationship_ids=evaluated.incoming_relationship_ids,
                compatibility_state=evaluated.compatibility_state,
                reason_codes=evaluated.reason_codes,
                uncertain_or_blocking_relationship_ids=tuple(
                    sorted(
                        {
                            relationship_id
                            for item in paths
                            for relationship_id in (
                                ()
                                if item.first_uncertain_or_blocking_relationship_id
                                is None
                                else (
                                    item.first_uncertain_or_blocking_relationship_id,
                                )
                            )
                        }
                    )
                ),
                all_paths_share_first_uncertainty=len(first_edges) == 1,
                path_conclusions_differ=len(path_states) > 1,
                uncertainty_ids=(_ROOT_UNCERTAINTY,),
                steps=steps,
                human_explanation=" ".join(
                    item.human_statement for item in steps
                ),
                current_provenance_ids=evaluated.current_provenance_ids,
                counterfactual_provenance_ids=(
                    evaluated.counterfactual_provenance_ids
                ),
                evidence_chain_id=_CHAIN_ID,
            )
        )

    dataset_explanations: list[DatasetExplanation] = []
    for item in compatibility.dataset_summaries:
        statement = (
            f"This Dataset has {len(item.exposed_field_keys)} exposed field(s): "
            f"{item.compatible_exposed_fields} compatible, "
            f"{item.conditionally_compatible_exposed_fields} conditional, "
            f"{item.incompatible_exposed_fields} incompatible, and "
            f"{item.unknown_exposed_fields} unknown. This is a technical "
            "compatibility summary of exposed fields, not a business-impact "
            "or health verdict."
        )
        steps = (
            _step(
                f"dataset-{item.dataset_urn}-summary",
                ExplanationStepType.COMPATIBILITY_EVIDENCE,
                item.dataset_urn,
                "EXPOSED_FIELD_COMPATIBILITY_SUMMARY",
                statement,
                "compatibility_evaluation.json",
                item.dataset_urn,
                (),
                ExplanationClassification.DERIVED,
            ),
            _step(
                f"dataset-{item.dataset_urn}-conclusion",
                ExplanationStepType.CONCLUSION,
                item.dataset_urn,
                item.compatibility_state.value.upper(),
                (
                    "The existing Phase 3.4 Dataset rollup conclusion is "
                    f"{item.compatibility_state.value.upper()}."
                ),
                "compatibility_evaluation.json",
                item.dataset_urn,
                (),
                ExplanationClassification.CONCLUSION,
            ),
        )
        dataset_explanations.append(
            DatasetExplanation(
                dataset_urn=item.dataset_urn,
                exposed_field_keys=item.exposed_field_keys,
                compatible_fields=item.compatible_exposed_fields,
                incompatible_fields=item.incompatible_exposed_fields,
                conditionally_compatible_fields=(
                    item.conditionally_compatible_exposed_fields
                ),
                unknown_fields=item.unknown_exposed_fields,
                compatibility_state=item.compatibility_state,
                steps=steps,
                human_explanation=" ".join(
                    value.human_statement for value in steps
                ),
                evidence_chain_id=_CHAIN_ID,
            )
        )

    canonical_narrative = _render_canonical_narrative(
        source_explanation,
        next(
            item
            for item in relationship_explanations
            if item.relationship_id == source_edge.relationship_id
        ),
        tuple(path_explanations),
        tuple(relationship_explanations),
    )
    bundle = ExplanationBundle(
        schema_version=EXPLANATION_BUNDLE_SCHEMA_VERSION,
        demonstration_id=CANONICAL_DEMONSTRATION_ID,
        compatibility_fingerprint=compatibility.semantic_fingerprint,
        future_graph_fingerprint=future_graph.semantic_fingerprint,
        propagation_fingerprint=propagation.semantic_fingerprint,
        source_explanation=source_explanation,
        relationship_explanations=tuple(relationship_explanations),
        path_explanations=tuple(path_explanations),
        field_explanations=tuple(field_explanations),
        dataset_explanations=tuple(dataset_explanations),
        uncertainties=(uncertainty,),
        evidence_chains=(chain,),
        canonical_narrative=canonical_narrative,
        input_artifact_hashes=input_artifact_hashes,
        created_at=_timestamp(clock),
        validation_state=ExplanationValidationState.VALID,
    )
    validate_explanation_bundle(
        bundle,
        snapshot,
        source_state,
        future_graph,
        propagation,
        compatibility,
    )
    return bundle


def _render_canonical_narrative(
    source: SourceExplanation,
    first_boundary: RelationshipExplanation,
    paths: tuple[PathExplanation, ...],
    relationships: tuple[RelationshipExplanation, ...],
) -> str:
    """Render the demo narrative exclusively from typed explanation records."""
    unknown_paths = sum(
        item.compatibility_state is CompatibilityState.UNKNOWN for item in paths
    )
    conditional_relationships = sum(
        item.compatibility_state
        is CompatibilityState.CONDITIONALLY_COMPATIBLE
        for item in relationships
    )
    mapping_kind = (
        "Spark export mapping"
        if any(
            "spark," in value.lower()
            for value in first_boundary.mapping_group_ids
        )
        else "captured lineage mapping"
    )
    missing_semantics = (
        not first_boundary.transform_operations
        and not first_boundary.query_evidence
    )
    evidence_statement = (
        "The current metadata does not contain transform or query evidence "
        "showing that the mapping references or adapts to the renamed field."
        if missing_semantics
        else "The captured transform or query evidence is retained in the "
        "typed boundary explanation."
    )
    return (
        f"CHRONOS verified that PostgreSQL "
        f"orders.{source.current_field.field_path} currently feeds S3 "
        f"orders.{first_boundary.current_downstream.field_path} through a "
        f"{mapping_kind}. The proposed change replaces the PostgreSQL source "
        f"field with {source.candidate_field.field_path}. {evidence_statement} "
        f"CHRONOS therefore preserves this boundary as "
        f"{first_boundary.compatibility_state.value.upper()}. All "
        f"{unknown_paths} downstream dependency paths pass through this "
        "unresolved boundary, so their end-to-end compatibility remains "
        f"{CompatibilityState.UNKNOWN.value.upper()} even though "
        f"{conditional_relationships} downstream relationships retain "
        "conditionally compatible local structure."
    )


def build_explanation_bundle_from_artifacts(
    snapshot_path: str | Path,
    proposal_path: str | Path,
    validation_path: str | Path,
    contract_path: str | Path,
    certification_path: str | Path,
    source_state_path: str | Path,
    future_graph_path: str | Path,
    propagation_path: str | Path,
    compatibility_path: str | Path,
    *,
    clock: Clock | None = None,
) -> ExplanationBundle:
    paths = (
        ("current_metadata_snapshot.json", Path(snapshot_path)),
        ("change_proposal.json", Path(proposal_path)),
        ("change_proposal_validation.json", Path(validation_path)),
        ("change_semantic_contract.json", Path(contract_path)),
        ("phase_2_certification.json", Path(certification_path)),
        ("counterfactual_source_state.json", Path(source_state_path)),
        ("future_metadata_graph.json", Path(future_graph_path)),
        ("dependency_propagation.json", Path(propagation_path)),
        ("compatibility_evaluation.json", Path(compatibility_path)),
    )
    before = {name: _file_hash(path) for name, path in paths}
    snapshot = load_snapshot(snapshot_path)
    proposal = load_proposal(proposal_path)
    validation = load_validation_result(validation_path)
    contract = load_contract(contract_path)
    certification = load_certification(certification_path)
    source_state = load_source_state(source_state_path)
    future_graph = load_future_graph(future_graph_path)
    propagation = load_dependency_propagation(propagation_path)
    compatibility = load_compatibility_evaluation(compatibility_path)
    after_load = {name: _file_hash(path) for name, path in paths}
    hashes = tuple(
        InputArtifactHash(name, before[name], after_load[name])
        for name, _ in paths
    )
    bundle = build_explanation_bundle(
        snapshot,
        proposal,
        validation,
        contract,
        certification,
        source_state,
        future_graph,
        propagation,
        compatibility,
        input_artifact_hashes=hashes,
        clock=clock,
    )
    if {name: _file_hash(path) for name, path in paths} != before:
        raise ExplanationValidationError(
            "An authoritative artifact changed during explanation generation."
        )
    return bundle


def validate_explanation_bundle(
    bundle: ExplanationBundle,
    snapshot: CurrentMetadataSnapshot,
    source_state: CounterfactualSourceState,
    future_graph: FutureMetadataGraph,
    propagation: DependencyPropagationResult,
    compatibility: CompatibilityEvaluationResult,
) -> None:
    issues: list[str] = []

    def require(condition: bool, message: str) -> None:
        if not condition:
            issues.append(message)

    require(
        bundle.compatibility_fingerprint == compatibility.semantic_fingerprint
        and bundle.future_graph_fingerprint == future_graph.semantic_fingerprint
        and bundle.propagation_fingerprint == propagation.semantic_fingerprint,
        "Explanation fingerprint chain mismatch",
    )
    require(
        bundle.source_explanation.current_field == snapshot.source_field_key
        and bundle.source_explanation.candidate_field
        == next(
            (
                FieldMachineKey(
                    item.candidate_identity.dataset_urn,
                    item.candidate_identity.field_path,
                )
                for item in source_state.field_identity_mappings
                if item.current_identity.machine_key
                == (
                    snapshot.source_field_key.dataset_urn,
                    snapshot.source_field_key.field_path,
                )
            ),
            None,
        ),
        "Source explanation mismatch",
    )
    current_source = snapshot.field_by_key().get(snapshot.source_field_key)
    require(
        current_source is not None
        and bundle.source_explanation.current_native_type
        == current_source.native_type
        and bundle.source_explanation.current_normalized_type
        == current_source.normalized_type
        and bundle.source_explanation.nullable == current_source.nullable
        and bundle.source_explanation.is_part_of_key
        == current_source.is_part_of_key,
        "Source current-state evidence mismatch",
    )
    graph_rel = {
        item.relationship_id: item for item in future_graph.relationship_registry
    }
    propagation_rel = {
        item.relationship_id: item
        for item in propagation.relationship_exposure_registry
    }
    rel = {item.relationship_id: item for item in bundle.relationship_explanations}
    comp_rel = {
        item.relationship_id: item
        for item in compatibility.relationship_evaluations
    }
    require(set(rel) == set(comp_rel), "Relationship explanation scope mismatch")
    for key, item in rel.items():
        if (
            key not in comp_rel
            or key not in graph_rel
            or key not in propagation_rel
        ):
            issues.append(f"Unknown relationship explanation subject: {key}")
            continue
        require(
            item.compatibility_state == comp_rel[key].compatibility_state
            and item.exposure_state == propagation_rel[key].exposure_state
            and item.current_upstream == graph_rel[key].current_upstream
            and item.current_downstream == graph_rel[key].current_downstream
            and item.candidate_upstream == graph_rel[key].upstream
            and item.candidate_downstream == graph_rel[key].downstream
            and item.evidence_strength == comp_rel[key].evidence_strength
            and item.reason_codes == (comp_rel[key].reason_code,)
            and item.transform_operations == comp_rel[key].transform_operations
            and item.query_evidence == comp_rel[key].query_evidence
            and item.mapping_group_ids == comp_rel[key].mapping_group_ids,
            f"Relationship conclusion changed: {key}",
        )
        require(
            item.compatibility_state.value.upper()
            in item.human_explanation,
            f"Relationship human conclusion mismatch: {key}",
        )
    path = {item.path_id: item for item in bundle.path_explanations}
    comp_path = {item.path_id: item for item in compatibility.path_evaluations}
    propagation_path = {
        item.path_id: item for item in propagation.path_registry
    }
    require(set(path) == set(comp_path), "Path explanation scope mismatch")
    for key, item in path.items():
        if key not in comp_path or key not in propagation_path:
            issues.append(f"Unknown path explanation subject: {key}")
            continue
        evaluated = comp_path[key]
        source_path = propagation_path[key]
        unresolved = set(
            evaluated.blocking_relationship_ids
            + evaluated.uncertain_relationship_ids
        )
        expected_first = next(
            (
                relationship_id
                for relationship_id in evaluated.relationship_ids
                if relationship_id in unresolved
            ),
            None,
        )
        require(
            item.compatibility_state == evaluated.compatibility_state
            and item.ordered_relationship_ids == evaluated.relationship_ids
            and item.ordered_fields == source_path.node_keys
            and item.depth == evaluated.depth
            and item.edge_compatibility_states
            == evaluated.edge_compatibility_states
            and item.first_uncertain_or_blocking_relationship_id
            == expected_first
            and item.reason_codes == evaluated.reason_codes
            and all(value in graph_rel for value in item.ordered_relationship_ids),
            f"Path explanation mismatch: {key}",
        )
        require(
            item.compatibility_state.value.upper() in item.human_explanation,
            f"Path human conclusion mismatch: {key}",
        )
    field = {item.field_key: item for item in bundle.field_explanations}
    comp_field = {
        item.field_key: item for item in compatibility.field_evaluations
    }
    propagation_field = {
        item.field_key: item for item in propagation.field_exposure_registry
    }
    graph_field_keys = {value.key for value in future_graph.field_registry}
    require(set(field) == set(comp_field), "Field explanation scope mismatch")
    for key, item in field.items():
        if key not in comp_field or key not in propagation_field:
            issues.append(f"Unknown field explanation subject: {key.text}")
            continue
        evaluated = comp_field[key]
        exposure = propagation_field[key]
        require(
            key in graph_field_keys
            and item.compatibility_state == evaluated.compatibility_state
            and item.supporting_path_ids == evaluated.supporting_path_ids
            and item.minimum_depth == evaluated.minimum_depth
            and item.exposure_state == exposure.exposure_state
            and item.incoming_relationship_ids
            == evaluated.incoming_relationship_ids
            and item.reason_codes == evaluated.reason_codes
            and all(value in path for value in item.supporting_path_ids),
            f"Field explanation mismatch: {key.text}",
        )
        require(
            item.compatibility_state.value.upper() in item.human_explanation,
            f"Field human conclusion mismatch: {key.text}",
        )
    dataset = {item.dataset_urn: item for item in bundle.dataset_explanations}
    comp_dataset = {
        item.dataset_urn: item for item in compatibility.dataset_summaries
    }
    require(set(dataset) == set(comp_dataset), "Dataset explanation scope mismatch")
    for key, item in dataset.items():
        if key not in comp_dataset:
            issues.append(f"Unknown Dataset explanation subject: {key}")
            continue
        evaluated = comp_dataset[key]
        require(
            item.exposed_field_keys == evaluated.exposed_field_keys
            and item.compatible_fields == evaluated.compatible_exposed_fields
            and item.incompatible_fields
            == evaluated.incompatible_exposed_fields
            and item.conditionally_compatible_fields
            == evaluated.conditionally_compatible_exposed_fields
            and item.unknown_fields == evaluated.unknown_exposed_fields
            and item.compatibility_state == evaluated.compatibility_state,
            f"Dataset explanation mismatch: {key}",
        )
        require(
            item.compatibility_state.value.upper() in item.human_explanation,
            f"Dataset human conclusion mismatch: {key}",
        )
    require(
        len(rel) == 27
        and len(path) == 48
        and len(field) == 25
        and len(dataset) == 20
        and len(bundle.uncertainties) >= 1,
        "Canonical explanation count mismatch",
    )
    known_provenance = {
        item.provenance_id for item in future_graph.provenance_registry
    }
    known_evidence = set(snapshot.evidence_by_id())
    known_relationship_ids = set(graph_rel)
    known_path_ids = set(propagation_path)
    known_field_keys = set(comp_field)
    for record in bundle.uncertainties:
        require(
            all(value in known_relationship_ids for value in record.affected_relationship_ids)
            and all(value in known_path_ids for value in record.affected_path_ids)
            and all(value in known_field_keys for value in record.affected_field_keys),
            f"Dangling uncertainty subject: {record.uncertainty_id}",
        )
    for step in _all_steps(bundle):
        require(
            all(
                value in known_provenance or value in known_evidence
                for value in step.provenance_ids
            ),
            f"Dangling step provenance: {step.step_id}",
        )
    boundary_candidates = tuple(
        item
        for item in bundle.relationship_explanations
        if item.candidate_upstream == _CANDIDATE
    )
    require(
        len(boundary_candidates) == 1,
        "Canonical boundary explanation is missing or ambiguous",
    )
    if len(boundary_candidates) == 1:
        expected_narrative = _render_canonical_narrative(
            bundle.source_explanation,
            boundary_candidates[0],
            bundle.path_explanations,
            bundle.relationship_explanations,
        )
        require(
            bundle.canonical_narrative == expected_narrative,
            "Canonical narrative is not derived from typed evidence",
        )
    forbidden = (
        "risk score",
        "severity",
        "repair recommendation",
        "business impact",
        "broken",
        "safe deployment",
    )
    text = bundle.to_json().lower()
    require(
        all(value not in text for value in forbidden),
        "Unsupported impact, risk, or repair conclusion exists",
    )
    if issues:
        raise ExplanationValidationError("; ".join(issues))


def _require_preconditions(
    snapshot: CurrentMetadataSnapshot,
    proposal: ChangeProposal,
    validation: ProposalValidationResult,
    contract: ChangeSemanticContract,
    certification: Phase2CertificationResult,
    source_state: CounterfactualSourceState,
    future_graph: FutureMetadataGraph,
    propagation: DependencyPropagationResult,
    compatibility: CompatibilityEvaluationResult,
    hashes: tuple[InputArtifactHash, ...],
) -> None:
    try:
        validate_counterfactual_source_state(
            source_state,
            snapshot,
            proposal,
            validation,
            contract,
            certification,
        )
        validate_future_metadata_graph(
            future_graph,
            snapshot,
            proposal,
            validation,
            contract,
            certification,
            source_state,
        )
        validate_dependency_propagation(propagation, future_graph)
        validate_compatibility_evaluation(
            compatibility,
            future_graph,
            propagation,
        )
    except ValueError as exc:
        raise ExplanationEntryPreconditionError(
            "The authoritative explanation chain is invalid."
        ) from exc
    if (
        certification.certification_state
        is not Phase2CertificationState.CERTIFIED
        or proposal.change_type is not ChangeType.FIELD_RENAME
        or compatibility.validation_state
        is not CompatibilityValidationState.VALID
        or compatibility_semantic_fingerprint(compatibility)
        != compatibility.semantic_fingerprint
        or future_graph_semantic_fingerprint(future_graph)
        != future_graph.semantic_fingerprint
        or propagation_semantic_fingerprint(propagation)
        != propagation.semantic_fingerprint
    ):
        raise ExplanationEntryPreconditionError(
            "A prerequisite Phase is not certified or reproducible."
        )
    if (
        proposal.demonstration_id != CANONICAL_DEMONSTRATION_ID
        or source_state.demonstration_id != CANONICAL_DEMONSTRATION_ID
        or future_graph.demonstration_id != CANONICAL_DEMONSTRATION_ID
        or propagation.demonstration_id != CANONICAL_DEMONSTRATION_ID
        or compatibility.demonstration_id != CANONICAL_DEMONSTRATION_ID
        or compatibility.proposal_id != proposal.proposal_id
    ):
        raise ExplanationEntryPreconditionError(
            "Demonstration or proposal identity mismatch."
        )
    expected = {
        "current_metadata_snapshot.json",
        "change_proposal.json",
        "change_proposal_validation.json",
        "change_semantic_contract.json",
        "phase_2_certification.json",
        "counterfactual_source_state.json",
        "future_metadata_graph.json",
        "dependency_propagation.json",
        "compatibility_evaluation.json",
    }
    if {item.artifact_name for item in hashes} != expected or any(
        not item.unchanged for item in hashes
    ):
        raise ExplanationEntryPreconditionError(
            "All nine explanation input hashes must be unchanged."
        )


def _step(
    seed: str,
    kind: ExplanationStepType,
    subject: str,
    code: str,
    statement: str,
    artifact: str,
    object_id: str,
    provenance: tuple[str, ...],
    classification: ExplanationClassification,
) -> ExplanationStep:
    return ExplanationStep(
        step_id="explanation-step-" + hashlib.sha256(
            seed.encode("utf-8")
        ).hexdigest()[:24],
        step_type=kind,
        subject=subject,
        statement_code=code,
        human_statement=statement,
        supporting_artifact=artifact,
        supporting_object_id=object_id,
        provenance_ids=tuple(sorted(set(provenance))),
        classification=classification,
    )


def _all_steps(bundle: ExplanationBundle) -> tuple[ExplanationStep, ...]:
    return (
        bundle.source_explanation.steps
        + tuple(
            step
            for item in bundle.relationship_explanations
            for step in item.steps
        )
        + tuple(
            step for item in bundle.path_explanations for step in item.steps
        )
        + tuple(
            step for item in bundle.field_explanations for step in item.steps
        )
        + tuple(
            step for item in bundle.dataset_explanations for step in item.steps
        )
    )


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _timestamp(clock: Clock | None) -> str:
    value = (clock or (lambda: datetime.now(timezone.utc)))()
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()
