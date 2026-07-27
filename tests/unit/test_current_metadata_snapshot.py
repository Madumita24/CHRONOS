from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from chronos.context import ContextRetrievalState
from chronos.snapshot import (
    CurrentMetadataSnapshotAssembler,
    FieldMachineKey,
    RelationshipCategory,
    SnapshotBuildState,
    SnapshotSerializationError,
    SnapshotValidationState,
    export_snapshot,
    load_snapshot,
    semantic_fingerprint,
    validate_snapshot,
)

from snapshot_fixtures import SOURCE_URN, dataset_urn, fixed_clock, inputs


class CurrentMetadataSnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.inputs = inputs()
        cls.assembler = CurrentMetadataSnapshotAssembler(
            clock=fixed_clock()
        )
        cls.result = cls.assembler.assemble(cls.inputs)
        if cls.result.snapshot is None:
            raise AssertionError(cls.result.findings)
        cls.snapshot = cls.result.snapshot

    def test_01_successful_snapshot_assembly(self) -> None:
        self.assertEqual(self.result.state, SnapshotBuildState.VALIDATED)
        self.assertEqual(
            self.snapshot.validation_result.state,
            SnapshotValidationState.VALID,
        )
        self.assertEqual(self.result.findings, ())

    def test_02_dataset_registry_uses_urn_keys(self) -> None:
        by_urn = self.snapshot.dataset_by_urn()
        self.assertEqual(len(by_urn), 21)
        self.assertEqual(set(by_urn), {item.dataset_urn for item in self.snapshot.datasets})

    def test_03_field_registry_uses_parent_urn_and_path(self) -> None:
        key = FieldMachineKey(SOURCE_URN, "order_total")
        self.assertIn(key, self.snapshot.field_by_key())

    def test_04_source_field_included_exactly_once(self) -> None:
        self.assertEqual(
            sum(
                item.key == self.snapshot.source_field_key
                for item in self.snapshot.fields
            ),
            1,
        )

    def test_05_downstream_fields_included_exactly_once(self) -> None:
        keys = [
            item.key
            for item in self.snapshot.fields
            if item.key != self.snapshot.source_field_key
        ]
        self.assertEqual(len(keys), 25)
        self.assertEqual(len(set(keys)), 25)

    def test_06_same_name_cross_platform_datasets_remain_distinct(self) -> None:
        first = self.snapshot.dataset_by_urn()[dataset_urn(1)]
        second = self.snapshot.dataset_by_urn()[dataset_urn(2)]
        self.assertEqual(first.logical_name, second.logical_name)
        self.assertNotEqual(first.platform, second.platform)
        self.assertNotEqual(first.dataset_urn, second.dataset_urn)

    def test_07_same_name_fields_on_different_datasets_remain_distinct(self) -> None:
        first = FieldMachineKey(dataset_urn(1), "order_total")
        second = FieldMachineKey(dataset_urn(2), "order_total")
        self.assertIn(first, self.snapshot.field_by_key())
        self.assertIn(second, self.snapshot.field_by_key())
        self.assertNotEqual(first, second)

    def test_08_complete_source_schema_is_preserved(self) -> None:
        self.assertEqual(len(self.snapshot.source_schema.fields), 15)
        self.assertEqual(
            self.snapshot.source_schema.fields[5].field_path,
            "order_total",
        )

    def test_09_lineage_edges_are_preserved(self) -> None:
        self.assertEqual(len(self.snapshot.lineage_edges), 27)
        self.assertTrue(
            all(
                item.upstream in self.snapshot.field_by_key()
                and item.downstream in self.snapshot.field_by_key()
                for item in self.snapshot.lineage_edges
            )
        )

    def test_10_mapping_group_evidence_is_preserved(self) -> None:
        self.assertEqual(len(self.snapshot.mapping_groups), 28)
        self.assertIn(
            2,
            {
                len(item.mapping_group_ids)
                for item in self.snapshot.lineage_edges
            },
        )

    def test_11_multiple_paths_are_preserved(self) -> None:
        targets = [path.node_keys[-1] for path in self.snapshot.lineage_paths]
        self.assertGreater(targets.count(FieldMachineKey(dataset_urn(6), "order_total")), 1)

    def test_12_governance_attaches_to_the_correct_asset(self) -> None:
        owners = [
            item
            for item in self.snapshot.relationships
            if item.category is RelationshipCategory.OWNERSHIP
        ]
        self.assertEqual(len(owners), 1)
        self.assertEqual(owners[0].source_key, SOURCE_URN)

    def test_13_governance_is_not_propagated_through_lineage(self) -> None:
        downstream_owner_sources = {
            item.source_key
            for item in self.snapshot.relationships
            if item.category is RelationshipCategory.OWNERSHIP
            and item.source_key != SOURCE_URN
        }
        self.assertEqual(downstream_owner_sources, set())

    def test_14_bi_context_is_separate_from_field_lineage(self) -> None:
        categories = {item.category for item in self.snapshot.relationships}
        self.assertIn(RelationshipCategory.BI_REACHABLE_CONTEXT, categories)
        self.assertIn(RelationshipCategory.FIELD_LINEAGE, categories)
        self.assertNotEqual(
            [
                item
                for item in self.snapshot.relationships
                if item.category is RelationshipCategory.BI_REACHABLE_CONTEXT
            ][0].category,
            RelationshipCategory.FIELD_LINEAGE,
        )

    def test_15_pipeline_context_is_separate_from_field_lineage(self) -> None:
        pipeline = [
            item
            for item in self.snapshot.relationships
            if item.category is RelationshipCategory.PIPELINE_CONTEXT
        ]
        self.assertEqual(len(pipeline), 2)
        self.assertTrue(
            all(item.category is not RelationshipCategory.FIELD_LINEAGE for item in pipeline)
        )

    def test_16_unresolved_references_are_retained(self) -> None:
        unresolved = [
            item for item in self.snapshot.relationships if item.state == "unresolved"
        ]
        self.assertEqual(len(unresolved), 1)
        self.assertEqual(unresolved[0].target_key, "urn:li:tag:unresolved")

    def test_17_missing_optional_metadata_remains_missing(self) -> None:
        downstream = self.snapshot.field_by_key()[
            FieldMachineKey(dataset_urn(1), "order_total")
        ]
        self.assertIsNone(downstream.native_type)
        self.assertIsNone(downstream.description)

    def test_18_registry_ordering_is_deterministic(self) -> None:
        self.assertEqual(
            [item.dataset_urn for item in self.snapshot.datasets],
            sorted(item.dataset_urn for item in self.snapshot.datasets),
        )
        self.assertEqual(
            [item.evidence_id for item in self.snapshot.evidence],
            sorted(item.evidence_id for item in self.snapshot.evidence),
        )

    def test_19_serialization_is_deterministic(self) -> None:
        self.assertEqual(self.snapshot.to_json(), self.snapshot.to_json())
        self.assertEqual(
            self.snapshot.semantic_json(),
            self.snapshot.semantic_json(),
        )

    def test_20_fingerprint_ignores_observation_times(self) -> None:
        later_metadata = replace(
            self.snapshot.metadata,
            created_at="2026-08-01T00:00:00+00:00",
            snapshot_id="snapshot-later",
        )
        later_evidence = tuple(
            replace(item, observed_at="2026-08-01T00:00:00+00:00")
            for item in self.snapshot.evidence
        )
        later = replace(
            self.snapshot,
            metadata=later_metadata,
            evidence=later_evidence,
        )
        self.assertEqual(
            semantic_fingerprint(self.snapshot),
            semantic_fingerprint(later),
        )

    def test_21_fingerprint_changes_when_schema_changes(self) -> None:
        fields = list(self.snapshot.source_schema.fields)
        fields[0] = replace(fields[0], native_type="INTEGER")
        changed = replace(
            self.snapshot,
            source_schema=replace(
                self.snapshot.source_schema,
                fields=tuple(fields),
            ),
        )
        self.assertNotEqual(
            semantic_fingerprint(self.snapshot),
            semantic_fingerprint(changed),
        )

    def test_22_fingerprint_changes_when_lineage_changes(self) -> None:
        changed = replace(
            self.snapshot,
            lineage_edges=self.snapshot.lineage_edges[:-1],
        )
        self.assertNotEqual(
            semantic_fingerprint(self.snapshot),
            semantic_fingerprint(changed),
        )

    def test_23_fingerprint_changes_when_governance_changes(self) -> None:
        relationships = list(self.snapshot.relationships)
        owner_index = next(
            index
            for index, item in enumerate(relationships)
            if item.category is RelationshipCategory.OWNERSHIP
        )
        relationships[owner_index] = replace(
            relationships[owner_index],
            target_key="urn:li:corpuser:changed",
        )
        changed = replace(
            self.snapshot,
            relationships=tuple(relationships),
        )
        self.assertNotEqual(
            semantic_fingerprint(self.snapshot),
            semantic_fingerprint(changed),
        )

    def test_24_validation_catches_missing_source_dataset(self) -> None:
        changed = replace(
            self.snapshot,
            datasets=tuple(
                item
                for item in self.snapshot.datasets
                if item.dataset_urn != SOURCE_URN
            ),
        )
        self.assertIn(
            "source_dataset_exists",
            {item.invariant for item in validate_snapshot(changed).findings},
        )

    def test_25_validation_catches_missing_source_field(self) -> None:
        changed = replace(
            self.snapshot,
            fields=tuple(
                item
                for item in self.snapshot.fields
                if item.key != self.snapshot.source_field_key
            ),
        )
        self.assertIn(
            "source_field_exists",
            {item.invariant for item in validate_snapshot(changed).findings},
        )

    def test_26_validation_catches_source_type_mismatch(self) -> None:
        source_fields = tuple(
            replace(item, native_type="FLOAT")
            if item.field_path == "order_total"
            else item
            for item in self.snapshot.source_schema.fields
        )
        changed = replace(
            self.snapshot,
            source_schema=replace(
                self.snapshot.source_schema,
                fields=source_fields,
            ),
        )
        self.assertIn(
            "order_total_native_type",
            {item.invariant for item in validate_snapshot(changed).findings},
        )

    def test_27_validation_catches_dangling_lineage_endpoint(self) -> None:
        edge = replace(
            self.snapshot.lineage_edges[0],
            downstream=FieldMachineKey("urn:li:dataset:missing", "field"),
        )
        changed = replace(
            self.snapshot,
            lineage_edges=(edge, *self.snapshot.lineage_edges[1:]),
        )
        self.assertIn(
            "all_lineage_endpoints_known",
            {item.invariant for item in validate_snapshot(changed).findings},
        )

    def test_28_validation_catches_unknown_parent_dataset(self) -> None:
        field = replace(
            self.snapshot.fields[1],
            key=FieldMachineKey("urn:li:dataset:unknown", "order_total"),
        )
        changed = replace(
            self.snapshot,
            fields=(
                self.snapshot.fields[0],
                field,
                *self.snapshot.fields[2:],
            ),
        )
        self.assertIn(
            "all_field_parents_known",
            {item.invariant for item in validate_snapshot(changed).findings},
        )

    def test_29_validation_catches_duplicate_machine_key(self) -> None:
        changed = replace(
            self.snapshot,
            datasets=(*self.snapshot.datasets, self.snapshot.datasets[0]),
        )
        self.assertIn(
            "dataset_machine_keys_unique",
            {item.invariant for item in validate_snapshot(changed).findings},
        )

    def test_30_validation_catches_incorrect_downstream_count(self) -> None:
        changed = replace(
            self.snapshot,
            fields=self.snapshot.fields[:-1],
        )
        self.assertIn(
            "downstream_field_count",
            {item.invariant for item in validate_snapshot(changed).findings},
        )

    def test_31_validation_catches_incorrect_dataset_count(self) -> None:
        changed = replace(
            self.snapshot,
            datasets=self.snapshot.datasets[:-1],
        )
        self.assertIn(
            "dataset_scope_count",
            {item.invariant for item in validate_snapshot(changed).findings},
        )

    def test_32_validation_catches_incorrect_maximum_depth(self) -> None:
        changed_fields = tuple(
            replace(item, lineage_depth=4)
            if item.lineage_depth == 5
            else item
            for item in self.snapshot.fields
        )
        changed = replace(self.snapshot, fields=changed_fields)
        self.assertIn(
            "maximum_field_depth",
            {item.invariant for item in validate_snapshot(changed).findings},
        )

    def test_33_secret_serialization_is_rejected(self) -> None:
        environment = replace(
            self.snapshot.metadata.environment,
            endpoint="authorization: bearer unit-secret",
        )
        changed = replace(
            self.snapshot,
            metadata=replace(
                self.snapshot.metadata,
                environment=environment,
            ),
        )
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(SnapshotSerializationError):
                export_snapshot(changed, Path(directory) / "snapshot.json")

    def test_34_round_trip_is_semantically_equivalent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = export_snapshot(
                self.snapshot,
                Path(directory) / "snapshot.json",
            )
            reloaded = load_snapshot(path)
        self.assertTrue(self.snapshot.semantically_equals(reloaded))
        self.assertEqual(
            self.snapshot.semantic_fingerprint,
            reloaded.semantic_fingerprint,
        )

    def test_35_assembler_has_no_transport_or_write_boundary(self) -> None:
        self.assertFalse(hasattr(self.assembler, "_transport"))
        self.assertFalse(hasattr(self.assembler, "emit"))
        self.assertFalse(hasattr(self.assembler, "write"))

    def test_36_partial_phase_input_fails_closed(self) -> None:
        partial = replace(
            self.inputs.context_retrieval,
            state=ContextRetrievalState.PARTIAL,
        )
        result = self.assembler.assemble(
            replace(self.inputs, context_retrieval=partial)
        )
        self.assertEqual(result.state, SnapshotBuildState.INVALID_INPUT)
        self.assertIsNone(result.snapshot)

    def test_37_snapshot_id_is_observational_not_semantic(self) -> None:
        later = CurrentMetadataSnapshotAssembler(
            clock=fixed_clock(27)
        ).assemble(self.inputs)
        self.assertIsNotNone(later.snapshot)
        self.assertNotEqual(
            self.snapshot.metadata.snapshot_id,
            later.snapshot.metadata.snapshot_id,
        )
        self.assertEqual(
            self.snapshot.semantic_fingerprint,
            later.snapshot.semantic_fingerprint,
        )

    def test_38_proposed_change_is_not_present(self) -> None:
        self.assertNotIn("order_amount", self.snapshot.to_json())
        categories = {item.category.value for item in self.snapshot.relationships}
        self.assertNotIn("impacted", categories)
        self.assertNotIn("requires_repair", categories)


if __name__ == "__main__":
    unittest.main()
