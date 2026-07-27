from __future__ import annotations

import hashlib
import tempfile
import unittest
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
from pathlib import Path

from chronos.proposal import (
    CANONICAL_DATASET_URN,
    CANONICAL_DEMONSTRATION_ID,
    CANONICAL_PROPOSAL_ID,
    ChangeProposal,
    ChangeType,
    ClaimedFieldState,
    FieldRenameChange,
    InvalidChangeProposal,
    InvalidChangeTarget,
    InvalidFieldRename,
    InvalidProposalSnapshotReference,
    ProposalInformationClassification,
    ProposalLifecycleState,
    ProposalProvenance,
    ProposalSerializationError,
    ProposalSnapshotReference,
    ProposalSource,
    RequestedFieldState,
    SchemaFieldTarget,
    UnsupportedChangeType,
    create_canonical_proposal,
    create_field_rename_proposal,
    export_proposal,
    load_proposal,
    proposal_semantic_fingerprint,
)
from chronos.snapshot import load_snapshot


ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_PATH = ROOT / "artifacts" / "current_metadata_snapshot.json"


def clock(hour: int):
    return lambda: datetime(2026, 7, 27, hour, tzinfo=timezone.utc)


class ChangeProposalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.snapshot_hash_before = hashlib.sha256(
            SNAPSHOT_PATH.read_bytes()
        ).hexdigest()
        cls.snapshot_before = load_snapshot(SNAPSHOT_PATH)
        cls.proposal = create_canonical_proposal(
            SNAPSHOT_PATH,
            clock=clock(1),
        )

    def test_01_canonical_field_rename_constructs(self) -> None:
        self.assertEqual(self.proposal.proposal_id, CANONICAL_PROPOSAL_ID)
        self.assertEqual(
            self.proposal.demonstration_id,
            CANONICAL_DEMONSTRATION_ID,
        )
        self.assertEqual(self.proposal.change_type, ChangeType.FIELD_RENAME)
        self.assertEqual(
            self.proposal.lifecycle_state,
            ProposalLifecycleState.STRUCTURALLY_VALID,
        )

    def test_02_proposal_is_immutable(self) -> None:
        with self.assertRaises(FrozenInstanceError):
            self.proposal.proposal_id = "changed"
        with self.assertRaises(FrozenInstanceError):
            self.proposal.change.before.field_path = "changed"
        with self.assertRaises(FrozenInstanceError):
            self.proposal.change.requested_after.field_path = "changed"

    def test_03_target_uses_exact_machine_identity(self) -> None:
        target = self.proposal.change.target
        self.assertEqual(target.dataset_urn, CANONICAL_DATASET_URN)
        self.assertEqual(target.field_path, "order_total")
        self.assertEqual(
            target.machine_key,
            (CANONICAL_DATASET_URN, "order_total"),
        )

    def test_04_empty_proposal_id_is_rejected(self) -> None:
        with self.assertRaises(InvalidChangeProposal):
            replace(self.proposal, proposal_id="")

    def test_05_empty_demonstration_id_is_rejected(self) -> None:
        with self.assertRaises(InvalidChangeProposal):
            replace(self.proposal, demonstration_id="")

    def test_06_missing_snapshot_fingerprint_is_rejected(self) -> None:
        with self.assertRaises(InvalidProposalSnapshotReference):
            ProposalSnapshotReference(semantic_fingerprint="")

    def test_07_unsupported_change_type_is_rejected(self) -> None:
        with self.assertRaises(UnsupportedChangeType):
            replace(self.proposal, change_type="field_delete")

    def test_08_empty_target_dataset_urn_is_rejected(self) -> None:
        with self.assertRaises(InvalidChangeTarget):
            SchemaFieldTarget(dataset_urn="", field_path="order_total")

    def test_09_malformed_target_dataset_urn_is_rejected(self) -> None:
        with self.assertRaises(InvalidChangeTarget):
            SchemaFieldTarget(
                dataset_urn="orders",
                field_path="order_total",
            )

    def test_10_empty_target_field_path_is_rejected(self) -> None:
        with self.assertRaises(InvalidChangeTarget):
            SchemaFieldTarget(
                dataset_urn=CANONICAL_DATASET_URN,
                field_path="",
            )

    def test_11_empty_old_field_name_is_rejected(self) -> None:
        with self.assertRaises(InvalidFieldRename):
            ClaimedFieldState(
                field_path="order_total",
                field_name="",
                native_type="DOUBLE PRECISION",
                normalized_type="Number",
            )

    def test_12_empty_new_field_name_is_rejected(self) -> None:
        with self.assertRaises(InvalidFieldRename):
            RequestedFieldState(field_path="order_amount", field_name="")

    def test_13_whitespace_only_new_name_is_rejected(self) -> None:
        with self.assertRaises(InvalidFieldRename):
            RequestedFieldState(field_path="order_amount", field_name=" ")

    def test_14_surrounding_whitespace_is_rejected_not_normalized(self) -> None:
        with self.assertRaises(InvalidChangeTarget):
            SchemaFieldTarget(
                dataset_urn=CANONICAL_DATASET_URN,
                field_path=" order_total ",
            )
        with self.assertRaises(InvalidFieldRename):
            RequestedFieldState(
                field_path="order_amount",
                field_name=" order_amount ",
            )

    def test_15_same_old_and_new_field_path_is_rejected(self) -> None:
        with self.assertRaises(InvalidFieldRename):
            FieldRenameChange(
                target=self.proposal.change.target,
                before=self.proposal.change.before,
                requested_after=RequestedFieldState(
                    field_path="order_total",
                    field_name="order_amount",
                ),
            )

    def test_16_same_old_and_new_field_name_is_rejected(self) -> None:
        with self.assertRaises(InvalidFieldRename):
            FieldRenameChange(
                target=self.proposal.change.target,
                before=self.proposal.change.before,
                requested_after=RequestedFieldState(
                    field_path="order_amount",
                    field_name="order_total",
                ),
            )

    def test_17_before_state_is_preserved_exactly(self) -> None:
        self.assertEqual(
            self.proposal.change.before,
            ClaimedFieldState(
                field_path="order_total",
                field_name="order_total",
                native_type="DOUBLE PRECISION",
                normalized_type="Number",
            ),
        )

    def test_18_requested_after_state_is_preserved_exactly(self) -> None:
        self.assertEqual(
            self.proposal.change.requested_after,
            RequestedFieldState(
                field_path="order_amount",
                field_name="order_amount",
            ),
        )

    def test_19_current_and_requested_states_are_separate_objects(self) -> None:
        self.assertIsNot(
            self.proposal.change.before,
            self.proposal.change.requested_after,
        )
        self.assertEqual(
            self.proposal.change.before.field_path,
            self.proposal.change.target.field_path,
        )
        self.assertNotEqual(
            self.proposal.change.before.field_path,
            self.proposal.change.requested_after.field_path,
        )

    def test_20_serialization_is_deterministic(self) -> None:
        self.assertEqual(self.proposal.to_json(), self.proposal.to_json())
        self.assertEqual(
            self.proposal.semantic_json(),
            self.proposal.semantic_json(),
        )

    def test_21_created_at_does_not_change_semantic_fingerprint(self) -> None:
        later = create_canonical_proposal(SNAPSHOT_PATH, clock=clock(2))
        self.assertNotEqual(self.proposal.created_at, later.created_at)
        self.assertEqual(
            self.proposal.semantic_fingerprint,
            later.semantic_fingerprint,
        )

    def test_22_different_new_name_changes_fingerprint(self) -> None:
        changed = self._proposal(
            requested_after=RequestedFieldState(
                field_path="total_amount",
                field_name="total_amount",
            )
        )
        self.assertNotEqual(
            self.proposal.semantic_fingerprint,
            changed.semantic_fingerprint,
        )

    def test_23_different_target_changes_fingerprint(self) -> None:
        target_urn = (
            "urn:li:dataset:(urn:li:dataPlatform:postgres,"
            "b2fd91.other.orders,PROD)"
        )
        changed = self._proposal(
            target=SchemaFieldTarget(
                dataset_urn=target_urn,
                field_path="order_total",
            )
        )
        self.assertNotEqual(
            self.proposal.semantic_fingerprint,
            changed.semantic_fingerprint,
        )

    def test_24_different_baseline_changes_fingerprint(self) -> None:
        changed = self._proposal(
            snapshot_reference=ProposalSnapshotReference(
                semantic_fingerprint="sha256:" + ("0" * 64),
            )
        )
        self.assertNotEqual(
            self.proposal.semantic_fingerprint,
            changed.semantic_fingerprint,
        )

    def test_25_human_readable_summary_is_deterministic(self) -> None:
        expected = "\n".join(
            (
                "Proposal: CHRONOS-DEMO-001-PROPOSAL-001",
                "Operation: FIELD_RENAME",
                (
                    "Target: PostgreSQL / order_entry_db / order_entry / "
                    "orders / order_total"
                ),
                "Requested change: order_total -> order_amount",
                (
                    "Baseline: "
                    "sha256:774185f19c6fea113ef7adfc5e14583e05e7e08a1fad0c59bd6c6fad755db72c"
                ),
                "State: STRUCTURALLY_VALID",
            )
        )
        self.assertEqual(self.proposal.summary(), expected)
        self.assertEqual(self.proposal.summary(), self.proposal.summary())

    def test_26_no_impact_or_future_graph_terminology_is_generated(self) -> None:
        generated = (
            self.proposal.to_json() + "\n" + self.proposal.summary()
        ).casefold()
        for term in (
            "impact",
            "broken",
            "severity",
            "repair",
            "future_graph",
            "future graph",
        ):
            self.assertNotIn(term, generated)

    def test_27_no_datahub_client_is_required(self) -> None:
        self.assertFalse(hasattr(self.proposal, "_transport"))
        self.assertFalse(hasattr(self.proposal, "_client"))
        self.assertEqual(
            self.proposal.snapshot_reference.semantic_fingerprint,
            self.snapshot_before.semantic_fingerprint,
        )

    def test_28_no_datahub_write_path_is_exposed(self) -> None:
        write_names = {
            "create",
            "update",
            "delete",
            "patch",
            "upsert",
            "emit",
            "rollback",
            "mutation",
        }
        public = {
            name
            for name in dir(self.proposal)
            if not name.startswith("_")
        }
        self.assertTrue(public.isdisjoint(write_names))

    def test_29_snapshot_unchanged_after_proposal_export(self) -> None:
        before_fingerprint = self.snapshot_before.semantic_fingerprint
        before_hash = self.snapshot_hash_before
        with tempfile.TemporaryDirectory() as directory:
            exported = export_proposal(
                self.proposal,
                Path(directory) / "change_proposal.json",
            )
            reloaded = load_proposal(exported)
        snapshot_after = load_snapshot(SNAPSHOT_PATH)
        after_hash = hashlib.sha256(SNAPSHOT_PATH.read_bytes()).hexdigest()
        self.assertEqual(before_fingerprint, snapshot_after.semantic_fingerprint)
        self.assertEqual(before_hash, after_hash)
        self.assertTrue(self.proposal.semantically_equals(reloaded))

    def test_30_round_trip_preserves_semantics(self) -> None:
        reloaded = ChangeProposal.from_json(self.proposal.to_json())
        self.assertTrue(self.proposal.semantically_equals(reloaded))
        self.assertEqual(self.proposal, reloaded)

    def test_31_tampered_fingerprint_is_rejected(self) -> None:
        tampered = self.proposal.to_json().replace(
            self.proposal.semantic_fingerprint,
            "sha256:" + ("f" * 64),
        )
        with self.assertRaises(ProposalSerializationError):
            ChangeProposal.from_json(tampered)

    def test_32_draft_proposal_cannot_be_exported(self) -> None:
        draft = replace(
            self.proposal,
            lifecycle_state=ProposalLifecycleState.DRAFT,
        )
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ProposalSerializationError):
                export_proposal(
                    draft,
                    Path(directory) / "draft.json",
                )

    def test_33_provenance_is_proposed_not_verified(self) -> None:
        self.assertEqual(
            self.proposal.provenance.classification,
            ProposalInformationClassification.PROPOSED,
        )
        self.assertEqual(
            self.proposal.provenance.source,
            ProposalSource.CANONICAL_DEMO,
        )

    def test_34_fingerprint_function_matches_recorded_value(self) -> None:
        self.assertEqual(
            proposal_semantic_fingerprint(self.proposal),
            self.proposal.semantic_fingerprint,
        )

    def test_35_unsupported_proposal_schema_version_is_rejected(self) -> None:
        with self.assertRaises(InvalidChangeProposal):
            replace(self.proposal, proposal_schema_version="2.0")

    def _proposal(
        self,
        *,
        target: SchemaFieldTarget | None = None,
        requested_after: RequestedFieldState | None = None,
        snapshot_reference: ProposalSnapshotReference | None = None,
    ) -> ChangeProposal:
        selected_target = target or self.proposal.change.target
        return create_field_rename_proposal(
            proposal_id=self.proposal.proposal_id,
            demonstration_id=self.proposal.demonstration_id,
            target=selected_target,
            before=self.proposal.change.before,
            requested_after=(
                requested_after or self.proposal.change.requested_after
            ),
            snapshot_reference=(
                snapshot_reference or self.proposal.snapshot_reference
            ),
            provenance=self.proposal.provenance,
            description=self.proposal.description,
            rationale=self.proposal.rationale,
            clock=clock(1),
        )


if __name__ == "__main__":
    unittest.main()
