"""Fail-closed builder for the certified FIELD_RENAME semantic contract."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from chronos.proposal import (
    ChangeProposal,
    ChangeType,
    load_proposal,
    validate_change_proposal,
)
from chronos.proposal_validation import (
    PreconditionStatus as ValidationPreconditionStatus,
    ProposalValidationResult,
    ProposalValidationState,
    load_validation_result,
)
from chronos.snapshot import (
    CurrentMetadataSnapshot,
    FieldMachineKey,
    SnapshotValidationState,
    load_snapshot,
)

from .errors import SemanticContractPreconditionError
from .models import (
    ChangeSemanticContract,
    ChangedProperty,
    ConsequenceStatus,
    ContractPrecondition,
    EvaluationStatus,
    FieldMachineIdentity,
    IdentityClassification,
    PreconditionStatus,
    RuleDisposition,
    SemanticRule,
    SemanticRuleCode,
    SourceSchemaSemanticContract,
    UnchangedProperty,
    UnknownConsequence,
)


Clock = Callable[[], datetime]


_UNKNOWN_CONSEQUENCES = (
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
)


def build_change_semantic_contract(
    snapshot: CurrentMetadataSnapshot,
    proposal: ChangeProposal,
    validation: ProposalValidationResult,
    *,
    clock: Clock | None = None,
) -> ChangeSemanticContract:
    """Build a declaration of meaning without constructing future state."""

    _require_inputs(snapshot, proposal, validation)
    target = proposal.change.target
    key = FieldMachineKey(target.dataset_urn, target.field_path)
    datasets = tuple(
        item
        for item in snapshot.datasets
        if item.dataset_urn == target.dataset_urn
    )
    graph_fields = tuple(item for item in snapshot.fields if item.key == key)
    schema_fields = tuple(
        item
        for item in snapshot.source_schema.fields
        if item.field_path == target.field_path
    )
    requested_collisions = tuple(
        item
        for item in snapshot.source_schema.fields
        if item.field_path == proposal.change.requested_after.field_path
    )
    if len(datasets) != 1:
        raise SemanticContractPreconditionError(
            "Target dataset must exist exactly once."
        )
    if len(graph_fields) != 1 or len(schema_fields) != 1:
        raise SemanticContractPreconditionError(
            "Target field must exist exactly once in certified current state."
        )
    if requested_collisions:
        raise SemanticContractPreconditionError(
            "Requested field path collides with the source schema."
        )
    field = schema_fields[0]
    before = proposal.change.before
    if (
        field.field_path != before.field_path
        or field.field_name != before.field_name
        or field.native_type != before.native_type
        or field.normalized_type != before.normalized_type
    ):
        raise SemanticContractPreconditionError(
            "Proposal before-state does not match certified current state."
        )

    unchanged = [
        UnchangedProperty("target_dataset_urn", target.dataset_urn),
        UnchangedProperty("platform", datasets[0].platform),
        UnchangedProperty("environment", datasets[0].environment),
        UnchangedProperty("native_type", field.native_type),
        UnchangedProperty("normalized_type", field.normalized_type),
    ]
    if field.nullable is not None:
        unchanged.append(UnchangedProperty("nullable", field.nullable))
    if field.is_part_of_key is not None:
        unchanged.append(
            UnchangedProperty("is_part_of_key", field.is_part_of_key)
        )
    other_fields = tuple(
        item.field_path
        for item in snapshot.source_schema.fields
        if item.field_path != target.field_path
    )
    unchanged.append(UnchangedProperty("other_source_fields", other_fields))

    requested = proposal.change.requested_after
    return ChangeSemanticContract(
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.semantic_fingerprint,
        validation_fingerprint=validation.semantic_fingerprint,
        baseline_snapshot_fingerprint=snapshot.semantic_fingerprint,
        change_type=proposal.change_type,
        current_target=FieldMachineIdentity(
            dataset_urn=target.dataset_urn,
            field_path=target.field_path,
            schema_field_urn=field.schema_field_urn,
            classification=IdentityClassification.CERTIFIED_CURRENT,
        ),
        counterfactual_candidate=FieldMachineIdentity(
            dataset_urn=target.dataset_urn,
            field_path=requested.field_path,
            schema_field_urn=None,
            classification=(
                IdentityClassification.COUNTERFACTUAL_CANDIDATE
            ),
        ),
        changed_properties=(
            ChangedProperty(
                property_name="field_path",
                before=before.field_path,
                after=requested.field_path,
            ),
            ChangedProperty(
                property_name="field_name",
                before=before.field_name,
                after=requested.field_name,
            ),
        ),
        unchanged_properties=tuple(unchanged),
        unknown_consequences=tuple(
            UnknownConsequence(
                consequence=item,
                status=ConsequenceStatus.UNKNOWN,
                evaluation=EvaluationStatus.NOT_EVALUATED,
            )
            for item in _UNKNOWN_CONSEQUENCES
        ),
        preconditions=_preconditions(snapshot, proposal, validation),
        semantic_rules=_rules(),
        source_schema_contract=SourceSchemaSemanticContract(
            current_field_count=len(snapshot.source_schema.fields),
            counterfactual_candidate_field_count=(
                len(snapshot.source_schema.fields)
            ),
            current_field_path=target.field_path,
            counterfactual_candidate_field_path=requested.field_path,
            unchanged_field_paths=other_fields,
            transformed_schema_materialized=False,
        ),
        created_at=_timestamp(clock),
    )


def build_contract_from_artifacts(
    snapshot_path: str | Path,
    proposal_path: str | Path,
    validation_path: str | Path,
    *,
    clock: Clock | None = None,
) -> ChangeSemanticContract:
    snapshot = load_snapshot(snapshot_path)
    proposal = load_proposal(proposal_path)
    validation = load_validation_result(validation_path)
    return build_change_semantic_contract(
        snapshot,
        proposal,
        validation,
        clock=clock,
    )


def _require_inputs(
    snapshot: object,
    proposal: object,
    validation: object,
) -> None:
    if not isinstance(snapshot, CurrentMetadataSnapshot):
        raise SemanticContractPreconditionError(
            "A CurrentMetadataSnapshot is required."
        )
    if snapshot.validation_result.state is not SnapshotValidationState.VALID:
        raise SemanticContractPreconditionError(
            "The Phase 1 snapshot must be certified valid."
        )
    if not isinstance(proposal, ChangeProposal):
        raise SemanticContractPreconditionError(
            "A structurally valid ChangeProposal is required."
        )
    try:
        validate_change_proposal(proposal)
    except ValueError as exc:
        raise SemanticContractPreconditionError(
            "The Phase 2.1 proposal is structurally invalid."
        ) from exc
    if proposal.change_type is not ChangeType.FIELD_RENAME:
        raise SemanticContractPreconditionError(
            "Phase 2.3 supports FIELD_RENAME only."
        )
    if not isinstance(validation, ProposalValidationResult):
        raise SemanticContractPreconditionError(
            "A Phase 2.2 ProposalValidationResult is required."
        )
    if validation.validation_state is not ProposalValidationState.VALID:
        raise SemanticContractPreconditionError(
            "Phase 2.2 proposal validation must be VALID."
        )
    if proposal.snapshot_reference.semantic_fingerprint != (
        snapshot.semantic_fingerprint
    ):
        raise SemanticContractPreconditionError(
            "Proposal baseline fingerprint does not match the snapshot."
        )
    if validation.snapshot_fingerprint != snapshot.semantic_fingerprint:
        raise SemanticContractPreconditionError(
            "Validation snapshot fingerprint does not match the snapshot."
        )
    if validation.proposal_fingerprint != proposal.semantic_fingerprint:
        raise SemanticContractPreconditionError(
            "Validation proposal fingerprint does not match the proposal."
        )
    if validation.proposal_id != proposal.proposal_id:
        raise SemanticContractPreconditionError(
            "Validation proposal ID does not match the proposal."
        )
    required_validation_preconditions = {
        "baseline_fingerprint",
        "demonstration_identity",
        "target_dataset",
        "target_field",
        "before_state",
        "source_schema_collision",
        "rename_admissibility",
        "additional_requested_mutation",
    }
    observed = {
        item.name: item.status for item in validation.preconditions
    }
    if any(
        observed.get(name) is not ValidationPreconditionStatus.PASS
        for name in required_validation_preconditions
    ):
        raise SemanticContractPreconditionError(
            "Required Phase 2.2 preconditions are not satisfied."
        )


def _preconditions(
    snapshot: CurrentMetadataSnapshot,
    proposal: ChangeProposal,
    validation: ProposalValidationResult,
) -> tuple[ContractPrecondition, ...]:
    target = validation.validated_target
    before = validation.validated_before_state
    requested = validation.requested_after_state
    return (
        ContractPrecondition(
            "baseline_snapshot_fingerprint_matches",
            PreconditionStatus.SATISFIED,
            snapshot.semantic_fingerprint,
            proposal.snapshot_reference.semantic_fingerprint,
        ),
        ContractPrecondition(
            "proposal_fingerprint_matches_validation",
            PreconditionStatus.SATISFIED,
            proposal.semantic_fingerprint,
            validation.proposal_fingerprint or "",
        ),
        ContractPrecondition(
            "validation_state",
            PreconditionStatus.SATISFIED,
            "valid",
            validation.validation_state.value,
        ),
        ContractPrecondition(
            "target_dataset_exists",
            PreconditionStatus.SATISFIED,
            "1",
            str(target.dataset_occurrences if target else 0),
        ),
        ContractPrecondition(
            "target_field_exists",
            PreconditionStatus.SATISFIED,
            "1",
            str(target.field_occurrences if target else 0),
        ),
        ContractPrecondition(
            "before_state_matches",
            PreconditionStatus.SATISFIED,
            "true",
            str(bool(before and before.matches)).lower(),
        ),
        ContractPrecondition(
            "requested_field_collision_count",
            PreconditionStatus.SATISFIED,
            "0",
            str(requested.source_schema_occurrences if requested else -1),
        ),
        ContractPrecondition(
            "proposal_type",
            PreconditionStatus.SATISFIED,
            "field_rename",
            proposal.change_type.value,
        ),
    )


def _rules() -> tuple[SemanticRule, ...]:
    return (
        SemanticRule(
            SemanticRuleCode.CREATE_COUNTERFACTUAL_REPRESENTATION,
            RuleDisposition.REQUIRED,
            "Application must create a new counterfactual representation.",
        ),
        SemanticRule(
            SemanticRuleCode.RENAME_TARGET_SOURCE_IDENTITY,
            RuleDisposition.ALLOWED,
            "Only the target source field path and name may be renamed.",
        ),
        SemanticRule(
            SemanticRuleCode.PRESERVE_UNCHANGED_SOURCE_PROPERTIES,
            RuleDisposition.REQUIRED,
            "All unchanged-by-proposal source properties must be preserved.",
        ),
        SemanticRule(
            SemanticRuleCode.PRESERVE_CURRENT_SNAPSHOT,
            RuleDisposition.REQUIRED,
            "The certified CurrentMetadataSnapshot must remain unchanged.",
        ),
        SemanticRule(
            SemanticRuleCode.MUTATE_CURRENT_SNAPSHOT,
            RuleDisposition.FORBIDDEN,
            "The certified CurrentMetadataSnapshot cannot be mutated.",
        ),
        SemanticRule(
            SemanticRuleCode.CHANGE_UNRELATED_FIELDS,
            RuleDisposition.FORBIDDEN,
            "Unrelated source fields cannot be changed.",
        ),
        SemanticRule(
            SemanticRuleCode.CHANGE_DATASET_IDENTITY,
            RuleDisposition.FORBIDDEN,
            "The target Dataset identity cannot be changed.",
        ),
        SemanticRule(
            SemanticRuleCode.CHANGE_SOURCE_TYPES,
            RuleDisposition.FORBIDDEN,
            "Native and normalized source types cannot be changed.",
        ),
        SemanticRule(
            SemanticRuleCode.DELETE_CURRENT_EVIDENCE,
            RuleDisposition.FORBIDDEN,
            "Certified current-state evidence cannot be deleted.",
        ),
        SemanticRule(
            SemanticRuleCode.AUTOMATIC_DOWNSTREAM_RENAME,
            RuleDisposition.FORBIDDEN,
            "The source rename cannot automatically rename downstream fields.",
        ),
        SemanticRule(
            SemanticRuleCode.INFER_DOWNSTREAM_COMPATIBILITY,
            RuleDisposition.FORBIDDEN,
            "Downstream compatibility cannot be inferred in Phase 2.3.",
        ),
        SemanticRule(
            SemanticRuleCode.WRITE_DATAHUB,
            RuleDisposition.FORBIDDEN,
            "The semantic contract cannot write to DataHub.",
        ),
        SemanticRule(
            SemanticRuleCode.PRESERVE_EVIDENCE_PROVENANCE,
            RuleDisposition.REQUIRED,
            "Certified current evidence must retain current-state provenance.",
        ),
        SemanticRule(
            (
                SemanticRuleCode
                .REINTERPRET_CURRENT_EVIDENCE_AS_COUNTERFACTUAL
            ),
            RuleDisposition.FORBIDDEN,
            "Current-state evidence cannot be treated as counterfactual evidence.",
        ),
    )


def _timestamp(clock: Clock | None) -> str:
    value = (clock or (lambda: datetime.now(timezone.utc)))()
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()
