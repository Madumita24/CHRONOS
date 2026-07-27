"""Read-only certification of the complete CHRONOS Phase 2 package."""

from __future__ import annotations

import hashlib
from dataclasses import fields, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from chronos.change_semantics import (
    ChangeSemanticContract,
    ConsequenceStatus,
    EvaluationStatus,
    IdentityClassification,
    RuleDisposition,
    SemanticCategory,
    SemanticRuleCode,
    contract_semantic_fingerprint,
    load_contract,
)
from chronos.proposal import (
    CANONICAL_DATASET_URN,
    CANONICAL_DEMONSTRATION_ID,
    ChangeProposal,
    ChangeType,
    load_proposal,
    proposal_semantic_fingerprint,
)
from chronos.proposal_validation import (
    PreconditionStatus as ValidationPreconditionStatus,
    ProposalValidationResult,
    ProposalValidationState,
    ValidationFindingSeverity,
    load_validation_result,
    validation_result_semantic_fingerprint,
)
from chronos.snapshot import (
    CurrentMetadataSnapshot,
    FieldMachineKey,
    SnapshotValidationState,
    contains_secret,
    load_snapshot,
    semantic_fingerprint as snapshot_semantic_fingerprint,
)

from .models import (
    ArtifactHashEvidence,
    CertificationCheck,
    CertificationCheckStatus,
    CertificationFinding,
    CertificationFindingCode,
    CertificationFindingSeverity,
    Phase2CertificationResult,
    Phase2CertificationState,
)


Clock = Callable[[], datetime]
_CURRENT_FIELD = "order_total"
_REQUESTED_FIELD = "order_amount"
_EXPECTED_CHANGED = {"field_path", "field_name"}
_EXPECTED_UNCHANGED = {
    "target_dataset_urn",
    "platform",
    "environment",
    "native_type",
    "normalized_type",
    "nullable",
    "is_part_of_key",
    "other_source_fields",
}
_EXPECTED_UNKNOWN = {
    "downstream_field_names_change",
    "downstream_mappings_adapt",
    "spark_jobs_remain_valid",
    "dbt_models_remain_valid",
    "snowflake_transformations_remain_valid",
    "looker_assets_remain_valid",
    "power_bi_assets_remain_valid",
    "tableau_assets_remain_valid",
    "charts_or_dashboards_break",
    "governance_should_propagate",
    "data_products_require_updates",
    "documentation_requires_updates",
    "repair_is_possible",
}
_REQUIRED_VALIDATION_PRECONDITIONS = {
    "baseline_fingerprint",
    "demonstration_identity",
    "target_dataset",
    "target_field",
    "before_state",
    "source_schema_collision",
    "rename_admissibility",
    "additional_requested_mutation",
}
_FORBIDDEN_STATES = {
    "broken",
    "impacted",
    "high_risk",
    "requires_repair",
    "safe_to_deploy",
    "fixed",
    "auto_renamed",
}


def certify_phase2(
    snapshot: CurrentMetadataSnapshot,
    proposal: ChangeProposal,
    validation: ProposalValidationResult,
    contract: ChangeSemanticContract,
    *,
    artifact_hashes: tuple[ArtifactHashEvidence, ...] = (),
    clock: Clock | None = None,
) -> Phase2CertificationResult:
    """Audit the frozen package without modifying or repairing any input."""

    checks: list[CertificationCheck] = []
    findings: list[CertificationFinding] = []

    def check(
        name: str,
        condition: bool,
        expected: object,
        observed: object,
        code: CertificationFindingCode,
        failure_message: str,
    ) -> None:
        status = (
            CertificationCheckStatus.PASS
            if condition
            else CertificationCheckStatus.FAIL
        )
        checks.append(
            CertificationCheck(
                name=name,
                status=status,
                expected=_text(expected),
                observed=_text(observed),
            )
        )
        if not condition:
            findings.append(
                CertificationFinding(
                    code=code,
                    severity=CertificationFindingSeverity.BLOCKING,
                    message=failure_message,
                    check_name=name,
                )
            )

    check(
        "snapshot_embedded_validation",
        snapshot.validation_result.state is SnapshotValidationState.VALID,
        "valid",
        snapshot.validation_result.state.value,
        CertificationFindingCode.STRUCTURAL_INTEGRITY,
        "The Phase 1 snapshot is not certified valid.",
    )
    check(
        "proposal_change_type",
        proposal.change_type is ChangeType.FIELD_RENAME,
        "field_rename",
        getattr(proposal.change_type, "value", proposal.change_type),
        CertificationFindingCode.STRUCTURAL_INTEGRITY,
        "The proposal change type is unsupported.",
    )
    check(
        "validation_state",
        validation.validation_state is ProposalValidationState.VALID,
        "valid",
        validation.validation_state.value,
        CertificationFindingCode.VALIDATION_RESULT,
        "Phase 2.2 validation is not VALID.",
    )

    chain_checks = (
        (
            "proposal_baseline_to_snapshot",
            proposal.snapshot_reference.semantic_fingerprint,
            snapshot.semantic_fingerprint,
        ),
        (
            "validation_proposal_to_proposal",
            validation.proposal_fingerprint,
            proposal.semantic_fingerprint,
        ),
        (
            "validation_snapshot_to_snapshot",
            validation.snapshot_fingerprint,
            snapshot.semantic_fingerprint,
        ),
        (
            "contract_proposal_to_proposal",
            contract.proposal_fingerprint,
            proposal.semantic_fingerprint,
        ),
        (
            "contract_validation_to_validation",
            contract.validation_fingerprint,
            validation.semantic_fingerprint,
        ),
        (
            "contract_baseline_to_snapshot",
            contract.baseline_snapshot_fingerprint,
            snapshot.semantic_fingerprint,
        ),
    )
    for name, observed, expected in chain_checks:
        check(
            name,
            observed == expected,
            expected,
            observed,
            CertificationFindingCode.ARTIFACT_CHAIN,
            f"Artifact-chain reference failed: {name}.",
        )

    demonstration_values = (
        snapshot.metadata.demonstration_id,
        proposal.demonstration_id,
        validation.proposal_id,
        contract.proposal_id,
    )
    demonstration_matches = (
        snapshot.metadata.demonstration_id
        == proposal.demonstration_id
        == CANONICAL_DEMONSTRATION_ID
        and validation.proposal_id == proposal.proposal_id
        and contract.proposal_id == proposal.proposal_id
    )
    check(
        "demonstration_identity",
        demonstration_matches,
        CANONICAL_DEMONSTRATION_ID,
        demonstration_values,
        CertificationFindingCode.DEMONSTRATION_IDENTITY,
        "Artifacts do not belong to one canonical demonstration.",
    )

    target_key = FieldMachineKey(CANONICAL_DATASET_URN, _CURRENT_FIELD)
    validation_target = validation.validated_target
    target_values = (
        snapshot.source_dataset_urn,
        snapshot.source_field_key,
        proposal.change.target.machine_key,
        validation_target.machine_key if validation_target else None,
        contract.current_target.machine_key,
    )
    target_matches = (
        snapshot.source_dataset_urn == CANONICAL_DATASET_URN
        and snapshot.source_field_key == target_key
        and proposal.change.target.machine_key
        == (CANONICAL_DATASET_URN, _CURRENT_FIELD)
        and validation_target is not None
        and validation_target.machine_key
        == (CANONICAL_DATASET_URN, _CURRENT_FIELD)
        and contract.current_target.machine_key
        == (CANONICAL_DATASET_URN, _CURRENT_FIELD)
    )
    check(
        "target_machine_identity",
        target_matches,
        (CANONICAL_DATASET_URN, _CURRENT_FIELD),
        target_values,
        CertificationFindingCode.TARGET_IDENTITY,
        "The canonical target machine identity is inconsistent.",
    )

    source_fields = tuple(
        item
        for item in snapshot.source_schema.fields
        if item.field_path == _CURRENT_FIELD
    )
    source_field = source_fields[0] if len(source_fields) == 1 else None
    validation_before = validation.validated_before_state
    changed = {
        item.property_name: item for item in contract.changed_properties
    }
    unchanged = {
        item.property_name: item.value
        for item in contract.unchanged_properties
    }
    before_matches = (
        source_field is not None
        and source_field.field_path == _CURRENT_FIELD
        and source_field.field_name == _CURRENT_FIELD
        and source_field.native_type == "DOUBLE PRECISION"
        and source_field.normalized_type == "Number"
        and proposal.change.before.field_path == _CURRENT_FIELD
        and proposal.change.before.field_name == _CURRENT_FIELD
        and proposal.change.before.native_type == "DOUBLE PRECISION"
        and proposal.change.before.normalized_type == "Number"
        and validation_before is not None
        and validation_before.matches
        and validation_before.observed_field_path == _CURRENT_FIELD
        and validation_before.observed_field_name == _CURRENT_FIELD
        and validation_before.observed_native_type == "DOUBLE PRECISION"
        and validation_before.observed_normalized_type == "Number"
        and changed.get("field_path") is not None
        and changed["field_path"].before == _CURRENT_FIELD
        and changed.get("field_name") is not None
        and changed["field_name"].before == _CURRENT_FIELD
        and unchanged.get("native_type") == "DOUBLE PRECISION"
        and unchanged.get("normalized_type") == "Number"
    )
    check(
        "before_state_consistency",
        before_matches,
        "order_total|order_total|DOUBLE PRECISION|Number",
        (
            source_field,
            proposal.change.before,
            validation_before,
            (
                changed.get("field_path"),
                changed.get("field_name"),
                unchanged.get("native_type"),
                unchanged.get("normalized_type"),
            ),
        ),
        CertificationFindingCode.BEFORE_STATE,
        "The certified before-state is inconsistent.",
    )

    validation_requested = validation.requested_after_state
    requested_current_occurrences = sum(
        item.field_path == _REQUESTED_FIELD
        for item in snapshot.source_schema.fields
    )
    requested_matches = (
        proposal.change.requested_after.field_path == _REQUESTED_FIELD
        and proposal.change.requested_after.field_name == _REQUESTED_FIELD
        and validation_requested is not None
        and validation_requested.field_path == _REQUESTED_FIELD
        and validation_requested.field_name == _REQUESTED_FIELD
        and validation_requested.source_schema_occurrences == 0
        and contract.counterfactual_candidate.machine_key
        == (CANONICAL_DATASET_URN, _REQUESTED_FIELD)
        and contract.counterfactual_candidate.classification
        is IdentityClassification.COUNTERFACTUAL_CANDIDATE
        and contract.counterfactual_candidate.schema_field_urn is None
        and changed.get("field_path") is not None
        and changed["field_path"].after == _REQUESTED_FIELD
        and changed.get("field_name") is not None
        and changed["field_name"].after == _REQUESTED_FIELD
        and requested_current_occurrences == 0
    )
    check(
        "requested_state_consistency",
        requested_matches,
        "order_amount proposed only; current occurrences=0",
        (
            proposal.change.requested_after,
            validation_requested,
            contract.counterfactual_candidate,
            requested_current_occurrences,
        ),
        CertificationFindingCode.REQUESTED_STATE,
        "The requested state is inconsistent or appears as current metadata.",
    )

    validation_preconditions = {
        item.name: item.status for item in validation.preconditions
    }
    required_validation_passed = all(
        validation_preconditions.get(name)
        is ValidationPreconditionStatus.PASS
        for name in _REQUIRED_VALIDATION_PRECONDITIONS
    )
    blocking_validation_findings = tuple(
        item
        for item in validation.findings
        if item.severity
        in (
            ValidationFindingSeverity.ERROR,
            ValidationFindingSeverity.WARNING,
        )
    )
    validation_certifiable = (
        validation.validation_state is ProposalValidationState.VALID
        and required_validation_passed
        and not blocking_validation_findings
    )
    check(
        "validation_required_checks",
        validation_certifiable,
        "8 required PASS; 0 ERROR/WARNING",
        (
            sum(
                validation_preconditions.get(name)
                is ValidationPreconditionStatus.PASS
                for name in _REQUIRED_VALIDATION_PRECONDITIONS
            ),
            len(blocking_validation_findings),
        ),
        CertificationFindingCode.VALIDATION_RESULT,
        "Phase 2.2 required checks are not certifiable.",
    )

    changed_names = {item.property_name for item in contract.changed_properties}
    changed_exact = (
        changed_names == _EXPECTED_CHANGED
        and len(contract.changed_properties) == 2
        and all(
            item.category is SemanticCategory.CHANGED
            for item in contract.changed_properties
        )
    )
    check(
        "semantic_contract_changed_set",
        changed_exact,
        tuple(sorted(_EXPECTED_CHANGED)),
        tuple(sorted(changed_names)),
        CertificationFindingCode.SEMANTIC_CONTRACT,
        "The semantic contract changed-property set is not exact.",
    )

    unchanged_names = {
        item.property_name for item in contract.unchanged_properties
    }
    other_fields = unchanged.get("other_source_fields")
    unchanged_exact = (
        unchanged_names == _EXPECTED_UNCHANGED
        and unchanged.get("target_dataset_urn") == CANONICAL_DATASET_URN
        and unchanged.get("platform") == "postgres"
        and unchanged.get("environment") == "PROD"
        and unchanged.get("native_type") == "DOUBLE PRECISION"
        and unchanged.get("normalized_type") == "Number"
        and unchanged.get("nullable") is True
        and unchanged.get("is_part_of_key") is False
        and isinstance(other_fields, tuple)
        and len(other_fields) == 14
        and _CURRENT_FIELD not in other_fields
        and _REQUESTED_FIELD not in other_fields
        and all(
            item.category is SemanticCategory.UNCHANGED_BY_PROPOSAL
            for item in contract.unchanged_properties
        )
    )
    check(
        "semantic_contract_unchanged_set",
        unchanged_exact,
        tuple(sorted(_EXPECTED_UNCHANGED)),
        tuple(sorted(unchanged_names)),
        CertificationFindingCode.SEMANTIC_CONTRACT,
        "The unchanged-by-proposal set is inconsistent.",
    )

    unknown_names = {
        item.consequence for item in contract.unknown_consequences
    }
    unknown_exact = (
        unknown_names == _EXPECTED_UNKNOWN
        and all(
            item.status is ConsequenceStatus.UNKNOWN
            and item.evaluation is EvaluationStatus.NOT_EVALUATED
            and item.category is SemanticCategory.UNKNOWN_CONSEQUENCE
            for item in contract.unknown_consequences
        )
        and not (unknown_names & unchanged_names)
    )
    check(
        "semantic_contract_unknown_consequences",
        unknown_exact,
        "13 UNKNOWN/NOT_EVALUATED consequences",
        (len(unknown_names), tuple(sorted(unknown_names & unchanged_names))),
        CertificationFindingCode.SEMANTIC_CONTRACT,
        "Unknown consequences are incomplete or misclassified.",
    )

    schema_contract = contract.source_schema_contract
    cardinality_valid = (
        len(snapshot.source_schema.fields) == 15
        and schema_contract.current_field_count == 15
        and schema_contract.counterfactual_candidate_field_count == 15
        and not schema_contract.transformed_schema_materialized
        and len(schema_contract.unchanged_field_paths) == 14
    )
    check(
        "source_schema_cardinality",
        cardinality_valid,
        "current=15; candidate=15; materialized=false",
        (
            len(snapshot.source_schema.fields),
            schema_contract.current_field_count,
            schema_contract.counterfactual_candidate_field_count,
            schema_contract.transformed_schema_materialized,
        ),
        CertificationFindingCode.SCHEMA_CARDINALITY,
        "The source-schema cardinality contract is inconsistent.",
    )

    rules = {item.code: item.disposition for item in contract.semantic_rules}
    non_propagation_valid = (
        rules.get(SemanticRuleCode.AUTOMATIC_DOWNSTREAM_RENAME)
        is RuleDisposition.FORBIDDEN
        and rules.get(SemanticRuleCode.INFER_DOWNSTREAM_COMPATIBILITY)
        is RuleDisposition.FORBIDDEN
        and rules.get(SemanticRuleCode.CHANGE_UNRELATED_FIELDS)
        is RuleDisposition.FORBIDDEN
        and rules.get(SemanticRuleCode.DELETE_CURRENT_EVIDENCE)
        is RuleDisposition.FORBIDDEN
    )
    check(
        "non_propagation_rules",
        non_propagation_valid,
        "all propagation and inference rules forbidden",
        tuple(
            (code.value, disposition.value)
            for code, disposition in sorted(
                rules.items(),
                key=lambda item: item[0].value,
            )
            if code
            in {
                SemanticRuleCode.AUTOMATIC_DOWNSTREAM_RENAME,
                SemanticRuleCode.INFER_DOWNSTREAM_COMPATIBILITY,
                SemanticRuleCode.CHANGE_UNRELATED_FIELDS,
                SemanticRuleCode.DELETE_CURRENT_EVIDENCE,
            }
        ),
        CertificationFindingCode.NON_PROPAGATION,
        "The contract permits prohibited propagation behavior.",
    )

    boundary_valid = (
        contract.current_target.classification
        is IdentityClassification.CERTIFIED_CURRENT
        and contract.counterfactual_candidate.classification
        is IdentityClassification.COUNTERFACTUAL_CANDIDATE
        and not hasattr(contract, "future_graph")
        and not hasattr(contract, "lineage_edges")
        and schema_contract.transformed_schema_materialized is False
    )
    check(
        "current_counterfactual_boundary",
        boundary_valid,
        "current certified; candidate counterfactual; no graph",
        (
            contract.current_target.classification.value,
            contract.counterfactual_candidate.classification.value,
            hasattr(contract, "future_graph"),
        ),
        CertificationFindingCode.STATE_BOUNDARY,
        "Current and counterfactual semantics are mixed.",
    )

    phase2_objects_frozen = all(
        _all_dataclasses_frozen(value)
        for value in (proposal, validation, contract)
    )
    check(
        "phase2_domain_immutability",
        phase2_objects_frozen,
        "all Phase 2 dataclasses frozen",
        phase2_objects_frozen,
        CertificationFindingCode.IMMUTABILITY,
        "A Phase 2 domain object is mutable.",
    )

    for item in artifact_hashes:
        check(
            f"artifact_hash_unchanged:{item.artifact_name}",
            item.before_sha256 == item.after_sha256,
            item.before_sha256,
            item.after_sha256,
            CertificationFindingCode.ARTIFACT_HASH,
            f"Artifact changed during certification: {item.artifact_name}.",
        )

    fingerprint_checks = (
        (
            "snapshot_fingerprint_recomputed",
            snapshot_semantic_fingerprint(snapshot),
            snapshot.semantic_fingerprint,
        ),
        (
            "proposal_fingerprint_recomputed",
            proposal_semantic_fingerprint(proposal),
            proposal.semantic_fingerprint,
        ),
        (
            "validation_fingerprint_recomputed",
            validation_result_semantic_fingerprint(validation),
            validation.semantic_fingerprint,
        ),
        (
            "contract_fingerprint_recomputed",
            contract_semantic_fingerprint(contract),
            contract.semantic_fingerprint,
        ),
    )
    for name, observed, expected in fingerprint_checks:
        check(
            name,
            observed == expected,
            expected,
            observed,
            CertificationFindingCode.DETERMINISM,
            f"Stored semantic fingerprint does not reproduce: {name}.",
        )

    try:
        round_trips = (
            snapshot.semantically_equals(
                CurrentMetadataSnapshot.from_json(snapshot.to_json())
            )
            and proposal.semantically_equals(
                ChangeProposal.from_json(proposal.to_json())
            )
            and validation.semantically_equals(
                ProposalValidationResult.from_json(validation.to_json())
            )
            and contract.semantically_equals(
                ChangeSemanticContract.from_json(contract.to_json())
            )
        )
    except ValueError:
        round_trips = False
    check(
        "deterministic_round_trips",
        round_trips,
        True,
        round_trips,
        CertificationFindingCode.DETERMINISM,
        "An artifact failed deterministic semantic round trip.",
    )

    secret_free = not any(
        contains_secret(value.to_dict())
        for value in (snapshot, proposal, validation, contract)
    )
    check(
        "credential_content_audit",
        secret_free,
        "no credential-shaped data",
        "none" if secret_free else "detected",
        CertificationFindingCode.SECRET_AUDIT,
        "Credential-shaped content was detected.",
    )

    phase2_payload = "\n".join(
        (proposal.to_json(), validation.to_json(), contract.to_json())
    ).casefold()
    forbidden_present = tuple(
        term for term in sorted(_FORBIDDEN_STATES) if term in phase2_payload
    )
    check(
        "forbidden_semantic_states",
        not forbidden_present,
        "none",
        forbidden_present,
        CertificationFindingCode.FORBIDDEN_SEMANTICS,
        "A forbidden semantic state is present in Phase 2 artifacts.",
    )

    no_live_client_state = all(
        not hasattr(value, "_client") and not hasattr(value, "_transport")
        for value in (proposal, validation, contract)
    )
    check(
        "no_live_datahub_dependency",
        no_live_client_state,
        "no client or transport state",
        no_live_client_state,
        CertificationFindingCode.STATE_BOUNDARY,
        "Phase 2 contains live-client state.",
    )

    structural_valid = (
        proposal.snapshot_reference.semantic_fingerprint
        == snapshot.semantic_fingerprint
        and validation.proposal_fingerprint == proposal.semantic_fingerprint
        and contract.validation_fingerprint == validation.semantic_fingerprint
        and bool(contract.changed_properties)
        and not (changed_names & unknown_names)
        and _CURRENT_FIELD != _REQUESTED_FIELD
        and requested_current_occurrences == 0
        and proposal.change.target.dataset_urn.startswith(
            "urn:li:dataset:("
        )
    )
    check(
        "structural_integrity",
        structural_valid,
        "no dangling or contradictory references",
        structural_valid,
        CertificationFindingCode.STRUCTURAL_INTEGRITY,
        "The Phase 2 package has structural contradictions.",
    )

    state = (
        Phase2CertificationState.CERTIFIED
        if all(
            item.status is CertificationCheckStatus.PASS for item in checks
        )
        else Phase2CertificationState.NOT_CERTIFIED
    )
    return Phase2CertificationResult(
        demonstration_id=CANONICAL_DEMONSTRATION_ID,
        certification_state=state,
        snapshot_fingerprint=snapshot.semantic_fingerprint,
        proposal_fingerprint=proposal.semantic_fingerprint,
        validation_fingerprint=validation.semantic_fingerprint,
        semantic_contract_fingerprint=contract.semantic_fingerprint,
        checks=tuple(checks),
        findings=tuple(findings),
        warnings=(),
        artifact_hashes=artifact_hashes,
        certified_at=_timestamp(clock),
    )


def certify_phase2_from_artifacts(
    snapshot_path: str | Path,
    proposal_path: str | Path,
    validation_path: str | Path,
    contract_path: str | Path,
    *,
    clock: Clock | None = None,
) -> Phase2CertificationResult:
    paths = (
        ("current_metadata_snapshot.json", Path(snapshot_path)),
        ("change_proposal.json", Path(proposal_path)),
        ("change_proposal_validation.json", Path(validation_path)),
        ("change_semantic_contract.json", Path(contract_path)),
    )
    before = {
        name: hashlib.sha256(path.read_bytes()).hexdigest()
        for name, path in paths
    }
    snapshot = load_snapshot(snapshot_path)
    proposal = load_proposal(proposal_path)
    validation = load_validation_result(validation_path)
    contract = load_contract(contract_path)
    after = {
        name: hashlib.sha256(path.read_bytes()).hexdigest()
        for name, path in paths
    }
    hashes = tuple(
        ArtifactHashEvidence(
            artifact_name=name,
            before_sha256=before[name],
            after_sha256=after[name],
        )
        for name, _ in paths
    )
    return certify_phase2(
        snapshot,
        proposal,
        validation,
        contract,
        artifact_hashes=hashes,
        clock=clock,
    )


def _all_dataclasses_frozen(value: object) -> bool:
    if is_dataclass(value) and not isinstance(value, type):
        params = getattr(type(value), "__dataclass_params__", None)
        if params is None or not params.frozen:
            return False
        return all(
            _all_dataclasses_frozen(getattr(value, item.name))
            for item in fields(value)
        )
    if isinstance(value, tuple):
        return all(_all_dataclasses_frozen(item) for item in value)
    return True


def _text(value: object) -> str:
    if isinstance(value, tuple):
        return repr(value)
    return str(value)


def _timestamp(clock: Clock | None) -> str:
    value = (clock or (lambda: datetime.now(timezone.utc)))()
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()
