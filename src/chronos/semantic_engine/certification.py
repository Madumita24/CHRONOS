"""General semantic analysis certification without fixed scenario counts."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .errors import SemanticCertificationError
from .models import SQL_PARSER_VERSION, DeltaType, SemanticAnalysisIdentity
from .serialization import semantic_fingerprint


PRE_CERTIFICATION_ARTIFACTS = {
    "semantic_change_proposal.json",
    "proposal_validation.json",
    "before_parsed_model.json",
    "after_parsed_model.json",
    "semantic_diff.json",
    "entity_resolution.json",
    "code_change_set.json",
    "counterfactual_semantic_state.json",
    "future_metadata_graph.json",
    "dependency_propagation.json",
    "compatibility_evaluation.json",
    "technical_impact_analysis.json",
    "business_context_propagation.json",
    "severity_criticality_analysis.json",
    "impact_synthesis.json",
    "explanation_bundle.json",
}


def certify_semantic_artifacts(
    identity: SemanticAnalysisIdentity,
    artifacts: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, str], str]:
    checks = []
    _check_package(artifacts)
    checks.append(_passed("package_contract"))
    _check_identity(identity, artifacts)
    checks.append(_passed("identity_and_snapshot"))
    _check_parser(identity, artifacts)
    checks.append(_passed("parser_and_ast_normalization"))
    _check_deltas(artifacts)
    checks.append(_passed("semantic_delta_integrity"))
    _check_operation_semantics(artifacts)
    checks.append(_passed("operation_specific_semantics"))
    _check_resolution(artifacts)
    checks.append(_passed("model_and_output_resolution"))
    _check_graph(artifacts)
    checks.append(_passed("graph_and_path_integrity"))
    _check_traceability(artifacts)
    checks.append(_passed("compatibility_impact_decision_traceability"))
    _check_evidence_classes(artifacts)
    checks.append(_passed("evidence_classification"))
    _check_portability(artifacts)
    checks.append(_passed("security_and_portability"))
    fingerprints = {
        name: semantic_fingerprint(content)
        for name, content in sorted(artifacts.items())
    }
    diff = artifacts["semantic_diff.json"]
    graph = artifacts["future_metadata_graph.json"]
    synthesis = artifacts["impact_synthesis.json"]
    semantic_identity = asdict(identity)
    semantic_identity.pop("created_at", None)
    semantic_graph = dict(graph)
    semantic_graph.pop("created_at", None)
    analysis_fingerprint = semantic_fingerprint(
        {
            "after_ast_fingerprint": diff["after_ast_fingerprint"],
            "before_ast_fingerprint": diff["before_ast_fingerprint"],
            "engine_version": identity.engine_version,
            "graph": semantic_graph,
            "identity": semantic_identity,
            "semantic_deltas": diff["semantic_deltas"],
            "structural_deltas": diff["structural_deltas"],
            "decision": synthesis["decision"],
        }
    )
    certification = {
        "analysis_id": identity.analysis_id,
        "analysis_semantic_fingerprint": analysis_fingerprint,
        "artifact_fingerprints": fingerprints,
        "artifact_schema_version": "1.0",
        "artifact_type": "semantic_analysis_certification",
        "certification_status": "certified",
        "checks": checks,
        "engine_version": identity.engine_version,
        "model_dataset_urn": identity.model_dataset_urn,
        "operation": identity.operation.value,
        "parser_name": identity.parser_name,
        "parser_version": identity.parser_version,
        "proposal_fingerprint": identity.proposal_fingerprint,
        "proposal_id": identity.proposal_id,
        "source_snapshot_fingerprint": identity.source_snapshot_fingerprint,
        "sql_dialect": identity.sql_dialect,
    }
    return certification, fingerprints, analysis_fingerprint


def _passed(check_id):
    return {"check_id": check_id, "status": "passed"}


def _check_package(artifacts):
    if set(artifacts) != PRE_CERTIFICATION_ARTIFACTS:
        raise SemanticCertificationError(
            "Semantic pre-certification artifact package is incomplete or unknown."
        )
    if artifacts["proposal_validation.json"].get("state") != "valid":
        raise SemanticCertificationError("Semantic proposal validation is not valid.")


def _check_identity(identity, artifacts):
    expected = {
        "analysis_id": identity.analysis_id,
        "model_dataset_urn": identity.model_dataset_urn,
        "operation": identity.operation.value,
        "proposal_fingerprint": identity.proposal_fingerprint,
        "proposal_id": identity.proposal_id,
        "source_snapshot_fingerprint": identity.source_snapshot_fingerprint,
    }
    for name, artifact in artifacts.items():
        for key, value in expected.items():
            if artifact.get(key) != value:
                raise SemanticCertificationError(
                    f"{name} has inconsistent semantic identity {key}."
                )


def _check_parser(identity, artifacts):
    if identity.parser_version != SQL_PARSER_VERSION:
        raise SemanticCertificationError("Semantic identity has unexpected parser version.")
    before = artifacts["before_parsed_model.json"]["parsed_model"]
    after = artifacts["after_parsed_model.json"]["parsed_model"]
    for model in (before, after):
        if model["parser_version"] != SQL_PARSER_VERSION:
            raise SemanticCertificationError("Parsed model parser version is inconsistent.")
        if model["dialect"] != identity.sql_dialect:
            raise SemanticCertificationError("Parsed model dialect is inconsistent.")
    if before["canonical_ast_fingerprint"] != identity.before_content_fingerprint:
        raise SemanticCertificationError("BEFORE canonical AST identity is inconsistent.")
    if after["canonical_ast_fingerprint"] != identity.after_content_fingerprint:
        raise SemanticCertificationError("AFTER canonical AST identity is inconsistent.")


def _check_deltas(artifacts):
    diff = artifacts["semantic_diff.json"]
    deltas = diff["structural_deltas"] + diff["semantic_deltas"]
    ids = [item["delta_id"] for item in deltas]
    if len(ids) != len(set(ids)):
        raise SemanticCertificationError("Semantic package has duplicate delta IDs.")
    if not deltas and diff["change_state"] != "NO_SEMANTIC_CHANGE":
        raise SemanticCertificationError("No-change state is inconsistent.")
    if deltas and diff["change_state"] != "CHANGES_DETECTED":
        raise SemanticCertificationError("Detected delta state is inconsistent.")


def _check_operation_semantics(artifacts):
    diff = artifacts["semantic_diff.json"]
    for delta in diff["semantic_deltas"]:
        delta_type = DeltaType(delta["delta_type"])
        if delta_type is DeltaType.AGGREGATION_CHANGE:
            if delta["before_representation"] == delta["after_representation"]:
                raise SemanticCertificationError("Aggregation delta has equal representations.")
            if not delta["affected_output_field"] or not delta["input_references"]:
                raise SemanticCertificationError("Aggregation delta lacks output or inputs.")
        elif delta_type is DeltaType.FILTER_CHANGE:
            if delta["scope"] != "MODEL_WIDE":
                raise SemanticCertificationError("Filter delta scope is not model-wide.")
            if any(token in delta["explanation"].lower() for token in ("rows lost", "exact row")):
                raise SemanticCertificationError("Filter delta invents exact row impact.")
        elif delta_type in {
            DeltaType.JOIN_TYPE_CHANGE,
            DeltaType.JOIN_PREDICATE_CHANGE,
            DeltaType.JOINED_RELATION_CHANGE,
        }:
            if "unresolved" not in delta["explanation"].lower() and "may" not in delta["explanation"].lower():
                raise SemanticCertificationError("Join consequence is not conservative.")
        elif delta_type is DeltaType.DERIVED_EXPRESSION_CHANGE:
            if not delta["affected_output_field"]:
                raise SemanticCertificationError("Expression delta lacks affected output.")
            if delta["before_representation"] == delta["after_representation"]:
                raise SemanticCertificationError("Expression fingerprints are not meaningfully different.")


def _check_resolution(artifacts):
    resolution = artifacts["entity_resolution.json"]
    if resolution["model"]["resolution_state"] != "RESOLVED":
        raise SemanticCertificationError("Target model is not exactly resolved.")
    for item in resolution["output_mappings"]:
        key = item.get("datahub_field_key")
        if key and not key.startswith("urn:li:dataset:("):
            raise SemanticCertificationError("Output mapping has a malformed DataHub key.")


def _check_graph(artifacts):
    graph = artifacts["future_metadata_graph.json"]
    nodes = {item["field_key"] for item in graph["nodes"]}
    relationships = {item["relationship_id"] for item in graph["relationships"]}
    for edge in graph["relationships"]:
        if edge["upstream_key"] not in nodes or edge["downstream_key"] not in nodes:
            raise SemanticCertificationError("Semantic graph has a dangling endpoint.")
    for path in graph["paths"]:
        if not set(path["node_keys"]).issubset(nodes):
            raise SemanticCertificationError("Semantic path has a dangling node.")
        if not set(path["relationship_ids"]).issubset(relationships):
            raise SemanticCertificationError("Semantic path has a dangling relationship.")
        if len(path["node_keys"]) != len(path["relationship_ids"]) + 1:
            raise SemanticCertificationError("Semantic path cardinality is invalid.")


def _check_traceability(artifacts):
    compatibility = artifacts["compatibility_evaluation.json"]
    technical = artifacts["technical_impact_analysis.json"]
    synthesis = artifacts["impact_synthesis.json"]
    if not all(item.get("rule_id") for item in compatibility["rule_evaluations"]):
        raise SemanticCertificationError("Compatibility rule traceability is incomplete.")
    causes = {item["root_cause_id"] for item in technical["root_causes"]}
    if any(not set(item["root_cause_ids"]).issubset(causes) for item in technical["findings"]):
        raise SemanticCertificationError("Technical impact has an unknown root cause.")
    if not synthesis["decision"].get("rule_id"):
        raise SemanticCertificationError("Decision rule traceability is incomplete.")


def _check_evidence_classes(artifacts):
    allowed = {
        "OBSERVED_DATAHUB_EVIDENCE",
        "CODE_DERIVED_EVIDENCE",
        "COUNTERFACTUAL_DERIVATION",
        "COUNTERFACTUAL_DERIVATION_FROM_OBSERVED_EDGES",
        "MISSING_EVIDENCE",
        "DECISION_EVIDENCE",
    }

    def visit(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key == "evidence_class" and item not in allowed:
                    raise SemanticCertificationError(
                        f"Unknown semantic evidence class {item!r}."
                    )
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(artifacts)


def _check_portability(value):
    def visit(item):
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
        raise SemanticCertificationError(
            "Semantic artifact contains an absolute local path."
        )
