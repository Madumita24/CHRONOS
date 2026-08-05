"""General certification for deterministic Phase 6.3 composite packages."""

from __future__ import annotations

import re
from dataclasses import asdict
from typing import Any

from chronos.snapshot import contains_secret
from chronos.structural_engine.serialization import semantic_fingerprint

from .errors import PullRequestCertificationError
from .models import PullRequestAnalysisIdentity


PRE_CERTIFICATION_ARTIFACTS = {
    "pr_analysis_proposal.json", "proposal_validation.json", "repository_identity.json",
    "changed_file_inventory.json", "file_classification.json", "file_analysis_results.json",
    "structural_change_set.json", "semantic_change_set.json", "pipeline_change_set.json",
    "contract_quality_change_set.json", "entity_resolution.json",
    "logical_change_groups.json", "coherence_evaluation.json", "composite_change_set.json",
    "counterfactual_repository_state.json", "counterfactual_metadata_state.json",
    "future_metadata_graph.json", "dependency_propagation.json", "compatibility_evaluation.json",
    "technical_impact_analysis.json", "business_context_propagation.json",
    "severity_criticality_analysis.json", "impact_synthesis.json", "explanation_bundle.json",
}


def certify_pr_artifacts(identity, artifacts):
    checks = []
    _require(set(artifacts) == PRE_CERTIFICATION_ARTIFACTS, "Pre-certification package is incomplete or unknown.")
    checks.append(_pass("package_contract"))
    _identity(identity, artifacts)
    checks.append(_pass("identity_snapshot_repository_base_head"))
    _inventory(artifacts)
    checks.append(_pass("changed_file_inventory_and_fingerprints"))
    _file_results(artifacts)
    checks.append(_pass("parser_assignments_and_file_results"))
    delta_ids = _deltas(artifacts)
    checks.append(_pass("typed_delta_integrity"))
    root_ids = _groups_and_roots(artifacts, delta_ids)
    checks.append(_pass("correlation_groups_coherence_conflicts"))
    _graph(artifacts, root_ids)
    checks.append(_pass("counterfactual_graph_paths_and_traceability"))
    _decision(artifacts, root_ids)
    checks.append(_pass("compatibility_impact_severity_decision"))
    _portability(artifacts)
    checks.append(_pass("evidence_security_and_portability"))
    fingerprints = {name: semantic_fingerprint(value) for name, value in sorted(artifacts.items())}
    semantic_identity = asdict(identity)
    semantic_identity.pop("created_at", None)
    analysis_fingerprint = semantic_fingerprint({
        "identity": semantic_identity,
        "composite_change_set": artifacts["composite_change_set.json"],
        "counterfactual_metadata_state": artifacts["counterfactual_metadata_state.json"],
        "future_metadata_graph": artifacts["future_metadata_graph.json"],
        "decision": artifacts["impact_synthesis.json"]["decision"],
    })
    certification = {
        "analysis_id": identity.analysis_id,
        "artifact_type": "pr_analysis_certification",
        "artifact_schema_version": "1.0",
        "certification_status": "certified",
        "analysis_semantic_fingerprint": analysis_fingerprint,
        "artifact_fingerprints": fingerprints,
        "checks": checks,
        "engine_version": identity.engine_version,
        "proposal_id": identity.proposal_id,
        "proposal_fingerprint": identity.proposal_fingerprint,
        "repository_fingerprint": identity.repository_fingerprint,
        "base_commit": identity.base_commit,
        "head_commit": identity.head_commit,
        "source_snapshot_fingerprint": identity.source_snapshot_fingerprint,
    }
    return certification, fingerprints, analysis_fingerprint


def validate_completed_package(artifacts, manifest, expected_names, fingerprints):
    _require(set(artifacts) == set(expected_names), "Completed PR package is incomplete.")
    _require(manifest.get("artifact_names") == list(expected_names), "Manifest artifact names are incomplete.")
    _require(manifest.get("artifact_fingerprints") == fingerprints, "Manifest fingerprints are inconsistent.")
    _require(manifest.get("certification_status") == "certified", "Manifest is not certified.")
    _portability(artifacts)


def _identity(identity, artifacts):
    for name, value in artifacts.items():
        _require(value.get("analysis_id") == identity.analysis_id, f"Analysis identity mismatch in {name}.")
        _require(value.get("proposal_id") == identity.proposal_id, f"Proposal identity mismatch in {name}.")
        _require(value.get("repository_fingerprint") == identity.repository_fingerprint, f"Repository identity mismatch in {name}.")
        _require(value.get("base_commit") == identity.base_commit and value.get("head_commit") == identity.head_commit, f"Base/head identity mismatch in {name}.")
        _require(value.get("source_snapshot_fingerprint") == identity.source_snapshot_fingerprint, f"Snapshot identity mismatch in {name}.")


def _inventory(artifacts):
    inventory = artifacts["changed_file_inventory.json"]["files"]
    ids = [item["file_change_id"] for item in inventory]
    _require(len(ids) == len(set(ids)), "Duplicate changed-file identity.")
    for item in inventory:
        _require(item["base_path"] or item["head_path"], "Changed file lacks a path.")
        _require(item["base_content_fingerprint"] or item["head_content_fingerprint"], "Changed file lacks content evidence.")
        _require(item["base_size"] >= 0 and item["head_size"] >= 0, "Changed file size is invalid.")


def _file_results(artifacts):
    inventory_ids = {item["file_change_id"] for item in artifacts["changed_file_inventory.json"]["files"]}
    classifications = {item["file_change_id"] for item in artifacts["file_classification.json"]["classifications"]}
    results = artifacts["file_analysis_results.json"]["results"]
    result_ids = {item["file_change_id"] for item in results}
    _require(inventory_ids == classifications == result_ids, "Inventory, classification, and result coverage differ.")
    for item in results:
        _require(item["parser"].get("name") and item["parser"].get("version"), "File parser identity is absent.")
        _require(item["analysis_status"] in {"ANALYZED", "PARTIAL", "UNSUPPORTED"}, "File analysis status is invalid.")


def _deltas(artifacts):
    names = ("structural_change_set.json", "semantic_change_set.json", "pipeline_change_set.json", "contract_quality_change_set.json")
    items = [item for name in names for item in artifacts[name]["deltas"]]
    ids = [item["delta_id"] for item in items]
    _require(len(ids) == len(set(ids)), "Composite delta IDs are not unique.")
    _require(all(item.get("delta_class") and item.get("delta_type") for item in items), "Delta discriminator is incomplete.")
    return set(ids)


def _groups_and_roots(artifacts, delta_ids):
    file_ids = {item["file_change_id"] for item in artifacts["changed_file_inventory.json"]["files"]}
    groups = artifacts["logical_change_groups.json"]["groups"]
    group_ids = {item["logical_change_id"] for item in groups}
    _require(len(group_ids) == len(groups), "Logical group IDs are not unique.")
    for group in groups:
        _require(set(group["contributing_file_ids"]) <= file_ids, "Logical group has dangling file reference.")
        referenced = set(group["structural_delta_ids"] + group["semantic_delta_ids"] + group["pipeline_delta_ids"] + group["contract_delta_ids"])
        _require(referenced <= delta_ids, "Logical group has dangling delta reference.")
        _require(group["coherence_state"] in {"COHERENT", "PARTIALLY_COHERENT", "INCONSISTENT", "UNRESOLVED"}, "Logical group coherence is invalid.")
    technical = artifacts["technical_impact_analysis.json"]
    roots = technical["root_causes"]
    root_ids = {item["root_cause_id"] for item in roots}
    _require(len(root_ids) == len(roots), "Root cause IDs are not unique.")
    _require(all(set(item["contributing_file_ids"]) <= file_ids for item in roots), "Root cause has dangling file reference.")
    conflicts = artifacts["coherence_evaluation.json"]["conflicts"]
    _require(all(set(item["file_change_ids"]) <= file_ids for item in conflicts), "Conflict has dangling file reference.")
    return root_ids


def _graph(artifacts, root_ids):
    graph = artifacts["future_metadata_graph.json"]
    node_ids = {item["node_id"] for item in graph["nodes"]}
    relationship_ids = {item["relationship_id"] for item in graph["relationships"]}
    _require(len(node_ids) == len(graph["nodes"]), "Future Graph node IDs are not unique.")
    _require(len(relationship_ids) == len(graph["relationships"]), "Future Graph edge IDs are not unique.")
    for item in graph["relationships"]:
        _require(item["source"] in node_ids and item["target"] in node_ids, "Future Graph edge is dangling.")
        if item["edge_kind"] == "OBSERVED_DATAHUB_EDGE":
            _require(item.get("current_edge_id"), "Observed edge lacks current DataHub evidence.")
    path_ids = set()
    for path in graph["paths"]:
        _require(path["path_id"] not in path_ids, "Future Graph path ID is duplicated.")
        path_ids.add(path["path_id"])
        _require(set(path["node_ids"]) <= node_ids and set(path["relationship_ids"]) <= relationship_ids, "Future Graph path is dangling.")
        _require(path["root_cause_id"] in root_ids, "Future Graph path has unknown root.")
    propagation = artifacts["dependency_propagation.json"]
    for finding in propagation["findings"]:
        _require(set(finding["root_cause_ids"]) <= root_ids, "Propagation finding has unknown root.")
        _require(set(finding["path_ids"]) <= path_ids, "Propagation finding has unknown path.")


def _decision(artifacts, root_ids):
    compatibility = artifacts["compatibility_evaluation.json"]
    _require(compatibility.get("dimensions_are_independent") is True, "Compatibility dimensions were collapsed.")
    _require(all(item.get("rule_id") for item in compatibility["evaluations"]), "Compatibility rule traceability is absent.")
    technical = artifacts["technical_impact_analysis.json"]
    _require({item["root_cause_id"] for item in technical["root_causes"]} == root_ids, "Technical roots are inconsistent.")
    synthesis = artifacts["impact_synthesis.json"]
    _require(synthesis["decision"].get("decision_rule_id"), "PR decision rule is absent.")
    _require(synthesis["decision"]["disposition"] in {"proceed", "hold_for_review", "block_confirmed_incompatibility", "no_material_change"}, "PR disposition is invalid.")
    for item in synthesis["blocking_questions"] + synthesis["required_evidence"]:
        _require(item["root_cause_id"] in root_ids, "Question or evidence has unknown root.")


def _portability(artifacts):
    _require(not contains_secret(artifacts), "Credential-shaped content entered the PR package.")
    serialized = str(artifacts)
    _require(re.search(r"[A-Za-z]:\\Users\\", serialized) is None, "Absolute machine path entered the PR package.")
    _require("-----BEGIN PRIVATE KEY-----" not in serialized, "Private key entered the PR package.")


def _pass(check_id):
    return {"check_id": check_id, "status": "passed"}


def _require(condition, message):
    if not condition:
        raise PullRequestCertificationError(message)
