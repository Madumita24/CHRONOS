from __future__ import annotations

import copy
import hashlib
import inspect
import tempfile
import unittest
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
from pathlib import Path

from chronos.proposal import (
    CANONICAL_DATASET_URN,
    ChangeProposal,
    ChangeType,
    ClaimedFieldState,
    FieldRenameChange,
    InvalidFieldRename,
    ProposalSnapshotReference,
    RequestedFieldState,
    load_proposal,
)
from chronos.proposal_validation import (
    PreconditionStatus,
    ProposalValidationResult,
    ProposalValidationSerializationError,
    ProposalValidationState,
    ValidationFindingCode,
    export_validation_result,
    load_validation_result,
    validate_proposal,
)
from chronos.snapshot import (
    FieldMachineKey,
    SnapshotValidationState,
    load_snapshot,
)


ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_PATH = ROOT / "artifacts" / "current_metadata_snapshot.json"
PROPOSAL_PATH = ROOT / "artifacts" / "change_proposal.json"


def clock(hour: int):
    return lambda: datetime(2026, 7, 27, hour, tzinfo=timezone.utc)


class ProposalValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.snapshot_hash = hashlib.sha256(SNAPSHOT_PATH.read_bytes()).hexdigest()
        cls.proposal_hash = hashlib.sha256(PROPOSAL_PATH.read_bytes()).hexdigest()
        cls.snapshot = load_snapshot(SNAPSHOT_PATH)
        cls.proposal = load_proposal(PROPOSAL_PATH)

    def setUp(self) -> None:
        self.result = validate_proposal(
            self.snapshot,
            self.proposal,
            clock=clock(4),
        )

    def test_01_canonical_proposal_validates(self) -> None:
        self.assertEqual(
            self.result.validation_state,
            ProposalValidationState.VALID,
        )
        self.assertEqual(
            self.result.proposal_id,
            "CHRONOS-DEMO-001-PROPOSAL-001",
        )

    def test_02_snapshot_fingerprint_matches_baseline(self) -> None:
        self.assertEqual(
            self.proposal.snapshot_reference.semantic_fingerprint,
            self.snapshot.semantic_fingerprint,
        )
        self.assertPrecondition("baseline_fingerprint", "MATCH")

    def test_03_wrong_snapshot_fingerprint_is_stale(self) -> None:
        proposal = replace(
            self.proposal,
            snapshot_reference=ProposalSnapshotReference(
                semantic_fingerprint="sha256:" + ("0" * 64),
                snapshot_id=self.snapshot.metadata.snapshot_id,
                snapshot_schema_version=(
                    self.snapshot.metadata.snapshot_schema_version
                ),
            ),
        )
        result = validate_proposal(self.snapshot, proposal, clock=clock(4))
        self.assertEqual(
            result.validation_state,
            ProposalValidationState.STALE_BASELINE,
        )
        self.assertFinding(
            result,
            ValidationFindingCode.SNAPSHOT_FINGERPRINT_MISMATCH,
        )

    def test_04_wrong_demonstration_id_is_invalid(self) -> None:
        proposal = replace(self.proposal, demonstration_id="OTHER-DEMO")
        result = validate_proposal(self.snapshot, proposal, clock=clock(4))
        self.assertEqual(result.validation_state, ProposalValidationState.INVALID)
        self.assertFinding(result, ValidationFindingCode.DEMONSTRATION_MISMATCH)

    def test_05_missing_target_dataset_fails_closed(self) -> None:
        snapshot = replace(
            self.snapshot,
            datasets=tuple(
                item
                for item in self.snapshot.datasets
                if item.dataset_urn != CANONICAL_DATASET_URN
            ),
        )
        result = validate_proposal(snapshot, self.proposal, clock=clock(4))
        self.assertFinding(
            result,
            ValidationFindingCode.TARGET_DATASET_NOT_FOUND,
        )
        self.assertEqual(result.validation_state, ProposalValidationState.INVALID)

    def test_06_duplicate_target_dataset_fails_closed(self) -> None:
        source = next(
            item
            for item in self.snapshot.datasets
            if item.dataset_urn == CANONICAL_DATASET_URN
        )
        snapshot = replace(
            self.snapshot,
            datasets=self.snapshot.datasets + (source,),
        )
        result = validate_proposal(snapshot, self.proposal, clock=clock(4))
        self.assertFinding(
            result,
            ValidationFindingCode.TARGET_DATASET_DUPLICATE,
        )

    def test_07_missing_target_field_is_invalid(self) -> None:
        key = FieldMachineKey(CANONICAL_DATASET_URN, "order_total")
        snapshot = replace(
            self.snapshot,
            fields=tuple(
                item for item in self.snapshot.fields if item.key != key
            ),
        )
        result = validate_proposal(snapshot, self.proposal, clock=clock(4))
        self.assertFinding(result, ValidationFindingCode.TARGET_FIELD_NOT_FOUND)
        self.assertEqual(result.validation_state, ProposalValidationState.INVALID)

    def test_08_duplicate_target_field_fails_closed(self) -> None:
        key = FieldMachineKey(CANONICAL_DATASET_URN, "order_total")
        source = next(item for item in self.snapshot.fields if item.key == key)
        snapshot = replace(
            self.snapshot,
            fields=self.snapshot.fields + (source,),
        )
        result = validate_proposal(snapshot, self.proposal, clock=clock(4))
        self.assertFinding(result, ValidationFindingCode.TARGET_FIELD_DUPLICATE)

    def test_09_field_on_another_dataset_is_not_a_target_match(self) -> None:
        key = FieldMachineKey(CANONICAL_DATASET_URN, "order_total")
        source = next(item for item in self.snapshot.fields if item.key == key)
        wrong = replace(
            source,
            key=FieldMachineKey(
                "urn:li:dataset:(urn:li:dataPlatform:test,wrong.orders,PROD)",
                "order_total",
            ),
        )
        snapshot = replace(
            self.snapshot,
            fields=tuple(
                item for item in self.snapshot.fields if item.key != key
            )
            + (wrong,),
        )
        result = validate_proposal(snapshot, self.proposal, clock=clock(4))
        self.assertFinding(result, ValidationFindingCode.TARGET_FIELD_NOT_FOUND)

    def test_10_before_field_path_mismatch_is_invalid(self) -> None:
        proposal = copy.deepcopy(self.proposal)
        object.__setattr__(
            proposal.change.before,
            "field_path",
            "wrong_name",
        )
        result = validate_proposal(self.snapshot, proposal, clock=clock(4))
        self.assertBeforeMismatch(result)

    def test_11_before_field_name_mismatch_is_invalid(self) -> None:
        proposal = self.proposal_with_before(field_name="wrong_name")
        result = validate_proposal(self.snapshot, proposal, clock=clock(4))
        self.assertBeforeMismatch(result)

    def test_12_native_type_mismatch_is_invalid(self) -> None:
        proposal = self.proposal_with_before(native_type="BIGINT")
        result = validate_proposal(self.snapshot, proposal, clock=clock(4))
        self.assertBeforeMismatch(result)
        finding = next(
            item
            for item in result.findings
            if item.code is ValidationFindingCode.BEFORE_STATE_MISMATCH
        )
        self.assertEqual(finding.expected, "DOUBLE PRECISION")
        self.assertEqual(finding.observed, "BIGINT")

    def test_13_normalized_type_mismatch_is_invalid(self) -> None:
        proposal = self.proposal_with_before(normalized_type="String")
        result = validate_proposal(self.snapshot, proposal, clock=clock(4))
        self.assertBeforeMismatch(result)

    def test_14_existing_source_field_name_collides(self) -> None:
        proposal = self.proposal_with_requested("customer_id")
        result = validate_proposal(self.snapshot, proposal, clock=clock(4))
        self.assertEqual(result.validation_state, ProposalValidationState.INVALID)
        self.assertFinding(result, ValidationFindingCode.FIELD_NAME_COLLISION)

    def test_15_same_new_and_old_field_is_rejected_by_phase_2_1(self) -> None:
        with self.assertRaises(InvalidFieldRename):
            replace(
                self.proposal.change,
                requested_after=RequestedFieldState(
                    field_path="order_total",
                    field_name="order_total",
                ),
            )

    def test_16_valid_noncolliding_name_is_admissible(self) -> None:
        proposal = self.proposal_with_requested("total_amount")
        result = validate_proposal(self.snapshot, proposal, clock=clock(4))
        self.assertEqual(result.validation_state, ProposalValidationState.VALID)
        precondition = self.precondition(result, "rename_admissibility")
        self.assertEqual(precondition.status, PreconditionStatus.PASS)

    def test_17_collision_is_exact_and_case_sensitive(self) -> None:
        proposal = self.proposal_with_requested("CUSTOMER_ID")
        result = validate_proposal(self.snapshot, proposal, clock=clock(4))
        self.assertEqual(result.validation_state, ProposalValidationState.VALID)

    def test_18_unsupported_proposal_type_is_unavailable(self) -> None:
        proposal = copy.deepcopy(self.proposal)
        object.__setattr__(proposal, "change_type", "field_delete")
        result = validate_proposal(self.snapshot, proposal, clock=clock(4))
        self.assertEqual(
            result.validation_state,
            ProposalValidationState.UNAVAILABLE,
        )
        self.assertFinding(
            result,
            ValidationFindingCode.UNSUPPORTED_PROPOSAL_TYPE,
        )

    def test_19_invalid_snapshot_is_unavailable(self) -> None:
        validation = replace(
            self.snapshot.validation_result,
            state=SnapshotValidationState.INVALID,
        )
        snapshot = replace(self.snapshot, validation_result=validation)
        result = validate_proposal(snapshot, self.proposal, clock=clock(4))
        self.assertEqual(
            result.validation_state,
            ProposalValidationState.UNAVAILABLE,
        )
        self.assertFinding(
            result,
            ValidationFindingCode.SNAPSHOT_VALIDATION_FAILURE,
        )

    def test_20_invalid_proposal_is_unavailable(self) -> None:
        result = validate_proposal(self.snapshot, object(), clock=clock(4))
        self.assertEqual(
            result.validation_state,
            ProposalValidationState.UNAVAILABLE,
        )
        self.assertFinding(result, ValidationFindingCode.MALFORMED_PROPOSAL)

    def test_21_result_is_deeply_immutable(self) -> None:
        with self.assertRaises(FrozenInstanceError):
            self.result.validation_state = ProposalValidationState.INVALID
        with self.assertRaises(FrozenInstanceError):
            self.result.validated_target.field_path = "changed"
        with self.assertRaises(FrozenInstanceError):
            self.result.findings[0].message = "changed"

    def test_22_inputs_and_fingerprints_are_unchanged(self) -> None:
        proposal_json = self.proposal.to_json()
        snapshot_json = self.snapshot.to_json()
        proposal_fingerprint = self.proposal.semantic_fingerprint
        snapshot_fingerprint = self.snapshot.semantic_fingerprint
        validate_proposal(self.snapshot, self.proposal, clock=clock(5))
        self.assertEqual(self.proposal.to_json(), proposal_json)
        self.assertEqual(self.snapshot.to_json(), snapshot_json)
        self.assertEqual(
            self.proposal.semantic_fingerprint,
            proposal_fingerprint,
        )
        self.assertEqual(
            self.snapshot.semantic_fingerprint,
            snapshot_fingerprint,
        )

    def test_23_artifact_hashes_are_unchanged(self) -> None:
        validate_proposal(self.snapshot, self.proposal, clock=clock(5))
        self.assertEqual(
            hashlib.sha256(SNAPSHOT_PATH.read_bytes()).hexdigest(),
            self.snapshot_hash,
        )
        self.assertEqual(
            hashlib.sha256(PROPOSAL_PATH.read_bytes()).hexdigest(),
            self.proposal_hash,
        )

    def test_24_semantic_result_is_deterministic(self) -> None:
        later = validate_proposal(
            self.snapshot,
            self.proposal,
            clock=clock(9),
        )
        self.assertNotEqual(self.result.validated_at, later.validated_at)
        self.assertTrue(self.result.semantically_equals(later))
        self.assertEqual(
            self.result.semantic_fingerprint,
            later.semantic_fingerprint,
        )

    def test_25_round_trip_and_export_preserve_result(self) -> None:
        reloaded = ProposalValidationResult.from_json(self.result.to_json())
        self.assertEqual(reloaded, self.result)
        with tempfile.TemporaryDirectory() as directory:
            path = export_validation_result(
                self.result,
                Path(directory) / "result.json",
            )
            exported = load_validation_result(path)
        self.assertEqual(exported, self.result)

    def test_26_tampered_result_fingerprint_is_rejected(self) -> None:
        value = self.result.to_json().replace(
            self.result.semantic_fingerprint,
            "sha256:" + ("0" * 64),
        )
        with self.assertRaises(ProposalValidationSerializationError):
            ProposalValidationResult.from_json(value)

    def test_27_summary_records_only_validation_observations(self) -> None:
        expected = "\n".join(
            (
                "Proposal: CHRONOS-DEMO-001-PROPOSAL-001",
                "Baseline: MATCH",
                "Demonstration: MATCH",
                "Target dataset: FOUND",
                "Target field: FOUND",
                "Before state: MATCH",
                "Requested field: order_amount",
                "Source-schema collision: NONE",
                "Result: VALID",
            )
        )
        self.assertEqual(self.result.summary(), expected)

    def test_28_no_datahub_client_or_network_transport(self) -> None:
        source = inspect.getsource(validate_proposal).casefold()
        for term in ("datahubgraph", "graphql", "requests.", "httpx", "gms"):
            self.assertNotIn(term, source)
        self.assertFalse(hasattr(self.result, "_client"))
        self.assertFalse(hasattr(self.result, "_transport"))

    def test_29_no_lineage_traversal_or_future_graph(self) -> None:
        source = inspect.getsource(validate_proposal).casefold()
        for term in (
            "lineage_edges",
            "lineage_paths",
            "mapping_groups",
            "future_graph",
            "future graph",
        ):
            self.assertNotIn(term, source)

    def test_30_no_business_impact_or_repair_semantics(self) -> None:
        generated = (self.result.to_json() + self.result.summary()).casefold()
        for term in (
            "blast radius",
            "downstream",
            "dashboard",
            "repair",
            "critical",
            "high impact",
            "low impact",
        ):
            self.assertNotIn(term, generated)

    def test_31_no_datahub_write_path_is_exposed(self) -> None:
        public = {
            name for name in dir(self.result) if not name.startswith("_")
        }
        self.assertTrue(
            public.isdisjoint(
                {"emit", "upsert", "patch", "delete", "rollback", "mutation"}
            )
        )

    def test_32_no_additional_requested_mutation_is_recorded(self) -> None:
        requested = self.result.requested_after_state
        self.assertFalse(requested.additional_requested_mutation)
        self.assertFinding(
            self.result,
            ValidationFindingCode.NO_ADDITIONAL_REQUESTED_MUTATION,
        )
        self.assertEqual(
            self.precondition(
                self.result,
                "additional_requested_mutation",
            ).observed,
            "NONE",
        )

    def test_33_exact_target_machine_key_is_recorded(self) -> None:
        self.assertEqual(
            self.result.validated_target.machine_key,
            (CANONICAL_DATASET_URN, "order_total"),
        )
        self.assertEqual(self.result.validated_target.dataset_occurrences, 1)
        self.assertEqual(self.result.validated_target.field_occurrences, 1)
        self.assertTrue(self.result.validated_target.field_parent_matches)

    def test_34_all_claimed_before_values_match_observed(self) -> None:
        before = self.result.validated_before_state
        self.assertTrue(before.matches)
        self.assertEqual(before.observed_field_path, "order_total")
        self.assertEqual(before.observed_field_name, "order_total")
        self.assertEqual(before.observed_native_type, "DOUBLE PRECISION")
        self.assertEqual(before.observed_normalized_type, "Number")

    def test_35_requested_name_absent_from_15_field_source_schema(self) -> None:
        self.assertEqual(len(self.snapshot.source_schema.fields), 15)
        self.assertEqual(
            self.result.requested_after_state.source_schema_occurrences,
            0,
        )

    def test_36_canonical_validation_artifact_loads(self) -> None:
        artifact = load_validation_result(
            ROOT / "artifacts" / "change_proposal_validation.json"
        )
        self.assertEqual(
            artifact.validation_state,
            ProposalValidationState.VALID,
        )
        self.assertTrue(artifact.semantically_equals(self.result))

    def proposal_with_before(self, **changes: str) -> ChangeProposal:
        before = replace(self.proposal.change.before, **changes)
        change = replace(self.proposal.change, before=before)
        return replace(self.proposal, change=change)

    def proposal_with_requested(self, name: str) -> ChangeProposal:
        change = replace(
            self.proposal.change,
            requested_after=RequestedFieldState(
                field_path=name,
                field_name=name,
            ),
        )
        return replace(self.proposal, change=change)

    def precondition(
        self,
        result: ProposalValidationResult,
        name: str,
    ):
        return next(item for item in result.preconditions if item.name == name)

    def assertPrecondition(self, name: str, observed: str) -> None:
        self.assertEqual(self.precondition(self.result, name).observed, observed)

    def assertFinding(
        self,
        result: ProposalValidationResult,
        code: ValidationFindingCode,
    ) -> None:
        self.assertIn(code, {item.code for item in result.findings})

    def assertBeforeMismatch(self, result: ProposalValidationResult) -> None:
        self.assertEqual(result.validation_state, ProposalValidationState.INVALID)
        self.assertFinding(result, ValidationFindingCode.BEFORE_STATE_MISMATCH)
        self.assertFalse(result.validated_before_state.matches)


if __name__ == "__main__":
    unittest.main()
