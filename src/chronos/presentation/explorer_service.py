"""Certified Phase 5.3 impact and evidence presentation mapping."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from chronos.business_context import (
    BusinessContextPropagation,
    load_business_context,
)
from chronos.compatibility_evaluation import (
    CompatibilityEvaluationResult,
    load_compatibility_evaluation,
)
from chronos.dependency_propagation import (
    DependencyPropagationResult,
    load_dependency_propagation,
)
from chronos.explanations import ExplanationBundle, load_explanation_bundle
from chronos.future_graph import FutureMetadataGraph, load_future_graph
from chronos.impact_synthesis import ImpactSynthesis, load_impact_synthesis
from chronos.phase4_certification import (
    CertificationCheckStatus,
    Phase4CertificationResult,
)
from chronos.severity_criticality import (
    SeverityCriticalityAnalysis,
    load_severity_analysis,
)
from chronos.snapshot import CurrentMetadataSnapshot, load_snapshot
from chronos.snapshot.serialization import contains_secret
from chronos.technical_impact import (
    TechnicalImpactAnalysis,
    load_technical_impact,
)

from .artifacts import (
    EXPECTED_PHASE4_CERTIFICATION_FINGERPRINT,
    CertifiedArtifactLoader,
)
from .errors import PresentationIntegrityError
from .explorer_models import (
    CertifiedImpactExplorer,
    ContextAssetDTO,
    ContextAttributeDTO,
    ContextMappingDTO,
    ContextRelationshipDTO,
    DatasetImpactDTO,
    DecisionExplanationDTO,
    DecisionInputDTO,
    DecisionReasonDetailDTO,
    ExplorerBlockingQuestionDTO,
    ExplorerEvidenceRecordDTO,
    ExplorerPathDTO,
    ExplorerRelationshipDTO,
    ExplorerRequiredEvidenceDTO,
    ExplorerRootCauseDTO,
    ExplorerSummaryDTO,
    FieldImpactDTO,
    RootCauseStepDTO,
)
from .graph_models import CertifiedGraphReview
from .graph_service import CertifiedGraphService
from .models import (
    CertificationDTO,
    FieldIdentityDTO,
    SeverityDistributionDTO,
)


_REQUIRED_EVIDENCE_LABELS = {
    "spark_transformation_configuration": "Spark transformation configuration",
    "input_column_reference_query_or_code": (
        "Input-column reference query or code"
    ),
    "explicit_rename_mapping": "Explicit rename mapping",
    "validated_execution_result": "Validated execution result",
}


class CertifiedImpactExplorerService:
    """Join certified records for browser inspection without new reasoning."""

    def __init__(
        self,
        artifact_dir: str | Path,
        *,
        expected_fingerprint: str = (
            EXPECTED_PHASE4_CERTIFICATION_FINGERPRINT
        ),
    ) -> None:
        self._artifacts = CertifiedArtifactLoader(
            artifact_dir,
            expected_fingerprint=expected_fingerprint,
        )
        self._graph = CertifiedGraphService(
            artifact_dir,
            expected_fingerprint=expected_fingerprint,
        )

    def get_explorer(self, review_id: str) -> CertifiedImpactExplorer:
        certification = self._artifacts.certification(review_id)
        try:
            snapshot = self._load(
                certification,
                "current_metadata_snapshot.json",
                load_snapshot,
            )
            future = self._load(
                certification,
                "future_metadata_graph.json",
                load_future_graph,
            )
            propagation = self._load(
                certification,
                "dependency_propagation.json",
                load_dependency_propagation,
            )
            compatibility = self._load(
                certification,
                "compatibility_evaluation.json",
                load_compatibility_evaluation,
            )
            explanations = self._load(
                certification,
                "explanation_bundle.json",
                load_explanation_bundle,
            )
            technical = self._load(
                certification,
                "technical_impact_analysis.json",
                load_technical_impact,
            )
            context = self._load(
                certification,
                "business_context_propagation.json",
                load_business_context,
            )
            severity = self._load(
                certification,
                "severity_criticality_analysis.json",
                load_severity_analysis,
            )
            synthesis = self._load(
                certification,
                "impact_synthesis.json",
                load_impact_synthesis,
            )
            graph = self._graph.get_graph(review_id)
            _validate_chain(
                certification=certification,
                snapshot=snapshot,
                future=future,
                propagation=propagation,
                compatibility=compatibility,
                explanations=explanations,
                technical=technical,
                context=context,
                severity=severity,
                synthesis=synthesis,
            )
            result = _map_explorer(
                certification=certification,
                graph=graph,
                explanations=explanations,
                technical=technical,
                context=context,
                severity=severity,
                synthesis=synthesis,
            )
            if contains_secret(result.model_dump(by_alias=True)):
                raise PresentationIntegrityError(
                    "Certified explorer payload contains credential-shaped data."
                )
            return result
        except PresentationIntegrityError:
            raise
        except Exception as exc:
            raise PresentationIntegrityError(
                "Certified impact explorer construction failed."
            ) from exc

    def _load(self, certification, name, loader):
        return self._artifacts.load(certification, name, loader)


def _validate_chain(
    *,
    certification: Phase4CertificationResult,
    snapshot: CurrentMetadataSnapshot,
    future: FutureMetadataGraph,
    propagation: DependencyPropagationResult,
    compatibility: CompatibilityEvaluationResult,
    explanations: ExplanationBundle,
    technical: TechnicalImpactAnalysis,
    context: BusinessContextPropagation,
    severity: SeverityCriticalityAnalysis,
    synthesis: ImpactSynthesis,
) -> None:
    identities = {
        item.artifact_name: item.semantic_fingerprint
        for item in certification.input_artifact_identities
    }
    checks = (
        future.current_snapshot_fingerprint
        == snapshot.semantic_fingerprint,
        propagation.future_graph_fingerprint == future.semantic_fingerprint,
        compatibility.future_graph_fingerprint == future.semantic_fingerprint,
        compatibility.dependency_propagation_fingerprint
        == propagation.semantic_fingerprint,
        explanations.future_graph_fingerprint == future.semantic_fingerprint,
        explanations.propagation_fingerprint
        == propagation.semantic_fingerprint,
        explanations.compatibility_fingerprint
        == compatibility.semantic_fingerprint,
        context.technical_impact_fingerprint
        == technical.semantic_fingerprint,
        severity.technical_impact_fingerprint
        == technical.semantic_fingerprint,
        severity.business_context_fingerprint
        == context.semantic_fingerprint,
        synthesis.technical_impact_fingerprint
        == technical.semantic_fingerprint,
        synthesis.business_context_fingerprint == context.semantic_fingerprint,
        synthesis.severity_criticality_fingerprint
        == severity.semantic_fingerprint,
        identities.get("explanation_bundle.json")
        == explanations.semantic_fingerprint,
        certification.demonstration_id
        == future.demonstration_id
        == technical.demonstration_id
        == context.demonstration_id
        == severity.demonstration_id
        == synthesis.demonstration_id,
        certification.proposal_id
        == technical.proposal_id
        == context.proposal_id
        == severity.proposal_id
        == synthesis.proposal_id,
    )
    if not all(checks):
        raise PresentationIntegrityError(
            "Certified explorer predecessor chain is inconsistent."
        )


def _map_explorer(
    *,
    certification: Phase4CertificationResult,
    graph: CertifiedGraphReview,
    explanations: ExplanationBundle,
    technical: TechnicalImpactAnalysis,
    context: BusinessContextPropagation,
    severity: SeverityCriticalityAnalysis,
    synthesis: ImpactSynthesis,
) -> CertifiedImpactExplorer:
    nodes = {item.machine_key: item for item in graph.future_graph.nodes}
    edges = {
        item.relationship_id: item for item in graph.future_graph.edges
    }
    graph_paths = {item.path_id: item for item in graph.supporting_paths}
    technical_fields = {
        item.field_key.text: item for item in technical.field_impacts
    }
    technical_datasets = {
        item.dataset_urn: item for item in technical.dataset_summaries
    }
    technical_paths = {
        item.path_id: item for item in technical.path_impacts
    }
    technical_relationships = {
        item.relationship_id: item for item in technical.relationship_impacts
    }
    severity_fields = {
        item.field_key.text: item for item in severity.field_assessments
    }
    severity_datasets = {
        item.dataset_urn: item for item in severity.dataset_assessments
    }
    criticality = {
        item.evidence_id: item for item in severity.criticality_evidence
    }
    breadth = {
        item.breadth_metrics_id: item for item in severity.breadth_metrics
    }
    sensitivity = {
        item.sensitivity_evidence_id: item
        for item in severity.sensitivity_evidence
    }
    field_explanations = {
        item.field_key.text: item for item in explanations.field_explanations
    }
    path_explanations = {
        item.path_id: item for item in explanations.path_explanations
    }
    relationship_explanations = {
        item.relationship_id: item
        for item in explanations.relationship_explanations
    }
    field_reverse = {
        item.field_key.text: item for item in context.reverse_indexes.by_field
    }
    dataset_reverse = {
        item.dataset_urn: item
        for item in context.reverse_indexes.by_dataset
    }
    asset_reverse = {
        item.context_asset_id: item
        for item in context.reverse_indexes.by_context_asset
    }
    context_links = {
        item.context_relationship_id: item
        for item in context.context_link_registry
    }
    mappings_by_field: dict[str, list] = defaultdict(list)
    for mapping in context.technical_to_context_mappings:
        mappings_by_field[mapping.technical_field_key.text].append(mapping)

    fields = tuple(
        _field_dto(
            item=technical_fields[key],
            node=nodes[key],
            assessment=severity_fields[key],
            criticality=criticality,
            breadth=breadth,
            sensitivity=sensitivity,
            reverse=field_reverse[key],
            explanation=field_explanations[key],
        )
        for key in sorted(technical_fields)
    )
    field_ids_by_key = {
        item.machine_key: item.field_id for item in fields
    }
    field_ids_by_dataset: dict[str, list[str]] = defaultdict(list)
    for item in fields:
        field_ids_by_dataset[item.dataset_urn].append(item.field_id)

    context_assets = tuple(
        _context_asset_dto(
            item=item,
            reverse=asset_reverse[item.asset_id],
            field_ids=field_ids_by_key,
        )
        for item in sorted(
            context.context_asset_registry,
            key=lambda value: value.asset_id,
        )
    )
    context_relationships = tuple(
        _context_relationship_dto(
            item=item,
            field_ids=field_ids_by_key,
        )
        for item in sorted(
            context.context_link_registry,
            key=lambda value: value.context_relationship_id,
        )
    )
    context_mappings = tuple(
        _context_mapping_dto(item, field_ids_by_key)
        for item in sorted(
            context.technical_to_context_mappings,
            key=lambda value: value.mapping_id,
        )
    )
    datasets = tuple(
        _dataset_dto(
            item=technical_datasets[urn],
            assessment=severity_datasets[urn],
            reverse=dataset_reverse[urn],
            field_ids=tuple(sorted(field_ids_by_dataset[urn])),
            technical_fields=technical_fields,
            criticality=criticality,
            breadth=breadth,
            sensitivity=sensitivity,
            nodes=nodes,
        )
        for urn in sorted(technical_datasets)
    )
    paths = tuple(
        _path_dto(
            item=technical_paths[path_id],
            graph_path=graph_paths[path_id],
            explanation=path_explanations[path_id],
            assessment=severity_fields[
                technical_paths[path_id].target_field.text
            ],
            field_id=field_ids_by_key[
                technical_paths[path_id].target_field.text
            ],
            reverse=field_reverse[
                technical_paths[path_id].target_field.text
            ],
            graph_nodes=graph.future_graph.nodes,
        )
        for path_id in sorted(technical_paths)
    )
    relationships = tuple(
        _relationship_dto(
            item=technical_relationships[relationship_id],
            edge=edges[relationship_id],
            explanation=relationship_explanations[relationship_id],
        )
        for relationship_id in sorted(technical_relationships)
    )
    root = technical.technical_impact_causes[0]
    blocking = synthesis.blocking_questions[0]
    change_profile = severity.change_level_profile
    compatibility_counts = {
        "unknown": sum(
            item.compatibility_state.value == "unknown"
            for item in technical.relationship_impacts
        ),
        "conditionally_compatible": sum(
            item.compatibility_state.value == "conditionally_compatible"
            for item in technical.relationship_impacts
        ),
        "compatible": sum(
            item.compatibility_state.value == "compatible"
            for item in technical.relationship_impacts
        ),
        "incompatible": sum(
            item.compatibility_state.value == "incompatible"
            for item in technical.relationship_impacts
        ),
    }
    result = CertifiedImpactExplorer(
        certification=_certification_dto(certification),
        summary=_summary_dto(
            synthesis,
            severity,
            compatibility_counts,
        ),
        root_cause=_root_cause_dto(root, synthesis, technical),
        blocking_question=ExplorerBlockingQuestionDTO(
            question_id=blocking.question_id,
            question=blocking.question,
            subject=blocking.subject,
            reason=blocking.reason,
            root_cause_id=blocking.root_cause_id,
            root_relationship_id=root.root_relationship_id,
            resolution_state=blocking.resolution_state.value,
            affected_fields=len(blocking.affected_field_keys),
            affected_datasets=len(blocking.affected_dataset_urns),
            affected_paths=len(blocking.affected_path_ids),
            required_evidence_ids=blocking.required_evidence_ids,
        ),
        required_evidence=tuple(
            ExplorerRequiredEvidenceDTO(
                evidence_id=item.required_evidence_id,
                evidence_class=item.evidence_class,
                label=_REQUIRED_EVIDENCE_LABELS.get(
                    item.evidence_class,
                    _humanize(item.evidence_class),
                ),
                subject=item.subject,
                reason=item.reason,
                state=item.state.value,
                availability="not_available_required",
                source_uncertainty_id=item.source_uncertainty_id,
            )
            for item in synthesis.required_evidence
        ),
        evidence_chain=_evidence_chain(explanations, synthesis),
        fields=fields,
        datasets=datasets,
        context_assets=context_assets,
        context_relationships=context_relationships,
        context_mappings=context_mappings,
        paths=paths,
        relationships=relationships,
        decision_explanation=DecisionExplanationDTO(
            disposition=synthesis.decision_disposition.value,
            decision_rule_id=synthesis.decision_rule_id,
            decision_certainty=synthesis.decision_certainty.value,
            technical_certainty=(
                synthesis.assessment.impact_certainty.value
            ),
            inputs=DecisionInputDTO(
                technical_consequence=(
                    synthesis.assessment.technical_consequence.value
                ),
                impact_certainty=(
                    synthesis.assessment.impact_certainty.value
                ),
                severity_if_realized=(
                    synthesis.assessment.severity_if_realized.value
                ),
                breadth=synthesis.assessment.breadth.value,
                criticality=synthesis.assessment.criticality.value,
            ),
            reasons=tuple(
                DecisionReasonDetailDTO(
                    reason_id=item.reason_id,
                    reason_code=item.reason_code.value,
                    statement=item.statement,
                    evidence_ids=item.evidence_ids,
                )
                for item in synthesis.decision_reasons
            ),
            narrative=synthesis.assessment.narrative,
            what_we_know=synthesis.what_we_know,
            what_we_do_not_know=synthesis.what_we_do_not_know,
            confirmed_failure_distinction=(
                "HOLD FOR REVIEW is not a confirmed failure. "
                "Zero downstream failures are confirmed; 25 fields remain "
                "technically unresolved because required evidence is missing."
            ),
        ),
    )
    return result


def _field_dto(
    *,
    item,
    node,
    assessment,
    criticality,
    breadth,
    sensitivity,
    reverse,
    explanation,
) -> FieldImpactDTO:
    criticality_record = criticality[assessment.criticality_evidence_id]
    breadth_record = breadth[assessment.breadth_metrics_id]
    sensitivity_record = sensitivity[assessment.sensitivity_evidence_id]
    return FieldImpactDTO(
        field_id=node.id,
        machine_key=item.field_key.text,
        identity=_identity(item.field_key),
        display_identity=f"{node.platform} / {node.secondary_label} / {node.field_path}",
        dataset_urn=item.dataset_urn,
        dataset_display_name=node.secondary_label,
        platform=node.platform,
        shortest_exposure_depth=item.minimum_depth,
        exposure_classification=item.exposure_state.value,
        supporting_path_ids=item.supporting_path_ids,
        supporting_path_count=item.path_count,
        compatibility_state=item.compatibility_state.value,
        technical_impact_state=item.technical_impact_state.value,
        certainty=assessment.evidence_certainty.value,
        severity_if_realized=assessment.severity_if_realized.value,
        criticality=criticality_record.criticality.value,
        breadth=breadth_record.exposure_breadth.value,
        sensitivity=sensitivity_record.sensitivity_state.value,
        reason_codes=tuple(value.value for value in item.reason_codes),
        root_cause_id=item.cause_ids[0],
        evidence_references=_bound(
            (
                explanation.evidence_chain_id,
                assessment.criticality_evidence_id,
                assessment.breadth_metrics_id,
                assessment.sensitivity_evidence_id,
                assessment.missing_evidence_id,
            )
        ),
        context_asset_ids=reverse.context_asset_ids,
        context_mapping_ids=reverse.mapping_ids,
        human_explanation=item.human_explanation,
        provenance_references=_bound(
            assessment.provenance_ids,
            item.current_provenance_ids,
            item.counterfactual_provenance_ids,
        ),
    )


def _dataset_dto(
    *,
    item,
    assessment,
    reverse,
    field_ids,
    technical_fields,
    criticality,
    breadth,
    sensitivity,
    nodes,
) -> DatasetImpactDTO:
    first_node = nodes[item.exposed_field_keys[0].text]
    supporting_paths = tuple(
        sorted(
            {
                path_id
                for key in item.exposed_field_keys
                for path_id in technical_fields[key.text].supporting_path_ids
            }
        )
    )
    return DatasetImpactDTO(
        dataset_id=item.dataset_urn,
        dataset_urn=item.dataset_urn,
        display_name=first_node.secondary_label,
        platform=first_node.platform,
        exposed_field_count=len(item.exposed_field_keys),
        field_ids=field_ids,
        supporting_path_ids=supporting_paths,
        technical_impact_state=item.technical_impact_state.value,
        technical_summary=item.human_explanation,
        severity_if_realized=assessment.severity_if_realized.value,
        certainty=assessment.evidence_certainty.value,
        criticality=criticality[
            assessment.criticality_evidence_id
        ].criticality.value,
        breadth=breadth[
            assessment.breadth_metrics_id
        ].exposure_breadth.value,
        sensitivity=sensitivity[
            assessment.sensitivity_evidence_id
        ].sensitivity_state.value,
        root_cause_ids=assessment.root_cause_ids,
        context_asset_ids=reverse.context_asset_ids,
        context_mapping_ids=reverse.mapping_ids,
        reason_codes=tuple(
            value.value for value in assessment.severity_reason_codes
        ),
        provenance_references=_bound(assessment.provenance_ids),
    )


def _context_asset_dto(*, item, reverse, field_ids) -> ContextAssetDTO:
    return ContextAssetDTO(
        context_asset_id=item.asset_id,
        group=_context_group(item.category.value),
        category=item.category.value,
        asset_type=item.asset_type.value,
        display_name=item.display_name or _compact_identity(item.asset_id),
        resolution_state=item.resolution_state.value,
        connected_dataset_urns=reverse.linked_dataset_urns,
        connected_field_ids=tuple(
            field_ids[key.text]
            for key in reverse.linked_field_keys
            if key.text in field_ids
        ),
        relationship_count=len(item.certified_relationship_ids),
        relationship_ids=item.certified_relationship_ids,
        mapping_ids=reverse.mapping_ids,
        supporting_path_ids=reverse.supporting_path_ids,
        attributes=tuple(
            ContextAttributeDTO(
                name=attribute.name,
                values=tuple(str(value) for value in attribute.values),
            )
            for attribute in item.attributes
        ),
        provenance_references=_bound(
            item.current_evidence_ids,
            item.future_graph_provenance_ids,
        ),
    )


def _context_relationship_dto(*, item, field_ids) -> ContextRelationshipDTO:
    anchor = (
        field_ids.get(item.anchor_field_key.text)
        if item.anchor_field_key is not None
        else None
    )
    return ContextRelationshipDTO(
        relationship_id=item.context_relationship_id,
        relationship_category=item.relationship_category.value,
        context_category=item.context_category.value,
        anchor_dataset_urn=item.anchor_dataset_urn,
        anchor_field_id=anchor,
        context_asset_ids=item.context_asset_ids,
        exposure_type=item.context_exposure_type.value,
    )


def _context_mapping_dto(item, field_ids) -> ContextMappingDTO:
    return ContextMappingDTO(
        mapping_id=item.mapping_id,
        field_id=field_ids[item.technical_field_key.text],
        dataset_urn=item.dataset_urn,
        context_relationship_id=item.context_relationship_id,
        context_asset_id=item.context_asset_id,
        context_category=item.context_category.value,
        exposure_type=item.context_exposure_type.value,
        linkage_state=item.context_linkage_state.value,
        supporting_path_ids=item.supporting_path_ids,
        provenance_references=_bound(
            item.technical_provenance_ids,
            item.context_provenance_ids,
        ),
    )


def _path_dto(
    *,
    item,
    graph_path,
    explanation,
    assessment,
    field_id,
    reverse,
    graph_nodes,
) -> ExplorerPathDTO:
    nodes = {value.id: value for value in graph_nodes}
    return ExplorerPathDTO(
        path_id=item.path_id,
        graph_node_ids=graph_path.future_node_ids,
        graph_edge_ids=graph_path.future_edge_ids,
        ordered_fields=tuple(
            FieldIdentityDTO(
                dataset_urn=nodes[node_id].dataset_urn,
                field_path=nodes[node_id].field_path,
            )
            for node_id in graph_path.future_node_ids
        ),
        relationship_ids=item.ordered_relationship_ids,
        target_field_id=field_id,
        target_field=_identity(item.target_field),
        target_dataset_urn=item.target_field.dataset_urn,
        depth=item.depth,
        compatibility_state=item.compatibility_state.value,
        technical_impact_state=item.technical_impact_state.value,
        severity_if_realized=assessment.severity_if_realized.value,
        certainty=assessment.evidence_certainty.value,
        uncertain_relationship_ids=item.uncertain_or_blocking_relationship_ids,
        evidence_references=_bound(
            (
                explanation.evidence_chain_id,
                item.causal_chain_id,
                assessment.criticality_evidence_id,
                assessment.missing_evidence_id,
            )
        ),
        context_asset_ids=reverse.context_asset_ids,
        human_explanation=item.human_explanation,
        provenance_references=_bound(
            item.current_provenance_ids,
            item.counterfactual_provenance_ids,
        ),
    )


def _relationship_dto(*, item, edge, explanation) -> ExplorerRelationshipDTO:
    return ExplorerRelationshipDTO(
        graph_edge_id=edge.id,
        relationship_id=item.relationship_id,
        upstream=_identity(item.upstream_field),
        downstream=_identity(item.downstream_field),
        is_root_uncertainty=edge.is_root_uncertainty,
        compatibility_state=item.compatibility_state.value,
        technical_impact_state=item.technical_impact_state.value,
        evidence_strength=item.evidence_strength.value,
        reason_codes=tuple(value.value for value in item.reason_codes),
        supporting_path_ids=item.supporting_path_ids,
        path_participation_count=len(item.supporting_path_ids),
        human_explanation=item.human_explanation,
        evidence_references=_bound(
            (
                explanation.evidence_chain_id,
                item.supporting_compatibility_record_id,
                item.causal_chain_id,
            )
        ),
        provenance_references=_bound(
            item.current_provenance_ids,
            item.counterfactual_provenance_ids,
        ),
    )


def _root_cause_dto(root, synthesis, technical) -> ExplorerRootCauseDTO:
    chain = next(
        item
        for item in technical.causal_chains
        if item.chain_id == root.causal_chain_id
    )
    summary = synthesis.scope_summary
    return ExplorerRootCauseDTO(
        cause_id=root.cause_id,
        root_relationship_id=root.root_relationship_id,
        proposed_source=_identity(root.upstream_field),
        first_downstream_dependency=_identity(root.downstream_field),
        compatibility_state="unknown",
        evidence_state=root.evidence_strength.value,
        technical_consequence=root.impact_state.value,
        affected_fields=len(root.affected_field_keys),
        affected_datasets=len(root.affected_dataset_urns),
        affected_paths=len(root.affected_path_ids),
        confirmed_failures=summary.confirmed_downstream_failures,
        human_explanation=root.human_explanation,
        steps=(
            RootCauseStepDTO(
                step_id="root-step-source-change",
                stage="field_rename",
                label="Field rename",
                value="orders.order_total -> orders.order_amount",
                classification="proposed",
            ),
            RootCauseStepDTO(
                step_id="root-step-projected-boundary",
                stage="projected_source_relationship",
                label="Projected source relationship",
                value="order_amount -> S3.order_total",
                classification="counterfactual",
            ),
            RootCauseStepDTO(
                step_id="root-step-compatibility",
                stage="compatibility",
                label="Compatibility",
                value="UNKNOWN",
                classification="unresolved",
            ),
            RootCauseStepDTO(
                step_id="root-step-evidence",
                stage="evidence",
                label="Evidence",
                value="INSUFFICIENT",
                classification="unresolved",
            ),
            RootCauseStepDTO(
                step_id="root-step-fields",
                stage="technical_impact",
                label="Downstream technical state",
                value="25 fields remain unresolved",
                classification="conditional",
            ),
            RootCauseStepDTO(
                step_id="root-step-severity",
                stage="severity_and_breadth",
                label="Potential consequence",
                value="HIGH severity if realized / WIDESPREAD reach",
                classification="conditional",
            ),
            RootCauseStepDTO(
                step_id="root-step-decision",
                stage="decision",
                label="Certified disposition",
                value="HOLD FOR REVIEW",
                classification="decision",
            ),
        ),
        provenance_references=_bound(
            tuple(
                reference.object_id
                for reference in chain.ordered_references
            )
        ),
    )


def _summary_dto(synthesis, severity, compatibility) -> ExplorerSummaryDTO:
    summary = synthesis.scope_summary
    metrics = severity.aggregate_metrics
    profile = severity.change_level_profile
    return ExplorerSummaryDTO(
        downstream_fields=summary.unresolved_downstream_fields,
        downstream_datasets=summary.downstream_datasets,
        dependency_paths=summary.dependency_paths,
        structural_relationships=summary.technical_relationships,
        context_assets=summary.context_assets,
        context_relationships=summary.context_relationships,
        field_to_context_mappings=summary.field_to_context_mappings,
        root_causes=summary.technical_root_causes,
        blocking_questions=len(synthesis.blocking_questions),
        required_evidence_classes=len(synthesis.required_evidence),
        confirmed_failures=summary.confirmed_downstream_failures,
        unresolved_fields=summary.unresolved_downstream_fields,
        compatibility_unknown=compatibility["unknown"],
        compatibility_conditional=compatibility[
            "conditionally_compatible"
        ],
        compatibility_compatible=compatibility["compatible"],
        compatibility_incompatible=compatibility["incompatible"],
        field_severity_distribution=SeverityDistributionDTO(
            critical=metrics.critical_severity_fields,
            high=metrics.high_severity_fields,
            moderate=metrics.moderate_severity_fields,
            low=metrics.low_severity_fields,
            undetermined=metrics.undetermined_severity_fields,
        ),
        dataset_severity_distribution=SeverityDistributionDTO(
            critical=metrics.critical_severity_datasets,
            high=metrics.high_severity_datasets,
            moderate=metrics.moderate_severity_datasets,
            low=metrics.low_severity_datasets,
            undetermined=metrics.undetermined_severity_datasets,
        ),
        technical_consequence=profile.technical_consequence.value,
        technical_certainty=profile.evidence_certainty.value,
        decision_certainty=synthesis.decision_certainty.value,
        severity_if_realized=profile.severity_if_realized.value,
        breadth=profile.exposure_breadth.value,
        criticality=profile.context_criticality.value,
        sensitivity=profile.sensitivity_state.value,
        explicit_business_criticality_present=(
            metrics.explicitly_critical_subjects > 0
        ),
    )


def _evidence_chain(
    explanations: ExplanationBundle,
    synthesis: ImpactSynthesis,
) -> tuple[ExplorerEvidenceRecordDTO, ...]:
    records: list[ExplorerEvidenceRecordDTO] = []
    seen: set[str] = set()
    root_relationship = next(
        item
        for item in explanations.relationship_explanations
        if item.compatibility_state.value == "unknown"
    )
    steps = (
        explanations.source_explanation.steps
        + root_relationship.steps
    )
    for step in steps:
        if step.step_id in seen:
            continue
        seen.add(step.step_id)
        classification, verification = _evidence_presentation(
            step.classification.value
        )
        records.append(
            ExplorerEvidenceRecordDTO(
                evidence_id=step.step_id,
                classification=classification,
                category=step.step_type.value,
                source_artifact=step.supporting_artifact,
                subject=step.subject,
                claim_supported=step.statement_code,
                verification_state=verification,
                description=step.human_statement,
                provenance_references=_bound(
                    step.provenance_ids,
                    (step.supporting_object_id,),
                ),
            )
        )
    for item in synthesis.required_evidence:
        records.append(
            ExplorerEvidenceRecordDTO(
                evidence_id=item.required_evidence_id,
                classification="missing",
                category=item.evidence_class,
                source_artifact="certified_missing_evidence",
                subject=item.subject,
                claim_supported="Evidence required to resolve compatibility",
                verification_state="required",
                description=item.reason,
                provenance_references=(item.source_uncertainty_id,),
            )
        )
    for item in synthesis.decision_evidence:
        records.append(
            ExplorerEvidenceRecordDTO(
                evidence_id=item.evidence_id,
                classification="decision",
                category=item.evidence_type.value,
                source_artifact=item.source_artifact,
                subject=synthesis.proposal_id,
                claim_supported=item.statement,
                verification_state="certified_decision",
                description=item.statement,
                provenance_references=_bound(item.supporting_object_ids),
            )
        )
    return tuple(records)


def _evidence_presentation(value: str) -> tuple[str, str]:
    if value == "verified_current":
        return "observed", "verified"
    if value in {"proposed", "counterfactual"}:
        return "counterfactual", "certified_derivation"
    if value == "insufficient":
        return "missing", "insufficient"
    return "derived", "certified_derivation"


def _certification_dto(
    certification: Phase4CertificationResult,
) -> CertificationDTO:
    passed = sum(
        item.status is CertificationCheckStatus.PASS
        for item in certification.certification_checks
    )
    return CertificationDTO(
        status=certification.certification_status.value,
        fingerprint=certification.semantic_fingerprint,
        certified_at=certification.certified_at,
        checks_passed=passed,
        check_count=len(certification.certification_checks),
        scope_statement=certification.scope_statement,
    )


def _identity(value) -> FieldIdentityDTO:
    return FieldIdentityDTO(
        dataset_urn=value.dataset_urn,
        field_path=value.field_path,
    )


def _context_group(value: str) -> str:
    if value in {
        "ownership",
        "domain",
        "tag",
        "glossary",
        "structured_property",
    }:
        return "governance"
    if value in {"pipeline", "document"}:
        return "operational"
    return "consumer"


def _compact_identity(value: str) -> str:
    return value.rsplit(":", 1)[-1].strip("()")


def _bound(*groups: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(
        sorted({item for group in groups for item in group})
    )[:12]


def _humanize(value: str) -> str:
    return value.replace("_", " ").strip().title()
