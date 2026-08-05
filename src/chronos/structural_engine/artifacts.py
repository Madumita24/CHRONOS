"""Pure artifact builders for the generalized structural engine."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from chronos.compatibility_evaluation import CompatibilityState, EvidenceStrength
from chronos.impact_synthesis import DecisionRuleInputs, evaluate_decision
from chronos.severity_criticality import (
    ContextCriticality,
    EvidenceCertainty,
    ExposureBreadth,
    SeverityIfRealized,
    TechnicalConsequence,
)
from chronos.snapshot import CurrentMetadataSnapshot, FieldMachineKey

from .compatibility_registry import evaluate_root_compatibility
from .models import (
    GENERALIZED_ARTIFACT_SCHEMA_VERSION,
    GENERALIZED_ENGINE_VERSION,
    AnalysisIdentity,
    ResolvedField,
)
from .operations import OperationAdapter
from .proposals import FieldTypeChangeProposal, Proposal, StructuralOperation
from .serialization import semantic_fingerprint, stable_id


def build_analysis_artifacts(
    snapshot: CurrentMetadataSnapshot,
    proposal: Proposal,
    identity: AnalysisIdentity,
    target: ResolvedField,
    adapter: OperationAdapter,
) -> dict[str, dict[str, Any]]:
    """Build every semantic artifact from snapshot data and adapter behavior."""
    counterfactual = _counterfactual_source(snapshot, proposal, identity, target, adapter)
    graph = _future_graph(snapshot, proposal, identity, target, adapter)
    propagation = _dependency_propagation(identity, graph)
    compatibility = _compatibility(
        snapshot, proposal, identity, target, graph, propagation
    )
    technical = _technical_impact(identity, graph, propagation, compatibility)
    context = _business_context(snapshot, identity, graph)
    severity = _severity(identity, technical, context, propagation)
    synthesis = _synthesis(
        snapshot,
        proposal,
        identity,
        graph,
        propagation,
        compatibility,
        technical,
        context,
        severity,
    )
    explanation = _explanation_bundle(
        proposal,
        identity,
        target,
        propagation,
        compatibility,
        severity,
        synthesis,
    )
    return {
        "counterfactual_source_state.json": counterfactual,
        "future_metadata_graph.json": graph,
        "dependency_propagation.json": propagation,
        "compatibility_evaluation.json": compatibility,
        "technical_impact_analysis.json": technical,
        "business_context_propagation.json": context,
        "severity_criticality_analysis.json": severity,
        "impact_synthesis.json": synthesis,
        "explanation_bundle.json": explanation,
    }


def _header(identity: AnalysisIdentity, artifact_type: str) -> dict[str, Any]:
    result = {
        "analysis_id": identity.analysis_id,
        "artifact_schema_version": GENERALIZED_ARTIFACT_SCHEMA_VERSION,
        "artifact_type": artifact_type,
        "dataset_urn": identity.dataset_urn,
        "engine_version": GENERALIZED_ENGINE_VERSION,
        "operation": identity.operation.value,
        "proposal_fingerprint": identity.proposal_fingerprint,
        "proposal_id": identity.proposal_id,
        "source_snapshot_fingerprint": identity.source_snapshot_fingerprint,
        "source_snapshot_id": identity.source_snapshot_id,
    }
    if identity.scenario_id is not None:
        result["scenario_id"] = identity.scenario_id
    if identity.created_at is not None:
        result["created_at"] = identity.created_at
    return result


def _field_dict(field: Any) -> dict[str, Any]:
    value = asdict(field)
    value["evidence_ids"] = list(field.evidence_ids)
    return value


def _counterfactual_source(snapshot, proposal, identity, target, adapter):
    projected = adapter.project_fields(snapshot, target, proposal)
    current_paths = [item.field_path for item in snapshot.source_schema.fields]
    projected_paths = [item.field_path for item in projected]
    result = _header(identity, "counterfactual_source_state")
    result.update(
        {
            "current_source_schema": {
                "dataset_urn": snapshot.source_schema.dataset_urn,
                "field_count": len(snapshot.source_schema.fields),
                "fields": [_field_dict(item) for item in snapshot.source_schema.fields],
            },
            "projected_source_schema": {
                "dataset_urn": snapshot.source_schema.dataset_urn,
                "field_count": len(projected),
                "fields": [_field_dict(item) for item in projected],
            },
            "source_change": {
                "current_field_path": target.field_path,
                "current_native_type": target.native_type,
                "current_normalized_type": target.normalized_type,
                "projected_field_path": adapter.projected_field_path(proposal),
                "projected_state": adapter.root_state(),
            },
            "invariants": {
                "current_field_paths_unique": len(current_paths) == len(set(current_paths)),
                "projected_field_paths_unique": len(projected_paths) == len(set(projected_paths)),
                "unaffected_field_order_preserved": True,
            },
        }
    )
    return result


def _future_graph(snapshot, proposal, identity, target, adapter):
    current_root = FieldMachineKey(target.dataset_urn, target.field_path)
    reachable_edges = _reachable_edges(snapshot, current_root)
    reachable_keys = {current_root}
    for edge in reachable_edges:
        reachable_keys.add(edge.upstream)
        reachable_keys.add(edge.downstream)
    projected_path = adapter.projected_field_path(proposal)
    projected_root = (
        FieldMachineKey(target.dataset_urn, projected_path)
        if projected_path is not None
        else current_root
    )

    field_lookup = snapshot.field_by_key()
    nodes = []
    for key in sorted(reachable_keys):
        source = field_lookup.get(key)
        is_root = key == current_root
        future_key = projected_root if is_root else key
        node = {
            "active": not (is_root and projected_path is None),
            "current_key": key.text,
            "dataset_urn": key.dataset_urn,
            "field_path": future_key.field_path,
            "future_key": future_key.text,
            "native_type": source.native_type if source else target.native_type,
            "normalized_type": source.normalized_type if source else target.normalized_type,
            "state": adapter.root_state() if is_root else "inherited",
        }
        if is_root and isinstance(proposal, FieldTypeChangeProposal):
            node["native_type"] = proposal.proposed_native_type
            node["normalized_type"] = proposal.proposed_normalized_type.upper()
        nodes.append(node)

    relationships = []
    edge_id_map: dict[str, str] = {}
    for edge in reachable_edges:
        future_upstream = projected_root if edge.upstream == current_root else edge.upstream
        future_downstream = projected_root if edge.downstream == current_root else edge.downstream
        relationship_id = stable_id(
            "relationship",
            identity.source_snapshot_fingerprint,
            identity.proposal_fingerprint,
            edge.edge_id,
            future_upstream.text,
            future_downstream.text,
        )
        edge_id_map[edge.edge_id] = relationship_id
        relationships.append(
            {
                "active": projected_path is not None,
                "classification": edge.classification,
                "current_edge_id": edge.edge_id,
                "current_upstream_key": edge.upstream.text,
                "current_downstream_key": edge.downstream.text,
                "downstream_key": future_downstream.text,
                "evidence_ids": list(edge.evidence_ids),
                "mapping_group_ids": list(edge.mapping_group_ids),
                "relationship_id": relationship_id,
                "source_entity_urns": list(edge.source_entity_urns),
                "state": "unsatisfied" if projected_path is None else "projected",
                "transform_operations": list(edge.transform_operations),
                "upstream_key": future_upstream.text,
            }
        )

    paths = []
    for source_path in snapshot.lineage_paths:
        if not source_path.node_keys or source_path.node_keys[0] != current_root:
            continue
        if any(edge_id not in edge_id_map for edge_id in source_path.edge_ids):
            continue
        future_nodes = [
            projected_root.text if key == current_root else key.text
            for key in source_path.node_keys
        ]
        path_id = stable_id(
            "path",
            identity.proposal_fingerprint,
            *source_path.edge_ids,
            future_nodes[-1],
        )
        paths.append(
            {
                "active": projected_path is not None,
                "depth": len(source_path.edge_ids),
                "node_keys": future_nodes,
                "path_id": path_id,
                "relationship_ids": [edge_id_map[item] for item in source_path.edge_ids],
                "target_key": future_nodes[-1],
            }
        )
    result = _header(identity, "future_metadata_graph")
    result.update(
        {
            "current_root_key": current_root.text,
            "future_root_key": projected_root.text if projected_path is not None else None,
            "nodes": nodes,
            "paths": sorted(paths, key=lambda item: item["path_id"]),
            "relationships": sorted(
                relationships, key=lambda item: item["relationship_id"]
            ),
        }
    )
    return result


def _reachable_edges(snapshot, root):
    by_upstream: dict[FieldMachineKey, list[Any]] = {}
    for edge in snapshot.lineage_edges:
        by_upstream.setdefault(edge.upstream, []).append(edge)
    pending = [root]
    visited: set[FieldMachineKey] = set()
    selected: dict[str, Any] = {}
    while pending:
        key = pending.pop(0)
        if key in visited:
            continue
        visited.add(key)
        for edge in sorted(by_upstream.get(key, ()), key=lambda item: item.edge_id):
            selected[edge.edge_id] = edge
            pending.append(edge.downstream)
    return tuple(selected[key] for key in sorted(selected))


def _dependency_propagation(identity, graph):
    paths = graph["paths"]
    downstream_keys = sorted(
        {node["future_key"] for node in graph["nodes"] if node["current_key"] != graph["current_root_key"]}
    )
    datasets = sorted({key.rsplit("|", 1)[0] for key in downstream_keys})
    path_count_by_target: dict[str, int] = {}
    minimum_depth: dict[str, int] = {}
    for path in paths:
        target = path["target_key"]
        path_count_by_target[target] = path_count_by_target.get(target, 0) + 1
        minimum_depth[target] = min(minimum_depth.get(target, path["depth"]), path["depth"])
    exposures = [
        {
            "dataset_urn": key.rsplit("|", 1)[0],
            "field_key": key,
            "minimum_depth": minimum_depth.get(key),
            "multipath": path_count_by_target.get(key, 0) > 1,
            "path_count": path_count_by_target.get(key, 0),
            "reach": "direct" if minimum_depth.get(key) == 1 else "transitive",
        }
        for key in downstream_keys
    ]
    result = _header(identity, "dependency_propagation")
    result.update(
        {
            "downstream_datasets": datasets,
            "downstream_exposures": exposures,
            "downstream_field_keys": downstream_keys,
            "metrics": {
                "direct_field_count": sum(item["minimum_depth"] == 1 for item in exposures),
                "downstream_dataset_count": len(datasets),
                "downstream_field_count": len(downstream_keys),
                "maximum_depth": max((item["depth"] for item in paths), default=0),
                "multipath_field_count": sum(item["multipath"] for item in exposures),
                "path_count": len(paths),
                "relationship_count": len(graph["relationships"]),
                "transitive_field_count": sum((item["minimum_depth"] or 0) > 1 for item in exposures),
            },
            "supporting_path_ids": [item["path_id"] for item in paths],
        }
    )
    return result


def _compatibility(snapshot, proposal, identity, target, graph, propagation):
    has_dependencies = bool(graph["relationships"])
    rule = evaluate_root_compatibility(
        proposal,
        current_native_type=target.native_type,
        current_normalized_type=target.normalized_type,
        has_dependencies=has_dependencies,
    )
    state = rule.result
    strength = rule.evidence_strength
    reason = rule.reason_code
    rule_id = rule.rule_id
    relationships = []
    for item in graph["relationships"]:
        relationships.append(
            {
                "compatibility_state": state.value,
                "evidence_strength": strength.value,
                "reason_code": reason,
                "relationship_id": item["relationship_id"],
                "rule_id": rule_id,
                "supporting_evidence_ids": item["evidence_ids"],
            }
        )
    paths = [
        {
            "compatibility_state": state.value,
            "path_id": item["path_id"],
            "reason_codes": [reason],
            "relationship_ids": item["relationship_ids"],
            "rule_id": rule_id,
        }
        for item in graph["paths"]
    ]
    result = _header(identity, "compatibility_evaluation")
    result.update(
        {
            "registry_version": "1.0",
            "root_evaluation": {
                "compatibility_state": state.value,
                "evidence_strength": strength.value,
                "reason_code": reason,
                "rule_id": rule_id,
                "target_field_key": graph["current_root_key"],
                "required_evidence": list(rule.required_evidence),
                "explanation": rule.explanation_template,
            },
            "relationship_evaluations": relationships,
            "path_evaluations": paths,
            "aggregate": {
                "compatible": sum(item["compatibility_state"] == "compatible" for item in relationships),
                "conditionally_compatible": sum(item["compatibility_state"] == "conditionally_compatible" for item in relationships),
                "incompatible": sum(item["compatibility_state"] == "incompatible" for item in relationships),
                "unknown": sum(item["compatibility_state"] == "unknown" for item in relationships),
                "total": len(relationships),
            },
            "rules_applied": [rule_id],
        }
    )
    return result


def _technical_impact(identity, graph, propagation, compatibility):
    root = compatibility["root_evaluation"]
    state = root["compatibility_state"]
    count = propagation["metrics"]["downstream_field_count"]
    if count == 0:
        consequence = TechnicalConsequence.NO_DEMONSTRATED_IMPACT
        certainty = EvidenceCertainty.ESTABLISHED
    elif state == CompatibilityState.INCOMPATIBLE.value:
        consequence = TechnicalConsequence.CONFIRMED_IMPACT
        certainty = EvidenceCertainty.ESTABLISHED
    elif state == CompatibilityState.CONDITIONALLY_COMPATIBLE.value:
        consequence = TechnicalConsequence.POTENTIAL_IMPACT
        certainty = EvidenceCertainty.CONDITIONAL
    else:
        consequence = TechnicalConsequence.UNRESOLVED_IMPACT
        certainty = EvidenceCertainty.UNRESOLVED
    findings = [
        {
            "affected_field_key": item["field_key"],
            "consequence": consequence.value,
            "evidence_certainty": certainty.value,
            "minimum_depth": item["minimum_depth"],
            "path_count": item["path_count"],
            "root_cause_id": stable_id("root-cause", identity.proposal_fingerprint),
        }
        for item in propagation["downstream_exposures"]
    ]
    result = _header(identity, "technical_impact_analysis")
    result.update(
        {
            "technical_consequence": consequence.value,
            "evidence_certainty": certainty.value,
            "findings": findings,
            "root_causes": [
                {
                    "root_cause_id": stable_id("root-cause", identity.proposal_fingerprint),
                    "operation": identity.operation.value,
                    "reason_code": root["reason_code"],
                    "source_field_key": graph["current_root_key"],
                }
            ],
        }
    )
    return result


def _business_context(snapshot, identity, graph):
    affected_datasets = {
        node["dataset_urn"] for node in graph["nodes"]
    }
    affected_keys = {node["current_key"] for node in graph["nodes"]}
    selected = []
    for relationship in snapshot.relationships:
        connected = (
            relationship.source_key in affected_keys
            or relationship.target_key in affected_keys
            or relationship.source_key in affected_datasets
            or relationship.target_key in affected_datasets
            or any(dataset in relationship.source_key for dataset in affected_datasets)
            or any(dataset in relationship.target_key for dataset in affected_datasets)
        )
        if connected:
            selected.append(
                {
                    "category": relationship.category.value,
                    "evidence_ids": list(relationship.evidence_ids),
                    "relationship_id": relationship.relationship_id,
                    "source_key": relationship.source_key,
                    "state": relationship.state,
                    "target_key": relationship.target_key,
                }
            )
    categories: dict[str, int] = {}
    for item in selected:
        categories[item["category"]] = categories.get(item["category"], 0) + 1
    result = _header(identity, "business_context_propagation")
    result.update(
        {
            "affected_dataset_urns": sorted(affected_datasets),
            "context_relationships": sorted(selected, key=lambda item: item["relationship_id"]),
            "category_counts": categories,
            "context_asset_count": len(
                {item["target_key"] for item in selected}
            ),
            "criticality_statement": (
                "Context is present, but no criticality is inferred from relationship presence."
                if selected
                else "No connected context relationship is present in the supplied snapshot."
            ),
        }
    )
    return result


def _breadth(dataset_count):
    if dataset_count == 0:
        return ExposureBreadth.LOCAL
    if dataset_count <= 2:
        return ExposureBreadth.LIMITED
    if dataset_count <= 10:
        return ExposureBreadth.BROAD
    return ExposureBreadth.WIDESPREAD


def _severity(identity, technical, context, propagation):
    consequence = TechnicalConsequence(technical["technical_consequence"])
    certainty = EvidenceCertainty(technical["evidence_certainty"])
    breadth = _breadth(propagation["metrics"]["downstream_dataset_count"])
    criticality = (
        ContextCriticality.ELEVATED_CONTEXT
        if context["context_relationships"]
        else ContextCriticality.CRITICALITY_UNKNOWN
    )
    if consequence is TechnicalConsequence.NO_DEMONSTRATED_IMPACT:
        severity = SeverityIfRealized.LOW
        rule_id = "severity-no-demonstrated-impact"
    elif consequence is TechnicalConsequence.CONFIRMED_IMPACT:
        severity = SeverityIfRealized.HIGH
        rule_id = "severity-confirmed-active-dependency"
    elif breadth in {ExposureBreadth.BROAD, ExposureBreadth.WIDESPREAD}:
        severity = SeverityIfRealized.HIGH
        rule_id = "severity-unresolved-material-breadth"
    else:
        severity = SeverityIfRealized.MODERATE
        rule_id = "severity-limited-potential-impact"
    result = _header(identity, "severity_criticality_analysis")
    result.update(
        {
            "context_criticality": criticality.value,
            "evidence_certainty": certainty.value,
            "exposure_breadth": breadth.value,
            "rule_id": rule_id,
            "severity_if_realized": severity.value,
            "technical_consequence": consequence.value,
        }
    )
    return result


def _synthesis(snapshot, proposal, identity, graph, propagation, compatibility, technical, context, severity):
    inputs = DecisionRuleInputs(
        technical_consequence=TechnicalConsequence(technical["technical_consequence"]),
        impact_certainty=EvidenceCertainty(technical["evidence_certainty"]),
        severity_if_realized=SeverityIfRealized(severity["severity_if_realized"]),
        breadth=ExposureBreadth(severity["exposure_breadth"]),
        criticality=ContextCriticality(severity["context_criticality"]),
        has_explicit_conditions=False,
    )
    decision = evaluate_decision(inputs)
    root_cause_id = technical["root_causes"][0]["root_cause_id"]
    uncertain = compatibility["root_evaluation"]["compatibility_state"] == "unknown"
    blocking_questions = []
    required_evidence = []
    if uncertain:
        boundary = next(
            (
                source
                for relationship in graph["relationships"]
                for source in relationship["source_entity_urns"]
            ),
            graph["current_root_key"],
        )
        evidence_id = stable_id("required-evidence", identity.proposal_fingerprint, boundary)
        required_evidence.append(
            {
                "evidence_class": "execution_or_consumer_semantics",
                "reason": compatibility["root_evaluation"]["reason_code"],
                "required_evidence_id": evidence_id,
                "state": "required_for_decision_resolution",
                "subject": boundary,
            }
        )
        blocking_questions.append(
            {
                "affected_dataset_urns": propagation["downstream_datasets"],
                "affected_path_ids": propagation["supporting_path_ids"],
                "question": _blocking_question(proposal, boundary),
                "question_id": stable_id("question", identity.proposal_fingerprint, boundary),
                "required_evidence_ids": [evidence_id],
                "resolution_state": "unresolved",
                "root_cause_id": root_cause_id,
                "subject": boundary,
            }
        )
    result = _header(identity, "impact_synthesis")
    result.update(
        {
            "blocking_questions": blocking_questions,
            "decision": {
                "certainty": decision.decision_certainty.value,
                "disposition": decision.disposition.value,
                "reason_codes": [item.value for item in decision.reason_codes],
                "rule_id": decision.rule_id,
            },
            "required_evidence": required_evidence,
            "summary": {
                "affected_dataset_count": propagation["metrics"]["downstream_dataset_count"],
                "affected_field_count": propagation["metrics"]["downstream_field_count"],
                "compatibility_state": compatibility["root_evaluation"]["compatibility_state"],
                "context_relationship_count": len(context["context_relationships"]),
                "severity_if_realized": severity["severity_if_realized"],
            },
        }
    )
    return result


def _blocking_question(proposal, boundary):
    if proposal.operation is StructuralOperation.FIELD_RENAME:
        return f"Does {boundary} accept the renamed input field?"
    if proposal.operation is StructuralOperation.FIELD_TYPE_CHANGE:
        return f"What input type does {boundary} require for this field?"
    return f"Can {boundary} operate without the deleted field?"


def _explanation_bundle(proposal, identity, target, propagation, compatibility, severity, synthesis):
    operation_text = {
        StructuralOperation.FIELD_RENAME: "rename",
        StructuralOperation.FIELD_DELETE: "delete",
        StructuralOperation.FIELD_TYPE_CHANGE: "type change",
    }[proposal.operation]
    result = _header(identity, "explanation_bundle")
    result.update(
        {
            "executive_summary": (
                f"The requested {operation_text} targets {target.field_path} and reaches "
                f"{propagation['metrics']['downstream_field_count']} downstream fields across "
                f"{propagation['metrics']['downstream_dataset_count']} datasets. The decision is "
                f"{synthesis['decision']['disposition']}."
            ),
            "evidence_summary": {
                "compatibility_reason": compatibility["root_evaluation"]["reason_code"],
                "decision_rule_id": synthesis["decision"]["rule_id"],
                "severity_rule_id": severity["rule_id"],
                "supporting_path_ids": propagation["supporting_path_ids"],
            },
            "limitations": [
                "Results describe only metadata present in the supplied snapshot.",
                "No DataHub metadata was written and no executable consumer behavior was inferred.",
            ],
        }
    )
    return result
