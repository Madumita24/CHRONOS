"""Deterministic cross-file correlation and composite future-state builders."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import asdict
from typing import Any

from chronos.semantic_engine.compatibility import rule_for_delta
from chronos.semantic_engine.models import DeltaType
from chronos.snapshot import CurrentMetadataSnapshot, FieldMachineKey
from chronos.structural_engine.compatibility_registry import evaluate_root_compatibility
from chronos.structural_engine.proposals import (
    FieldDeleteProposal,
    FieldRenameProposal,
    StructuralOperation,
)
from chronos.structural_engine.serialization import semantic_fingerprint, stable_id

from .models import CoherenceState, PullRequestAnalysisIdentity
from .proposals import pr_proposal_to_dict


def build_pre_certification_artifacts(
    snapshot,
    proposal,
    identity,
    pr_input,
    file_results,
) -> dict[str, dict[str, Any]]:
    correlated = _correlate(snapshot, proposal, pr_input, file_results)
    graph = _future_graph(snapshot, identity, correlated)
    propagation = _propagation(identity, graph, correlated["root_causes"])
    compatibility = _compatibility(identity, correlated, propagation)
    technical = _technical(identity, correlated, propagation, compatibility)
    context = _context(snapshot, identity, graph)
    severity = _severity(identity, correlated, propagation, technical, context)
    synthesis = _synthesis(identity, correlated, propagation, compatibility, severity)
    explanations = _explanations(identity, correlated, propagation, compatibility, synthesis)
    inventory = [_file_record(item.record) for item in pr_input.files]
    classifications = [
        {
            "file_change_id": item.record.file_change_id,
            "category": item.record.category.value,
            "parser_assignment": item.record.parser_assignment,
            "warnings": list(item.record.warnings),
        }
        for item in pr_input.files
    ]
    repository_state = _repository_state(identity, pr_input, file_results)
    metadata_state = _metadata_state(identity, correlated)
    change_sets = _change_sets(correlated["deltas"])
    artifacts = {
        "pr_analysis_proposal.json": _with(_header(identity, "pr_analysis_proposal"), proposal=pr_proposal_to_dict(proposal)),
        "proposal_validation.json": _with(_header(identity, "proposal_validation"), state="valid", checks=["strict_proposal", "snapshot_identity", "intake_mode", "repository_identity", "base_head_identity"]),
        "repository_identity.json": _with(_header(identity, "repository_identity"), repository=pr_input.repository_identity),
        "changed_file_inventory.json": _with(_header(identity, "changed_file_inventory"), files=inventory, summary=_inventory_summary(pr_input)),
        "file_classification.json": _with(_header(identity, "file_classification"), classifications=classifications),
        "file_analysis_results.json": _with(_header(identity, "file_analysis_results"), results=file_results),
        "structural_change_set.json": _with(_header(identity, "structural_change_set"), deltas=change_sets["structural"]),
        "semantic_change_set.json": _with(_header(identity, "semantic_change_set"), deltas=change_sets["semantic"]),
        "pipeline_change_set.json": _with(_header(identity, "pipeline_change_set"), deltas=change_sets["pipeline"]),
        "contract_quality_change_set.json": _with(_header(identity, "contract_quality_change_set"), deltas=change_sets["contract_quality"]),
        "entity_resolution.json": _with(_header(identity, "entity_resolution"), **correlated["entity_resolution"]),
        "logical_change_groups.json": _with(_header(identity, "logical_change_groups"), groups=correlated["logical_change_groups"]),
        "coherence_evaluation.json": _with(_header(identity, "coherence_evaluation"), state=correlated["coherence_state"].value, findings=correlated["coherence_findings"], conflicts=correlated["conflicts"]),
        "composite_change_set.json": _with(_header(identity, "composite_change_set"), **_composite(correlated, pr_input, file_results)),
        "counterfactual_repository_state.json": repository_state,
        "counterfactual_metadata_state.json": metadata_state,
        "future_metadata_graph.json": graph,
        "dependency_propagation.json": propagation,
        "compatibility_evaluation.json": compatibility,
        "technical_impact_analysis.json": technical,
        "business_context_propagation.json": context,
        "severity_criticality_analysis.json": severity,
        "impact_synthesis.json": synthesis,
        "explanation_bundle.json": explanations,
    }
    return artifacts


def _correlate(snapshot, proposal, pr_input, file_results):
    deltas = []
    file_by_id = {item.record.file_change_id: item for item in pr_input.files}
    for result in file_results:
        for raw in result["detected_deltas"]:
            item = dict(raw)
            item["file_change_id"] = result["file_change_id"]
            item.setdefault("file_path", file_by_id[result["file_change_id"]].record.head_path or file_by_id[result["file_change_id"]].record.base_path)
            deltas.append(item)
    deltas.sort(key=lambda item: item["delta_id"])
    mappings = {item.path: item for item in proposal.file_model_mappings}
    rename_claims = []
    for item in deltas:
        if item.get("delta_type") == "OUTPUT_COLUMN_RENAME":
            path = item["file_path"]
            mapping = mappings.get(path)
            rename_claims.append({
                "claim_id": stable_id("pr-claim", item["delta_id"], "sql-rename"),
                "claim_type": "SQL_OUTPUT_RENAME",
                "current_field": item["before_representation"],
                "future_field": item["after_representation"],
                "model_dataset_urn": mapping.model_dataset_urn if mapping else item.get("affected_model_urn"),
                "file_change_id": item["file_change_id"],
                "delta_ids": [item["delta_id"]],
                "evidence_class": "CODE_DERIVED_EVIDENCE",
            })
    schema_claims = _schema_rename_claims(deltas)
    conflicts = []
    logical_groups = []
    coherence_findings = []
    stale = []
    adapted = []
    claimed_delta_ids = set()
    for rename in rename_claims:
        related_schema = [
            item for item in schema_claims
            if item["current_field"] == rename["current_field"]
        ]
        future_names = {rename["future_field"], *(item["future_field"] for item in related_schema)}
        contributing = {rename["file_change_id"], *(item["file_change_id"] for item in related_schema)}
        related_ids = set(rename["delta_ids"])
        for item in related_schema:
            related_ids.update(item["delta_ids"])
        for result in file_results:
            path = file_by_id[result["file_change_id"]].record.head_path or file_by_id[result["file_change_id"]].record.base_path
            refs = _head_references(result)
            if rename["current_field"] in refs and result["file_change_id"] != rename["file_change_id"]:
                finding = {
                    "finding_id": stable_id("pr-stale", result["file_change_id"], rename["current_field"], rename["future_field"]),
                    "finding_type": "STALE_REFERENCE",
                    "current_field": rename["current_field"],
                    "future_field": rename["future_field"],
                    "file_change_id": result["file_change_id"],
                    "file_path": path,
                    "evidence_class": "CODE_DERIVED_EVIDENCE",
                    "explanation": f"The proposed repository still contains a supported static reference to {rename['current_field']} while the model proposes {rename['future_field']}.",
                }
                stale.append(finding)
                contributing.add(result["file_change_id"])
            if rename["future_field"] in refs:
                contributing.add(result["file_change_id"])
                adapted.append({
                    "reference_id": stable_id("pr-adapted", result["file_change_id"], rename["future_field"]),
                    "file_change_id": result["file_change_id"], "file_path": path,
                    "current_field": rename["current_field"], "future_field": rename["future_field"],
                    "model_dataset_urn": rename["model_dataset_urn"],
                    "evidence_class": "CODE_DERIVED_EVIDENCE",
                })
        if len(future_names) > 1:
            conflict = {
                "conflict_id": stable_id("pr-conflict", rename["current_field"], *sorted(future_names)),
                "conflict_type": "CONFLICTING_FUTURE_FIELD_IDENTITIES",
                "current_field": rename["current_field"],
                "proposed_future_fields": sorted(future_names),
                "file_change_ids": sorted(contributing),
                "evidence_class": "CODE_DERIVED_EVIDENCE",
                "explanation": "Supported files make contradictory future-identity claims; neither claim was overwritten.",
            }
            conflicts.append(conflict)
        group_delta_ids = {
            item["delta_id"] for item in deltas
            if item["file_change_id"] in contributing
            and (
                rename["current_field"] in _strings(item)
                or rename["future_field"] in _strings(item)
                or item.get("delta_class") == "SemanticSqlDelta"
            )
        } | related_ids
        claimed_delta_ids.update(group_delta_ids)
        group_state = (
            CoherenceState.INCONSISTENT if len(future_names) > 1 or any(item["file_change_id"] in contributing for item in stale)
            else CoherenceState.PARTIALLY_COHERENT if any(_result_dynamic(result) and result["file_change_id"] in contributing for result in file_results)
            else CoherenceState.COHERENT if related_schema
            else CoherenceState.UNRESOLVED
        )
        logical_groups.append({
            "logical_change_id": stable_id("logical-change", rename["model_dataset_urn"] or "unresolved", rename["current_field"], *sorted(future_names)),
            "change_categories": sorted({item["delta_class"] for item in deltas if item["delta_id"] in group_delta_ids}),
            "contributing_file_ids": sorted(contributing),
            "resolved_current_entities": [f"{rename['model_dataset_urn']}|{rename['current_field']}"] if rename["model_dataset_urn"] else [],
            "counterfactual_entities": [f"{rename['model_dataset_urn']}|{name}" for name in sorted(future_names)] if rename["model_dataset_urn"] else [],
            "structural_delta_ids": sorted(item["delta_id"] for item in deltas if item["delta_id"] in group_delta_ids and item["delta_class"] == "StructuralFieldDelta"),
            "semantic_delta_ids": sorted(item["delta_id"] for item in deltas if item["delta_id"] in group_delta_ids and item["delta_class"] == "SemanticSqlDelta"),
            "pipeline_delta_ids": sorted(item["delta_id"] for item in deltas if item["delta_id"] in group_delta_ids and item["delta_class"] in {"PipelineTaskDelta", "PipelineDependencyDelta", "DatasetReferenceDelta", "FieldReferenceDelta", "ConfigurationDelta"}),
            "contract_delta_ids": sorted(item["delta_id"] for item in deltas if item["delta_id"] in group_delta_ids and item["delta_class"] in {"ModelContractDelta", "QualityExpectationDelta"}),
            "evidence_references": sorted(group_delta_ids | {item["finding_id"] for item in stale if item["file_change_id"] in contributing}),
            "coherence_state": group_state.value,
            "warnings": ["execution_validity_unverified"],
            "root_cause_candidates": [],
            "current_field": rename["current_field"],
            "future_fields": sorted(future_names),
            "model_dataset_urn": rename["model_dataset_urn"],
        })
    for item in deltas:
        if item.get("delta_type") != "OUTPUT_COLUMN_REMOVED" or item["delta_id"] in claimed_delta_ids:
            continue
        claimed_delta_ids.add(item["delta_id"])
        logical_groups.append({
            "logical_change_id": stable_id("logical-change", item["affected_model_urn"], item["affected_output_field"], "removed"),
            "change_categories": ["StructuralFieldDelta"],
            "contributing_file_ids": [item["file_change_id"]],
            "resolved_current_entities": [f"{item['affected_model_urn']}|{item['affected_output_field']}"],
            "counterfactual_entities": [], "structural_delta_ids": [item["delta_id"]],
            "semantic_delta_ids": [], "pipeline_delta_ids": [], "contract_delta_ids": [],
            "evidence_references": [item["delta_id"]],
            "coherence_state": CoherenceState.UNRESOLVED.value,
            "warnings": ["output_removed_without_repository_wide_execution_evidence"],
            "root_cause_candidates": [], "current_field": item["affected_output_field"],
            "future_fields": [], "model_dataset_urn": item["affected_model_urn"],
            "removed": True,
        })
    ungrouped = [item for item in deltas if item["delta_id"] not in claimed_delta_ids and item.get("material", True)]
    if ungrouped:
        for key in sorted({(item["file_change_id"], item["delta_class"]) for item in ungrouped}):
            subset = [item for item in ungrouped if (item["file_change_id"], item["delta_class"]) == key]
            logical_groups.append({
                "logical_change_id": stable_id("logical-change", *key),
                "change_categories": [key[1]], "contributing_file_ids": [key[0]],
                "resolved_current_entities": [], "counterfactual_entities": [],
                "structural_delta_ids": [item["delta_id"] for item in subset if item["delta_class"] == "StructuralFieldDelta"],
                "semantic_delta_ids": [item["delta_id"] for item in subset if item["delta_class"] == "SemanticSqlDelta"],
                "pipeline_delta_ids": [item["delta_id"] for item in subset if "Pipeline" in item["delta_class"] or "Reference" in item["delta_class"]],
                "contract_delta_ids": [item["delta_id"] for item in subset if item["delta_class"] in {"ModelContractDelta", "QualityExpectationDelta"}],
                "evidence_references": [item["delta_id"] for item in subset],
                "coherence_state": CoherenceState.UNRESOLVED.value,
                "warnings": ["no_cross_file_identity_evidence"],
                "root_cause_candidates": [],
                "current_field": None, "future_fields": [], "model_dataset_urn": None,
            })
    material_deltas = [item for item in deltas if item.get("material", True) and item["delta_class"] != "UnsupportedFileDelta"]
    dynamic = [item for result in file_results for item in result["unresolved_references"] if item.get("reason") == "dynamic_python_expression"]
    if conflicts or stale:
        coherence = CoherenceState.INCONSISTENT
    elif dynamic:
        coherence = CoherenceState.PARTIALLY_COHERENT
    elif not material_deltas:
        coherence = CoherenceState.COHERENT
    elif logical_groups and all(item["coherence_state"] == CoherenceState.COHERENT.value for item in logical_groups):
        coherence = CoherenceState.COHERENT
    else:
        coherence = CoherenceState.UNRESOLVED
    coherence_findings.extend(stale)
    coherence_findings.extend({
        "finding_id": stable_id("pr-dynamic", item["code_reference"]),
        "finding_type": "UNRESOLVED_DYNAMIC_REFERENCE",
        "evidence_class": "CODE_DERIVED_EVIDENCE",
        "explanation": "A dynamic Python reference cannot be resolved by the certified static parser.",
        **item,
    } for item in dynamic)
    root_causes = _root_causes(deltas, stale, conflicts, logical_groups)
    for group in logical_groups:
        group["root_cause_candidates"] = sorted(
            root["root_cause_id"] for root in root_causes
            if root.get("logical_change_id") == group["logical_change_id"]
            or set(root["contributing_file_ids"]) & set(group["contributing_file_ids"])
        )
    entity_resolution = _entity_resolution(snapshot, file_results, logical_groups)
    return {
        "deltas": deltas,
        "material_delta_count": len(material_deltas),
        "logical_change_groups": sorted(logical_groups, key=lambda item: item["logical_change_id"]),
        "coherence_state": coherence,
        "coherence_findings": sorted(coherence_findings, key=lambda item: item["finding_id"]),
        "stale_references": sorted(stale, key=lambda item: item["finding_id"]),
        "adapted_references": sorted(adapted, key=lambda item: item["reference_id"]),
        "conflicts": sorted(conflicts, key=lambda item: item["conflict_id"]),
        "root_causes": root_causes,
        "entity_resolution": entity_resolution,
    }


def _schema_rename_claims(deltas):
    removed = defaultdict(list)
    added = defaultdict(list)
    for item in deltas:
        if item.get("delta_class") != "ModelContractDelta":
            continue
        scope = item.get("scope", "")
        if ":column:" not in scope:
            continue
        model = scope.split(":column:", 1)[0]
        if item.get("delta_type") == "COLUMN_REMOVED":
            removed[(item["file_change_id"], model)].append(item)
        elif item.get("delta_type") == "COLUMN_ADDED":
            added[(item["file_change_id"], model)].append(item)
    result = []
    for key in sorted(set(removed) & set(added)):
        if len(removed[key]) == len(added[key]) == 1:
            old, new = removed[key][0], added[key][0]
            result.append({
                "claim_id": stable_id("pr-claim", old["delta_id"], new["delta_id"]),
                "claim_type": "DBT_SCHEMA_COLUMN_RENAME_CANDIDATE",
                "current_field": old["before"]["name"],
                "future_field": new["after"]["name"],
                "file_change_id": key[0],
                "delta_ids": [old["delta_id"], new["delta_id"]],
                "evidence_class": "CODE_DERIVED_EVIDENCE",
            })
    return result


def _head_references(result):
    head = result.get("parsed_head") or {}
    values = set()
    if isinstance(head, dict):
        for item in head.get("references", []):
            if isinstance(item, dict) and isinstance(item.get("value"), str):
                values.add(item["value"])
        for task in head.get("tasks", []):
            for value in task.get("static_arguments", {}).values():
                if isinstance(value, str):
                    values.add(value)
    return values


def _result_dynamic(result):
    return any(item.get("reason") == "dynamic_python_expression" for item in result["unresolved_references"])


def _strings(value):
    result = set()
    if isinstance(value, str):
        result.add(value)
    elif isinstance(value, dict):
        for item in value.values():
            result.update(_strings(item))
    elif isinstance(value, list):
        for item in value:
            result.update(_strings(item))
    return result


def _root_causes(deltas, stale, conflicts, groups):
    group_for_delta = {
        delta_id: group["logical_change_id"]
        for group in groups
        for delta_id in group["evidence_references"]
    }
    result = []
    material_classes = {
        "StructuralFieldDelta": "STRUCTURAL_CHANGE",
        "SemanticSqlDelta": "SEMANTIC_DEFINITION_CHANGED",
        "ModelContractDelta": "CONTRACT_CHANGE",
        "QualityExpectationDelta": "QUALITY_EXPECTATION_CHANGED",
        "PipelineTaskDelta": "PIPELINE_TASK_CHANGED",
        "PipelineDependencyDelta": "PIPELINE_DEPENDENCY_CHANGED",
        "DatasetReferenceDelta": "DATASET_REFERENCE_CHANGED",
        "FieldReferenceDelta": "FIELD_REFERENCE_CHANGED",
        "ConfigurationDelta": "CONFIGURATION_CHANGED",
    }
    for item in deltas:
        if not item.get("material", True) or item["delta_class"] not in material_classes:
            continue
        result.append({
            "root_cause_id": stable_id("pr-root", item["delta_id"]),
            "root_type": material_classes[item["delta_class"]],
            "delta_ids": [item["delta_id"]],
            "contributing_file_ids": [item["file_change_id"]],
            "logical_change_id": group_for_delta.get(item["delta_id"]),
            "resolved_entities": list(item.get("references", item.get("input_references", []))),
            "evidence_state": "CODE_DERIVED",
            "compatibility_state": "UNRESOLVED",
            "scope": item.get("scope"),
        })
    for item in stale:
        result.append({
            "root_cause_id": stable_id("pr-root", item["finding_id"]),
            "root_type": "STALE_PIPELINE_OR_QUALITY_REFERENCE",
            "delta_ids": [], "contributing_file_ids": [item["file_change_id"]],
            "logical_change_id": None,
            "resolved_entities": [item["current_field"], item["future_field"]],
            "evidence_state": "CODE_DERIVED", "compatibility_state": "REPOSITORY_INCONSISTENT",
            "scope": item["file_path"],
        })
    for item in conflicts:
        result.append({
            "root_cause_id": stable_id("pr-root", item["conflict_id"]),
            "root_type": item["conflict_type"], "delta_ids": [],
            "contributing_file_ids": item["file_change_ids"], "logical_change_id": None,
            "resolved_entities": item["proposed_future_fields"],
            "evidence_state": "CODE_DERIVED", "compatibility_state": "CONFIRMED_CONFLICT",
            "scope": item["current_field"],
        })
    return sorted(result, key=lambda item: item["root_cause_id"])


def _entity_resolution(snapshot, file_results, groups):
    observed = {}
    unresolved = []
    for result in file_results:
        for item in result["resolved_entities"]:
            key = item.get("dataset_urn") or item.get("datahub_field_key")
            if key:
                observed[str(key)] = item
        unresolved.extend(result["unresolved_references"])
    counterfactual = []
    field_keys = {item.key.text for item in snapshot.fields}
    for group in groups:
        model = group.get("model_dataset_urn")
        current = group.get("current_field")
        if model and current:
            key = f"{model}|{current}"
            if key in field_keys:
                observed[key] = {
                    "datahub_field_key": key, "resolution_state": "RESOLVED",
                    "evidence_class": "OBSERVED_DATAHUB_EVIDENCE",
                }
            for future in group.get("future_fields", []):
                counterfactual.append({
                    "counterfactual_field_key": f"{model}|{future}",
                    "current_field_key": key,
                    "resolution_state": "COUNTERFACTUAL",
                    "evidence_class": "COUNTERFACTUAL_DERIVATION",
                })
    return {
        "resolved_entities": [observed[key] for key in sorted(observed)],
        "counterfactual_entities": sorted(counterfactual, key=lambda item: item["counterfactual_field_key"]),
        "unresolved_references": sorted(unresolved, key=str),
        "summary": {
            "resolved_count": len(observed), "counterfactual_count": len(counterfactual),
            "unresolved_count": len(unresolved),
        },
    }


def _future_graph(snapshot, identity, correlated):
    roots = []
    for group in correlated["logical_change_groups"]:
        model, current = group.get("model_dataset_urn"), group.get("current_field")
        if model and current:
            current_key = f"{model}|{current}"
            for root in correlated["root_causes"]:
                if root.get("logical_change_id") == group["logical_change_id"]:
                    roots.append({
                        "root_cause_id": root["root_cause_id"],
                        "current_origin": current_key,
                        "future_origins": [f"{model}|{item}" for item in group.get("future_fields", [])],
                        "contributing_file_ids": root["contributing_file_ids"],
                    })
    roots = sorted({item["root_cause_id"]: item for item in roots}.values(), key=lambda item: item["root_cause_id"])
    observed_edges = {item.edge_id: item for item in snapshot.lineage_edges}
    outgoing = defaultdict(list)
    for edge in snapshot.lineage_edges:
        outgoing[edge.upstream.text].append(edge)
    reachable_edges = {}
    for root in roots:
        queue = deque([root["current_origin"]])
        seen = {root["current_origin"]}
        while queue:
            current = queue.popleft()
            for edge in sorted(outgoing[current], key=lambda item: item.edge_id):
                reachable_edges[edge.edge_id] = edge
                if edge.downstream.text not in seen:
                    seen.add(edge.downstream.text)
                    queue.append(edge.downstream.text)
    nodes = {}
    relationships = []
    for edge_id in sorted(reachable_edges):
        edge = observed_edges[edge_id]
        for key in (edge.upstream.text, edge.downstream.text):
            nodes[key] = {"node_id": key, "node_type": "DATAHUB_FIELD", "state": "CURRENT_OBSERVED"}
        relationships.append({
            "relationship_id": stable_id("pr-edge", edge.edge_id),
            "edge_kind": "OBSERVED_DATAHUB_EDGE",
            "source": edge.upstream.text, "target": edge.downstream.text,
            "current_edge_id": edge.edge_id,
            "evidence_references": list(edge.evidence_ids),
            "mapping_group_ids": list(edge.mapping_group_ids),
            "transform_operations": list(edge.transform_operations),
        })
    for group in correlated["logical_change_groups"]:
        model, current = group.get("model_dataset_urn"), group.get("current_field")
        if not model or not current:
            continue
        source = f"{model}|{current}"
        nodes.setdefault(source, {"node_id": source, "node_type": "DATAHUB_FIELD", "state": "CURRENT_OBSERVED"})
        for future in group.get("future_fields", []):
            target = f"{model}|{future}"
            nodes[target] = {"node_id": target, "node_type": "COUNTERFACTUAL_FIELD", "state": "PROPOSED"}
            relationships.append({
                "relationship_id": stable_id("pr-edge", group["logical_change_id"], source, target),
                "edge_kind": "COUNTERFACTUAL_EDGE", "source": source, "target": target,
                "current_edge_id": None,
                "evidence_references": group["evidence_references"],
                "mapping_group_ids": [], "transform_operations": ["RENAME"],
            })
        if group.get("removed"):
            target = f"removed:{source}"
            nodes[target] = {"node_id": target, "node_type": "REMOVED_FIELD", "state": "REMOVED"}
            relationships.append({
                "relationship_id": stable_id("pr-edge", group["logical_change_id"], "removed"),
                "edge_kind": "REMOVED_EDGE", "source": source, "target": target,
                "current_edge_id": None, "evidence_references": group["evidence_references"],
                "mapping_group_ids": [], "transform_operations": ["REMOVE_OUTPUT"],
            })
    for reference in correlated["adapted_references"]:
        source = f"repo-file:{reference['file_path']}"
        target = f"{reference['model_dataset_urn']}|{reference['future_field']}"
        nodes[source] = {"node_id": source, "node_type": "REPOSITORY_FILE", "state": "PROPOSED_HEAD"}
        nodes.setdefault(target, {"node_id": target, "node_type": "COUNTERFACTUAL_FIELD", "state": "PROPOSED"})
        relationships.append({
            "relationship_id": stable_id("pr-edge", reference["reference_id"]),
            "edge_kind": "CODE_DERIVED_PROPOSED_EDGE", "source": source, "target": target,
            "current_edge_id": None, "evidence_references": [reference["reference_id"]],
            "mapping_group_ids": [], "transform_operations": ["STATIC_REFERENCE"],
        })
    for finding in correlated["stale_references"]:
        file_node = f"repo-file:{finding['file_path']}"
        target = next(
            (f"{group['model_dataset_urn']}|{finding['current_field']}" for group in correlated["logical_change_groups"] if group.get("model_dataset_urn") and group.get("current_field") == finding["current_field"]),
            f"code-field:{finding['current_field']}",
        )
        nodes[file_node] = {"node_id": file_node, "node_type": "REPOSITORY_FILE", "state": "PROPOSED_HEAD"}
        nodes.setdefault(target, {"node_id": target, "node_type": "CODE_REFERENCE", "state": "UNRESOLVED"})
        relationships.append({
            "relationship_id": stable_id("pr-edge", finding["finding_id"]),
            "edge_kind": "UNRESOLVED_REFERENCE", "source": file_node, "target": target,
            "current_edge_id": None, "evidence_references": [finding["finding_id"]],
            "mapping_group_ids": [], "transform_operations": [],
        })
    relationships = sorted({item["relationship_id"]: item for item in relationships}.values(), key=lambda item: item["relationship_id"])
    paths = _graph_paths(roots, relationships)
    value = _header(identity, "future_metadata_graph")
    value.update({
        "roots": roots, "nodes": [nodes[key] for key in sorted(nodes)],
        "relationships": relationships, "paths": paths,
        "edge_classification": {
            "observed": "Current supplied DataHub lineage only.",
            "counterfactual": "Explicit parser-derived proposed identity mapping.",
            "unresolved": "Static repository reference inconsistent with the proposed identity.",
        },
    })
    return value


def _graph_paths(roots, relationships):
    adjacency = defaultdict(list)
    for item in relationships:
        if item["edge_kind"] == "OBSERVED_DATAHUB_EDGE":
            adjacency[item["source"]].append(item)
    paths = {}
    for root in roots:
        queue = deque([(root["current_origin"], [root["current_origin"]], [])])
        while queue:
            current, nodes, edges = queue.popleft()
            for edge in sorted(adjacency[current], key=lambda item: item["relationship_id"]):
                if edge["target"] in nodes:
                    continue
                next_nodes = nodes + [edge["target"]]
                next_edges = edges + [edge["relationship_id"]]
                path_id = stable_id("pr-path", root["root_cause_id"], *next_edges)
                paths[path_id] = {
                    "path_id": path_id, "root_cause_id": root["root_cause_id"],
                    "node_ids": next_nodes, "relationship_ids": next_edges,
                    "target": edge["target"], "contributing_file_ids": root["contributing_file_ids"],
                    "observed_edge_count": len(next_edges), "code_derived_edge_count": 0,
                    "counterfactual_edge_count": 0,
                }
                queue.append((edge["target"], next_nodes, next_edges))
    return [paths[key] for key in sorted(paths)]


def _propagation(identity, graph, roots):
    root_by_id = {item["root_cause_id"]: item for item in roots}
    targets = defaultdict(lambda: {"root_cause_ids": set(), "file_change_ids": set(), "path_ids": set()})
    for path in graph["paths"]:
        item = targets[path["target"]]
        item["root_cause_ids"].add(path["root_cause_id"])
        item["file_change_ids"].update(path["contributing_file_ids"])
        item["path_ids"].add(path["path_id"])
    findings = [
        {
            "target_field_key": target,
            "root_cause_ids": sorted(value["root_cause_ids"]),
            "contributing_file_ids": sorted(value["file_change_ids"]),
            "path_ids": sorted(value["path_ids"]),
            "multipath": len(value["path_ids"]) > 1,
            "evidence_class": "COUNTERFACTUAL_DERIVATION",
        }
        for target, value in sorted(targets.items())
    ]
    datasets = {item["target_field_key"].rsplit("|", 1)[0] for item in findings if "|" in item["target_field_key"]}
    value = _header(identity, "dependency_propagation")
    value.update({
        "findings": findings,
        "metrics": {
            "root_count": len(root_by_id), "downstream_field_count": len(findings),
            "downstream_dataset_count": len(datasets), "path_count": len(graph["paths"]),
            "relationship_count": len(graph["relationships"]),
            "multipath_target_count": sum(item["multipath"] for item in findings),
            "maximum_depth": max((len(item["node_ids"]) - 1 for item in graph["paths"]), default=0),
        },
    })
    return value


def _compatibility(identity, correlated, propagation):
    evaluations = []
    has_dependencies = propagation["metrics"]["downstream_field_count"] > 0
    for item in correlated["deltas"]:
        if item.get("delta_class") == "SemanticSqlDelta":
            try:
                rule = rule_for_delta(DeltaType(item["delta_type"]))
            except ValueError:
                continue
            evaluations.append({
                "evaluation_id": stable_id("pr-compat", item["delta_id"]),
                "dimension": "SEMANTIC_COMPATIBILITY", "delta_id": item["delta_id"],
                "rule_id": rule.rule_id, "result": rule.result.value,
                "certainty": rule.evidence_certainty, "reason_code": rule.reason_code,
                "required_evidence": list(rule.required_evidence),
            })
        elif item.get("delta_type") == "OUTPUT_COLUMN_RENAME":
            proposal = FieldRenameProposal(
                proposal_id=identity.proposal_id, analysis_id=identity.analysis_id,
                operation=StructuralOperation.FIELD_RENAME,
                dataset_urn=item["affected_model_urn"], current_field_path=item["before_representation"],
                proposed_field_path=item["after_representation"],
                source_snapshot_fingerprint=identity.source_snapshot_fingerprint,
            )
            rule = evaluate_root_compatibility(
                proposal, current_native_type=None, current_normalized_type="UNKNOWN",
                has_dependencies=has_dependencies,
            )
            evaluations.append({
                "evaluation_id": stable_id("pr-compat", item["delta_id"]),
                "dimension": "STRUCTURAL_COMPATIBILITY", "delta_id": item["delta_id"],
                "rule_id": rule.rule_id, "result": rule.result.value,
                "certainty": rule.evidence_strength.value, "reason_code": rule.reason_code,
                "required_evidence": list(rule.required_evidence),
            })
        elif item.get("delta_type") == "OUTPUT_COLUMN_REMOVED":
            structural_proposal = FieldDeleteProposal(
                proposal_id=identity.proposal_id, analysis_id=identity.analysis_id,
                operation=StructuralOperation.FIELD_DELETE,
                dataset_urn=item["affected_model_urn"], current_field_path=item["affected_output_field"],
                source_snapshot_fingerprint=identity.source_snapshot_fingerprint,
            )
            rule = evaluate_root_compatibility(
                structural_proposal, current_native_type=None,
                current_normalized_type="UNKNOWN", has_dependencies=has_dependencies,
            )
            evaluations.append({
                "evaluation_id": stable_id("pr-compat", item["delta_id"]),
                "dimension": "STRUCTURAL_COMPATIBILITY", "delta_id": item["delta_id"],
                "rule_id": rule.rule_id, "result": rule.result.value,
                "certainty": rule.evidence_strength.value, "reason_code": rule.reason_code,
                "required_evidence": list(rule.required_evidence),
            })
    value = _header(identity, "compatibility_evaluation")
    value.update({
        "evaluations": sorted(evaluations, key=lambda item: item["evaluation_id"]),
        "repository_coherence": correlated["coherence_state"].value,
        "execution_validity": "UNVERIFIED",
        "dimensions_are_independent": True,
    })
    return value


def _technical(identity, correlated, propagation, compatibility):
    findings = []
    for root in correlated["root_causes"]:
        kind = root["root_type"]
        consequence = {
            "SEMANTIC_DEFINITION_CHANGED": "SEMANTIC_DEFINITION_CHANGED",
            "STALE_PIPELINE_OR_QUALITY_REFERENCE": "STALE_PIPELINE_REFERENCE",
            "CONFLICTING_FUTURE_FIELD_IDENTITIES": "CONTRACT_MISMATCH",
            "CONTRACT_CHANGE": "CONTRACT_MISMATCH",
            "QUALITY_EXPECTATION_CHANGED": "QUALITY_CHECK_STALE",
        }.get(kind, "UNRESOLVED_RENAME_ADAPTATION" if kind == "STRUCTURAL_CHANGE" else kind)
        target_count = sum(root["root_cause_id"] in item["root_cause_ids"] for item in propagation["findings"])
        findings.append({
            "finding_id": stable_id("pr-impact", root["root_cause_id"]),
            "root_cause_id": root["root_cause_id"], "consequence": consequence,
            "certainty": "CONFIRMED_REPOSITORY_STATE" if "CONFLICT" in root["compatibility_state"] or "INCONSISTENT" in root["compatibility_state"] else "UNRESOLVED_RUNTIME_EFFECT",
            "downstream_target_count": target_count,
            "contributing_file_ids": root["contributing_file_ids"],
        })
    value = _header(identity, "technical_impact_analysis")
    value.update({"root_causes": correlated["root_causes"], "findings": findings, "confirmed_runtime_failures": 0})
    return value


def _context(snapshot, identity, graph):
    datasets = {
        node["node_id"].rsplit("|", 1)[0]
        for node in graph["nodes"] if node["node_type"] in {"DATAHUB_FIELD", "COUNTERFACTUAL_FIELD"} and "|" in node["node_id"]
    }
    relationships = [
        {
            "relationship_id": item.relationship_id,
            "category": item.category.value,
            "source_key": item.source_key, "target_key": item.target_key,
            "state": item.state, "evidence_ids": list(item.evidence_ids),
        }
        for item in snapshot.relationships
        if any(dataset in item.source_key or dataset in item.target_key for dataset in datasets)
    ]
    value = _header(identity, "business_context_propagation")
    value.update({
        "connected_relationships": sorted(relationships, key=lambda item: item["relationship_id"]),
        "summary": {"connected_relationship_count": len(relationships)},
        "interpretation": "Connected certified context; no failure, criticality, or sensitivity is inferred.",
    })
    return value


def _severity(identity, correlated, propagation, technical, context):
    if correlated["conflicts"]:
        severity, rule = "high", "pr-severity-explicit-conflict"
    elif correlated["material_delta_count"] and propagation["metrics"]["downstream_field_count"]:
        severity, rule = "high", "pr-severity-unresolved-material-reach"
    elif correlated["material_delta_count"]:
        severity, rule = "moderate", "pr-severity-material-local"
    else:
        severity, rule = "low", "pr-severity-no-material-change"
    value = _header(identity, "severity_criticality_analysis")
    value.update({
        "severity_if_realized": severity, "severity_rule_id": rule,
        "repository_coherence": correlated["coherence_state"].value,
        "technical_certainty": "unresolved" if correlated["material_delta_count"] else "established_no_material_change",
        "breadth": "widespread" if propagation["metrics"]["downstream_dataset_count"] > 1 else "localized",
        "context_criticality": "connected_context_only" if context["summary"]["connected_relationship_count"] else "unknown",
        "file_count_not_used_as_severity": True,
    })
    return value


def _synthesis(identity, correlated, propagation, compatibility, severity):
    if correlated["material_delta_count"] == 0:
        disposition, certainty, rule = "no_material_change", "high_confidence", "pr-decision-no-material-change"
    elif correlated["conflicts"]:
        disposition, certainty, rule = "block_confirmed_incompatibility", "high_confidence", "pr-decision-explicit-conflict"
    else:
        disposition, certainty, rule = "hold_for_review", "high_confidence", "pr-decision-material-unresolved"
    questions, requirements = _questions(correlated)
    value = _header(identity, "impact_synthesis")
    value.update({
        "decision": {
            "disposition": disposition, "certainty": certainty, "decision_rule_id": rule,
            "precedence": ["confirmed_blocking_incompatibility", "material_unresolved_compatibility", "no_material_change"],
        },
        "summary": {
            "material_delta_count": correlated["material_delta_count"],
            "logical_change_group_count": len(correlated["logical_change_groups"]),
            "root_cause_count": len(correlated["root_causes"]),
            "conflict_count": len(correlated["conflicts"]),
            "coherence_state": correlated["coherence_state"].value,
            "downstream_field_count": propagation["metrics"]["downstream_field_count"],
            "confirmed_runtime_failure_count": 0,
        },
        "blocking_questions": questions, "required_evidence": requirements,
        "warnings": ["execution_validity_unverified"] if correlated["material_delta_count"] else [],
    })
    return value


def _questions(correlated):
    questions = []
    requirements = []
    for root in correlated["root_causes"]:
        kind = root["root_type"]
        if kind == "SEMANTIC_DEFINITION_CHANGED":
            text, evidence = "Is the parsed semantic definition change approved by the model owner?", ["approved_metric_or_semantic_definition", "execution_comparison", "downstream_semantic_tests"]
        elif kind == "STALE_PIPELINE_OR_QUALITY_REFERENCE":
            text, evidence = "Should the supported pipeline or quality reference still target the current field identity?", ["updated_pipeline_or_quality_mapping", "task_or_quality_validation"]
        elif kind == "CONFLICTING_FUTURE_FIELD_IDENTITIES":
            text, evidence = "Which explicitly proposed future field identity is authoritative?", ["one_consistent_model_and_contract_identity", "owner_approval"]
        elif kind == "STRUCTURAL_CHANGE":
            text, evidence = "Has every active consumer adapted to the proposed structural identity?", ["explicit_rename_mapping", "consumer_contract_or_execution_validation"]
        else:
            continue
        question_id = stable_id("pr-question", root["root_cause_id"])
        questions.append({
            "question_id": question_id, "root_cause_id": root["root_cause_id"],
            "question": text, "contributing_file_ids": root["contributing_file_ids"],
            "affected_entities": root["resolved_entities"], "downstream_scope": root["scope"],
            "required_evidence_types": evidence,
        })
        for evidence_type in evidence:
            requirements.append({
                "requirement_id": stable_id("pr-required-evidence", root["root_cause_id"], evidence_type),
                "root_cause_id": root["root_cause_id"], "requirement_type": evidence_type,
                "state": "MISSING", "instruction_type": "EVIDENCE_NOT_REPAIR",
            })
    return sorted(questions, key=lambda item: item["question_id"]), sorted(requirements, key=lambda item: item["requirement_id"])


def _explanations(identity, correlated, propagation, compatibility, synthesis):
    file_explanations = defaultdict(list)
    for root in correlated["root_causes"]:
        for file_id in root["contributing_file_ids"]:
            file_explanations[file_id].append(root["root_type"])
    value = _header(identity, "explanation_bundle")
    value.update({
        "pr_explanation": {
            "what_changed": f"{correlated['material_delta_count']} supported material deltas were correlated across one repository transition.",
            "files_agree": correlated["coherence_state"].value,
            "known": "Parsed code/config claims and supplied DataHub observations are retained with separate provenance.",
            "unresolved": "Runtime execution validity and missing contract/test evidence remain unverified.",
            "decision": synthesis["decision"],
        },
        "file_explanations": [{"file_change_id": key, "root_types": sorted(values)} for key, values in sorted(file_explanations.items())],
        "logical_group_explanations": [{
            "logical_change_id": item["logical_change_id"], "coherence_state": item["coherence_state"],
            "contributing_file_ids": item["contributing_file_ids"],
            "correlation_basis": "Exact model mapping, field transition, parser evidence, and supported static references.",
        } for item in correlated["logical_change_groups"]],
        "root_cause_explanations": correlated["root_causes"],
        "downstream_target_explanations": propagation["findings"],
        "decision_explanation": {
            "selected_rule": synthesis["decision"]["decision_rule_id"],
            "reason": "Explicit deterministic precedence over certified conflict, unresolved material change, and no-material state.",
        },
    })
    return value


def _repository_state(identity, pr_input, file_results):
    files = []
    result_by_id = {item["file_change_id"]: item for item in file_results}
    for payload in pr_input.files:
        record = payload.record
        files.append({
            "file_change_id": record.file_change_id,
            "active_head_path": record.head_path,
            "removed_base_path": record.base_path if record.head_path is None or record.status.value == "RENAMED" else None,
            "status": record.status.value, "category": record.category.value,
            "head_content_fingerprint": record.head_content_fingerprint,
            "parsed_head": result_by_id[record.file_change_id]["parsed_head"],
            "unresolved_constructs": result_by_id[record.file_change_id]["unresolved_references"],
        })
    value = _header(identity, "counterfactual_repository_state")
    value.update({"active_and_removed_files": files, "current_repository_mutated": False})
    return value


def _metadata_state(identity, correlated):
    value = _header(identity, "counterfactual_metadata_state")
    value.update({
        "state": "CONFLICTED" if correlated["conflicts"] else "COMPOSITE_PROPOSED",
        "logical_change_groups": correlated["logical_change_groups"],
        "current_entities": correlated["entity_resolution"]["resolved_entities"],
        "counterfactual_entities": correlated["entity_resolution"]["counterfactual_entities"],
        "stale_references": correlated["stale_references"],
        "adapted_references": correlated["adapted_references"],
        "removed_entities": [
            item for group in correlated["logical_change_groups"] if group.get("removed")
            for item in group["resolved_current_entities"]
        ],
        "unresolved_references": correlated["entity_resolution"]["unresolved_references"],
        "conflicting_alternatives": correlated["conflicts"],
        "current_snapshot_mutated": False,
    })
    return value


def _change_sets(deltas):
    result = {"structural": [], "semantic": [], "pipeline": [], "contract_quality": []}
    for item in deltas:
        klass = item["delta_class"]
        if klass == "StructuralFieldDelta": result["structural"].append(item)
        elif klass == "SemanticSqlDelta": result["semantic"].append(item)
        elif klass in {"PipelineTaskDelta", "PipelineDependencyDelta", "DatasetReferenceDelta", "FieldReferenceDelta", "ConfigurationDelta"}: result["pipeline"].append(item)
        elif klass in {"ModelContractDelta", "QualityExpectationDelta", "DocumentationOnlyDelta", "UnsupportedFileDelta"}: result["contract_quality"].append(item)
    return result


def _composite(correlated, pr_input, file_results):
    return {
        "pr_identity": {"base": pr_input.base_commit, "head": pr_input.head_commit},
        "repository_identity": pr_input.repository_identity,
        "changed_file_ids": [item.record.file_change_id for item in pr_input.files],
        "file_analysis_ids": [item["file_change_id"] for item in file_results],
        "logical_change_group_ids": [item["logical_change_id"] for item in correlated["logical_change_groups"]],
        "delta_ids": [item["delta_id"] for item in correlated["deltas"]],
        "resolved_entities": correlated["entity_resolution"]["resolved_entities"],
        "counterfactual_entities": correlated["entity_resolution"]["counterfactual_entities"],
        "unresolved_references": correlated["entity_resolution"]["unresolved_references"],
        "coherence_state": correlated["coherence_state"].value,
        "conflicts": correlated["conflicts"], "warnings": ["execution_validity_unverified"],
        "evidence_summary": {
            "file_count": len(pr_input.files), "material_delta_count": correlated["material_delta_count"],
            "root_cause_count": len(correlated["root_causes"]), "conflict_count": len(correlated["conflicts"]),
        },
    }


def _file_record(record):
    value = asdict(record)
    value["status"] = record.status.value
    value["category"] = record.category.value
    return value


def _inventory_summary(pr_input):
    categories = [item.record.category.value for item in pr_input.files]
    return {
        "changed_file_count": len(pr_input.files),
        "supported_count": sum(item != "UNSUPPORTED" for item in categories),
        "unsupported_count": categories.count("UNSUPPORTED"),
        "binary_count": sum(item.record.binary for item in pr_input.files),
    }


def _header(identity: PullRequestAnalysisIdentity, artifact_type: str):
    value = {
        "analysis_id": identity.analysis_id, "proposal_id": identity.proposal_id,
        "operation": identity.operation.value, "intake_mode": identity.intake_mode.value,
        "artifact_type": artifact_type, "artifact_schema_version": "1.0",
        "engine_version": identity.engine_version,
        "repository_fingerprint": identity.repository_fingerprint,
        "base_commit": identity.base_commit, "head_commit": identity.head_commit,
        "source_snapshot_id": identity.source_snapshot_id,
        "source_snapshot_fingerprint": identity.source_snapshot_fingerprint,
        "proposal_fingerprint": identity.proposal_fingerprint,
    }
    if identity.scenario_id: value["scenario_id"] = identity.scenario_id
    if identity.created_at: value["created_at"] = identity.created_at
    return value


def _with(value, **items):
    value.update(items)
    return value
