from __future__ import annotations

import hashlib
import json
import socket
import tempfile
import unittest
from collections import Counter
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from chronos.change_semantics import load_contract
from chronos.counterfactual_source import load_source_state
from chronos.dependency_propagation import (
    DatasetExposureState,
    DependencyPropagationEntryPreconditionError,
    DependencyPropagationResult,
    DependencyPropagationValidationError,
    FieldExposureState,
    PropagationValidationState,
    RelationshipExposureState,
    enumerate_dependency_paths,
    export_dependency_propagation,
    load_dependency_propagation,
    propagate_dependencies,
    propagate_dependencies_from_artifacts,
    propagation_semantic_fingerprint,
    shortest_dependency_depths,
    validate_dependency_propagation,
)
from chronos.future_graph import (
    FutureMetadataGraph,
    GraphObjectState,
    RelationshipEvaluationState,
    load_future_graph,
)
from chronos.phase2_certification import load_certification
from chronos.proposal import CANONICAL_DATASET_URN, load_proposal
from chronos.proposal_validation import load_validation_result
from chronos.snapshot import FieldMachineKey, RelationshipCategory, load_snapshot
from chronos.snapshot.serialization import contains_secret


ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "artifacts"
SNAPSHOT_PATH = ARTIFACTS / "current_metadata_snapshot.json"
PROPOSAL_PATH = ARTIFACTS / "change_proposal.json"
VALIDATION_PATH = ARTIFACTS / "change_proposal_validation.json"
CONTRACT_PATH = ARTIFACTS / "change_semantic_contract.json"
CERTIFICATION_PATH = ARTIFACTS / "phase_2_certification.json"
SOURCE_STATE_PATH = ARTIFACTS / "counterfactual_source_state.json"
FUTURE_GRAPH_PATH = ARTIFACTS / "future_metadata_graph.json"
PROPAGATION_PATH = ARTIFACTS / "dependency_propagation.json"
INPUT_PATHS = (
    SNAPSHOT_PATH,
    PROPOSAL_PATH,
    VALIDATION_PATH,
    CONTRACT_PATH,
    CERTIFICATION_PATH,
    SOURCE_STATE_PATH,
    FUTURE_GRAPH_PATH,
)
SOURCE = FieldMachineKey(CANONICAL_DATASET_URN, "order_amount")
CURRENT_SOURCE = FieldMachineKey(CANONICAL_DATASET_URN, "order_total")


def fixed_clock(hour: int):
    return lambda: datetime(2026, 7, 28, hour, tzinfo=timezone.utc)


class DependencyPropagationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.input_hashes = {
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in INPUT_PATHS
        }
        cls.snapshot = load_snapshot(SNAPSHOT_PATH)
        cls.proposal = load_proposal(PROPOSAL_PATH)
        cls.validation = load_validation_result(VALIDATION_PATH)
        cls.contract = load_contract(CONTRACT_PATH)
        cls.certification = load_certification(CERTIFICATION_PATH)
        cls.source_state = load_source_state(SOURCE_STATE_PATH)
        cls.future_graph = load_future_graph(FUTURE_GRAPH_PATH)
        cls.result = cls.build(1)

    @classmethod
    def build(cls, hour: int) -> DependencyPropagationResult:
        return propagate_dependencies_from_artifacts(
            SNAPSHOT_PATH,
            PROPOSAL_PATH,
            VALIDATION_PATH,
            CONTRACT_PATH,
            CERTIFICATION_PATH,
            SOURCE_STATE_PATH,
            FUTURE_GRAPH_PATH,
            clock=fixed_clock(hour),
        )

    def test_01_canonical_propagation_succeeds(self) -> None:
        self.assertIsInstance(self.result, DependencyPropagationResult)
        self.assertIs(
            self.result.validation_state,
            PropagationValidationState.VALID,
        )

    def test_02_source_is_classified_source_changed(self) -> None:
        source = self.field(SOURCE)
        self.assertIs(
            source.exposure_state,
            FieldExposureState.SOURCE_CHANGED,
        )
        self.assertEqual(source.minimum_depth, 0)
        self.assertIs(
            source.identity_state,
            GraphObjectState.COUNTERFACTUAL_CHANGED,
        )

    def test_03_direct_child_is_s3_order_total(self) -> None:
        direct = [
            item
            for item in self.result.field_exposure_registry
            if item.exposure_state is FieldExposureState.DIRECTLY_EXPOSED
        ]
        self.assertEqual(len(direct), 1)
        self.assertEqual(direct[0].minimum_depth, 1)
        self.assertEqual(direct[0].field_key.field_path, "order_total")
        self.assertIn("urn:li:dataPlatform:s3", direct[0].field_key.dataset_urn)

    def test_04_depth_two_field_is_transitively_exposed(self) -> None:
        record = next(
            item
            for item in self.result.field_exposure_registry
            if item.minimum_depth == 2
        )
        self.assertIs(
            record.exposure_state,
            FieldExposureState.TRANSITIVELY_EXPOSED,
        )
        self.assertIn(
            "urn:li:dataPlatform:snowflake",
            record.field_key.dataset_urn,
        )

    def test_05_depth_five_fields_are_exposed(self) -> None:
        records = [
            item
            for item in self.result.field_exposure_registry
            if item.minimum_depth == 5
        ]
        self.assertEqual(len(records), 5)
        self.assertTrue(
            all(
                item.exposure_state
                is FieldExposureState.MULTIPATH_EXPOSED
                for item in records
            )
        )

    def test_06_twenty_five_unique_downstream_fields_are_exposed(self) -> None:
        downstream = self.downstream()
        self.assertEqual(len(downstream), 25)
        self.assertEqual(
            len({item.field_key for item in downstream}),
            25,
        )
        self.assertEqual(
            self.result.summary.total_unique_downstream_exposed_fields,
            25,
        )

    def test_07_twenty_downstream_datasets_are_exposed(self) -> None:
        self.assertEqual(len(self.result.dataset_exposure_registry), 20)
        self.assertEqual(
            self.result.summary.unique_downstream_exposed_datasets,
            20,
        )

    def test_08_maximum_shortest_exposure_depth_is_five(self) -> None:
        self.assertEqual(self.result.summary.maximum_exposure_depth, 5)
        self.assertEqual(
            max(item.minimum_depth for item in self.downstream()),
            5,
        )

    def test_09_source_is_excluded_from_downstream_counts(self) -> None:
        self.assertNotIn(
            SOURCE.dataset_urn,
            {
                item.dataset_urn
                for item in self.result.dataset_exposure_registry
            },
        )
        self.assertNotIn(SOURCE, {item.field_key for item in self.downstream()})

    def test_10_all_twenty_seven_structural_relationships_are_processed(
        self,
    ) -> None:
        self.assertEqual(
            len(self.result.relationship_exposure_registry),
            27,
        )
        self.assertEqual(
            self.result.summary.processed_structural_relationships,
            27,
        )
        self.assertEqual(
            self.result.summary.exposed_structural_relationships,
            27,
        )

    def test_11_source_rebased_edge_is_identified(self) -> None:
        records = [
            item
            for item in self.result.relationship_exposure_registry
            if item.exposure_state
            is RelationshipExposureState.SOURCE_REBASED_EDGE
        ]
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].source_field, SOURCE)
        self.assertEqual(records[0].target_field, self.direct().field_key)

    def test_12_remaining_edges_are_downstream_exposed(self) -> None:
        self.assertEqual(
            sum(
                item.exposure_state
                is RelationshipExposureState.DOWNSTREAM_EXPOSED_EDGE
                for item in self.result.relationship_exposure_registry
            ),
            26,
        )

    def test_13_no_context_relationship_is_used(self) -> None:
        context_ids = {
            item.current_relationship_id
            for item in self.future_graph.context_relationship_registry
        }
        path_edge_ids = {
            value
            for item in self.result.path_registry
            for value in item.relationship_ids
        }
        self.assertTrue(path_edge_ids.isdisjoint(context_ids))
        self.assertEqual(len(path_edge_ids), 27)

    def test_14_multipath_fields_are_identified(self) -> None:
        multipath = [
            item
            for item in self.downstream()
            if item.exposure_state is FieldExposureState.MULTIPATH_EXPOSED
        ]
        self.assertEqual(len(multipath), 21)
        self.assertTrue(all(item.path_count > 1 for item in multipath))

    def test_15_shortest_depth_is_preserved_separately_from_long_paths(
        self,
    ) -> None:
        record = self.multipath_example()
        paths = [
            self.path_by_id()[value]
            for value in record.supporting_path_ids
        ]
        self.assertEqual(record.minimum_depth, min(item.depth for item in paths))
        self.assertGreater(max(item.depth for item in paths), record.minimum_depth)

    def test_16_path_count_matches_distinct_supporting_paths(self) -> None:
        for item in self.downstream():
            self.assertEqual(
                item.path_count,
                len(set(item.supporting_path_ids)),
            )
            self.assertEqual(
                item.path_count,
                sum(
                    path.target_field == item.field_key
                    for path in self.result.path_registry
                ),
            )

    def test_17_all_forty_eight_paths_are_preserved(self) -> None:
        self.assertEqual(len(self.result.path_registry), 48)
        self.assertEqual(
            len({item.path_id for item in self.result.path_registry}),
            48,
        )
        self.assertTrue(
            all(item.future_graph_path_id for item in self.result.path_registry)
        )

    def test_18_duplicate_paths_are_deduplicated(self) -> None:
        relationship = self.future_graph.relationship_registry[0]
        paths = enumerate_dependency_paths(
            relationship.upstream,
            (relationship, relationship),
        )
        self.assertEqual(len(paths), 1)

    def test_19_cycle_safe_traversal_terminates(self) -> None:
        a = FieldMachineKey("urn:li:dataset:(a,b,PROD)", "a")
        b = FieldMachineKey("urn:li:dataset:(a,b,PROD)", "b")
        c = FieldMachineKey("urn:li:dataset:(a,b,PROD)", "c")
        template = self.future_graph.relationship_registry[0]
        edges = (
            replace(template, relationship_id="ab", upstream=a, downstream=b),
            replace(template, relationship_id="bc", upstream=b, downstream=c),
            replace(template, relationship_id="ca", upstream=c, downstream=a),
        )
        self.assertEqual(shortest_dependency_depths(a, edges), {a: 0, b: 1, c: 2})
        paths = enumerate_dependency_paths(a, edges)
        self.assertEqual(len(paths), 2)
        self.assertTrue(all(len(set(item.node_keys)) == len(item.node_keys) for item in paths))

    def test_20_unreachable_field_is_not_exposed(self) -> None:
        edge = self.future_graph.relationship_registry[0]
        unreachable = FieldMachineKey(edge.downstream.dataset_urn, "unreachable")
        depths = shortest_dependency_depths(edge.upstream, (edge,))
        self.assertNotIn(unreachable, depths)

    def test_21_unreachable_relationship_is_not_traversed(self) -> None:
        edge = self.future_graph.relationship_registry[0]
        disconnected = replace(
            edge,
            relationship_id="disconnected",
            upstream=FieldMachineKey(
                edge.downstream.dataset_urn,
                "unreachable_upstream",
            ),
            downstream=FieldMachineKey(
                edge.downstream.dataset_urn,
                "unreachable_downstream",
            ),
        )
        paths = enumerate_dependency_paths(edge.upstream, (edge, disconnected))
        self.assertNotIn(
            "disconnected",
            {
                value
                for item in paths
                for value in item.relationship_ids
            },
        )

    def test_22_field_with_two_paths_is_multipath_exposed(self) -> None:
        record = self.multipath_example()
        self.assertGreaterEqual(record.path_count, 2)
        self.assertIs(
            record.exposure_state,
            FieldExposureState.MULTIPATH_EXPOSED,
        )

    def test_23_downstream_identity_is_unchanged(self) -> None:
        expected = {
            item.key
            for item in self.future_graph.field_registry
            if item.key != SOURCE
        }
        self.assertEqual(
            {item.field_key for item in self.downstream()},
            expected,
        )
        self.assertNotIn(CURRENT_SOURCE, expected)

    def test_24_phase_3_2_identity_state_is_preserved_separately(self) -> None:
        graph_fields = {
            item.key: item for item in self.future_graph.field_registry
        }
        for item in self.result.field_exposure_registry:
            self.assertEqual(
                item.identity_state,
                graph_fields[item.field_key].state,
            )
        self.assertTrue(
            all(
                item.identity_state
                is GraphObjectState.COUNTERFACTUAL_UNRESOLVED
                for item in self.downstream()
            )
        )

    def test_25_compatibility_remains_not_evaluated(self) -> None:
        self.assertTrue(
            all(
                item.compatibility_state
                is RelationshipEvaluationState.NOT_EVALUATED
                for item in self.result.relationship_exposure_registry
            )
        )

    def test_26_dataset_exposure_is_derived_from_fields(self) -> None:
        fields_by_dataset = Counter(
            item.parent_dataset_urn for item in self.downstream()
        )
        for item in self.result.dataset_exposure_registry:
            self.assertEqual(
                item.exposed_field_count,
                fields_by_dataset[item.dataset_urn],
            )
            self.assertEqual(
                set(item.field_keys),
                {
                    field.field_key
                    for field in self.downstream()
                    if field.parent_dataset_urn == item.dataset_urn
                },
            )

    def test_27_dataset_state_summary_is_separate_from_impact(self) -> None:
        counts = Counter(
            item.exposure_state
            for item in self.result.dataset_exposure_registry
        )
        self.assertEqual(
            counts[DatasetExposureState.DIRECTLY_EXPOSED_DATASET],
            1,
        )
        self.assertEqual(
            counts[DatasetExposureState.TRANSITIVELY_EXPOSED_DATASET],
            3,
        )
        self.assertEqual(
            counts[DatasetExposureState.MULTIPATH_EXPOSED_DATASET],
            16,
        )

    def test_28_no_impact_compatibility_or_repair_state_is_introduced(
        self,
    ) -> None:
        states = {
            item.exposure_state.value
            for item in self.result.field_exposure_registry
        } | {
            item.exposure_state.value
            for item in self.result.dataset_exposure_registry
        } | {
            item.exposure_state.value
            for item in self.result.relationship_exposure_registry
        }
        forbidden = {
            "broken",
            "impacted",
            "compatible",
            "incompatible",
            "safe",
            "risk",
            "repair_required",
            "requires_repair",
        }
        self.assertTrue(states.isdisjoint(forbidden))

    def test_29_current_and_counterfactual_provenance_are_preserved(
        self,
    ) -> None:
        for item in self.downstream():
            self.assertTrue(item.current_provenance_ids)
            self.assertTrue(item.counterfactual_provenance_ids)
        source_edge = next(
            item
            for item in self.result.relationship_exposure_registry
            if item.exposure_state
            is RelationshipExposureState.SOURCE_REBASED_EDGE
        )
        self.assertTrue(source_edge.current_provenance_ids)
        self.assertTrue(source_edge.counterfactual_provenance_ids)

    def test_30_ordering_is_deterministic(self) -> None:
        fields = list(self.result.field_exposure_registry)
        self.assertEqual(
            fields,
            sorted(
                fields,
                key=lambda item: (
                    item.minimum_depth,
                    item.field_key.dataset_urn,
                    item.field_key.field_path,
                ),
            ),
        )
        relationships = [
            item.relationship_id
            for item in self.result.relationship_exposure_registry
        ]
        self.assertEqual(relationships, sorted(relationships))
        paths = list(self.result.path_registry)
        self.assertEqual(
            paths,
            sorted(
                paths,
                key=lambda item: (
                    item.depth,
                    item.target_field.dataset_urn,
                    item.target_field.field_path,
                    item.path_id,
                ),
            ),
        )

    def test_31_serialization_is_deterministic(self) -> None:
        self.assertEqual(self.build(2).to_json(), self.build(2).to_json())

    def test_32_fingerprint_is_stable_across_timestamps(self) -> None:
        first = self.build(3)
        second = self.build(4)
        self.assertNotEqual(first.created_at, second.created_at)
        self.assertEqual(
            first.semantic_fingerprint,
            second.semantic_fingerprint,
        )
        self.assertTrue(first.semantically_equals(second))

    def test_33_semantic_exposure_change_changes_fingerprint(self) -> None:
        direct = self.direct()
        fields = tuple(
            replace(
                item,
                exposure_state=FieldExposureState.UNRESOLVED,
            )
            if item.field_key == direct.field_key
            else item
            for item in self.result.field_exposure_registry
        )
        changed = replace(self.result, field_exposure_registry=fields)
        self.assertNotEqual(
            changed.semantic_fingerprint,
            self.result.semantic_fingerprint,
        )

    def test_34_future_graph_fingerprint_change_changes_fingerprint(
        self,
    ) -> None:
        changed = replace(
            self.result,
            future_graph_fingerprint="sha256:" + ("0" * 64),
        )
        self.assertNotEqual(
            changed.semantic_fingerprint,
            self.result.semantic_fingerprint,
        )

    def test_35_round_trip_serialization(self) -> None:
        restored = DependencyPropagationResult.from_json(
            self.result.to_json()
        )
        self.assertEqual(restored, self.result)

    def test_36_export_and_load_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "propagation.json"
            export_dependency_propagation(self.result, path)
            self.assertEqual(
                load_dependency_propagation(path),
                self.result,
            )

    def test_37_result_is_deeply_immutable(self) -> None:
        with self.assertRaises(FrozenInstanceError):
            self.result.created_at = "changed"  # type: ignore[misc]

    def test_38_no_secrets(self) -> None:
        self.assertFalse(contains_secret(self.result.to_dict()))

    def test_39_no_datahub_or_network_dependency(self) -> None:
        with patch.object(
            socket,
            "create_connection",
            side_effect=AssertionError("network access attempted"),
        ):
            result = propagate_dependencies(
                self.snapshot,
                self.proposal,
                self.validation,
                self.contract,
                self.certification,
                self.source_state,
                self.future_graph,
                input_artifact_hashes=self.result.input_artifact_hashes,
                clock=fixed_clock(5),
            )
        self.assertEqual(
            result.summary.total_unique_downstream_exposed_fields,
            25,
        )

    def test_40_prior_artifacts_are_unchanged(self) -> None:
        self.build(6)
        for path, expected in self.input_hashes.items():
            self.assertEqual(
                hashlib.sha256(path.read_bytes()).hexdigest(),
                expected,
            )

    def test_41_wrong_future_graph_fingerprint_fails_validation(self) -> None:
        changed = replace(
            self.result,
            future_graph_fingerprint="sha256:" + ("f" * 64),
        )
        with self.assertRaises(DependencyPropagationValidationError):
            validate_dependency_propagation(changed, self.future_graph)

    def test_42_missing_source_candidate_fails_closed(self) -> None:
        raw = self.future_graph.to_dict()
        raw["field_registry"] = [
            item
            for item in raw["field_registry"]
            if item["key"]["field_path"] != "order_amount"
        ]
        with self.assertRaises(ValueError):
            FutureMetadataGraph.from_json(json.dumps(raw))

    def test_43_dangling_edge_fails_closed(self) -> None:
        first = self.future_graph.relationship_registry[0]
        dangling = FieldMachineKey(
            first.downstream.dataset_urn,
            "missing_field",
        )
        relationships = (
            replace(first, downstream=dangling),
            *self.future_graph.relationship_registry[1:],
        )
        with self.assertRaises(ValueError):
            replace(
                self.future_graph,
                relationship_registry=relationships,
            )

    def test_44_duplicate_edge_fails_entry_preconditions(self) -> None:
        first, second, *rest = self.future_graph.relationship_registry
        duplicate = replace(
            first,
            upstream=second.upstream,
            downstream=second.downstream,
        )
        graph = replace(
            self.future_graph,
            relationship_registry=(duplicate, second, *rest),
        )
        with self.assertRaises(
            DependencyPropagationEntryPreconditionError
        ):
            propagate_dependencies(
                self.snapshot,
                self.proposal,
                self.validation,
                self.contract,
                self.certification,
                self.source_state,
                graph,
                input_artifact_hashes=self.result.input_artifact_hashes,
                clock=fixed_clock(7),
            )

    def test_45_dangling_exposed_field_fails_closed(self) -> None:
        direct = self.direct()
        missing = FieldMachineKey(
            direct.parent_dataset_urn,
            "missing_field",
        )
        fields = tuple(
            replace(
                item,
                field_key=missing,
                parent_dataset_urn=missing.dataset_urn,
            )
            if item.field_key == direct.field_key
            else item
            for item in self.result.field_exposure_registry
        )
        with self.assertRaises(ValueError):
            replace(self.result, field_exposure_registry=fields)

    def test_46_context_only_relationship_does_not_propagate(self) -> None:
        context = next(
            item
            for item in self.future_graph.context_relationship_registry
            if item.category is RelationshipCategory.OWNERSHIP
        )
        paths = enumerate_dependency_paths(
            SOURCE,
            (context,),  # type: ignore[arg-type]
        )
        self.assertEqual(paths, ())

    def test_47_attempt_to_resolve_compatibility_is_rejected(self) -> None:
        first = self.result.relationship_exposure_registry[0]
        relationships = (
            replace(
                first,
                compatibility_state="compatible",  # type: ignore[arg-type]
            ),
            *self.result.relationship_exposure_registry[1:],
        )
        with self.assertRaises(ValueError):
            replace(
                self.result,
                relationship_exposure_registry=relationships,
            )

    def test_48_attempt_to_rename_downstream_is_rejected(self) -> None:
        direct = self.direct()
        renamed = FieldMachineKey(
            direct.field_key.dataset_urn,
            "order_amount",
        )
        fields = tuple(
            replace(
                item,
                field_key=renamed,
                parent_dataset_urn=renamed.dataset_urn,
            )
            if item.field_key == direct.field_key
            else item
            for item in self.result.field_exposure_registry
        )
        with self.assertRaises(ValueError):
            replace(self.result, field_exposure_registry=fields)

    def test_49_artifact_matches_canonical_propagation(self) -> None:
        artifact = load_dependency_propagation(PROPAGATION_PATH)
        self.assertTrue(artifact.semantically_equals(self.result))

    def test_50_semantic_fingerprint_reproduces(self) -> None:
        self.assertEqual(
            propagation_semantic_fingerprint(self.result),
            self.result.semantic_fingerprint,
        )

    def field(self, key: FieldMachineKey):
        return next(
            item
            for item in self.result.field_exposure_registry
            if item.field_key == key
        )

    def downstream(self):
        return tuple(
            item
            for item in self.result.field_exposure_registry
            if item.field_key != SOURCE
        )

    def direct(self):
        return next(
            item
            for item in self.result.field_exposure_registry
            if item.exposure_state is FieldExposureState.DIRECTLY_EXPOSED
        )

    def multipath_example(self):
        return next(
            item
            for item in self.result.field_exposure_registry
            if (
                "snowflake" in item.field_key.dataset_urn
                and "analytics.order_details,PROD"
                in item.field_key.dataset_urn
                and item.field_key.field_path == "order_total"
            )
        )

    def path_by_id(self):
        return {item.path_id: item for item in self.result.path_registry}


if __name__ == "__main__":
    unittest.main()
