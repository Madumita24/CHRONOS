"""Certified Phase 6 package loader and bounded presentation adapter."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from chronos.structural_engine.serialization import semantic_fingerprint

from .errors import CertifiedReviewNotFound, PresentationIntegrityError
from .phase6_models import (
    AnalysisDetailDTO,
    AnalysisGraphDTO,
    AnalysisIndexDTO,
    AnalysisSummaryDTO,
    ChangedFileDTO,
    ConflictDTO,
    EvidenceDTO,
    GraphEdgeDTO,
    GraphNodeDTO,
    GraphPathDTO,
    GraphMode,
    LogicalGroupDTO,
    PatchLineDTO,
    PatchPreviewDTO,
    PatchSummaryDTO,
    Phase6CertificationDTO,
    PullRequestAnalysisView,
    ReleaseCertificationDTO,
    RepairActionDTO,
    RepairAnalysisView,
    RepairComparisonDTO,
    RepairabilityDTO,
    SemanticAnalysisView,
    SemanticDeltaDTO,
    StructuralAnalysisView,
    StructuralChangeDTO,
    TestTotalsDTO,
)


_SAFE_ID = re.compile(r"^[A-Z0-9][A-Z0-9-]{5,127}$")
_FINGERPRINT = re.compile(r"^sha256:[0-9a-f]{64}$")
_WINDOWS_PATH = re.compile(r"[A-Za-z]:[\\/]")
_CERTIFIED_STATES = {
    "PHASE_6_CERTIFIED",
    "PHASE_6_CERTIFIED_WITH_NON_BLOCKING_LIMITATIONS",
}
_PHASE_7_PRESENTATION_REQUIREMENTS = (
    "clean_patch_application",
    "dependency_installation",
    "sql_dbt_validation",
    "schema_contract_validation",
    "dag_checks",
    "repository_tests",
    "data_comparison",
    "downstream_consumer_checks",
    "owner_business_approval",
    "runtime_evidence_collection",
)


@dataclass(frozen=True)
class _RegistryEntry:
    analysis_id: str
    directory: str
    analysis_type: Literal["structural", "semantic", "pull_request", "repair"]
    phase: Literal["6.1", "6.2", "6.3", "6.4"]
    scenario: str
    display_name: str


_REGISTRY = (
    _RegistryEntry("CHRONOS-DEMO-001-GENERALIZED-RENAME", "CHRONOS-DEMO-001-GENERALIZED-RENAME", "structural", "6.1", "field_rename", "Field rename - order total to order amount"),
    _RegistryEntry("CHRONOS-EXAMPLE-FIELD-DELETE-001", "CHRONOS-EXAMPLE-FIELD-DELETE-001", "structural", "6.1", "field_delete", "Field deletion - order total"),
    _RegistryEntry("CHRONOS-EXAMPLE-FIELD-TYPE-CHANGE-001", "CHRONOS-EXAMPLE-FIELD-TYPE-CHANGE-001", "structural", "6.1", "field_type_change", "Field type change - order total"),
    _RegistryEntry("CHRONOS-SEMANTIC-AGGREGATION-001", "CHRONOS-SEMANTIC-AGGREGATION-001", "semantic", "6.2", "aggregation", "Aggregation change - SUM to AVG"),
    _RegistryEntry("CHRONOS-SEMANTIC-FILTER-001", "CHRONOS-SEMANTIC-FILTER-001", "semantic", "6.2", "filter", "Filter semantics change"),
    _RegistryEntry("CHRONOS-SEMANTIC-JOIN-001", "CHRONOS-SEMANTIC-JOIN-001", "semantic", "6.2", "join", "Join semantics change"),
    _RegistryEntry("CHRONOS-SEMANTIC-EXPRESSION-001", "CHRONOS-SEMANTIC-EXPRESSION-001", "semantic", "6.2", "derived_expression", "Derived expression change"),
    _RegistryEntry("CHRONOS-PR-PRIMARY-001", "CHRONOS-PR-PRIMARY-001", "pull_request", "6.3", "primary", "Primary multi-file PR"),
    _RegistryEntry("CHRONOS-PR-COHERENT-001", "CHRONOS-PR-COHERENT-001", "pull_request", "6.3", "coherent", "Coherent multi-file PR"),
    _RegistryEntry("CHRONOS-PR-NO-MATERIAL-001", "CHRONOS-PR-NO-MATERIAL-001", "pull_request", "6.3", "no_material", "No-material-change PR"),
    _RegistryEntry("CHRONOS-PR-CONFLICT-001", "CHRONOS-PR-CONFLICT-001", "pull_request", "6.3", "conflict", "Conflicting multi-file PR"),
    _RegistryEntry("CHRONOS-REPAIR-PRIMARY-001", "CHRONOS-REPAIR-PRIMARY-001", "repair", "6.4", "primary", "Primary repair candidate"),
    _RegistryEntry("CHRONOS-REPAIR-COHERENT-001", "CHRONOS-REPAIR-COHERENT-001", "repair", "6.4", "coherent", "Coherent PR - no supported automatic repair"),
    _RegistryEntry("CHRONOS-REPAIR-NO-MATERIAL-001", "CHRONOS-REPAIR-NO-MATERIAL-001", "repair", "6.4", "no_material", "No-material-change repair review"),
    _RegistryEntry("CHRONOS-REPAIR-CONFLICT-001", "CHRONOS-REPAIR-CONFLICT-001", "repair", "6.4", "conflict", "Conflict-blocked repair"),
    _RegistryEntry("CHRONOS-REPAIR-DELETE-001", "CHRONOS-REPAIR-DELETE-001", "repair", "6.4", "delete", "Deletion repair candidate"),
    _RegistryEntry("CHRONOS-REPAIR-TYPE-001", "CHRONOS-REPAIR-TYPE-ALIGNMENT-001", "repair", "6.4", "type_alignment", "Type-alignment repair candidate"),
)
_BY_ID = {item.analysis_id: item for item in _REGISTRY}
_SUPPORT_PREDECESSORS = {
    "CHRONOS-PR-DELETE-REPAIR-001": "CHRONOS-PR-DELETE-REPAIR-001",
    "CHRONOS-PR-TYPE-ALIGNMENT-001": "CHRONOS-PR-TYPE-ALIGNMENT-001",
}


class Phase6PresentationService:
    """Expose only complete packages frozen by the Phase 6.5 replay records."""

    def __init__(self, repository_root: str | Path) -> None:
        self._root = Path(repository_root).resolve()
        self._package_root = self._root / "certified_packages" / "phase6"
        self._release_root = self._root / "artifacts" / "certifications" / "phase-6-rerun"

    def get_release(self) -> ReleaseCertificationDTO:
        release = self._release()
        top = release["phase_6_certification.json"]
        manifest = release["manifest.json"]
        release_manifest = release["phase_6_release_manifest.json"]
        tests = release["test_execution_summary.json"]
        golden = release["golden_fixture_certification.json"]
        state = top["certification_state"]
        self._require(state in _CERTIFIED_STATES, "Phase 6 release is not certified.")
        limitations = tuple(top["non_blocking_limitations"])
        self._require(limitations == ("seven live DataHub-dependent tests intentionally skipped",), "Phase 6 limitation contract is inconsistent.")
        certification = Phase6CertificationDTO(
            state=state,
            release_id=top["release_id"],
            certification_version=top["certification_version"],
            package_fingerprint=semantic_fingerprint(manifest),
            release_manifest_fingerprint=manifest["release_manifest_fingerprint"],
            top_level_certification_fingerprint=manifest["top_level_certification_fingerprint"],
            limitations=limitations,
        )
        return ReleaseCertificationDTO(
            certification=certification,
            source_commit=release_manifest["source_commit"],
            source_tree=release_manifest["source_tree"],
            test_totals=TestTotalsDTO(**tests["totals"]),
            skipped_test_count=release["skipped_test_justification.json"]["skip_count"],
            supported_capabilities=tuple(release_manifest["supported_capabilities"]),
            unsupported_capabilities=tuple(release_manifest["unsupported_capabilities"]),
            golden_preservation_state=golden["state"],
        )

    def list_analyses(self) -> AnalysisIndexDTO:
        certification = self.get_release().certification
        return AnalysisIndexDTO(
            certification=certification,
            analyses=tuple(self._summary(entry, certification) for entry in _REGISTRY),
        )

    def get_analysis(self, analysis_id: str) -> AnalysisDetailDTO:
        entry = self._entry(analysis_id)
        artifacts = self._package(entry)
        certification = self.get_release().certification
        if entry.analysis_type == "structural":
            return self._structural(entry, artifacts, certification)
        if entry.analysis_type == "semantic":
            return self._semantic(entry, artifacts, certification)
        if entry.analysis_type == "pull_request":
            return self._pr(entry, artifacts, certification)
        return self._repair(entry, artifacts, certification)

    def get_graph(self, analysis_id: str, mode: GraphMode | None = None) -> AnalysisGraphDTO:
        entry = self._entry(analysis_id)
        artifacts = self._package(entry)
        available: tuple[GraphMode, ...] = (
            ("CURRENT", "PROPOSED", "PROJECTED_REPAIRED")
            if entry.analysis_type == "repair"
            else ("CURRENT", "PROPOSED", "DIFF")
        )
        selected = mode or (
            "PROJECTED_REPAIRED" if entry.analysis_type == "repair" else "PROPOSED"
        )
        self._require(selected in available, "The requested graph mode is unsupported for this analysis.")
        if entry.analysis_type == "repair" and selected in {"CURRENT", "PROPOSED"}:
            predecessor_id = artifacts["manifest.json"]["predecessor_analysis_id"]
            if predecessor_id in _BY_ID:
                raw = self._package(self._entry(predecessor_id))["future_metadata_graph.json"]
            else:
                raw = self._support_predecessor_graph(artifacts["manifest.json"])
        else:
            graph_name = "projected_future_metadata_graph.json" if entry.analysis_type == "repair" else "future_metadata_graph.json"
            raw = artifacts[graph_name]
        if selected == "CURRENT":
            return self._map_current_graph(entry, raw, available)
        return self._map_graph(entry, raw, selected, available)

    def get_evidence(self, analysis_id: str) -> tuple[EvidenceDTO, ...]:
        entry = self._entry(analysis_id)
        artifacts = self._package(entry)
        records: list[EvidenceDTO] = []
        if entry.analysis_type == "repair":
            for item in artifacts["repairability_classification.json"]["classifications"]:
                records.append(EvidenceDTO(
                    evidence_id=item["root_cause_id"], evidence_class="CODE-DERIVED",
                    subject=item["root_type"], statement=item["reason"],
                    certainty=item["repairability"],
                ))
        elif entry.analysis_type == "pull_request":
            coherence = artifacts["coherence_evaluation.json"]
            for item in coherence["findings"] + coherence["conflicts"]:
                records.append(EvidenceDTO(
                    evidence_id=item.get("finding_id", item.get("conflict_id")),
                    evidence_class="CODE-DERIVED", subject=item.get("file_path", item.get("current_field", "repository")),
                    statement=item["explanation"], certainty=coherence["state"],
                ))
        else:
            impact = artifacts["impact_synthesis.json"]
            for item in impact.get("required_evidence", []):
                records.append(EvidenceDTO(
                    evidence_id=item.get("required_evidence_id", item.get("evidence_id", "required-evidence")),
                    evidence_class="MISSING EVIDENCE", subject=item.get("subject", entry.analysis_id),
                    statement=item.get("reason", "Evidence remains required."), certainty="REQUIRED",
                ))
        return tuple(records[:100])

    def get_repair(self, analysis_id: str) -> RepairAnalysisView:
        detail = self.get_analysis(analysis_id)
        if not isinstance(detail, RepairAnalysisView):
            raise CertifiedReviewNotFound("The requested analysis is not a repair package.")
        return detail

    def get_patch(self, analysis_id: str, patch_id: str) -> PatchPreviewDTO:
        entry = self._entry(analysis_id)
        if entry.analysis_type != "repair" or not re.fullmatch(r"patch-[0-9]{1,3}", patch_id):
            raise CertifiedReviewNotFound("The requested certified patch was not found.")
        artifacts = self._package(entry)
        records = artifacts["file_patch_records.json"]["files"]
        index = int(patch_id.split("-")[1])
        if index >= len(records):
            raise CertifiedReviewNotFound("The requested certified patch was not found.")
        record = records[index]
        package = self._package_root / entry.directory
        patch_path = self._safe_member(package, record["file_patch_path"])
        candidate_path = self._safe_member(package, record["candidate_preview_path"])
        patch = patch_path.read_text(encoding="utf-8")
        self._require(len(patch.encode("utf-8")) <= 64 * 1024, "Patch preview is too large.")
        self._require(semantic_fingerprint({"unified_diff": patch}) == record["patch_fingerprint"], "Patch preview fingerprint mismatch.")
        candidate = candidate_path.read_text(encoding="utf-8")
        parsed = _patch_lines(patch)
        original = tuple(item.text for item in parsed if item.kind in {"context", "removal"})[:80]
        return PatchPreviewDTO(
            analysis_id=analysis_id, patch_id=patch_id, file=record["target_path"],
            fingerprint=record["patch_fingerprint"], lines=parsed[:200],
            original_excerpt=original, candidate_excerpt=tuple(candidate.splitlines()[:80]),
            label="CANDIDATE - NOT APPLIED",
        )

    def _summary(self, entry: _RegistryEntry, certification: Phase6CertificationDTO) -> AnalysisSummaryDTO:
        artifacts = self._package(entry)
        manifest = artifacts["manifest.json"]
        proposal = artifacts[_proposal_name(entry)]
        scenario_id = proposal.get("scenario_id") or manifest.get("scenario_id") or entry.scenario
        proposal_id = manifest.get("proposal_id") or proposal["proposal_id"]
        decision = _decision(manifest, entry)
        repository = manifest.get("repository_identity") or {}
        coherence = manifest.get("original_coherence") or artifacts.get("coherence_evaluation.json", {}).get("state")
        files = manifest.get("changed_file_summary", {}).get("changed_file_count", manifest.get("affected_file_count", 0))
        datasets = _dataset_count(artifacts)
        return AnalysisSummaryDTO(
            analysis_id=entry.analysis_id, analysis_type=entry.analysis_type,
            display_name=entry.display_name, scenario_id=scenario_id, proposal_id=proposal_id,
            certification_state=certification.state, decision=decision, operation=manifest["operation"],
            repository_identity=repository.get("repository_name") if isinstance(repository, dict) else None,
            base_identity=_short(manifest.get("base_commit")), head_identity=_short(manifest.get("head_commit")),
            coherence=coherence, conflict_count=manifest.get("conflict_count", 0),
            root_cause_count=manifest.get("root_cause_count", manifest.get("selected_root_count", 0)),
            affected_file_count=files, affected_dataset_count=datasets,
            repair_action_count=manifest.get("repair_action_count", 0), configured_at=proposal.get("created_at"),
            warnings=tuple(manifest.get("warnings", [])), limitations=certification.limitations,
            manifest_fingerprint=semantic_fingerprint(manifest),
        )

    def _base(self, entry, artifacts, certification):
        manifest = artifacts["manifest.json"]
        proposal = artifacts[_proposal_name(entry)]
        return dict(
            analysis_id=entry.analysis_id, analysis_type=entry.analysis_type,
            display_name=entry.display_name, scenario_id=proposal.get("scenario_id", entry.scenario),
            proposal_id=manifest.get("proposal_id") or proposal["proposal_id"], operation=manifest["operation"],
            decision=_decision(manifest, entry), certification=certification,
            manifest_fingerprint=semantic_fingerprint(manifest), warnings=tuple(manifest.get("warnings", [])),
            limitations=certification.limitations,
        )

    def _structural(self, entry, artifacts, certification):
        source = artifacts["counterfactual_source_state.json"]["source_change"]
        contract = artifacts["change_semantic_contract.json"]
        compatibility = artifacts["compatibility_evaluation.json"]["aggregate"]
        impact = artifacts["technical_impact_analysis.json"]
        synthesis = artifacts["impact_synthesis.json"]
        metrics = artifacts["dependency_propagation.json"]["metrics"]
        current_field = source["current_field_path"]
        projected_field = source.get("projected_field_path")
        return StructuralAnalysisView(**self._base(entry, artifacts, certification), change=StructuralChangeDTO(
            dataset_urn=contract["dataset_urn"], current_field=current_field,
            proposed_field=projected_field if projected_field != current_field else None,
            current_type=source.get("current_normalized_type"), proposed_type=source.get("projected_normalized_type"),
            identity_mapping=contract["identity_mapping"]["classification"],
            compatibility=_compatibility_label(compatibility),
            downstream_fields=metrics.get("downstream_field_count", 0),
            downstream_datasets=metrics.get("downstream_dataset_count", 0),
            root_causes=tuple(item["root_cause_id"] for item in impact["root_causes"]),
            blocking_questions=tuple(item["question"] for item in synthesis["blocking_questions"]),
            required_evidence=tuple(item.get("evidence_class", "required evidence") for item in synthesis["required_evidence"]),
        ))

    def _semantic(self, entry, artifacts, certification):
        diff = artifacts["semantic_diff.json"]
        compatibility = artifacts["compatibility_evaluation.json"]
        synthesis = artifacts["impact_synthesis.json"]
        impact = artifacts["technical_impact_analysis.json"]
        deltas = []
        for item in diff["semantic_deltas"] + diff["structural_deltas"]:
            delta_type = item["delta_type"]
            if delta_type not in {"AGGREGATION_CHANGE", "FILTER_CHANGE", "JOIN_TYPE_CHANGE", "DERIVED_EXPRESSION_CHANGE", "OUTPUT_STRUCTURAL_CHANGE"}:
                delta_type = "OUTPUT_STRUCTURAL_CHANGE"
            deltas.append(SemanticDeltaDTO(
                delta_id=item["delta_id"], delta_type=delta_type,
                before=_representation(item.get("before_representation")), after=_representation(item.get("after_representation")),
                affected_output=item.get("affected_output_field"), affected_model=item["affected_model_urn"],
                scope="FIELD-SPECIFIC" if item.get("scope") == "OUTPUT_FIELD" else "MODEL-WIDE",
                certainty=item.get("certainty", "DERIVED"), evidence_class="CODE-DERIVED",
                potential_consequence=item.get("explanation", "Static semantic behavior may change."),
                missing_evidence=tuple(record.get("evidence_class", "runtime evidence") for record in synthesis["required_evidence"]),
            ))
        return SemanticAnalysisView(**self._base(entry, artifacts, certification),
            model_dataset_urn=diff["model_dataset_urn"], before_fingerprint=diff["before_ast_fingerprint"],
            after_fingerprint=diff["after_ast_fingerprint"], semantic_compatibility=compatibility["semantic_compatibility"],
            structural_compatibility=compatibility["structural_compatibility"], deltas=tuple(deltas),
            affected_output_fields=tuple(sorted({item.affected_output for item in deltas if item.affected_output})),
            root_causes=tuple(item["root_cause_id"] for item in impact["root_causes"]),
            blocking_questions=tuple(item["question"] for item in synthesis["blocking_questions"]),
        )

    def _pr(self, entry, artifacts, certification):
        manifest = artifacts["manifest.json"]
        inventory = artifacts["changed_file_inventory.json"]
        results = {item["file_change_id"]: item for item in artifacts["file_analysis_results.json"]["results"]}
        files = tuple(ChangedFileDTO(
            file_id=item["file_change_id"], path=item.get("head_path") or item.get("base_path"), status=item["status"],
            category=item["category"], parser=item["parser_assignment"],
            material_state=results.get(item["file_change_id"], {}).get("materiality", "SUPPORTED_STATIC"),
            delta_count=len(results.get(item["file_change_id"], {}).get("delta_ids", [])), warning_count=len(item["warnings"]),
            resolved_entity_count=len(results.get(item["file_change_id"], {}).get("resolved_entities", [])),
            unresolved_reference_count=len(results.get(item["file_change_id"], {}).get("unresolved_references", [])),
        ) for item in inventory["files"])
        coherence = artifacts["coherence_evaluation.json"]
        groups = tuple(LogicalGroupDTO(
            group_id=item["logical_change_id"], current_identity=item.get("current_field"),
            proposed_identities=tuple(item["future_fields"]), contributing_file_ids=tuple(item["contributing_file_ids"]),
            structural_change_ids=tuple(item["structural_delta_ids"]), semantic_change_ids=tuple(item["semantic_delta_ids"]),
            stale_reference_ids=tuple(value for value in item["evidence_references"] if value.startswith("pr-stale-")),
            coherence=item["coherence_state"], conflict_ids=(), root_ids=tuple(item["root_cause_candidates"]),
            evidence_ids=tuple(item["evidence_references"]),
        ) for item in artifacts["logical_change_groups.json"]["groups"])
        conflicts = tuple(ConflictDTO(
            conflict_id=item["conflict_id"], current_entity=item.get("current_field", "unknown"),
            proposed_identities=tuple(item.get("proposed_future_fields", [])),
            supporting_file_ids=tuple(item.get("file_change_ids", [])), reason=item["explanation"],
            required_evidence=("Resolve competing certified identity claims",),
        ) for item in coherence["conflicts"])
        repository = manifest["repository_identity"]
        roots = artifacts["technical_impact_analysis.json"]["root_causes"]
        return PullRequestAnalysisView(**self._base(entry, artifacts, certification),
            repository=repository["repository_name"], base_identity=_short(manifest["base_commit"]),
            head_identity=_short(manifest["head_commit"]), coherence=coherence["state"], changed_files=files,
            logical_groups=groups, conflicts=conflicts,
            root_causes=tuple(item["root_cause_id"] for item in roots),
        )

    def _repair(self, entry, artifacts, certification):
        manifest = artifacts["manifest.json"]
        classifications = tuple(RepairabilityDTO(
            root_id=item["root_cause_id"], root_type=item["root_type"], state=item["repairability"],
            reason=item["reason"], evidence_ids=tuple(item["supporting_evidence"]),
            remaining_uncertainty=tuple(item["remaining_uncertainty"]),
        ) for item in artifacts["repairability_classification.json"]["classifications"])
        order = {value: index + 1 for index, value in enumerate(artifacts["repair_actions.json"]["application_order"])}
        actions = tuple(RepairActionDTO(
            action_id=item["repair_action_id"], application_order=order[item["repair_action_id"]], file=item["target_path"],
            exact_target=item.get("target_location") or item["current_evidence"].get("task_id", item["target_path"]),
            current_value=str(item["current_evidence"].get("value", "")),
            proposed_value=str(item["intended_future_evidence"].get("value", "")), rule=item["repair_rule_id"],
            root_id=item["root_cause_id"], evidence_ids=tuple(item["intended_future_evidence"]["identity_claim_evidence"]),
            dependencies=tuple(item["dependency_actions"]),
            protected_semantics=tuple(item["static_validation_requirements"]),
            remaining_validation=tuple(item["remaining_evidence_requirements"]),
        ) for item in artifacts["repair_actions.json"]["repair_actions"])
        static_state = artifacts["static_patch_validation.json"]["state"]
        protected_state = artifacts["protected_semantics_validation.json"]["state"]
        patches = tuple(PatchSummaryDTO(
            patch_id=f"patch-{index}", file=item["target_path"], hunk_count=item["patch_hunk_count"],
            fingerprint=item["patch_fingerprint"], action_ids=tuple(item["repair_action_ids"]),
            protected_semantics_state=protected_state, static_validation_state=static_state,
        ) for index, item in enumerate(artifacts["file_patch_records.json"]["files"]))
        raw = artifacts["repair_comparison.json"]
        comparison = RepairComparisonDTO(
            original_coherence=raw["original_coherence"], projected_coherence=raw["projected_coherence"],
            original_stale_references=raw.get("original_stale_reference_count", 0),
            projected_stale_references=raw.get("projected_stale_reference_count", 0), targeted_roots=len(raw.get("targeted_root_ids", [])),
            projected_closed_roots=len(raw.get("projected_closed_root_ids", [])), remaining_roots=len(raw.get("unchanged_root_ids", [])),
            new_roots=len(raw.get("new_unresolved_root_ids", [])), conflicts_before=len(raw.get("original_conflict_ids", [])),
            conflicts_after=len(raw.get("projected_conflict_ids", [])), unresolved_semantic_questions=len(raw.get("unresolved_semantic_questions", [])),
        )
        certified_phase7 = tuple(
            item.get("validation_id", item.get("validation", item.get("name")))
            if isinstance(item, dict) else str(item)
            for item in artifacts["required_phase_7_validation.json"]["validations"]
        )
        self._require(all(isinstance(item, str) and item for item in certified_phase7), "Phase 7 validation identity is invalid.")
        self._require(
            {
                "apply_candidate_patch_in_disposable_checkout",
                "execute_affected_project_validation",
                "obtain_human_review_and_owner_approval",
                "verify_runtime_and_data_semantics",
            }.issubset(certified_phase7),
            "Certified Phase 7 validation coverage is incomplete.",
        )
        remaining = artifacts["remaining_findings.json"]
        return RepairAnalysisView(**self._base(entry, artifacts, certification),
            predecessor_analysis_id=manifest["predecessor_analysis_id"], repair_disposition=manifest["repair_disposition"],
            repair_completeness=manifest["repair_completeness"],
            projected_state_label="PROJECTED REPAIRED - STATIC ONLY - RUNTIME UNVERIFIED",
            repairability=classifications, actions=actions, patches=patches, comparison=comparison,
            remaining_findings=tuple(
                f"{item.get('root_cause_id', 'root')}: {item.get('root_type', item.get('compatibility_state', 'unresolved'))}"
                if isinstance(item, dict) else str(item)
                for item in remaining["remaining_predecessor_roots"]
            ), phase_7_requirements=_PHASE_7_PRESENTATION_REQUIREMENTS,
        )

    def _map_graph(self, entry, raw, mode: GraphMode, available: tuple[GraphMode, ...]):
        nodes = []
        for item in raw.get("nodes", [])[:160]:
            node_id = item.get("node_id") or item.get("field_key") or item.get("future_key")
            self._require(isinstance(node_id, str), "Graph node identity is missing.")
            state = str(item.get("state", item.get("node_state", "PROJECTED")))
            nodes.append(GraphNodeDTO(node_id=node_id, label=_compact(node_id), node_type=str(item.get("node_type", "FIELD")), state=state, evidence_class=_node_evidence(state)))
        node_ids = {item.node_id for item in nodes}
        edges = []
        for item in raw.get("relationships", [])[:240]:
            edge_id = item.get("relationship_id")
            source = item.get("source") or item.get("upstream_key")
            target = item.get("target") or item.get("downstream_key")
            if source not in node_ids or target not in node_ids:
                continue
            category = _edge_category(item)
            edges.append(GraphEdgeDTO(edge_id=edge_id, source=source, target=target, category=category, evidence_class=_edge_evidence(category), state=str(item.get("classification", item.get("state", "PROJECTED")))))
        edge_ids = {item.edge_id for item in edges}
        paths = []
        for item in raw.get("paths", [])[:12]:
            item_nodes = tuple(item.get("node_ids", item.get("node_keys", [])))
            item_edges = tuple(value for value in item.get("relationship_ids", []) if value in edge_ids)
            if set(item_nodes) <= node_ids and set(item_edges) <= edge_ids:
                root = item.get("root_cause_id")
                paths.append(GraphPathDTO(path_id=item["path_id"], node_ids=item_nodes, edge_ids=item_edges,
                    root_ids=(root,) if root else (), contributing_file_ids=tuple(item.get("contributing_file_ids", [])),
                    target=item.get("target", item.get("target_key", item_nodes[-1])), evidence_class="STATIC PROJECTED"))
        return AnalysisGraphDTO(
            analysis_id=entry.analysis_id,
            mode=mode,
            available_modes=available,
            nodes=tuple(nodes),
            edges=tuple(edges),
            representative_paths=tuple(paths),
        )

    def _map_current_graph(self, entry, raw, available: tuple[GraphMode, ...]):
        node_metadata: dict[str, tuple[str, str]] = {}
        for item in raw.get("nodes", [])[:160]:
            keys = (item.get("node_id"), item.get("current_key"), item.get("future_key"))
            for key in keys:
                if isinstance(key, str):
                    node_metadata[key] = (str(item.get("node_type", "FIELD")), _compact(key))
        edges: list[GraphEdgeDTO] = []
        endpoint_ids: set[str] = set()
        for item in raw.get("relationships", [])[:240]:
            observed = item.get("edge_kind") == "OBSERVED_DATAHUB_EDGE" or bool(item.get("current_edge_id"))
            if not observed:
                continue
            source = item.get("current_upstream_key") or item.get("source") or item.get("upstream_key")
            target = item.get("current_downstream_key") or item.get("target") or item.get("downstream_key")
            edge_id = item.get("current_edge_id") or item.get("relationship_id")
            if not all(isinstance(value, str) for value in (source, target, edge_id)):
                continue
            endpoint_ids.update((source, target))
            edges.append(GraphEdgeDTO(
                edge_id=edge_id,
                source=source,
                target=target,
                category="OBSERVED_DATAHUB_EDGE",
                evidence_class="OBSERVED DATAHUB",
                state="CURRENT",
            ))
        nodes = tuple(
            GraphNodeDTO(
                node_id=node_id,
                label=node_metadata.get(node_id, ("FIELD", _compact(node_id)))[1],
                node_type=node_metadata.get(node_id, ("FIELD", ""))[0],
                state="CURRENT",
                evidence_class="OBSERVED DATAHUB",
            )
            for node_id in sorted(endpoint_ids)
        )
        node_ids = {item.node_id for item in nodes}
        edge_ids = {item.edge_id for item in edges}
        paths = []
        for item in raw.get("paths", [])[:12]:
            path_nodes = tuple(item.get("current_node_ids", item.get("node_ids", [])))
            path_edges = tuple(item.get("current_relationship_ids", item.get("relationship_ids", [])))
            if path_nodes and set(path_nodes) <= node_ids and set(path_edges) <= edge_ids:
                root = item.get("root_cause_id")
                paths.append(GraphPathDTO(
                    path_id=f"current-{item['path_id']}",
                    node_ids=path_nodes,
                    edge_ids=path_edges,
                    root_ids=(root,) if root else (),
                    contributing_file_ids=tuple(item.get("contributing_file_ids", [])),
                    target=item.get("target", path_nodes[-1]),
                    evidence_class="OBSERVED DATAHUB",
                ))
        return AnalysisGraphDTO(
            analysis_id=entry.analysis_id,
            mode="CURRENT",
            available_modes=available,
            nodes=nodes,
            edges=tuple(edges),
            representative_paths=tuple(paths),
        )

    def _entry(self, analysis_id: str) -> _RegistryEntry:
        if not _SAFE_ID.fullmatch(analysis_id) or analysis_id not in _BY_ID:
            raise CertifiedReviewNotFound("The requested certified analysis was not found.")
        return _BY_ID[analysis_id]

    def _release(self):
        try:
            from chronos.phase6_certification import load_phase6_certification

            return load_phase6_certification(self._release_root)
        except Exception as exc:
            raise PresentationIntegrityError("Phase 6 release certification validation failed.") from exc

    def _package(self, entry: _RegistryEntry) -> dict[str, dict[str, Any]]:
        directory = (self._package_root / entry.directory).resolve()
        self._require(directory.parent == self._package_root.resolve(), "Analysis package path is unsafe.")
        manifest = _strict_json(directory / "manifest.json")
        expected = tuple(manifest.get("artifact_names", ()))
        self._require(expected and all(isinstance(name, str) and name.endswith(".json") and "/" not in name and "\\" not in name for name in expected), "Analysis manifest artifact list is invalid.")
        actual = {item.name for item in directory.iterdir()}
        allowed = set(expected) | ({"repairs"} if entry.analysis_type == "repair" else set())
        self._require(actual == allowed, "Analysis package is partial or contains unexpected files.")
        artifacts = {name: _strict_json(directory / name) for name in expected}
        self._require(artifacts["manifest.json"] == manifest, "Analysis manifest identity changed while loading.")
        fingerprints = manifest.get("artifact_fingerprints")
        self._require(isinstance(fingerprints, dict), "Analysis artifact fingerprints are missing.")
        for name in expected:
            if name == "manifest.json":
                continue
            self._require(fingerprints.get(name) == semantic_fingerprint(artifacts[name]), f"Analysis artifact fingerprint mismatch for {name}.")
        self._require(manifest.get("artifact_schema_version") == "1.0" and manifest.get("certification_status") == "certified", "Analysis package schema or certification is unsupported.")
        self._require((manifest.get("analysis_id") or manifest.get("repair_analysis_id")) == entry.analysis_id, "Analysis package identity mismatch.")
        replay = self._replay_record(entry)
        package_fp = manifest.get("analysis_semantic_fingerprint") or manifest.get("repair_semantic_fingerprint")
        self._require(package_fp == replay["semantic_fingerprint"], "Analysis package does not match the Phase 6.5 replay fingerprint.")
        if entry.analysis_type == "repair":
            self._require(manifest.get("patch_fingerprints") == replay["patch_fingerprints"], "Repair patch fingerprints do not match Phase 6.5.")
        serialized = json.dumps(artifacts, sort_keys=True)
        self._require(not _WINDOWS_PATH.search(serialized) and "-----BEGIN PRIVATE KEY-----" not in serialized and not re.search(r"https://[^/\s]+:[^@\s]+@", serialized), "Unsafe path or secret detected in analysis package.")
        return artifacts

    def _replay_record(self, entry):
        release = self._release()
        name = {"6.1": "phase_6_1_replay_certification.json", "6.2": "phase_6_2_replay_certification.json", "6.3": "phase_6_3_replay_certification.json", "6.4": "phase_6_4_replay_certification.json"}[entry.phase]
        records = release[name]["scenarios"]
        for item in records:
            if item["scenario"] == entry.scenario:
                return item
        raise PresentationIntegrityError(f"No Phase 6.5 replay record exists for {entry.analysis_id}.")

    def _support_predecessor_graph(self, repair_manifest: dict[str, Any]) -> dict[str, Any]:
        predecessor_id = repair_manifest["predecessor_analysis_id"]
        directory_name = _SUPPORT_PREDECESSORS.get(predecessor_id)
        self._require(directory_name is not None, "Repair predecessor package is not approved.")
        directory = (self._package_root / directory_name).resolve()
        self._require(directory.parent == self._package_root.resolve(), "Repair predecessor package path is unsafe.")
        manifest = _strict_json(directory / "manifest.json")
        names = tuple(manifest.get("artifact_names", ()))
        self._require(
            names and all(isinstance(name, str) and name.endswith(".json") and "/" not in name and "\\" not in name for name in names),
            "Repair predecessor manifest artifact list is invalid.",
        )
        self._require({item.name for item in directory.iterdir()} == set(names), "Repair predecessor package closure is invalid.")
        artifacts = {name: _strict_json(directory / name) for name in names}
        fingerprints = manifest.get("artifact_fingerprints")
        self._require(isinstance(fingerprints, dict), "Repair predecessor fingerprints are missing.")
        for name in names:
            if name != "manifest.json":
                self._require(fingerprints.get(name) == semantic_fingerprint(artifacts[name]), f"Repair predecessor fingerprint mismatch for {name}.")
        self._require(
            manifest.get("analysis_id") == predecessor_id
            and manifest.get("artifact_schema_version") == "1.0"
            and manifest.get("certification_status") == "certified",
            "Repair predecessor identity or certification is invalid.",
        )
        self._require(
            manifest.get("analysis_semantic_fingerprint") == repair_manifest.get("predecessor_analysis_fingerprint")
            and semantic_fingerprint(manifest) == repair_manifest.get("predecessor_manifest_fingerprint"),
            "Repair predecessor does not match the certified repair package.",
        )
        return artifacts["future_metadata_graph.json"]

    def _safe_member(self, root: Path, relative: str) -> Path:
        pure = PurePosixPath(relative)
        self._require(not pure.is_absolute() and ".." not in pure.parts and relative == pure.as_posix(), "Certified package member path is unsafe.")
        target = (root / Path(*pure.parts)).resolve()
        self._require(target.is_relative_to(root.resolve()) and target.is_file() and not target.is_symlink(), "Certified package member is unavailable.")
        return target

    @staticmethod
    def _require(condition: bool, message: str) -> None:
        if not condition:
            raise PresentationIntegrityError(message)


def _strict_json(path: Path) -> dict[str, Any]:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise PresentationIntegrityError(f"Duplicate key in {path.name}.")
            result[key] = value
        return result
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 5 * 1024 * 1024:
            raise PresentationIntegrityError(f"Unsafe package artifact {path.name}.")
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PresentationIntegrityError(f"Unable to load package artifact {path.name}.") from exc
    if not isinstance(value, dict):
        raise PresentationIntegrityError(f"Package artifact {path.name} is not an object.")
    return value


def _proposal_name(entry):
    return {"structural": "proposal.json", "semantic": "semantic_change_proposal.json", "pull_request": "pr_analysis_proposal.json", "repair": "repair_generation_proposal.json"}[entry.analysis_type]


def _decision(manifest, entry):
    if entry.analysis_type == "repair":
        return manifest["repair_disposition"]
    decision = manifest.get("decision", {})
    return decision.get("disposition", decision) if isinstance(decision, dict) else str(decision)


def _short(value):
    return value[:16] if isinstance(value, str) else None


def _dataset_count(artifacts):
    propagation = artifacts.get("dependency_propagation.json") or artifacts.get("projected_dependency_propagation.json") or {}
    metrics = propagation.get("metrics", {})
    return int(metrics.get("downstream_dataset_count", metrics.get("affected_dataset_count", 0)))


def _compatibility_label(value):
    for key in ("incompatible", "unknown", "conditionally_compatible", "compatible"):
        if value.get(key, 0):
            return key.upper()
    return "UNRESOLVED"


def _representation(value):
    if value is None:
        return "Not supplied"
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "; ".join(_representation(item) for item in value)
    if isinstance(value, dict):
        return str(value.get("normalized_expression") or value.get("expression") or value.get("function") or json.dumps(value, sort_keys=True))
    return str(value)


def _compact(value):
    return value.rsplit("|", 1)[-1] if "|" in value else value.removeprefix("repo-file:")


def _node_evidence(state):
    upper = state.upper()
    if "CURRENT" in upper or "OBSERVED" in upper:
        return "OBSERVED DATAHUB"
    if "REPOSITORY" in upper or "HEAD" in upper:
        return "CODE-DERIVED"
    return "COUNTERFACTUAL"


def _edge_category(item):
    value = item.get("edge_kind")
    if value in {"OBSERVED_DATAHUB_EDGE", "CODE_DERIVED_PROPOSED_EDGE", "COUNTERFACTUAL_EDGE", "REMOVED_EDGE", "UNRESOLVED_REFERENCE"}:
        return value
    classification = str(item.get("classification", item.get("state", ""))).upper()
    if "UNRESOLVED" in classification or "UNKNOWN" in classification:
        return "UNRESOLVED_REFERENCE"
    if "REMOVED" in classification:
        return "REMOVED_EDGE"
    if "OBSERVED" in classification:
        return "OBSERVED_DATAHUB_EDGE"
    return "COUNTERFACTUAL_EDGE"


def _edge_evidence(category):
    return {"OBSERVED_DATAHUB_EDGE": "OBSERVED DATAHUB", "CODE_DERIVED_PROPOSED_EDGE": "CODE-DERIVED", "COUNTERFACTUAL_EDGE": "COUNTERFACTUAL", "REMOVED_EDGE": "COUNTERFACTUAL", "UNRESOLVED_REFERENCE": "MISSING EVIDENCE"}[category]


def _patch_lines(patch: str) -> tuple[PatchLineDTO, ...]:
    old_line = new_line = None
    result = []
    for raw in patch.splitlines():
        if raw.startswith("@@"):
            match = re.search(r"-(\d+)(?:,\d+)? \+(\d+)", raw)
            if match:
                old_line, new_line = int(match.group(1)), int(match.group(2))
            result.append(PatchLineDTO(old_line=None, new_line=None, kind="header", text=raw))
        elif raw.startswith("+") and not raw.startswith("+++"):
            result.append(PatchLineDTO(old_line=None, new_line=new_line, kind="addition", text=raw[1:]))
            new_line = (new_line or 0) + 1
        elif raw.startswith("-") and not raw.startswith("---"):
            result.append(PatchLineDTO(old_line=old_line, new_line=None, kind="removal", text=raw[1:]))
            old_line = (old_line or 0) + 1
        else:
            text = raw[1:] if raw.startswith(" ") else raw
            result.append(PatchLineDTO(old_line=old_line, new_line=new_line, kind="context", text=text))
            if old_line is not None:
                old_line += 1
            if new_line is not None:
                new_line += 1
    return tuple(result)
