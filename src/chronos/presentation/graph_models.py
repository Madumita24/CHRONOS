"""Strict browser-facing DTOs for the certified Phase 5.2 graph."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from .models import CertificationDTO, FieldIdentityDTO, PresentationModel


GraphMode = Literal["current", "future", "diff"]
GraphState = Literal[
    "certified_current",
    "counterfactual_changed",
    "counterfactual_inherited",
    "counterfactual_unresolved",
]
DiffState = Literal[
    "removed_current_identity",
    "added_counterfactual_identity",
    "identity_preserved",
    "removed_current_relationship",
    "projected_source_relationship",
]


class GraphNodeDTO(PresentationModel):
    id: str
    machine_key: str
    label: str
    secondary_label: str
    entity_type: Literal["field"]
    platform: str
    dataset_urn: str
    field_path: str
    graph_state: GraphState
    diff_state: DiffState | None
    exposure_state: str | None
    compatibility_state: str | None
    technical_impact_state: str | None
    severity_if_realized: str | None
    certainty: str | None
    depth: int = Field(ge=0)
    path_count: int = Field(ge=0)
    is_change_origin: bool
    is_root_boundary_target: bool
    supporting_path_ids: tuple[str, ...]
    provenance_references: tuple[str, ...]


class GraphEdgeDTO(PresentationModel):
    id: str
    relationship_id: str
    source: str
    target: str
    upstream: FieldIdentityDTO
    downstream: FieldIdentityDTO
    current_upstream: FieldIdentityDTO | None
    current_downstream: FieldIdentityDTO | None
    relationship_type: str
    graph_state: str
    diff_state: DiffState | None
    exposure_state: str | None
    compatibility_state: str | None
    technical_impact_state: str | None
    evidence_strength: str | None
    reason_code: str | None
    explanation: str | None
    is_root_uncertainty: bool
    mapping_group_ids: tuple[str, ...]
    supporting_path_ids: tuple[str, ...]
    path_participation_count: int = Field(ge=0)
    transform_operations: tuple[str, ...]
    query_evidence: tuple[str, ...]
    provenance_references: tuple[str, ...]


class GraphProjectionDTO(PresentationModel):
    mode: GraphMode
    nodes: tuple[GraphNodeDTO, ...]
    edges: tuple[GraphEdgeDTO, ...]

    @model_validator(mode="after")
    def validate_references(self) -> "GraphProjectionDTO":
        node_ids = tuple(item.id for item in self.nodes)
        edge_ids = tuple(item.id for item in self.edges)
        if len(node_ids) != len(set(node_ids)):
            raise ValueError(f"{self.mode} graph node IDs must be unique.")
        if len(edge_ids) != len(set(edge_ids)):
            raise ValueError(f"{self.mode} graph edge IDs must be unique.")
        known_nodes = set(node_ids)
        if any(
            edge.source not in known_nodes or edge.target not in known_nodes
            for edge in self.edges
        ):
            raise ValueError(f"{self.mode} graph has a dangling edge.")
        return self


class IdentityMappingDTO(PresentationModel):
    mapping_id: str
    current_node_id: str
    future_node_id: str
    current_identity: FieldIdentityDTO
    future_identity: FieldIdentityDTO
    classification: Literal["renamed", "identity_preserved"]
    provenance_references: tuple[str, ...]


class MissingEvidenceDTO(PresentationModel):
    evidence_id: str
    evidence_class: str
    label: str
    reason: str


class RootUncertaintyDTO(PresentationModel):
    future_edge_id: str
    current_edge_id: str
    relationship_id: str
    current_source: FieldIdentityDTO
    current_target: FieldIdentityDTO
    future_source: FieldIdentityDTO
    future_target: FieldIdentityDTO
    compatibility_state: Literal["unknown"]
    evidence_strength: Literal["insufficient"]
    reason_code: Literal["source_rename_semantics_unknown"]
    explanation: str
    missing_evidence: tuple[MissingEvidenceDTO, ...]
    mapping_group_ids: tuple[str, ...]
    transform_operations: tuple[str, ...]
    query_evidence: tuple[str, ...]
    path_participation_count: int = Field(ge=1)
    provenance_references: tuple[str, ...]


class GraphPathDTO(PresentationModel):
    path_id: str
    future_graph_path_id: str
    target_field: FieldIdentityDTO
    depth: int = Field(ge=1)
    current_node_ids: tuple[str, ...]
    current_edge_ids: tuple[str, ...]
    future_node_ids: tuple[str, ...]
    future_edge_ids: tuple[str, ...]
    diff_node_ids: tuple[str, ...]
    diff_edge_ids: tuple[str, ...]
    compatibility_state: str
    technical_impact_state: str
    uncertain_relationship_ids: tuple[str, ...]
    provenance_references: tuple[str, ...]


class RepresentativeGraphPathDTO(PresentationModel):
    shortcut_id: str
    label: str
    kind: Literal["short", "deep", "multipath"]
    supporting_path_id: str
    explanation: str


class LegendTokenDTO(PresentationModel):
    key: str
    label: str
    description: str
    tone: str


class GraphSourceChangeDTO(PresentationModel):
    current: FieldIdentityDTO
    future: FieldIdentityDTO
    mapping_classification: Literal["renamed"]
    disposition: str
    technical_certainty: str
    severity_if_realized: str


class GraphSummaryDTO(PresentationModel):
    current_field_nodes: int = Field(ge=0)
    future_field_nodes: int = Field(ge=0)
    downstream_fields: int = Field(ge=0)
    downstream_datasets: int = Field(ge=0)
    structural_relationships: int = Field(ge=0)
    supporting_paths: int = Field(ge=0)
    root_unknown_boundaries: int = Field(ge=0)
    conditional_relationships: int = Field(ge=0)
    multipath_fields: int = Field(ge=0)
    confirmed_failures: int = Field(ge=0)
    maximum_depth: int = Field(ge=0)


class CertifiedGraphReview(PresentationModel):
    certification: CertificationDTO
    source_change: GraphSourceChangeDTO
    current_graph: GraphProjectionDTO
    future_graph: GraphProjectionDTO
    diff_graph: GraphProjectionDTO
    identity_mappings: tuple[IdentityMappingDTO, ...]
    root_uncertainty: RootUncertaintyDTO
    supporting_paths: tuple[GraphPathDTO, ...]
    representative_paths: tuple[RepresentativeGraphPathDTO, ...]
    legend: tuple[LegendTokenDTO, ...]
    summary: GraphSummaryDTO

    @model_validator(mode="after")
    def validate_certified_graph(self) -> "CertifiedGraphReview":
        if (
            self.current_graph.mode != "current"
            or self.future_graph.mode != "future"
            or self.diff_graph.mode != "diff"
        ):
            raise ValueError("Graph projection modes are inconsistent.")
        if (
            len(self.current_graph.nodes) != 26
            or len(self.current_graph.edges) != 27
            or len(self.future_graph.nodes) != 26
            or len(self.future_graph.edges) != 27
        ):
            raise ValueError("Certified graph cardinalities are invalid.")
        current_source = self.source_change.current
        future_source = self.source_change.future
        if current_source.field_path != "order_total":
            raise ValueError("Current graph source identity is invalid.")
        if future_source.field_path != "order_amount":
            raise ValueError("Future graph source identity is invalid.")
        current_keys = {item.machine_key for item in self.current_graph.nodes}
        future_keys = {item.machine_key for item in self.future_graph.nodes}
        if (
            _machine_key(current_source) not in current_keys
            or _machine_key(future_source) in current_keys
            or _machine_key(future_source) not in future_keys
            or _machine_key(current_source) in future_keys
        ):
            raise ValueError("Active graph source replacement is invalid.")
        if len(self.identity_mappings) != 26:
            raise ValueError("Exactly 26 identity mappings are required.")
        if (
            sum(item.classification == "renamed" for item in self.identity_mappings)
            != 1
            or sum(
                item.classification == "identity_preserved"
                for item in self.identity_mappings
            )
            != 25
        ):
            raise ValueError("Identity mapping classifications are invalid.")
        root_edges = tuple(
            item
            for item in self.future_graph.edges
            if item.is_root_uncertainty
        )
        if (
            len(root_edges) != 1
            or root_edges[0].id != self.root_uncertainty.future_edge_id
            or root_edges[0].compatibility_state != "unknown"
        ):
            raise ValueError("Root uncertainty edge is invalid.")
        if (
            sum(
                item.compatibility_state == "conditionally_compatible"
                for item in self.future_graph.edges
            )
            != 26
        ):
            raise ValueError("Conditional relationship count is invalid.")
        if len(self.supporting_paths) != 48:
            raise ValueError("Exactly 48 supporting paths are required.")
        path_ids = {item.path_id for item in self.supporting_paths}
        if len(path_ids) != 48:
            raise ValueError("Supporting path IDs must be unique.")
        if any(
            item.supporting_path_id not in path_ids
            for item in self.representative_paths
        ):
            raise ValueError("A representative path is dangling.")
        for projection, node_ids, edge_ids in (
            (
                self.current_graph,
                "current_node_ids",
                "current_edge_ids",
            ),
            (
                self.future_graph,
                "future_node_ids",
                "future_edge_ids",
            ),
            (
                self.diff_graph,
                "diff_node_ids",
                "diff_edge_ids",
            ),
        ):
            known_nodes = {item.id for item in projection.nodes}
            known_edges = {item.id for item in projection.edges}
            if any(
                not set(getattr(path, node_ids)) <= known_nodes
                or not set(getattr(path, edge_ids)) <= known_edges
                for path in self.supporting_paths
            ):
                raise ValueError(
                    f"A supporting path dangles in the {projection.mode} graph."
                )
        expected = GraphSummaryDTO(
            current_field_nodes=26,
            future_field_nodes=26,
            downstream_fields=25,
            downstream_datasets=20,
            structural_relationships=27,
            supporting_paths=48,
            root_unknown_boundaries=1,
            conditional_relationships=26,
            multipath_fields=21,
            confirmed_failures=0,
            maximum_depth=5,
        )
        if self.summary != expected:
            raise ValueError("Certified graph summary is invalid.")
        return self


def _machine_key(value: FieldIdentityDTO) -> str:
    return f"{value.dataset_urn}|{value.field_path}"
