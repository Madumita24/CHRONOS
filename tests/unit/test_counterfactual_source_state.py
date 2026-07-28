from __future__ import annotations

import copy
import hashlib
import inspect
import unittest
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
from pathlib import Path

from chronos.change_semantics import load_contract
from chronos.counterfactual_source import (
    CandidateSourceField,
    CounterfactualSourceState,
    CounterfactualSourceStateValidationError,
    FieldMappingClassification,
    Phase3EntryPreconditionError,
    SourceStateClassification,
    TransformationSummary,
    load_source_state,
    materialize_counterfactual_source_state,
    materialize_source_state_from_artifacts,
    validate_counterfactual_source_state,
)
from chronos.phase2_certification import (
    CertificationCheckStatus,
    Phase2CertificationState,
    load_certification,
)
from chronos.proposal import (
    RequestedFieldState,
    SchemaFieldTarget,
    load_proposal,
)
from chronos.proposal_validation import load_validation_result
from chronos.snapshot import load_snapshot


ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_PATH = ROOT / "artifacts" / "current_metadata_snapshot.json"
PROPOSAL_PATH = ROOT / "artifacts" / "change_proposal.json"
VALIDATION_PATH = ROOT / "artifacts" / "change_proposal_validation.json"
CONTRACT_PATH = ROOT / "artifacts" / "change_semantic_contract.json"
CERTIFICATION_PATH = ROOT / "artifacts" / "phase_2_certification.json"
STATE_PATH = ROOT / "artifacts" / "counterfactual_source_state.json"
INPUT_PATHS = (
    SNAPSHOT_PATH,
    PROPOSAL_PATH,
    VALIDATION_PATH,
    CONTRACT_PATH,
    CERTIFICATION_PATH,
)


def clock(hour: int):
    return lambda: datetime(2026, 7, 28, hour, tzinfo=timezone.utc)


class CounterfactualSourceStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.snapshot = load_snapshot(SNAPSHOT_PATH)
        cls.proposal = load_proposal(PROPOSAL_PATH)
        cls.validation = load_validation_result(VALIDATION_PATH)
        cls.contract = load_contract(CONTRACT_PATH)
        cls.certification = load_certification(CERTIFICATION_PATH)
        cls.input_hashes = {
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in INPUT_PATHS
        }
        cls.state = materialize_source_state_from_artifacts(
            SNAPSHOT_PATH,
            PROPOSAL_PATH,
            VALIDATION_PATH,
            CONTRACT_PATH,
            CERTIFICATION_PATH,
            clock=clock(1),
        )

    def test_01_canonical_transformation_succeeds(self) -> None:
        self.assertIsInstance(self.state, CounterfactualSourceState)
        self.assertEqual(self.state.operation.value, "field_rename")

    def test_02_phase_1_and_phase_2_entry_preconditions_pass(self) -> None:
        self.assertEqual(
            self.snapshot.validation_result.state.value,
            "valid",
        )
        self.assertEqual(
            self.certification.certification_state,
            Phase2CertificationState.CERTIFIED,
        )

    def test_03_candidate_schema_has_fifteen_fields(self) -> None:
        self.assertEqual(len(self.candidate_fields()), 15)

    def test_04_order_total_is_absent_from_candidate(self) -> None:
        self.assertEqual(self.paths().count("order_total"), 0)

    def test_05_order_amount_exists_exactly_once(self) -> None:
        self.assertEqual(self.paths().count("order_amount"), 1)

    def test_06_candidate_position_remains_five(self) -> None:
        self.assertEqual(self.target().position, 5)

    def test_07_dataset_identity_is_unchanged(self) -> None:
        identity = self.state.dataset_identity
        self.assertEqual(identity.dataset_urn, self.snapshot.source_dataset_urn)
        self.assertEqual(identity.platform, "postgres")
        self.assertEqual(identity.environment, "PROD")
        self.assertEqual(
            identity.qualified_name,
            "order_entry_db.order_entry.orders",
        )
        self.assertEqual(identity.logical_name, "orders")

    def test_08_target_types_are_preserved(self) -> None:
        self.assertEqual(self.target().native_type, "DOUBLE PRECISION")
        self.assertEqual(self.target().normalized_type, "Number")

    def test_09_target_nullability_and_key_status_are_preserved(self) -> None:
        self.assertIs(self.target().nullable, True)
        self.assertIs(self.target().is_part_of_key, False)

    def test_10_target_captured_metadata_is_preserved(self) -> None:
        current = next(
            item
            for item in self.snapshot.source_schema.fields
            if item.field_path == "order_total"
        )
        candidate = self.target()
        for attribute in (
            "datahub_type",
            "description",
            "is_partitioning_key",
            "json_path",
            "label",
            "recursive",
        ):
            self.assertEqual(
                getattr(candidate, attribute),
                getattr(current, attribute),
            )
        self.assertEqual(
            candidate.current_evidence_ids,
            current.evidence_ids,
        )

    def test_11_other_fourteen_fields_are_semantically_unchanged(self) -> None:
        current = {
            item.field_path: item
            for item in self.snapshot.source_schema.fields
            if item.field_path != "order_total"
        }
        candidate = {
            item.field_path: item
            for item in self.candidate_fields()
            if item.field_path != "order_amount"
        }
        self.assertEqual(set(current), set(candidate))
        for path, source in current.items():
            observed = candidate[path]
            self.assertEqual(
                self.field_semantics(observed),
                self.current_semantics(source),
            )

    def test_12_field_ordering_is_preserved(self) -> None:
        expected = [
            "order_amount" if item.field_path == "order_total"
            else item.field_path
            for item in self.snapshot.source_schema.fields
        ]
        self.assertEqual(list(self.paths()), expected)
        self.assertEqual(
            [item.position for item in self.candidate_fields()],
            list(range(15)),
        )

    def test_13_current_snapshot_remains_unchanged(self) -> None:
        before = self.snapshot.to_json()
        self.materialize()
        self.assertEqual(self.snapshot.to_json(), before)

    def test_14_all_phase_2_artifacts_remain_unchanged(self) -> None:
        self.materialize()
        for path, expected in self.input_hashes.items():
            self.assertEqual(
                hashlib.sha256(path.read_bytes()).hexdigest(),
                expected,
            )
        self.assertTrue(
            all(item.unchanged for item in self.state.input_artifact_hashes)
        )

    def test_15_candidate_schema_field_urn_is_not_fabricated(self) -> None:
        self.assertIsNone(self.target().schema_field_urn)

    def test_16_rename_mapping_is_exact(self) -> None:
        renamed = [
            item
            for item in self.state.field_identity_mappings
            if item.classification is FieldMappingClassification.RENAMED
        ]
        self.assertEqual(len(renamed), 1)
        self.assertEqual(
            renamed[0].current_identity.machine_key[1],
            "order_total",
        )
        self.assertEqual(
            renamed[0].candidate_identity.machine_key[1],
            "order_amount",
        )

    def test_17_other_mappings_are_unchanged(self) -> None:
        unchanged = [
            item
            for item in self.state.field_identity_mappings
            if item.classification is FieldMappingClassification.UNCHANGED
        ]
        self.assertEqual(len(unchanged), 14)
        self.assertTrue(
            all(
                item.current_identity.machine_key
                == item.candidate_identity.machine_key
                for item in unchanged
            )
        )

    def test_18_candidate_objects_are_counterfactual(self) -> None:
        self.assertEqual(
            self.state.state_classification,
            SourceStateClassification.COUNTERFACTUAL,
        )
        self.assertTrue(
            all(
                item.state_classification
                is SourceStateClassification.COUNTERFACTUAL
                for item in self.candidate_fields()
            )
        )

    def test_19_current_references_are_certified_current(self) -> None:
        reference = self.state.current_source_schema_reference
        self.assertEqual(
            reference.state_classification,
            SourceStateClassification.CERTIFIED_CURRENT,
        )
        self.assertTrue(
            all(
                item.current_source_identity.state_classification
                is SourceStateClassification.CERTIFIED_CURRENT
                for item in self.candidate_fields()
            )
        )

    def test_20_no_lineage_transformation_is_materialized(self) -> None:
        self.assertFalse(hasattr(self.state, "lineage_edges"))
        self.assertFalse(hasattr(self.state, "lineage_paths"))
        self.assertEqual(
            self.state.transformation_summary.lineage_edge_count,
            0,
        )

    def test_21_no_governance_transformation_is_materialized(self) -> None:
        for name in (
            "relationships",
            "owners",
            "domains",
            "tags",
            "glossary_terms",
            "dashboards",
            "data_products",
        ):
            self.assertFalse(hasattr(self.state, name))
        self.assertEqual(
            self.state.transformation_summary.governance_record_count,
            0,
        )

    def test_22_no_downstream_field_is_materialized(self) -> None:
        self.assertFalse(hasattr(self.state, "downstream_fields"))
        self.assertEqual(
            self.state.transformation_summary.downstream_field_count,
            0,
        )

    def test_23_wrong_snapshot_fingerprint_fails_closed(self) -> None:
        snapshot = replace(
            self.snapshot,
            semantic_fingerprint="sha256:" + ("1" * 64),
        )
        with self.assertRaises(Phase3EntryPreconditionError):
            self.materialize(snapshot=snapshot)

    def test_24_wrong_proposal_fingerprint_fails_closed(self) -> None:
        proposal = copy.deepcopy(self.proposal)
        object.__setattr__(
            proposal,
            "semantic_fingerprint",
            "sha256:" + ("2" * 64),
        )
        with self.assertRaises(Phase3EntryPreconditionError):
            self.materialize(proposal=proposal)

    def test_25_wrong_validation_fingerprint_fails_closed(self) -> None:
        validation = copy.deepcopy(self.validation)
        object.__setattr__(
            validation,
            "semantic_fingerprint",
            "sha256:" + ("3" * 64),
        )
        with self.assertRaises(Phase3EntryPreconditionError):
            self.materialize(validation=validation)

    def test_26_wrong_contract_fingerprint_fails_closed(self) -> None:
        contract = copy.deepcopy(self.contract)
        object.__setattr__(
            contract,
            "semantic_fingerprint",
            "sha256:" + ("4" * 64),
        )
        with self.assertRaises(Phase3EntryPreconditionError):
            self.materialize(contract=contract)

    def test_27_wrong_certification_fingerprint_fails_closed(self) -> None:
        certification = copy.deepcopy(self.certification)
        object.__setattr__(
            certification,
            "semantic_fingerprint",
            "sha256:" + ("5" * 64),
        )
        with self.assertRaises(Phase3EntryPreconditionError):
            self.materialize(certification=certification)

    def test_28_uncertified_phase_2_fails_closed(self) -> None:
        checks = (
            replace(
                self.certification.checks[0],
                status=CertificationCheckStatus.FAIL,
            ),
        ) + self.certification.checks[1:]
        certification = replace(
            self.certification,
            certification_state=Phase2CertificationState.NOT_CERTIFIED,
            checks=checks,
        )
        with self.assertRaises(Phase3EntryPreconditionError):
            self.materialize(certification=certification)

    def test_29_wrong_demonstration_fails_closed(self) -> None:
        proposal = replace(self.proposal, demonstration_id="OTHER-DEMO")
        with self.assertRaises(Phase3EntryPreconditionError):
            self.materialize(proposal=proposal)

    def test_30_wrong_dataset_urn_fails_closed(self) -> None:
        target = SchemaFieldTarget(
            dataset_urn=(
                "urn:li:dataset:(urn:li:dataPlatform:postgres,"
                "wrong.orders,PROD)"
            ),
            field_path="order_total",
        )
        proposal = replace(
            self.proposal,
            change=replace(self.proposal.change, target=target),
        )
        with self.assertRaises(Phase3EntryPreconditionError):
            self.materialize(proposal=proposal)

    def test_31_wrong_candidate_field_fails_closed(self) -> None:
        requested = RequestedFieldState(
            field_path="total_amount",
            field_name="total_amount",
        )
        proposal = replace(
            self.proposal,
            change=replace(
                self.proposal.change,
                requested_after=requested,
            ),
        )
        with self.assertRaises(Phase3EntryPreconditionError):
            self.materialize(proposal=proposal)

    def test_32_candidate_collision_fails_closed(self) -> None:
        first = replace(
            self.snapshot.source_schema.fields[0],
            field_path="order_amount",
            field_name="order_amount",
        )
        schema = replace(
            self.snapshot.source_schema,
            fields=(first,) + self.snapshot.source_schema.fields[1:],
        )
        snapshot = replace(self.snapshot, source_schema=schema)
        with self.assertRaises(Phase3EntryPreconditionError):
            self.materialize(snapshot=snapshot)

    def test_33_unrelated_source_field_mutation_is_rejected(self) -> None:
        fields = list(self.candidate_fields())
        fields[0] = replace(fields[0], native_type="TEXT")
        altered = replace(
            self.state,
            candidate_source_schema=replace(
                self.state.candidate_source_schema,
                fields=tuple(fields),
            ),
        )
        with self.assertRaises(CounterfactualSourceStateValidationError):
            self.validate(altered)

    def test_34_target_type_change_is_rejected(self) -> None:
        altered = self.alter_target(native_type="BIGINT")
        with self.assertRaises(CounterfactualSourceStateValidationError):
            self.validate(altered)

    def test_35_target_nullability_change_is_rejected(self) -> None:
        altered = self.alter_target(nullable=False)
        with self.assertRaises(CounterfactualSourceStateValidationError):
            self.validate(altered)

    def test_36_target_key_status_change_is_rejected(self) -> None:
        altered = self.alter_target(is_part_of_key=True)
        with self.assertRaises(CounterfactualSourceStateValidationError):
            self.validate(altered)

    def test_37_field_order_change_is_rejected(self) -> None:
        fields = list(self.candidate_fields())
        fields[0], fields[1] = fields[1], fields[0]
        with self.assertRaises(ValueError):
            replace(
                self.state,
                candidate_source_schema=replace(
                    self.state.candidate_source_schema,
                    fields=tuple(fields),
                ),
            )

    def test_38_candidate_schema_count_change_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            replace(
                self.state,
                candidate_source_schema=replace(
                    self.state.candidate_source_schema,
                    fields=self.state.candidate_source_schema.fields[:-1],
                ),
            )

    def test_39_fabricated_candidate_schema_field_urn_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.alter_target(
                schema_field_urn=(
                    "urn:li:schemaField:(counterfactual,order_amount)"
                )
            )

    def test_40_downstream_materialization_attempt_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            replace(
                self.state,
                transformation_summary=TransformationSummary(
                    14,
                    1,
                    0,
                    0,
                    1,
                    0,
                    0,
                ),
            )

    def test_41_current_snapshot_cannot_be_mutated(self) -> None:
        with self.assertRaises(FrozenInstanceError):
            self.snapshot.source_dataset_urn = "changed"

    def test_42_semantic_fingerprint_is_deterministic(self) -> None:
        repeated = self.materialize(clock_value=clock(1))
        self.assertTrue(self.state.semantically_equals(repeated))

    def test_43_timestamp_is_excluded_from_semantic_fingerprint(self) -> None:
        later = self.materialize(clock_value=clock(2))
        self.assertNotEqual(self.state.created_at, later.created_at)
        self.assertEqual(
            self.state.semantic_fingerprint,
            later.semantic_fingerprint,
        )

    def test_44_candidate_semantic_change_changes_fingerprint(self) -> None:
        fields = list(self.candidate_fields())
        fields[0] = replace(fields[0], description="changed")
        changed = replace(
            self.state,
            candidate_source_schema=replace(
                self.state.candidate_source_schema,
                fields=tuple(fields),
            ),
        )
        self.assertNotEqual(
            changed.semantic_fingerprint,
            self.state.semantic_fingerprint,
        )

    def test_45_input_contract_change_changes_fingerprint(self) -> None:
        changed = replace(
            self.state,
            semantic_contract_fingerprint="sha256:" + ("6" * 64),
        )
        self.assertNotEqual(
            changed.semantic_fingerprint,
            self.state.semantic_fingerprint,
        )

    def test_46_phase_2_certification_change_changes_fingerprint(self) -> None:
        changed = replace(
            self.state,
            phase_2_certification_fingerprint=(
                "sha256:" + ("7" * 64)
            ),
        )
        self.assertNotEqual(
            changed.semantic_fingerprint,
            self.state.semantic_fingerprint,
        )

    def test_47_serialization_round_trip(self) -> None:
        reloaded = CounterfactualSourceState.from_json(self.state.to_json())
        self.assertEqual(reloaded, self.state)

    def test_48_canonical_artifact_loads(self) -> None:
        artifact = load_source_state(STATE_PATH)
        self.assertTrue(artifact.semantically_equals(self.state))

    def test_49_artifact_contains_no_secret(self) -> None:
        raw = self.state.to_json().casefold()
        for term in (
            "authorization: bearer",
            '"password"',
            '"access_token"',
            '"api_key"',
        ):
            self.assertNotIn(term, raw)

    def test_50_no_datahub_client_or_network_dependency(self) -> None:
        source = inspect.getsource(
            materialize_counterfactual_source_state
        ).casefold()
        for term in ("datahubgraph", "graphql", "requests.", "httpx", "gms"):
            self.assertNotIn(term, source)
        self.assertFalse(hasattr(self.state, "_client"))
        self.assertFalse(hasattr(self.state, "_transport"))

    def test_51_candidate_field_name_change_changes_fingerprint(self) -> None:
        changed = self.alter_target(field_name="candidate_amount")
        self.assertNotEqual(
            changed.semantic_fingerprint,
            self.state.semantic_fingerprint,
        )
        with self.assertRaises(CounterfactualSourceStateValidationError):
            self.validate(changed)

    def test_52_dataset_semantic_change_changes_fingerprint(self) -> None:
        identity = replace(
            self.state.dataset_identity,
            qualified_name="changed.orders",
        )
        changed = replace(
            self.state,
            dataset_identity=identity,
            candidate_source_schema=replace(
                self.state.candidate_source_schema,
                dataset_identity=identity,
            ),
        )
        self.assertNotEqual(
            changed.semantic_fingerprint,
            self.state.semantic_fingerprint,
        )
        with self.assertRaises(CounterfactualSourceStateValidationError):
            self.validate(changed)

    def test_53_snapshot_fingerprint_change_changes_state_fingerprint(
        self,
    ) -> None:
        changed = replace(
            self.state,
            current_snapshot_fingerprint="sha256:" + ("8" * 64),
        )
        self.assertNotEqual(
            changed.semantic_fingerprint,
            self.state.semantic_fingerprint,
        )

    def candidate_fields(self) -> tuple[CandidateSourceField, ...]:
        return self.state.candidate_source_schema.fields

    def paths(self) -> tuple[str, ...]:
        return tuple(item.field_path for item in self.candidate_fields())

    def target(self) -> CandidateSourceField:
        return next(
            item
            for item in self.candidate_fields()
            if item.field_path == "order_amount"
        )

    def current_semantics(self, field) -> tuple[object, ...]:
        return (
            field.position,
            field.field_path,
            field.field_name,
            field.native_type,
            field.normalized_type,
            field.datahub_type,
            field.description,
            field.nullable,
            field.is_part_of_key,
            field.is_partitioning_key,
            field.json_path,
            field.label,
            field.recursive,
            field.schema_field_urn,
            field.evidence_ids,
        )

    def field_semantics(self, field) -> tuple[object, ...]:
        return (
            field.position,
            field.field_path,
            field.field_name,
            field.native_type,
            field.normalized_type,
            field.datahub_type,
            field.description,
            field.nullable,
            field.is_part_of_key,
            field.is_partitioning_key,
            field.json_path,
            field.label,
            field.recursive,
            field.schema_field_urn,
            field.current_evidence_ids,
        )

    def materialize(
        self,
        *,
        snapshot=None,
        proposal=None,
        validation=None,
        contract=None,
        certification=None,
        clock_value=None,
    ) -> CounterfactualSourceState:
        return materialize_counterfactual_source_state(
            snapshot or self.snapshot,
            proposal or self.proposal,
            validation or self.validation,
            contract or self.contract,
            certification or self.certification,
            input_artifact_hashes=self.state.input_artifact_hashes,
            clock=clock_value or clock(1),
        )

    def validate(self, state: CounterfactualSourceState) -> None:
        validate_counterfactual_source_state(
            state,
            self.snapshot,
            self.proposal,
            self.validation,
            self.contract,
            self.certification,
        )

    def alter_target(self, **changes) -> CounterfactualSourceState:
        fields = list(self.candidate_fields())
        index = next(
            position
            for position, item in enumerate(fields)
            if item.field_path == "order_amount"
        )
        fields[index] = replace(fields[index], **changes)
        return replace(
            self.state,
            candidate_source_schema=replace(
                self.state.candidate_source_schema,
                fields=tuple(fields),
            ),
        )


if __name__ == "__main__":
    unittest.main()
