"""Certification checks for generalized analysis artifact sets."""

from __future__ import annotations

from typing import Any

from .errors import CertificationError
from .models import AnalysisIdentity, GENERALIZED_ENGINE_VERSION
from .serialization import semantic_fingerprint


def certify_artifacts(
    identity: AnalysisIdentity,
    artifacts: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, str], str]:
    """Validate integrity and return certification, hashes, analysis hash."""
    checks: list[dict[str, str]] = []
    _check_package_contract(artifacts)
    checks.append(_passed("manifest_contract", "The required pre-certification artifact set is complete."))
    _check_identity(identity, artifacts)
    checks.append(_passed("identity_consistency", "All artifacts carry the same analysis identity."))
    _check_counterfactual(artifacts["counterfactual_source_state.json"])
    checks.append(_passed("counterfactual_invariants", "Projected schema invariants hold."))
    _check_operation_semantics(identity, artifacts)
    checks.append(_passed("operation_semantics", "Operation-specific invariants hold."))
    _check_graph(artifacts["future_metadata_graph.json"])
    checks.append(_passed("graph_integrity", "All graph and path references resolve."))
    _check_rule_traceability(artifacts)
    checks.append(_passed("rule_traceability", "Compatibility, severity, and decision rules are identified."))
    _check_impact_traceability(artifacts)
    checks.append(_passed("impact_traceability", "Impact findings and decision summary trace to propagation and one shared cause."))
    _check_context_distinction(artifacts["business_context_propagation.json"])
    checks.append(_passed("context_distinction", "Connected context is not asserted to be broken or critical."))
    _check_no_absolute_paths(artifacts)
    checks.append(_passed("artifact_portability", "No artifact contains an absolute local path."))

    fingerprints = {
        name: semantic_fingerprint(content)
        for name, content in sorted(artifacts.items())
    }
    analysis_fingerprint = semantic_fingerprint(
        {
            "analysis_id": identity.analysis_id,
            "artifact_fingerprints": fingerprints,
            "engine_version": GENERALIZED_ENGINE_VERSION,
            "proposal_fingerprint": identity.proposal_fingerprint,
            "source_snapshot_fingerprint": identity.source_snapshot_fingerprint,
        }
    )
    certification = {
        "analysis_id": identity.analysis_id,
        "analysis_semantic_fingerprint": analysis_fingerprint,
        "artifact_fingerprints": fingerprints,
        "artifact_schema_version": "1.0",
        "artifact_type": "phase_6_1_generalized_certification",
        "certification_status": "certified",
        "checks": checks,
        "engine_version": GENERALIZED_ENGINE_VERSION,
        "operation": identity.operation.value,
        "proposal_fingerprint": identity.proposal_fingerprint,
        "proposal_id": identity.proposal_id,
        "source_snapshot_fingerprint": identity.source_snapshot_fingerprint,
    }
    return certification, fingerprints, analysis_fingerprint


def _passed(check_id: str, statement: str) -> dict[str, str]:
    return {"check_id": check_id, "statement": statement, "status": "passed"}


def _check_package_contract(artifacts):
    expected = {
        "proposal.json",
        "proposal_validation.json",
        "change_semantic_contract.json",
        "counterfactual_source_state.json",
        "future_metadata_graph.json",
        "dependency_propagation.json",
        "compatibility_evaluation.json",
        "technical_impact_analysis.json",
        "business_context_propagation.json",
        "severity_criticality_analysis.json",
        "impact_synthesis.json",
        "explanation_bundle.json",
    }
    if set(artifacts) != expected:
        raise CertificationError("Pre-certification artifact package is incomplete or contains unknown files.")
    if artifacts["proposal_validation.json"].get("state") != "valid":
        raise CertificationError("Proposal validation artifact is not valid.")


def _check_identity(identity, artifacts):
    for name, content in artifacts.items():
        expected = {
            "analysis_id": identity.analysis_id,
            "operation": identity.operation.value,
            "proposal_fingerprint": identity.proposal_fingerprint,
            "proposal_id": identity.proposal_id,
            "source_snapshot_fingerprint": identity.source_snapshot_fingerprint,
        }
        for key, value in expected.items():
            if content.get(key) != value:
                raise CertificationError(f"{name} has inconsistent {key}.")


def _check_counterfactual(counterfactual):
    invariants = counterfactual.get("invariants", {})
    if not invariants or not all(invariants.values()):
        raise CertificationError("Counterfactual source invariants failed.")
    projected = counterfactual["projected_source_schema"]
    if projected["field_count"] != len(projected["fields"]):
        raise CertificationError("Projected source field count is inconsistent.")


def _check_operation_semantics(identity, artifacts):
    counterfactual = artifacts["counterfactual_source_state.json"]
    contract = artifacts["change_semantic_contract.json"]
    current_fields = counterfactual["current_source_schema"]["fields"]
    future_fields = counterfactual["projected_source_schema"]["fields"]
    current_path = identity.current_field_path
    future_path = counterfactual["source_change"]["projected_field_path"]
    current_target = next(item for item in current_fields if item["field_path"] == current_path)
    unaffected_current = [item for item in current_fields if item["field_path"] != current_path]
    unaffected_future = [item for item in future_fields if item["field_path"] != future_path]
    if identity.operation.value == "FIELD_RENAME":
        if len(future_fields) != len(current_fields):
            raise CertificationError("Rename changed source field count.")
        if any(item["field_path"] == current_path for item in future_fields):
            raise CertificationError("Rename retained the old active source identity.")
        renamed = [item for item in future_fields if item["field_path"] == future_path]
        if len(renamed) != 1:
            raise CertificationError("Rename did not create exactly one future identity.")
        ignored = {"field_path", "field_name", "schema_field_urn"}
        if {key: value for key, value in current_target.items() if key not in ignored} != {
            key: value for key, value in renamed[0].items() if key not in ignored
        }:
            raise CertificationError("Rename did not preserve non-name properties.")
        expected_classification = "RENAMED"
    elif identity.operation.value == "FIELD_DELETE":
        if len(future_fields) != len(current_fields) - 1:
            raise CertificationError("Delete did not decrease source field count by one.")
        if any(item["field_path"] == current_path for item in future_fields):
            raise CertificationError("Delete retained the source field in active future schema.")
        expected_classification = "DELETED"
    else:
        if len(future_fields) != len(current_fields):
            raise CertificationError("Type change changed source field count.")
        changed = [item for item in future_fields if item["field_path"] == current_path]
        if len(changed) != 1:
            raise CertificationError("Type change did not preserve field identity.")
        ignored = {"native_type", "normalized_type", "datahub_type", "schema_field_urn"}
        if {key: value for key, value in current_target.items() if key not in ignored} != {
            key: value for key, value in changed[0].items() if key not in ignored
        }:
            raise CertificationError("Type change did not preserve unrelated properties.")
        expected_classification = "IDENTITY_PRESERVED_TYPE_CHANGED"
    if unaffected_current != unaffected_future:
        raise CertificationError("Operation changed unrelated source fields.")
    if contract["identity_mapping"]["classification"] != expected_classification:
        raise CertificationError("Identity mapping classification is inconsistent.")


def _check_graph(graph):
    node_keys = {item["future_key"] for item in graph["nodes"]}
    relationship_ids = {item["relationship_id"] for item in graph["relationships"]}
    if len(node_keys) != len(graph["nodes"]):
        raise CertificationError("Future graph contains duplicate node identities.")
    if len(relationship_ids) != len(graph["relationships"]):
        raise CertificationError("Future graph contains duplicate relationship identities.")
    for relationship in graph["relationships"]:
        if relationship["upstream_key"] not in node_keys or relationship["downstream_key"] not in node_keys:
            raise CertificationError("Future graph contains a dangling relationship endpoint.")
    for path in graph["paths"]:
        if not set(path["node_keys"]).issubset(node_keys):
            raise CertificationError("Future graph path contains an unknown node.")
        if not set(path["relationship_ids"]).issubset(relationship_ids):
            raise CertificationError("Future graph path contains an unknown relationship.")
        if len(path["node_keys"]) != len(path["relationship_ids"]) + 1:
            raise CertificationError("Future graph path has inconsistent cardinality.")


def _check_rule_traceability(artifacts):
    compatibility = artifacts["compatibility_evaluation.json"]
    severity = artifacts["severity_criticality_analysis.json"]
    synthesis = artifacts["impact_synthesis.json"]
    if not compatibility.get("rules_applied"):
        raise CertificationError("Compatibility evaluation has no applied rule.")
    if not severity.get("rule_id"):
        raise CertificationError("Severity analysis has no applied rule.")
    if not synthesis.get("decision", {}).get("rule_id"):
        raise CertificationError("Impact synthesis has no applied decision rule.")


def _check_impact_traceability(artifacts):
    propagation = artifacts["dependency_propagation.json"]
    technical = artifacts["technical_impact_analysis.json"]
    synthesis = artifacts["impact_synthesis.json"]
    causes = {item["root_cause_id"] for item in technical["root_causes"]}
    if len(causes) != 1:
        raise CertificationError("Technical impact must expose one shared source cause.")
    if any(item["root_cause_id"] not in causes for item in technical["findings"]):
        raise CertificationError("A technical finding does not trace to the shared source cause.")
    summary = synthesis["summary"]
    metrics = propagation["metrics"]
    if summary["affected_field_count"] != metrics["downstream_field_count"]:
        raise CertificationError("Impact field count does not trace to propagation.")
    if summary["affected_dataset_count"] != metrics["downstream_dataset_count"]:
        raise CertificationError("Impact dataset count does not trace to propagation.")


def _check_context_distinction(context):
    statement = context.get("criticality_statement", "").lower()
    explicitly_noncritical = (
        "not inferred" in statement or "no criticality is inferred" in statement
    )
    if not statement or ("critical" in statement and not explicitly_noncritical):
        raise CertificationError("Business context improperly asserts criticality.")


def _check_no_absolute_paths(value):
    def visit(item: Any) -> bool:
        if isinstance(item, dict):
            return any(visit(key) or visit(child) for key, child in item.items())
        if isinstance(item, list):
            return any(visit(child) for child in item)
        if isinstance(item, str):
            normalized = item.replace("\\", "/")
            return normalized.startswith("/") or (
                len(normalized) > 2 and normalized[1:3] == ":/"
            )
        return False

    if visit(value):
        raise CertificationError("Generated artifact contains an absolute local path.")
