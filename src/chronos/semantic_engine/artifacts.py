"""Pure semantic artifact builders composed over certified snapshot topology."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from chronos.snapshot import CurrentMetadataSnapshot, FieldMachineKey

from .compatibility import no_change_rule, rule_for_delta
from .deltas import delta_to_dict
from .models import (
    SEMANTIC_ARTIFACT_SCHEMA_VERSION,
    Delta,
    DeltaScope,
    DeltaType,
    ParsedModel,
    SemanticAnalysisIdentity,
    SemanticCompatibilityState,
    SemanticCodeChangeProposal,
)
from .parser import parsed_model_to_dict
from .proposals import semantic_proposal_to_dict
from .serialization import semantic_fingerprint, stable_id


def build_semantic_artifacts(
    snapshot: CurrentMetadataSnapshot,
    proposal: SemanticCodeChangeProposal,
    identity: SemanticAnalysisIdentity,
    before: ParsedModel,
    after: ParsedModel,
    structural_deltas: tuple[Delta, ...],
    semantic_deltas: tuple[Delta, ...],
    resolution: dict[str, Any],
    *,
    before_raw_fingerprint: str,
    after_raw_fingerprint: str,
    before_input_kind: str,
    after_input_kind: str,
    dbt_references: tuple[str, ...],
) -> dict[str, dict[str, Any]]:
    proposal_artifact = _header(identity, "semantic_change_proposal")
    proposal_artifact["proposal"] = semantic_proposal_to_dict(proposal)
    validation = _header(identity, "proposal_validation")
    validation.update(
        {
            "after_input_kind": after_input_kind,
            "after_raw_content_fingerprint": after_raw_fingerprint,
            "before_input_kind": before_input_kind,
            "before_raw_content_fingerprint": before_raw_fingerprint,
            "checks": [
                "strict_proposal",
                "safe_code_paths",
                "snapshot_identity",
                "single_select_model",
                "parser_version",
                "exact_model_resolution",
            ],
            "dbt_references": list(dbt_references),
            "state": "valid",
        }
    )
    before_artifact = _parsed_artifact(identity, "before_parsed_model", before)
    after_artifact = _parsed_artifact(identity, "after_parsed_model", after)
    diff = _semantic_diff(identity, before, after, structural_deltas, semantic_deltas)
    entity = _header(identity, "entity_resolution")
    entity.update(resolution)
    change_set = _code_change_set(
        identity, before, after, structural_deltas, semantic_deltas, resolution
    )
    counterfactual = _counterfactual_state(
        identity, before, after, structural_deltas, semantic_deltas, resolution
    )
    graph = _semantic_graph(
        snapshot, identity, semantic_deltas, structural_deltas, resolution
    )
    propagation = _propagation(identity, graph)
    compatibility = _compatibility(
        identity, structural_deltas, semantic_deltas
    )
    technical = _technical_impact(
        identity, semantic_deltas, structural_deltas, propagation, compatibility
    )
    context = _business_context(snapshot, identity, graph)
    severity = _severity(identity, technical, propagation, context)
    synthesis = _synthesis(
        identity,
        semantic_deltas,
        structural_deltas,
        propagation,
        compatibility,
        technical,
        severity,
        context,
    )
    explanation = _explanations(
        identity,
        semantic_deltas,
        structural_deltas,
        resolution,
        propagation,
        compatibility,
        synthesis,
    )
    return {
        "semantic_change_proposal.json": proposal_artifact,
        "proposal_validation.json": validation,
        "before_parsed_model.json": before_artifact,
        "after_parsed_model.json": after_artifact,
        "semantic_diff.json": diff,
        "entity_resolution.json": entity,
        "code_change_set.json": change_set,
        "counterfactual_semantic_state.json": counterfactual,
        "future_metadata_graph.json": graph,
        "dependency_propagation.json": propagation,
        "compatibility_evaluation.json": compatibility,
        "technical_impact_analysis.json": technical,
        "business_context_propagation.json": context,
        "severity_criticality_analysis.json": severity,
        "impact_synthesis.json": synthesis,
        "explanation_bundle.json": explanation,
    }


def _header(identity: SemanticAnalysisIdentity, artifact_type: str) -> dict[str, Any]:
    value = {
        "analysis_id": identity.analysis_id,
        "artifact_schema_version": SEMANTIC_ARTIFACT_SCHEMA_VERSION,
        "artifact_type": artifact_type,
        "engine_version": identity.engine_version,
        "model_dataset_urn": identity.model_dataset_urn,
        "operation": identity.operation.value,
        "parser_name": identity.parser_name,
        "parser_version": identity.parser_version,
        "proposal_fingerprint": identity.proposal_fingerprint,
        "proposal_id": identity.proposal_id,
        "source_snapshot_fingerprint": identity.source_snapshot_fingerprint,
        "source_snapshot_id": identity.source_snapshot_id,
        "sql_dialect": identity.sql_dialect,
    }
    if identity.scenario_id:
        value["scenario_id"] = identity.scenario_id
    if identity.created_at:
        value["created_at"] = identity.created_at
    return value


def _parsed_artifact(identity, kind, model):
    value = _header(identity, kind)
    value["parsed_model"] = parsed_model_to_dict(model)
    return value


def _semantic_diff(identity, before, after, structural, semantic):
    value = _header(identity, "semantic_diff")
    value.update(
        {
            "after_ast_fingerprint": after.canonical_ast_fingerprint,
            "before_ast_fingerprint": before.canonical_ast_fingerprint,
            "change_state": (
                "NO_SEMANTIC_CHANGE"
                if not structural and not semantic
                else "CHANGES_DETECTED"
            ),
            "semantic_deltas": [delta_to_dict(item) for item in semantic],
            "structural_deltas": [delta_to_dict(item) for item in structural],
        }
    )
    return value


def _code_change_set(identity, before, after, structural, semantic, resolution):
    value = _header(identity, "code_change_set")
    value.update(
        {
            "after_ast_fingerprint": after.canonical_ast_fingerprint,
            "before_ast_fingerprint": before.canonical_ast_fingerprint,
            "evidence_summary": {
                "code_derived_delta_count": len(structural) + len(semantic),
                "observed_model_count": 1,
                "unresolved_reference_count": len(resolution["unresolved_references"]),
            },
            "resolved_entities": {
                "model": resolution["model"],
                "outputs": resolution["output_mappings"],
                "relations": resolution["after_relations"],
            },
            "semantic_deltas": [delta_to_dict(item) for item in semantic],
            "structural_deltas": [delta_to_dict(item) for item in structural],
            "unresolved_references": resolution["unresolved_references"],
            "warnings": _warnings(structural, semantic, resolution),
        }
    )
    value["code_change_set_fingerprint"] = semantic_fingerprint(value)
    return value


def _warnings(structural, semantic, resolution):
    warnings = []
    if structural:
        warnings.append(
            "Structural output deltas were discovered and are represented separately; no structural repair was attempted."
        )
    if resolution["unresolved_references"]:
        warnings.append(
            "Some code-derived references lack certified field identity in the supplied snapshot."
        )
    if semantic:
        warnings.append(
            "Semantic compatibility remains unresolved without contract or execution evidence."
        )
    return warnings


def _counterfactual_state(identity, before, after, structural, semantic, resolution):
    before_map = {item.output_name: item for item in before.output_columns}
    after_map = {item.output_name: item for item in after.output_columns}
    semantic_by_output: dict[str, list[str]] = {}
    model_wide = []
    for delta in semantic:
        if delta.affected_output_field:
            semantic_by_output.setdefault(delta.affected_output_field, []).append(delta.delta_id)
        else:
            model_wide.append(delta.delta_id)
    outputs = []
    for name in sorted(set(before_map) | set(after_map)):
        current = before_map.get(name)
        future = after_map.get(name)
        classifications = sorted(set(semantic_by_output.get(name, []) + model_wide))
        outputs.append(
            {
                "change_classifications": classifications,
                "current_expression_fingerprint": current.expression_fingerprint if current else None,
                "current_identity": f"{identity.model_dataset_urn}|{name}" if current else None,
                "future_expression_fingerprint": future.expression_fingerprint if future else None,
                "future_identity": f"{identity.model_dataset_urn}|{name}" if future else None,
                "output_name": name,
                "resolved_inputs": sorted(
                    {
                        item["datahub_field_key"]
                        for item in resolution["after_input_columns"]
                        if item["datahub_field_key"]
                    }
                ),
                "semantic_state": (
                    "SEMANTICS_CHANGED" if classifications else "SEMANTICS_PRESERVED"
                ),
                "structural_state": (
                    "REMOVED" if future is None else "NEW" if current is None else "PRESERVED"
                ),
                "unresolved_inputs": sorted(
                    {
                        item["code_reference"]
                        for item in resolution["after_input_columns"]
                        if not item["datahub_field_key"]
                    }
                ),
            }
        )
    value = _header(identity, "counterfactual_semantic_state")
    value.update(
        {
            "model_semantic_state": (
                "SEMANTICS_CHANGED" if semantic else "SEMANTICS_PRESERVED"
            ),
            "outputs": outputs,
            "row_set_semantics_changed": any(item.scope is DeltaScope.MODEL_WIDE for item in semantic),
            "snapshot_mutated": False,
        }
    )
    return value


def _semantic_graph(snapshot, identity, semantic, structural, resolution):
    resolved_outputs = {
        item["output_name"]: item["datahub_field_key"]
        for item in resolution["output_mappings"]
        if item["datahub_field_key"]
    }
    model_wide = any(item.scope is DeltaScope.MODEL_WIDE for item in semantic)
    affected_names = {
        item.affected_output_field
        for item in semantic + structural
        if item.affected_output_field
    }
    if model_wide:
        affected_names.update(resolved_outputs)
    origins = {
        _field_key(resolved_outputs[name])
        for name in affected_names
        if name in resolved_outputs
    }
    edges = _reachable_edges(snapshot, origins)
    node_keys = set(origins)
    for edge in edges:
        node_keys.add(edge.upstream)
        node_keys.add(edge.downstream)
    delta_ids_by_origin: dict[str, list[str]] = {}
    model_delta_ids = [
        item.delta_id for item in semantic if item.scope is DeltaScope.MODEL_WIDE
    ]
    for origin in origins:
        name = origin.field_path.lower()
        delta_ids_by_origin[origin.text] = sorted(
            model_delta_ids
            + [
                item.delta_id
                for item in semantic
                if item.affected_output_field == name
            ]
        )
    nodes = [
        {
            "dataset_urn": key.dataset_urn,
            "field_key": key.text,
            "field_path": key.field_path,
            "node_state": "SEMANTIC_ORIGIN" if key in origins else "INHERITED",
            "observed_in_snapshot": key in snapshot.field_by_key(),
            "semantic_delta_ids": delta_ids_by_origin.get(key.text, []),
        }
        for key in sorted(node_keys)
    ]
    relationships = [
        {
            "classification": edge.classification,
            "current_edge_id": edge.edge_id,
            "downstream_key": edge.downstream.text,
            "evidence_class": "OBSERVED_DATAHUB_EVIDENCE",
            "evidence_ids": list(edge.evidence_ids),
            "mapping_group_ids": list(edge.mapping_group_ids),
            "relationship_id": stable_id(
                "semantic-relationship",
                identity.proposal_fingerprint,
                edge.edge_id,
            ),
            "source_entity_urns": list(edge.source_entity_urns),
            "structural_state": "PRESERVED",
            "upstream_key": edge.upstream.text,
        }
        for edge in edges
    ]
    relationship_by_edge = {
        item["current_edge_id"]: item["relationship_id"] for item in relationships
    }
    paths = _paths_from_edges(origins, edges, relationship_by_edge, identity)
    value = _header(identity, "future_metadata_graph")
    value.update(
        {
            "model_semantics_changed": bool(semantic),
            "nodes": nodes,
            "origin_field_keys": sorted(item.text for item in origins),
            "paths": paths,
            "relationships": relationships,
            "semantic_delta_ids": [item.delta_id for item in semantic],
            "structural_topology_state": "PRESERVED",
        }
    )
    return value


def _field_key(text):
    dataset_urn, field_path = text.rsplit("|", 1)
    return FieldMachineKey(dataset_urn, field_path)


def _reachable_edges(snapshot, origins):
    adjacency: dict[FieldMachineKey, list[Any]] = {}
    for edge in snapshot.lineage_edges:
        adjacency.setdefault(edge.upstream, []).append(edge)
    pending = list(sorted(origins))
    visited = set()
    selected = {}
    while pending:
        key = pending.pop(0)
        if key in visited:
            continue
        visited.add(key)
        for edge in sorted(adjacency.get(key, ()), key=lambda item: item.edge_id):
            selected[edge.edge_id] = edge
            pending.append(edge.downstream)
    return tuple(selected[key] for key in sorted(selected))


def _paths_from_edges(origins, edges, relationship_by_edge, identity):
    adjacency: dict[FieldMachineKey, list[Any]] = {}
    for edge in edges:
        adjacency.setdefault(edge.upstream, []).append(edge)
    paths = []

    def walk(origin, current, nodes, edge_ids):
        outgoing = [
            item
            for item in sorted(adjacency.get(current, ()), key=lambda edge: edge.edge_id)
            if item.downstream not in nodes
        ]
        if edge_ids:
            path_id = stable_id(
                "semantic-path",
                identity.proposal_fingerprint,
                origin.text,
                *edge_ids,
            )
            paths.append(
                {
                    "depth": len(edge_ids),
                    "evidence_class": "COUNTERFACTUAL_DERIVATION_FROM_OBSERVED_EDGES",
                    "node_keys": [item.text for item in nodes],
                    "path_id": path_id,
                    "relationship_ids": [relationship_by_edge[item] for item in edge_ids],
                    "target_key": current.text,
                }
            )
        for edge in outgoing:
            walk(origin, edge.downstream, nodes + [edge.downstream], edge_ids + [edge.edge_id])

    for origin in sorted(origins):
        walk(origin, origin, [origin], [])
    unique = {item["path_id"]: item for item in paths}
    return [unique[key] for key in sorted(unique)]


def _propagation(identity, graph):
    origin_keys = set(graph["origin_field_keys"])
    downstream = sorted(
        {item["field_key"] for item in graph["nodes"] if item["field_key"] not in origin_keys}
    )
    datasets = sorted({item.rsplit("|", 1)[0] for item in downstream})
    path_count: dict[str, int] = {}
    min_depth: dict[str, int] = {}
    for path in graph["paths"]:
        target = path["target_key"]
        path_count[target] = path_count.get(target, 0) + 1
        min_depth[target] = min(min_depth.get(target, path["depth"]), path["depth"])
    exposures = [
        {
            "dataset_urn": item.rsplit("|", 1)[0],
            "field_key": item,
            "minimum_depth": min_depth.get(item),
            "multipath": path_count.get(item, 0) > 1,
            "path_count": path_count.get(item, 0),
            "reach": "DIRECT" if min_depth.get(item) == 1 else "TRANSITIVE",
        }
        for item in downstream
    ]
    value = _header(identity, "dependency_propagation")
    value.update(
        {
            "downstream_dataset_urns": datasets,
            "downstream_exposures": exposures,
            "downstream_field_keys": downstream,
            "metrics": {
                "direct_field_count": sum(item["minimum_depth"] == 1 for item in exposures),
                "downstream_dataset_count": len(datasets),
                "downstream_field_count": len(downstream),
                "maximum_depth": max((item["depth"] for item in graph["paths"]), default=0),
                "multipath_field_count": sum(item["multipath"] for item in exposures),
                "origin_field_count": len(origin_keys),
                "path_count": len(graph["paths"]),
                "relationship_count": len(graph["relationships"]),
            },
            "origin_field_keys": sorted(origin_keys),
            "supporting_path_ids": [item["path_id"] for item in graph["paths"]],
        }
    )
    return value


def _compatibility(identity, structural, semantic):
    evaluations = []
    for delta in semantic:
        rule = rule_for_delta(delta.delta_type)
        evaluations.append(
            {
                "delta_id": delta.delta_id,
                "delta_type": delta.delta_type.value,
                "evidence_certainty": rule.evidence_certainty,
                "explanation": rule.explanation_template,
                "reason_code": rule.reason_code,
                "required_evidence": list(rule.required_evidence),
                "rule_id": rule.rule_id,
                "semantic_compatibility": rule.result.value,
            }
        )
    if not semantic:
        rule = no_change_rule()
        evaluations.append(
            {
                "delta_id": None,
                "delta_type": rule.delta_type,
                "evidence_certainty": rule.evidence_certainty,
                "explanation": rule.explanation_template,
                "reason_code": rule.reason_code,
                "required_evidence": list(rule.required_evidence),
                "rule_id": rule.rule_id,
                "semantic_compatibility": rule.result.value,
            }
        )
    semantic_state = (
        SemanticCompatibilityState.SEMANTIC_COMPATIBILITY_UNKNOWN
        if semantic
        else SemanticCompatibilityState.SEMANTICALLY_COMPATIBLE
    )
    value = _header(identity, "compatibility_evaluation")
    value.update(
        {
            "execution_validity": "NOT_EXECUTED",
            "registry_version": "1.0",
            "rule_evaluations": evaluations,
            "semantic_compatibility": semantic_state.value,
            "structural_compatibility": (
                "STRUCTURALLY_COMPATIBLE" if not structural else "STRUCTURAL_COMPATIBILITY_UNKNOWN"
            ),
        }
    )
    return value


def _technical_impact(identity, semantic, structural, propagation, compatibility):
    if not semantic and not structural:
        consequence = "NO_DEMONSTRATED_MATERIAL_IMPACT"
        certainty = "ESTABLISHED"
    elif semantic:
        types = {item.delta_type for item in semantic}
        if types == {DeltaType.FILTER_CHANGE}:
            consequence = "ROW_SET_SEMANTICS_CHANGED"
        elif any(
            item in types
            for item in {
                DeltaType.JOIN_TYPE_CHANGE,
                DeltaType.JOIN_PREDICATE_CHANGE,
                DeltaType.JOINED_RELATION_CHANGE,
            }
        ):
            consequence = "JOIN_SEMANTICS_CHANGED"
        else:
            consequence = "SEMANTIC_DEFINITION_CHANGED"
        certainty = "UNRESOLVED"
    else:
        consequence = "UNRESOLVED_SEMANTIC_IMPACT"
        certainty = "UNRESOLVED"
    root_causes = []
    for delta_type in sorted({item.delta_type for item in semantic}, key=lambda item: item.value):
        root_causes.append(
            {
                "delta_ids": [
                    item.delta_id for item in semantic if item.delta_type is delta_type
                ],
                "reason_code": _cause_reason(delta_type),
                "root_cause_id": stable_id(
                    "semantic-root-cause",
                    identity.proposal_fingerprint,
                    delta_type.value,
                ),
            }
        )
    if structural and not root_causes:
        root_causes.append(
            {
                "delta_ids": [item.delta_id for item in structural],
                "reason_code": "structural-output-contract-changed",
                "root_cause_id": stable_id(
                    "semantic-root-cause",
                    identity.proposal_fingerprint,
                    "structural",
                ),
            }
        )
    cause_ids = [item["root_cause_id"] for item in root_causes]
    findings = [
        {
            "affected_field_key": item["field_key"],
            "consequence": consequence,
            "evidence_certainty": certainty,
            "minimum_depth": item["minimum_depth"],
            "path_count": item["path_count"],
            "root_cause_ids": cause_ids,
        }
        for item in propagation["downstream_exposures"]
    ]
    value = _header(identity, "technical_impact_analysis")
    value.update(
        {
            "evidence_certainty": certainty,
            "findings": findings,
            "root_causes": root_causes,
            "semantic_consequence": consequence,
        }
    )
    return value


def _cause_reason(delta_type):
    if delta_type is DeltaType.AGGREGATION_CHANGE:
        return "semantic-aggregation-definition-changed"
    if delta_type is DeltaType.FILTER_CHANGE:
        return "semantic-row-filter-changed"
    if delta_type in {
        DeltaType.JOIN_TYPE_CHANGE,
        DeltaType.JOIN_PREDICATE_CHANGE,
        DeltaType.JOINED_RELATION_CHANGE,
    }:
        return "semantic-join-behavior-changed"
    return "semantic-derived-expression-changed"


def _business_context(snapshot, identity, graph):
    affected_datasets = {item["dataset_urn"] for item in graph["nodes"]}
    affected_keys = {item["field_key"] for item in graph["nodes"]}
    selected = []
    for relationship in snapshot.relationships:
        connected = (
            relationship.source_key in affected_keys
            or relationship.target_key in affected_keys
            or relationship.source_key in affected_datasets
            or relationship.target_key in affected_datasets
            or any(item in relationship.source_key for item in affected_datasets)
            or any(item in relationship.target_key for item in affected_datasets)
        )
        if connected:
            selected.append(
                {
                    "category": relationship.category.value,
                    "evidence_class": "OBSERVED_DATAHUB_EVIDENCE",
                    "evidence_ids": list(relationship.evidence_ids),
                    "relationship_id": relationship.relationship_id,
                    "source_key": relationship.source_key,
                    "state": relationship.state,
                    "target_key": relationship.target_key,
                }
            )
    counts: dict[str, int] = {}
    for item in selected:
        counts[item["category"]] = counts.get(item["category"], 0) + 1
    value = _header(identity, "business_context_propagation")
    value.update(
        {
            "affected_dataset_urns": sorted(affected_datasets),
            "category_counts": counts,
            "context_relationships": sorted(
                selected, key=lambda item: item["relationship_id"]
            ),
            "context_statement": (
                "Connected governance and consumer metadata is evidence context only; it does not approve or invalidate the semantic change."
            ),
        }
    )
    return value


def _severity(identity, technical, propagation, context):
    dataset_count = propagation["metrics"]["downstream_dataset_count"]
    if dataset_count == 0:
        breadth = "local"
    elif dataset_count <= 2:
        breadth = "limited"
    elif dataset_count <= 10:
        breadth = "broad"
    else:
        breadth = "widespread"
    if technical["semantic_consequence"] == "NO_DEMONSTRATED_MATERIAL_IMPACT":
        severity = "low"
        rule_id = "semantic-severity-no-change"
    elif dataset_count == 0:
        severity = "moderate"
        rule_id = "semantic-severity-no-certified-downstream-reach"
    elif breadth in {"broad", "widespread"}:
        severity = "high"
        rule_id = "semantic-severity-unresolved-broad-reach"
    else:
        severity = "moderate"
        rule_id = "semantic-severity-unresolved-limited-reach"
    value = _header(identity, "severity_criticality_analysis")
    value.update(
        {
            "context_criticality": (
                "elevated_context" if context["context_relationships"] else "criticality_unknown"
            ),
            "evidence_certainty": technical["evidence_certainty"].lower(),
            "exposure_breadth": breadth,
            "rule_id": rule_id,
            "semantic_consequence": technical["semantic_consequence"],
            "severity_if_realized": severity,
        }
    )
    return value


def _synthesis(identity, semantic, structural, propagation, compatibility, technical, severity, context):
    reach = propagation["metrics"]["downstream_field_count"]
    if not semantic and not structural:
        disposition = "proceed"
        certainty = "high_confidence"
        rule_id = "semantic-decision-proceed-no-change"
        reasons = ["no_semantic_change", "structural_identity_preserved"]
    elif reach == 0:
        disposition = "proceed_with_conditions"
        certainty = "supported"
        rule_id = "semantic-decision-conditions-no-certified-downstream-reach"
        reasons = ["semantic_change_detected", "no_certified_downstream_reach"]
    else:
        disposition = "hold_for_review"
        certainty = "high_confidence"
        rule_id = "semantic-decision-hold-unresolved-downstream-reach"
        reasons = ["semantic_compatibility_unresolved", "certified_downstream_reach"]
    required = []
    questions = []
    for delta in semantic:
        rule = rule_for_delta(delta.delta_type)
        evidence_ids = []
        for evidence_class in rule.required_evidence:
            evidence_id = stable_id(
                "semantic-required-evidence", delta.delta_id, evidence_class
            )
            evidence_ids.append(evidence_id)
            required.append(
                {
                    "delta_id": delta.delta_id,
                    "requirement_type": evidence_class,
                    "required_evidence_id": evidence_id,
                    "state": "REQUIRED_FOR_DECISION_RESOLUTION",
                    "subject": delta.affected_output_field or identity.model_dataset_urn,
                }
            )
        questions.append(
            {
                "affected_output_field": delta.affected_output_field,
                "delta_id": delta.delta_id,
                "question": _question(delta),
                "question_id": stable_id("semantic-question", delta.delta_id),
                "required_evidence_ids": evidence_ids,
                "resolution_state": "UNRESOLVED",
                "subject": identity.model_dataset_urn,
            }
        )
    value = _header(identity, "impact_synthesis")
    value.update(
        {
            "blocking_questions": questions,
            "decision": {
                "certainty": certainty,
                "disposition": disposition,
                "reason_codes": reasons,
                "rule_id": rule_id,
            },
            "required_evidence": required,
            "summary": {
                "affected_dataset_count": propagation["metrics"]["downstream_dataset_count"],
                "affected_field_count": propagation["metrics"]["downstream_field_count"],
                "semantic_compatibility": compatibility["semantic_compatibility"],
                "semantic_delta_count": len(semantic),
                "severity_if_realized": severity["severity_if_realized"],
                "structural_delta_count": len(structural),
            },
        }
    )
    return value


def _question(delta):
    subject = delta.affected_output_field or delta.affected_model_urn
    if delta.delta_type is DeltaType.AGGREGATION_CHANGE:
        return f"Is the aggregation change for {subject} an approved redefinition of the downstream metric?"
    if delta.delta_type is DeltaType.FILTER_CHANGE:
        return f"Is the changed row filter for {delta.affected_model_urn} part of the certified model contract?"
    if delta.delta_type in {
        DeltaType.JOIN_TYPE_CHANGE,
        DeltaType.JOIN_PREDICATE_CHANGE,
        DeltaType.JOINED_RELATION_CHANGE,
    }:
        return f"Can consumers of {delta.affected_model_urn} accept the changed row-preservation and cardinality semantics?"
    return f"Does the revised expression for {subject} match the approved business definition?"


def _explanations(identity, semantic, structural, resolution, propagation, compatibility, synthesis):
    value = _header(identity, "explanation_bundle")
    value.update(
        {
            "decision_evidence": {
                "decision": synthesis["decision"],
                "semantic_compatibility": compatibility["semantic_compatibility"],
            },
            "detected_changes": [item.explanation for item in semantic + structural],
            "downstream_evidence": {
                "dataset_count": propagation["metrics"]["downstream_dataset_count"],
                "field_count": propagation["metrics"]["downstream_field_count"],
                "path_ids": propagation["supporting_path_ids"],
                "source": "OBSERVED_DATAHUB_EDGES",
            },
            "evidence_classes": {
                "code_derived": "Parsed SQL AST contracts and semantic deltas.",
                "counterfactual": "Future semantic state and overlay over preserved topology.",
                "decision": "Deterministic compatibility, reach, severity, and decision rules.",
                "missing": "Contract approval, consumer expectations, and execution comparison.",
                "observed_datahub": "Resolved Dataset/schema-field identities, edges, and context relationships.",
            },
            "limitations": [
                "SQL and dbt code were parsed but never executed.",
                "No exact row-count, null-rate, uniqueness, or cardinality outcome is claimed.",
                "Code-derived references are not represented as already stored DataHub lineage.",
            ],
            "resolved_model": resolution["model"],
            "resolved_outputs": resolution["output_mappings"],
            "unresolved_references": resolution["unresolved_references"],
        }
    )
    return value
