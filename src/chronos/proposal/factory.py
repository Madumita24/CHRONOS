"""Canonical and caller-supplied Phase 2.1 proposal construction."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from chronos.snapshot import load_snapshot

from .models import (
    ChangeProposal,
    ChangeType,
    ClaimedFieldState,
    FieldRenameChange,
    ProposalLifecycleState,
    ProposalProvenance,
    ProposalSnapshotReference,
    ProposalSource,
    RequestedFieldState,
    SchemaFieldTarget,
)


Clock = Callable[[], datetime]
CANONICAL_PROPOSAL_ID = "CHRONOS-DEMO-001-PROPOSAL-001"
CANONICAL_DEMONSTRATION_ID = "CHRONOS-DEMO-001"
CANONICAL_DATASET_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:postgres,"
    "b2fd91.order_entry_db.order_entry.orders,PROD)"
)


def create_field_rename_proposal(
    *,
    proposal_id: str,
    demonstration_id: str,
    target: SchemaFieldTarget,
    before: ClaimedFieldState,
    requested_after: RequestedFieldState,
    snapshot_reference: ProposalSnapshotReference,
    provenance: ProposalProvenance,
    description: str | None = None,
    rationale: str | None = None,
    clock: Clock | None = None,
) -> ChangeProposal:
    now = (clock or (lambda: datetime.now(timezone.utc)))()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return ChangeProposal(
        proposal_id=proposal_id,
        demonstration_id=demonstration_id,
        change_type=ChangeType.FIELD_RENAME,
        change=FieldRenameChange(
            target=target,
            before=before,
            requested_after=requested_after,
        ),
        snapshot_reference=snapshot_reference,
        lifecycle_state=ProposalLifecycleState.STRUCTURALLY_VALID,
        created_at=now.astimezone(timezone.utc).isoformat(),
        provenance=provenance,
        description=description,
        rationale=rationale,
    )


def create_canonical_proposal(
    snapshot_path: str | Path,
    *,
    clock: Clock | None = None,
) -> ChangeProposal:
    """Load only certified snapshot identity metadata; do no proposal check."""

    snapshot = load_snapshot(snapshot_path)
    reference = ProposalSnapshotReference(
        semantic_fingerprint=snapshot.semantic_fingerprint,
        snapshot_id=snapshot.metadata.snapshot_id,
        snapshot_schema_version=snapshot.metadata.snapshot_schema_version,
    )
    return create_field_rename_proposal(
        proposal_id=CANONICAL_PROPOSAL_ID,
        demonstration_id=CANONICAL_DEMONSTRATION_ID,
        target=SchemaFieldTarget(
            dataset_urn=CANONICAL_DATASET_URN,
            field_path="order_total",
            display_identity=(
                "PostgreSQL / order_entry_db / order_entry / orders / "
                "order_total"
            ),
            platform="postgres",
            environment="PROD",
        ),
        before=ClaimedFieldState(
            field_path="order_total",
            field_name="order_total",
            native_type="DOUBLE PRECISION",
            normalized_type="Number",
        ),
        requested_after=RequestedFieldState(
            field_path="order_amount",
            field_name="order_amount",
        ),
        snapshot_reference=reference,
        provenance=ProposalProvenance(
            source=ProposalSource.CANONICAL_DEMO,
            created_by="CHRONOS",
            source_reference=CANONICAL_DEMONSTRATION_ID,
        ),
        description="Rename the canonical orders total field.",
        rationale="Frozen CHRONOS demonstration proposal.",
        clock=clock,
    )
