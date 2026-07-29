"""Certified graph selection and browser-facing presentation mapping."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from pathlib import Path

from chronos.compatibility_evaluation import (
    CompatibilityEvaluationResult,
    load_compatibility_evaluation,
)
from chronos.counterfactual_source import (
    CounterfactualSourceState,
    load_source_state,
)
from chronos.dependency_propagation import (
    DependencyPropagationResult,
    load_dependency_propagation,
)
from chronos.future_graph import FutureMetadataGraph, load_future_graph
from chronos.impact_synthesis import ImpactSynthesis, load_impact_synthesis
from chronos.phase4_certification import (
    CertificationCheckStatus,
    Phase4CertificationResult,
)
from chronos.snapshot import (
    CurrentMetadataSnapshot,
    FieldMachineKey,
    load_snapshot,
)
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
from .graph_models import (
    CertifiedGraphReview,
    GraphEdgeDTO,
    GraphNodeDTO,
    GraphPathDTO,
    GraphProjectionDTO,
    GraphSourceChangeDTO,
    GraphSummaryDTO,
    IdentityMappingDTO,
    LegendTokenDTO,
    MissingEvidenceDTO,
    RepresentativeGraphPathDTO,
    RootUncertaintyDTO,
)
from .models import CertificationDTO, FieldIdentityDTO


class CertifiedGraphService:
    """Select certified graph records without performing graph reasoning."""

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

    def get_graph(self, review_id: str) -> CertifiedGraphReview:
        certification = self._artifacts.certification(review_id)
        try:
            snapshot = self._artifacts.load(
                certification,
                "current_metadata_snapshot.json",
                load_snapshot,
            )
            source_state = self._artifacts.load(
                certification,
                "counterfactual_source_state.json",
                load_source_state,
            )
            future = self._artifacts.load(
                certification,
                "future_metadata_graph.json",
                load_future_graph,
            )
            propagation = self._artifacts.load(
                certification,
                "dependency_propagation.json",
                load_dependency_propagation,
            )
            compatibility = self._artifacts.load(
                certification,
                "compatibility_evaluation.json",
                load_compatibility_evaluation,
            )
            technical = self._artifacts.load(
                certification,
                "technical_impact_analysis.json",
                load_technical_impact,
            )
            synthesis = self._artifacts.load(
                certification,
                "impact_synthesis.json",
                load_impact_synthesis,
            )
            _validate_chain(
                certification=certification,
                snapshot=snapshot,
                source_state=source_state,
                future=future,
                propagation=propagation,
                compatibility=compatibility,
                technical=technical,
                synthesis=synthesis,
            )
            graph = _map_graph(
                certification=certification,
                snapshot=snapshot,
                future=future,
                propagation=propagation,
                compatibility=compatibility,
                technical=technical,
                synthesis=synthesis,
            )
            if contains_secret(graph.model_dump(by_alias=True)):
                raise PresentationIntegrityError(
                    "Certified graph payload contains credential-shaped data."
                )
            return graph
        except PresentationIntegrityError:
            raise
        except Exception as exc:
            raise PresentationIntegrityError(
                "Certified graph contract could not be materialized."
            ) from exc


def _validate_chain(
    *,
    certification: Phase4CertificationResult,
    snapshot: CurrentMetadataSnapshot,
    source_state: CounterfactualSourceState,
    future: FutureMetadataGraph,
    propagation: DependencyPropagationResult,
    compatibility: CompatibilityEvaluationResult,
    technical: TechnicalImpactAnalysis,
    synthesis: ImpactSynthesis,
) -> None:
    if not (
        snapshot.metadata.demonstration_id
        == source_state.demonstration_id
        == future.demonstration_id
        == propagation.demonstration_id
        == compatibility.demonstration_id
        == technical.demonstration_id
        == synthesis.demonstration_id
        == certification.demonstration_id
    ):
        raise PresentationIntegrityError(
            "Certified graph demonstration identities are inconsistent."
        )
    if not (
        future.current_snapshot_fingerprint == snapshot.semantic_fingerprint
        and future.counterfactual_source_state_fingerprint
        == source_state.semantic_fingerprint
        and propagation.future_graph_fingerprint
        == future.semantic_fingerprint
        and compatibility.future_graph_fingerprint
        == future.semantic_fingerprint
        and compatibility.dependency_propagation_fingerprint
        == propagation.semantic_fingerprint
        and synthesis.technical_impact_fingerprint
        == technical.semantic_fingerprint
    ):
        raise PresentationIntegrityError(
            "Certified graph predecessor fingerprints are inconsistent."
        )
    if (
        technical.proposal_id != certification.proposal_id
        or compatibility.proposal_id != certification.proposal_id
        or synthesis.proposal_id != certification.proposal_id
    ):
        raise PresentationIntegrityError(
            "Certified graph proposal identities are inconsistent."
        )


def _map_graph(
    *,
    certification: Phase4CertificationResult,
    snapshot: CurrentMetadataSnapshot,
    future: FutureMetadataGraph,
    propagation: DependencyPropagationResult,
    compatibility: CompatibilityEvaluationResult,
    technical: TechnicalImpactAnalysis,
    synthesis: ImpactSynthesis,
) -> CertifiedGraphReview:
    exposure_by_field = {
        item.field_key: item
        for item in propagation.field_exposure_registry
    }
    compatibility_by_field = {
        item.field_key: item
        for item in compatibility.field_evaluations
    }
    impact_by_field = {
        item.field_key: item for item in technical.field_impacts
    }
    exposure_by_relationship = {
        item.relationship_id: item
        for item in propagation.relationship_exposure_registry
    }
    compatibility_by_relationship = {
        item.relationship_id: item
        for item in compatibility.relationship_evaluations
    }
    impact_by_relationship = {
        item.relationship_id: item
        for item in technical.relationship_impacts
    }
    compatibility_by_path = {
        item.path_id: item for item in compatibility.path_evaluations
    }
    impact_by_path = {
        item.path_id: item for item in technical.path_impacts
    }
    future_path_by_id = {
        item.path_id: item for item in future.path_registry
    }
    future_relationship_by_current = {
        item.current_edge_id: item for item in future.relationship_registry
    }
    current_paths_by_key: dict[FieldMachineKey, list[str]] = defaultdict(list)
    for path in propagation.path_registry:
        projected = future_path_by_id[path.future_graph_path_id or ""]
        for key in projected.current_node_keys:
            current_paths_by_key[key].append(path.path_id)

    root_relationship_id = certification.technical_baseline.root_relationship_id
    root_future = next(
        item
        for item in future.relationship_registry
        if item.relationship_id == root_relationship_id
    )
    root_current = next(
        item
        for item in snapshot.lineage_edges
        if item.edge_id == root_future.current_edge_id
    )

    current_nodes = tuple(
        _current_node(
            item,
            is_root_target=item.key == root_current.downstream,
            supporting_path_ids=tuple(
                sorted(current_paths_by_key.get(item.key, ()))
            ),
        )
        for item in sorted(snapshot.fields, key=lambda value: value.key.text)
    )
    future_nodes = tuple(
        _future_node(
            item,
            exposure=exposure_by_field.get(item.key),
            compatibility=compatibility_by_field.get(item.key),
            impact=impact_by_field.get(item.key),
            is_root_target=item.key == root_future.downstream,
            source_candidate=propagation.source_candidate_field,
        )
        for item in sorted(future.field_registry, key=lambda value: value.key.text)
    )
    current_node_ids = {
        item.key: _node_id("current", item.key) for item in snapshot.fields
    }
    future_node_ids = {
        item.key: _node_id("future", item.key)
        for item in future.field_registry
    }
    current_edges = tuple(
        _current_edge(
            item,
            node_ids=current_node_ids,
            future_relationship=future_relationship_by_current.get(
                item.edge_id
            ),
            relationship_exposure=(
                exposure_by_relationship.get(
                    future_relationship_by_current[item.edge_id].relationship_id
                )
                if item.edge_id in future_relationship_by_current
                else None
            ),
            is_root_current=item.edge_id == root_current.edge_id,
        )
        for item in sorted(
            snapshot.lineage_edges,
            key=lambda value: value.edge_id,
        )
    )
    future_edges = tuple(
        _future_edge(
            item,
            node_ids=future_node_ids,
            exposure=exposure_by_relationship[item.relationship_id],
            compatibility=compatibility_by_relationship[item.relationship_id],
            impact=impact_by_relationship[item.relationship_id],
            is_root=item.relationship_id == root_relationship_id,
            mode="future",
        )
        for item in sorted(
            future.relationship_registry,
            key=lambda value: value.relationship_id,
        )
    )

    current_graph = GraphProjectionDTO(
        mode="current",
        nodes=current_nodes,
        edges=current_edges,
    )
    future_graph = GraphProjectionDTO(
        mode="future",
        nodes=future_nodes,
        edges=future_edges,
    )

    diff_current_source_id = _node_id(
        "diff-current",
        snapshot.source_field_key,
    )
    diff_future_node_ids = {
        item.key: _node_id("diff-future", item.key)
        for item in future.field_registry
    }
    current_source_node = next(
        item
        for item in current_nodes
        if item.machine_key == snapshot.source_field_key.text
    ).model_copy(
        update={
            "id": diff_current_source_id,
            "diff_state": "removed_current_identity",
        }
    )
    diff_future_nodes = tuple(
        item.model_copy(
            update={
                "id": diff_future_node_ids[
                    FieldMachineKey(item.dataset_urn, item.field_path)
                ],
                "diff_state": (
                    "added_counterfactual_identity"
                    if item.is_change_origin
                    else "identity_preserved"
                ),
            }
        )
        for item in future_nodes
    )
    current_root_edge = next(
        item
        for item in current_edges
        if item.relationship_id == root_current.edge_id
    ).model_copy(
        update={
            "id": _edge_id("diff-current", root_current.edge_id),
            "source": diff_current_source_id,
            "target": diff_future_node_ids[root_future.downstream],
            "diff_state": "removed_current_relationship",
        }
    )
    diff_future_edges = tuple(
        item.model_copy(
            update={
                "id": _edge_id("diff-future", item.relationship_id),
                "source": diff_future_node_ids[
                    FieldMachineKey(
                        item.upstream.dataset_urn,
                        item.upstream.field_path,
                    )
                ],
                "target": diff_future_node_ids[
                    FieldMachineKey(
                        item.downstream.dataset_urn,
                        item.downstream.field_path,
                    )
                ],
                "diff_state": (
                    "projected_source_relationship"
                    if item.is_root_uncertainty
                    else "identity_preserved"
                ),
            }
        )
        for item in future_edges
    )
    diff_graph = GraphProjectionDTO(
        mode="diff",
        nodes=(current_source_node,) + diff_future_nodes,
        edges=(current_root_edge,) + diff_future_edges,
    )

    supporting_paths = tuple(
        _graph_path(
            item,
            future_path=future_path_by_id[item.future_graph_path_id or ""],
            path_compatibility=compatibility_by_path[item.path_id],
            path_impact=impact_by_path[item.path_id],
        )
        for item in sorted(
            propagation.path_registry,
            key=lambda value: value.path_id,
        )
    )
    graph = CertifiedGraphReview(
        certification=_certification(certification),
        source_change=GraphSourceChangeDTO(
            current=_identity(compatibility.source_change.current_field),
            future=_identity(compatibility.source_change.candidate_field),
            mapping_classification="renamed",
            disposition=certification.decision_baseline.disposition,
            technical_certainty=(
                certification.decision_baseline.technical_certainty
            ),
            severity_if_realized=(
                certification.severity_baseline.severity_if_realized
            ),
        ),
        current_graph=current_graph,
        future_graph=future_graph,
        diff_graph=diff_graph,
        identity_mappings=tuple(
            IdentityMappingDTO(
                mapping_id=_mapping_id(
                    item.current_identity,
                    item.future_identity,
                ),
                current_node_id=_node_id(
                    "current",
                    item.current_identity,
                ),
                future_node_id=_node_id(
                    "future",
                    item.future_identity,
                ),
                current_identity=_identity(item.current_identity),
                future_identity=_identity(item.future_identity),
                classification=item.classification.value,
                provenance_references=item.provenance_ids,
            )
            for item in sorted(
                future.current_to_future_identity_mappings,
                key=lambda value: value.current_identity.text,
            )
        ),
        root_uncertainty=_root_uncertainty(
            root_future=root_future,
            root_current=root_current,
            compatibility=compatibility_by_relationship[
                root_future.relationship_id
            ],
            impact=impact_by_relationship[root_future.relationship_id],
            synthesis=synthesis,
        ),
        supporting_paths=supporting_paths,
        representative_paths=tuple(
            RepresentativeGraphPathDTO(
                shortcut_id=item.representative_path_id,
                label=f"{item.kind.value.title()} path",
                kind=item.kind.value,
                supporting_path_id=item.technical_path_id,
                explanation=item.explanation,
            )
            for item in synthesis.representative_evidence_paths
        ),
        legend=_legend(),
        summary=GraphSummaryDTO(
            current_field_nodes=len(snapshot.fields),
            future_field_nodes=len(future.field_registry),
            downstream_fields=(
                propagation.summary.total_unique_downstream_exposed_fields
            ),
            downstream_datasets=(
                propagation.summary.unique_downstream_exposed_datasets
            ),
            structural_relationships=len(future.relationship_registry),
            supporting_paths=len(propagation.path_registry),
            root_unknown_boundaries=(
                compatibility.aggregate.relationship_counts.unknown
            ),
            conditional_relationships=(
                compatibility.aggregate.relationship_counts.conditionally_compatible
            ),
            multipath_fields=propagation.summary.multipath_exposed_fields,
            confirmed_failures=(
                technical.aggregate_metrics.confirmed_impacted_fields
            ),
            maximum_depth=propagation.summary.maximum_exposure_depth,
        ),
    )
    return graph


def _current_node(
    field,
    *,
    is_root_target: bool,
    supporting_path_ids: tuple[str, ...],
) -> GraphNodeDTO:
    return GraphNodeDTO(
        id=_node_id("current", field.key),
        machine_key=field.key.text,
        label=field.field_name,
        secondary_label=field.dataset_name,
        entity_type="field",
        platform=field.platform,
        dataset_urn=field.key.dataset_urn,
        field_path=field.key.field_path,
        graph_state="certified_current",
        diff_state=(
            "removed_current_identity"
            if field.lineage_depth == 0
            else "identity_preserved"
        ),
        exposure_state=None,
        compatibility_state=None,
        technical_impact_state=None,
        severity_if_realized=None,
        certainty=None,
        depth=field.lineage_depth,
        path_count=field.path_count,
        is_change_origin=field.lineage_depth == 0,
        is_root_boundary_target=is_root_target,
        supporting_path_ids=supporting_path_ids,
        provenance_references=_unique(field.evidence_ids),
    )


def _future_node(
    field,
    *,
    exposure,
    compatibility,
    impact,
    is_root_target: bool,
    source_candidate: FieldMachineKey,
) -> GraphNodeDTO:
    return GraphNodeDTO(
        id=_node_id("future", field.key),
        machine_key=field.key.text,
        label=field.field_name,
        secondary_label=field.dataset_name,
        entity_type="field",
        platform=field.platform,
        dataset_urn=field.key.dataset_urn,
        field_path=field.key.field_path,
        graph_state=field.state.value,
        diff_state=(
            "added_counterfactual_identity"
            if field.key == source_candidate
            else "identity_preserved"
        ),
        exposure_state=(
            exposure.exposure_state.value if exposure is not None else None
        ),
        compatibility_state=(
            compatibility.compatibility_state.value
            if compatibility is not None
            else None
        ),
        technical_impact_state=(
            impact.technical_impact_state.value
            if impact is not None
            else None
        ),
        severity_if_realized=None,
        certainty=(
            compatibility.evidence_strength.value
            if compatibility is not None
            else None
        ),
        depth=field.structural_depth,
        path_count=exposure.path_count if exposure is not None else 0,
        is_change_origin=field.key == source_candidate,
        is_root_boundary_target=is_root_target,
        supporting_path_ids=(
            exposure.supporting_path_ids if exposure is not None else ()
        ),
        provenance_references=_unique(
            field.provenance_ids,
            (
                exposure.current_provenance_ids
                + exposure.counterfactual_provenance_ids
                if exposure is not None
                else ()
            ),
        ),
    )


def _current_edge(
    edge,
    *,
    node_ids: dict[FieldMachineKey, str],
    future_relationship,
    relationship_exposure,
    is_root_current: bool,
) -> GraphEdgeDTO:
    supporting = (
        relationship_exposure.supporting_path_ids
        if relationship_exposure is not None
        else ()
    )
    return GraphEdgeDTO(
        id=_edge_id("current", edge.edge_id),
        relationship_id=edge.edge_id,
        source=node_ids[edge.upstream],
        target=node_ids[edge.downstream],
        upstream=_identity(edge.upstream),
        downstream=_identity(edge.downstream),
        current_upstream=None,
        current_downstream=None,
        relationship_type=edge.classification,
        graph_state="certified_current",
        diff_state=(
            "removed_current_relationship"
            if is_root_current
            else "identity_preserved"
        ),
        exposure_state=None,
        compatibility_state=None,
        technical_impact_state=None,
        evidence_strength=None,
        reason_code=None,
        explanation=None,
        is_root_uncertainty=False,
        mapping_group_ids=edge.mapping_group_ids,
        supporting_path_ids=supporting,
        path_participation_count=len(supporting),
        transform_operations=edge.transform_operations,
        query_evidence=(),
        provenance_references=_unique(
            edge.evidence_ids,
            (
                future_relationship.provenance_ids
                if future_relationship is not None
                else ()
            ),
        ),
    )


def _future_edge(
    relationship,
    *,
    node_ids: dict[FieldMachineKey, str],
    exposure,
    compatibility,
    impact,
    is_root: bool,
    mode: str,
) -> GraphEdgeDTO:
    return GraphEdgeDTO(
        id=_edge_id(mode, relationship.relationship_id),
        relationship_id=relationship.relationship_id,
        source=node_ids[relationship.upstream],
        target=node_ids[relationship.downstream],
        upstream=_identity(relationship.upstream),
        downstream=_identity(relationship.downstream),
        current_upstream=_identity(relationship.current_upstream),
        current_downstream=_identity(relationship.current_downstream),
        relationship_type=relationship.current_classification,
        graph_state=relationship.relationship_state.value,
        diff_state=(
            "projected_source_relationship"
            if is_root
            else "identity_preserved"
        ),
        exposure_state=exposure.exposure_state.value,
        compatibility_state=compatibility.compatibility_state.value,
        technical_impact_state=impact.technical_impact_state.value,
        evidence_strength=compatibility.evidence_strength.value,
        reason_code=compatibility.reason_code.value,
        explanation=compatibility.explanation,
        is_root_uncertainty=is_root,
        mapping_group_ids=compatibility.mapping_group_ids,
        supporting_path_ids=compatibility.supporting_path_ids,
        path_participation_count=len(compatibility.supporting_path_ids),
        transform_operations=compatibility.transform_operations,
        query_evidence=compatibility.query_evidence,
        provenance_references=_unique(
            relationship.provenance_ids,
            compatibility.current_provenance_ids,
            compatibility.counterfactual_provenance_ids,
            impact.current_provenance_ids,
            impact.counterfactual_provenance_ids,
        ),
    )


def _graph_path(
    path,
    *,
    future_path,
    path_compatibility,
    path_impact,
) -> GraphPathDTO:
    return GraphPathDTO(
        path_id=path.path_id,
        future_graph_path_id=path.future_graph_path_id,
        target_field=_identity(path.target_field),
        depth=path.depth,
        current_node_ids=tuple(
            _node_id("current", key)
            for key in future_path.current_node_keys
        ),
        current_edge_ids=tuple(
            _edge_id("current", edge_id)
            for edge_id in future_path.current_edge_ids
        ),
        future_node_ids=tuple(
            _node_id("future", key) for key in path.node_keys
        ),
        future_edge_ids=tuple(
            _edge_id("future", edge_id)
            for edge_id in path.relationship_ids
        ),
        diff_node_ids=tuple(
            _node_id("diff-future", key) for key in path.node_keys
        ),
        diff_edge_ids=tuple(
            _edge_id("diff-future", edge_id)
            for edge_id in path.relationship_ids
        ),
        compatibility_state=path_compatibility.compatibility_state.value,
        technical_impact_state=path_impact.technical_impact_state.value,
        uncertain_relationship_ids=(
            path_compatibility.uncertain_relationship_ids
        ),
        provenance_references=_unique(
            path.current_provenance_ids,
            path.counterfactual_provenance_ids,
            path_compatibility.current_provenance_ids,
            path_compatibility.counterfactual_provenance_ids,
            path_impact.current_provenance_ids,
            path_impact.counterfactual_provenance_ids,
        ),
    )


def _root_uncertainty(
    *,
    root_future,
    root_current,
    compatibility,
    impact,
    synthesis: ImpactSynthesis,
) -> RootUncertaintyDTO:
    required = {
        item.required_evidence_id: item
        for item in synthesis.required_evidence
    }
    question = synthesis.blocking_questions[0]
    return RootUncertaintyDTO(
        future_edge_id=_edge_id(
            "future",
            root_future.relationship_id,
        ),
        current_edge_id=_edge_id("current", root_current.edge_id),
        relationship_id=root_future.relationship_id,
        current_source=_identity(root_current.upstream),
        current_target=_identity(root_current.downstream),
        future_source=_identity(root_future.upstream),
        future_target=_identity(root_future.downstream),
        compatibility_state=compatibility.compatibility_state.value,
        evidence_strength=compatibility.evidence_strength.value,
        reason_code=compatibility.reason_code.value,
        explanation=compatibility.explanation,
        missing_evidence=tuple(
            MissingEvidenceDTO(
                evidence_id=item.required_evidence_id,
                evidence_class=item.evidence_class,
                label=_humanize(item.evidence_class),
                reason=item.reason,
            )
            for item in (
                required[evidence_id]
                for evidence_id in question.required_evidence_ids
            )
        ),
        mapping_group_ids=compatibility.mapping_group_ids,
        transform_operations=compatibility.transform_operations,
        query_evidence=compatibility.query_evidence,
        path_participation_count=len(compatibility.supporting_path_ids),
        provenance_references=_unique(
            root_future.provenance_ids,
            compatibility.current_provenance_ids,
            compatibility.counterfactual_provenance_ids,
            impact.current_provenance_ids,
            impact.counterfactual_provenance_ids,
        ),
    )


def _certification(
    certification: Phase4CertificationResult,
) -> CertificationDTO:
    return CertificationDTO(
        status=certification.certification_status.value,
        fingerprint=certification.semantic_fingerprint,
        certified_at=certification.certified_at,
        checks_passed=sum(
            item.status is CertificationCheckStatus.PASS
            for item in certification.certification_checks
        ),
        check_count=len(certification.certification_checks),
        scope_statement=certification.scope_statement,
    )


def _identity(key: FieldMachineKey) -> FieldIdentityDTO:
    return FieldIdentityDTO(
        dataset_urn=key.dataset_urn,
        field_path=key.field_path,
    )


def _node_id(mode: str, key: FieldMachineKey) -> str:
    digest = hashlib.sha256(key.text.encode("utf-8")).hexdigest()[:16]
    return f"{mode}-field-{digest}"


def _edge_id(mode: str, relationship_id: str) -> str:
    digest = hashlib.sha256(
        relationship_id.encode("utf-8")
    ).hexdigest()[:16]
    return f"{mode}-edge-{digest}"


def _mapping_id(
    current: FieldMachineKey,
    future: FieldMachineKey,
) -> str:
    digest = hashlib.sha256(
        f"{current.text}->{future.text}".encode("utf-8")
    ).hexdigest()[:16]
    return f"identity-mapping-{digest}"


def _unique(*values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted({item for group in values for item in group}))[:12]


def _humanize(value: str) -> str:
    return value.replace("_", " ").strip().title()


def _legend() -> tuple[LegendTokenDTO, ...]:
    return (
        LegendTokenDTO(
            key="certified_current",
            label="Current",
            description="Observed and certified current metadata.",
            tone="current",
        ),
        LegendTokenDTO(
            key="counterfactual_changed",
            label="Counterfactual",
            description="Projected future metadata, not a DataHub observation.",
            tone="future",
        ),
        LegendTokenDTO(
            key="source_changed",
            label="Changed",
            description="The proposed source identity replacement.",
            tone="changed",
        ),
        LegendTokenDTO(
            key="unknown",
            label="Unknown",
            description="Evidence cannot establish compatibility.",
            tone="unknown",
        ),
        LegendTokenDTO(
            key="conditionally_compatible",
            label="Conditional",
            description="Local continuity depends on unresolved upstream evidence.",
            tone="conditional",
        ),
        LegendTokenDTO(
            key="compatible",
            label="Compatible",
            description="Compatibility established by certified evidence.",
            tone="compatible",
        ),
        LegendTokenDTO(
            key="incompatible",
            label="Incompatible",
            description="Certified evidence establishes incompatibility.",
            tone="incompatible",
        ),
        LegendTokenDTO(
            key="multipath_exposed",
            label="Multipath",
            description="More than one certified dependency path reaches the field.",
            tone="multipath",
        ),
    )
