"""Pure in-memory validation of a proposal against a certified snapshot."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from chronos.proposal import (
    CANONICAL_DATASET_URN,
    CANONICAL_DEMONSTRATION_ID,
    ChangeProposal,
    ChangeType,
    FieldRenameChange,
    validate_change_proposal,
)
from chronos.snapshot import (
    CurrentMetadataSnapshot,
    FieldMachineKey,
    SnapshotValidationState,
)

from .models import (
    PreconditionResult,
    PreconditionStatus,
    ProposalValidationFinding,
    ProposalValidationResult,
    ProposalValidationState,
    ValidatedBeforeState,
    ValidatedRequestedAfterState,
    ValidatedTarget,
    ValidationFindingCode,
    ValidationFindingSeverity,
)


Clock = Callable[[], datetime]


def validate_proposal(
    snapshot: object,
    proposal: object,
    *,
    clock: Clock | None = None,
) -> ProposalValidationResult:
    """Validate only certified current-state preconditions; perform no I/O."""

    validated_at = _timestamp(clock)
    if not isinstance(snapshot, CurrentMetadataSnapshot):
        return _unavailable(
            proposal,
            snapshot,
            validated_at,
            ValidationFindingCode.SNAPSHOT_VALIDATION_FAILURE,
            "A CurrentMetadataSnapshot is required.",
        )
    if snapshot.validation_result.state is not SnapshotValidationState.VALID:
        return _unavailable(
            proposal,
            snapshot,
            validated_at,
            ValidationFindingCode.SNAPSHOT_VALIDATION_FAILURE,
            "The snapshot is not certified valid.",
        )
    if not isinstance(proposal, ChangeProposal):
        return _unavailable(
            proposal,
            snapshot,
            validated_at,
            ValidationFindingCode.MALFORMED_PROPOSAL,
            "A structurally valid ChangeProposal is required.",
        )
    if (
        proposal.change_type is not ChangeType.FIELD_RENAME
        or not isinstance(proposal.change, FieldRenameChange)
    ):
        return _unavailable(
            proposal,
            snapshot,
            validated_at,
            ValidationFindingCode.UNSUPPORTED_PROPOSAL_TYPE,
            "Phase 2.2 supports FIELD_RENAME proposals only.",
        )
    try:
        validate_change_proposal(proposal)
    except ValueError as exc:
        return _unavailable(
            proposal,
            snapshot,
            validated_at,
            ValidationFindingCode.MALFORMED_PROPOSAL,
            f"Proposal structural validation failed: {exc}",
        )

    findings: list[ProposalValidationFinding] = []
    preconditions: list[PreconditionResult] = []

    baseline_matches = (
        proposal.snapshot_reference.semantic_fingerprint
        == snapshot.semantic_fingerprint
    )
    _precondition(
        preconditions,
        "baseline_fingerprint",
        baseline_matches,
        proposal.snapshot_reference.semantic_fingerprint,
        "MATCH" if baseline_matches else "MISMATCH",
    )
    if not baseline_matches:
        _finding(
            findings,
            ValidationFindingCode.SNAPSHOT_FINGERPRINT_MISMATCH,
            "Proposal baseline does not match the certified snapshot.",
            expected=snapshot.semantic_fingerprint,
            observed=proposal.snapshot_reference.semantic_fingerprint,
        )

    demonstration_matches = (
        proposal.demonstration_id == CANONICAL_DEMONSTRATION_ID
        and snapshot.metadata.demonstration_id
        == CANONICAL_DEMONSTRATION_ID
        and proposal.demonstration_id
        == snapshot.metadata.demonstration_id
    )
    _precondition(
        preconditions,
        "demonstration_identity",
        demonstration_matches,
        CANONICAL_DEMONSTRATION_ID,
        "MATCH" if demonstration_matches else "MISMATCH",
    )
    if not demonstration_matches:
        _finding(
            findings,
            ValidationFindingCode.DEMONSTRATION_MISMATCH,
            "Proposal and snapshot must belong to CHRONOS-DEMO-001.",
            expected=CANONICAL_DEMONSTRATION_ID,
            observed=(
                f"proposal={proposal.demonstration_id};"
                f"snapshot={snapshot.metadata.demonstration_id}"
            ),
        )

    target = proposal.change.target
    target_is_canonical = target.dataset_urn == CANONICAL_DATASET_URN
    if not target_is_canonical:
        _finding(
            findings,
            ValidationFindingCode.TARGET_DATASET_MISMATCH,
            "Proposal target is not the frozen demonstration dataset.",
            expected=CANONICAL_DATASET_URN,
            observed=target.dataset_urn,
            affected_key=target.dataset_urn,
        )

    dataset_matches = tuple(
        item
        for item in snapshot.datasets
        if item.dataset_urn == target.dataset_urn
    )
    dataset_found_once = len(dataset_matches) == 1
    _precondition(
        preconditions,
        "target_dataset",
        dataset_found_once and target_is_canonical,
        "exactly 1 canonical dataset",
        "FOUND" if dataset_found_once and target_is_canonical else (
            f"COUNT={len(dataset_matches)}"
        ),
    )
    if not dataset_matches:
        _finding(
            findings,
            ValidationFindingCode.TARGET_DATASET_NOT_FOUND,
            "Target dataset URN was not found in the snapshot registry.",
            expected="1",
            observed="0",
            affected_key=target.dataset_urn,
        )
    elif len(dataset_matches) != 1:
        _finding(
            findings,
            ValidationFindingCode.TARGET_DATASET_DUPLICATE,
            "Target dataset URN is duplicated in the snapshot registry.",
            expected="1",
            observed=str(len(dataset_matches)),
            affected_key=target.dataset_urn,
        )

    target_key = FieldMachineKey(target.dataset_urn, target.field_path)
    field_matches = tuple(
        item for item in snapshot.fields if item.key == target_key
    )
    field_found_once = len(field_matches) == 1
    parent_matches = (
        field_matches[0].key.dataset_urn == target.dataset_urn
        if field_found_once
        else None
    )
    _precondition(
        preconditions,
        "target_field",
        field_found_once and parent_matches is True,
        "exactly 1 field with the target machine key",
        "FOUND" if field_found_once and parent_matches else (
            f"COUNT={len(field_matches)}"
        ),
    )
    if not field_matches:
        _finding(
            findings,
            ValidationFindingCode.TARGET_FIELD_NOT_FOUND,
            "Target field machine key was not found in the snapshot.",
            expected="1",
            observed="0",
            affected_key=target_key.text,
        )
    elif len(field_matches) != 1:
        _finding(
            findings,
            ValidationFindingCode.TARGET_FIELD_DUPLICATE,
            "Target field machine key is duplicated in the snapshot.",
            expected="1",
            observed=str(len(field_matches)),
            affected_key=target_key.text,
        )
    elif not parent_matches:
        _finding(
            findings,
            ValidationFindingCode.TARGET_FIELD_PARENT_MISMATCH,
            "Target field does not belong to the target dataset.",
            expected=target.dataset_urn,
            observed=field_matches[0].key.dataset_urn,
            affected_key=target_key.text,
        )

    current_field = field_matches[0] if field_found_once else None
    before = proposal.change.before
    before_matches = (
        current_field is not None
        and before.field_path == current_field.key.field_path
        and before.field_name == current_field.field_name
        and before.native_type == current_field.native_type
        and before.normalized_type == current_field.normalized_type
    )
    _precondition(
        preconditions,
        "before_state",
        before_matches,
        (
            f"{before.field_path}|{before.field_name}|"
            f"{before.native_type}|{before.normalized_type}"
        ),
        "MATCH" if before_matches else "MISMATCH",
    )
    if current_field is not None:
        comparisons = (
            ("field_path", before.field_path, current_field.key.field_path),
            ("field_name", before.field_name, current_field.field_name),
            ("native_type", before.native_type, current_field.native_type),
            (
                "normalized_type",
                before.normalized_type,
                current_field.normalized_type,
            ),
        )
        for attribute, claimed, observed in comparisons:
            if claimed != observed:
                _finding(
                    findings,
                    ValidationFindingCode.BEFORE_STATE_MISMATCH,
                    f"Claimed before-state {attribute} does not match.",
                    expected=str(observed),
                    observed=str(claimed),
                    affected_key=target_key.text,
                )

    requested = proposal.change.requested_after
    source_schema_is_target = (
        snapshot.source_schema.dataset_urn == target.dataset_urn
    )
    collision_count = (
        sum(
            1
            for item in snapshot.source_schema.fields
            if item.field_path == requested.field_path
        )
        if source_schema_is_target
        else 0
    )
    collision_free = source_schema_is_target and collision_count == 0
    _precondition(
        preconditions,
        "source_schema_collision",
        collision_free,
        "0 exact requested field-path matches",
        "NONE" if collision_free else (
            f"COUNT={collision_count}"
            if source_schema_is_target
            else "TARGET SCHEMA UNAVAILABLE"
        ),
    )
    if collision_count:
        _finding(
            findings,
            ValidationFindingCode.FIELD_NAME_COLLISION,
            "Requested field path already exists in the target source schema.",
            expected="0",
            observed=str(collision_count),
            affected_key=f"{target.dataset_urn}|{requested.field_path}",
        )

    genuine_rename = (
        proposal.change_type is ChangeType.FIELD_RENAME
        and current_field is not None
        and requested.field_path != before.field_path
        and requested.field_name != before.field_name
        and source_schema_is_target
        and collision_count == 0
    )
    _precondition(
        preconditions,
        "rename_admissibility",
        genuine_rename,
        "existing old field and distinct collision-free new field",
        "ADMISSIBLE" if genuine_rename else "NOT ADMISSIBLE",
    )
    if not genuine_rename:
        _finding(
            findings,
            ValidationFindingCode.RENAME_NOT_ADMISSIBLE,
            "The FIELD_RENAME structural preconditions are not satisfied.",
            expected="admissible",
            observed="not admissible",
            affected_key=target_key.text,
        )

    preconditions.append(
        PreconditionResult(
            name="additional_requested_mutation",
            status=PreconditionStatus.PASS,
            expected="none",
            observed="NONE",
        )
    )
    findings.append(
        ProposalValidationFinding(
            code=ValidationFindingCode.NO_ADDITIONAL_REQUESTED_MUTATION,
            severity=ValidationFindingSeverity.INFO,
            message=(
                "Requested-after state contains only field path and field name."
            ),
            expected="none",
            observed="none",
            affected_key=target_key.text,
        )
    )

    has_error = any(
        item.severity is ValidationFindingSeverity.ERROR for item in findings
    )
    state = (
        ProposalValidationState.STALE_BASELINE
        if not baseline_matches
        else (
            ProposalValidationState.INVALID
            if has_error
            else ProposalValidationState.VALID
        )
    )
    return ProposalValidationResult(
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.semantic_fingerprint,
        snapshot_id=snapshot.metadata.snapshot_id,
        snapshot_fingerprint=snapshot.semantic_fingerprint,
        validation_state=state,
        validated_target=ValidatedTarget(
            dataset_urn=target.dataset_urn,
            field_path=target.field_path,
            dataset_occurrences=len(dataset_matches),
            field_occurrences=len(field_matches),
            field_parent_matches=parent_matches,
        ),
        validated_before_state=ValidatedBeforeState(
            claimed_field_path=before.field_path,
            observed_field_path=(
                current_field.key.field_path if current_field else None
            ),
            claimed_field_name=before.field_name,
            observed_field_name=(
                current_field.field_name if current_field else None
            ),
            claimed_native_type=before.native_type,
            observed_native_type=(
                current_field.native_type if current_field else None
            ),
            claimed_normalized_type=before.normalized_type,
            observed_normalized_type=(
                current_field.normalized_type if current_field else None
            ),
            matches=before_matches,
        ),
        requested_after_state=ValidatedRequestedAfterState(
            field_path=requested.field_path,
            field_name=requested.field_name,
            source_schema_occurrences=collision_count,
            additional_requested_mutation=False,
        ),
        findings=tuple(findings),
        preconditions=tuple(preconditions),
        validated_at=validated_at,
    )


def _timestamp(clock: Clock | None) -> str:
    value = (clock or (lambda: datetime.now(timezone.utc)))()
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _precondition(
    target: list[PreconditionResult],
    name: str,
    passed: bool,
    expected: str,
    observed: str,
) -> None:
    target.append(
        PreconditionResult(
            name=name,
            status=(
                PreconditionStatus.PASS
                if passed
                else PreconditionStatus.FAIL
            ),
            expected=expected,
            observed=observed,
        )
    )


def _finding(
    target: list[ProposalValidationFinding],
    code: ValidationFindingCode,
    message: str,
    *,
    expected: str | None = None,
    observed: str | None = None,
    affected_key: str | None = None,
) -> None:
    target.append(
        ProposalValidationFinding(
            code=code,
            severity=ValidationFindingSeverity.ERROR,
            message=message,
            expected=expected,
            observed=observed,
            affected_key=affected_key,
        )
    )


def _unavailable(
    proposal: object,
    snapshot: object,
    validated_at: str,
    code: ValidationFindingCode,
    message: str,
) -> ProposalValidationResult:
    return ProposalValidationResult(
        proposal_id=getattr(proposal, "proposal_id", None),
        proposal_fingerprint=getattr(
            proposal,
            "semantic_fingerprint",
            None,
        ),
        snapshot_id=getattr(
            getattr(snapshot, "metadata", None),
            "snapshot_id",
            None,
        ),
        snapshot_fingerprint=getattr(
            snapshot,
            "semantic_fingerprint",
            None,
        ),
        validation_state=ProposalValidationState.UNAVAILABLE,
        validated_target=None,
        validated_before_state=None,
        requested_after_state=None,
        findings=(
            ProposalValidationFinding(
                code=code,
                severity=ValidationFindingSeverity.ERROR,
                message=message,
            ),
        ),
        preconditions=(),
        validated_at=validated_at,
    )
