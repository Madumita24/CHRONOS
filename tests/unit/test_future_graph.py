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
from chronos.counterfactual_source import InputArtifactHash, load_source_state
from chronos.future_graph import (
    CANONICAL_DATASET_URN,
    CurrentToFutureIdentityMapping,
    FutureGraphEntryPreconditionError,
    FutureIdentityMappingClassification,
    FutureMetadataGraph,
    FuturePathClassification,
    FutureRelationshipState,
    GraphObjectState,
    ProvenanceKind,
    RelationshipEvaluationState,
    build_future_graph_from_artifacts,
    build_future_metadata_graph,
    export_future_graph,
    future_graph_semantic_fingerprint,
    load_future_graph,
    validate_future_metadata_graph,
)
from chronos.phase2_certification import (
    Phase2CertificationState,
    load_certification,
)
from chronos.proposal import load_proposal
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
INPUT_PATHS = (
    SNAPSHOT_PATH,
    PROPOSAL_PATH,
    VALIDATION_PATH,
    CONTRACT_PATH,
    CERTIFICATION_PATH,
    SOURCE_STATE_PATH,
)
CURRENT_SOURCE = FieldMachineKey(CANONICAL_DATASET_URN, "order_total")
FUTURE_SOURCE = FieldMachineKey(CANONICAL_DATASET_URN, "order_amount")
FORBIDDEN_STATES = {
    "broken",
    "impacted",
    "compatible",
    "incompatible",
    "safe",
    "risk",
    "requires_repair",
    "repair_required",
}


def fixed_clock(hour: int):
    return lambda: datetime(2026, 7, 28, hour, tzinfo=timezone.utc)


class FutureMetadataGraphTests(unittest.TestCase):
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
        cls.graph = cls.build(hour=1)

    @classmethod
    def build(cls, *, hour: int) -> FutureMetadataGraph:
        return build_future_graph_from_artifacts(
            SNAPSHOT_PATH,
            PROPOSAL_PATH,
            VALIDATION_PATH,
            CONTRACT_PATH,
            CERTIFICATION_PATH,
            SOURCE_STATE_PATH,
            clock=fixed_clock(hour),
        )

    def test_01_canonical_future_graph_construction(self) -> None:
        self.assertIsInstance(self.graph, FutureMetadataGraph)
        self.assertEqual(self.graph.demonstration_id, "CHRONOS-DEMO-001")
        self.assertEqual(self.graph.validation_state.value, "valid")

    def test_02_phase_entry_preconditions_are_certified(self) -> None:
        self.assertEqual(self.snapshot.validation_result.state.value, "valid")
        self.assertEqual(
            self.certification.certification_state,
            Phase2CertificationState.CERTIFIED,
        )
        self.assertEqual(
            self.source_state.state_classification.value,
            "counterfactual",
        )

    def test_03_twenty_one_dataset_identities_are_preserved(self) -> None:
        self.assertEqual(len(self.graph.dataset_registry), 21)
        self.assertEqual(
            {item.dataset_urn for item in self.graph.dataset_registry},
            {item.dataset_urn for item in self.snapshot.datasets},
        )

    def test_04_twenty_six_active_field_nodes_exist(self) -> None:
        self.assertEqual(len(self.graph.field_registry), 26)
        self.assertEqual(
            len({item.key for item in self.graph.field_registry}),
            26,
        )

    def test_05_current_source_is_not_active(self) -> None:
        self.assertNotIn(
            CURRENT_SOURCE,
            {item.key for item in self.graph.field_registry},
        )

    def test_06_candidate_source_exists_once(self) -> None:
        self.assertEqual(
            sum(item.key == FUTURE_SOURCE for item in self.graph.field_registry),
            1,
        )

    def test_07_twenty_five_downstream_identities_are_unchanged(self) -> None:
        current = {
            item.key
            for item in self.snapshot.fields
            if item.key != CURRENT_SOURCE
        }
        future = {
            item.key
            for item in self.graph.field_registry
            if item.key != FUTURE_SOURCE
        }
        self.assertEqual(len(future), 25)
        self.assertEqual(future, current)

    def test_08_source_dataset_identity_is_unchanged(self) -> None:
        dataset = next(
            item
            for item in self.graph.dataset_registry
            if item.dataset_urn == CANONICAL_DATASET_URN
        )
        self.assertEqual(dataset.dataset_urn, CANONICAL_DATASET_URN)
        self.assertEqual(dataset.platform, "postgres")
        self.assertEqual(dataset.environment, "PROD")

    def test_09_candidate_source_schema_is_integrated_exactly(self) -> None:
        self.assertEqual(
            self.graph.source_schema,
            self.source_state.candidate_source_schema,
        )
        self.assertEqual(len(self.graph.source_schema.fields), 15)

    def test_10_candidate_schema_replaces_only_the_source_name(self) -> None:
        paths = tuple(item.field_path for item in self.graph.source_schema.fields)
        self.assertNotIn("order_total", paths)
        self.assertEqual(paths.count("order_amount"), 1)
        expected = tuple(
            (
                "order_amount"
                if item.field_path == "order_total"
                else item.field_path
            )
            for item in self.snapshot.source_schema.fields
        )
        self.assertEqual(paths, expected)

    def test_11_candidate_source_is_changed(self) -> None:
        source = self.future_field(FUTURE_SOURCE)
        self.assertEqual(source.current_key, CURRENT_SOURCE)
        self.assertIs(source.state, GraphObjectState.COUNTERFACTUAL_CHANGED)

    def test_12_downstream_fields_are_unresolved(self) -> None:
        self.assertTrue(
            all(
                item.state is GraphObjectState.COUNTERFACTUAL_UNRESOLVED
                for item in self.graph.field_registry
                if item.key != FUTURE_SOURCE
            )
        )

    def test_13_identity_map_has_one_rename(self) -> None:
        renamed = [
            item
            for item in self.graph.current_to_future_identity_mappings
            if item.classification
            is FutureIdentityMappingClassification.RENAMED
        ]
        self.assertEqual(len(renamed), 1)
        self.assertEqual(renamed[0].current_identity, CURRENT_SOURCE)
        self.assertEqual(renamed[0].future_identity, FUTURE_SOURCE)

    def test_14_identity_map_has_twenty_five_preserved_entries(self) -> None:
        preserved = [
            item
            for item in self.graph.current_to_future_identity_mappings
            if item.classification
            is FutureIdentityMappingClassification.IDENTITY_PRESERVED
        ]
        self.assertEqual(len(preserved), 25)
        self.assertTrue(
            all(
                item.current_identity == item.future_identity
                for item in preserved
            )
        )

    def test_15_twenty_seven_structural_edges_are_preserved(self) -> None:
        self.assertEqual(len(self.graph.relationship_registry), 27)
        self.assertEqual(
            {item.current_edge_id for item in self.graph.relationship_registry},
            {item.edge_id for item in self.snapshot.lineage_edges},
        )

    def test_16_source_edge_is_rebased_only_at_source(self) -> None:
        edge = self.source_edge()
        self.assertEqual(edge.current_upstream, CURRENT_SOURCE)
        self.assertEqual(edge.upstream, FUTURE_SOURCE)
        self.assertEqual(edge.current_downstream, edge.downstream)
        self.assertEqual(edge.downstream.field_path, "order_total")

    def test_17_source_edge_is_projected_and_not_evaluated(self) -> None:
        edge = self.source_edge()
        self.assertIs(
            edge.relationship_state,
            FutureRelationshipState.COUNTERFACTUAL_PROJECTED,
        )
        self.assertIs(
            edge.evaluation_state,
            RelationshipEvaluationState.NOT_EVALUATED,
        )

    def test_18_remaining_edge_endpoints_are_unchanged(self) -> None:
        for item in self.graph.relationship_registry:
            if item.current_upstream == CURRENT_SOURCE:
                continue
            self.assertEqual(item.upstream, item.current_upstream)
            self.assertEqual(item.downstream, item.current_downstream)

    def test_19_every_edge_endpoint_exists(self) -> None:
        fields = {item.key for item in self.graph.field_registry}
        for item in self.graph.relationship_registry:
            self.assertIn(item.upstream, fields)
            self.assertIn(item.downstream, fields)

    def test_20_all_relationship_compatibility_is_not_evaluated(self) -> None:
        self.assertTrue(
            all(
                item.evaluation_state
                is RelationshipEvaluationState.NOT_EVALUATED
                for item in self.graph.relationship_registry
            )
        )

    def test_21_current_edge_provenance_is_retained(self) -> None:
        edge = self.source_edge()
        records = self.provenance(edge.provenance_ids)
        current = [
            item for item in records
            if item.kind is ProvenanceKind.CURRENT_EVIDENCE
        ]
        self.assertEqual(len(current), 1)
        self.assertEqual(current[0].source_object_key, edge.current_edge_id)
        self.assertEqual(
            current[0].source_artifact_fingerprint,
            self.snapshot.semantic_fingerprint,
        )

    def test_22_twenty_eight_mapping_groups_are_retained(self) -> None:
        self.assertEqual(len(self.graph.mapping_group_registry), 28)
        self.assertEqual(
            {item.group_id for item in self.graph.mapping_group_registry},
            {item.group_id for item in self.snapshot.mapping_groups},
        )

    def test_23_current_mapping_evidence_is_not_rewritten(self) -> None:
        current = {
            item.group_id: item for item in self.snapshot.mapping_groups
        }
        for future in self.graph.mapping_group_registry:
            source = current[future.group_id]
            self.assertEqual(
                future.current_upstream_fields,
                source.upstream_fields,
            )
            self.assertEqual(
                future.current_downstream_fields,
                source.downstream_fields,
            )
            self.assertEqual(
                future.current_raw_upstream_references,
                source.raw_upstream_references,
            )
            self.assertEqual(
                future.current_raw_downstream_references,
                source.raw_downstream_references,
            )

    def test_24_only_source_mapping_projection_changes_identity(self) -> None:
        changed = [
            item
            for item in self.graph.mapping_group_registry
            if item.relationship_state
            is FutureRelationshipState.COUNTERFACTUAL_PROJECTED
        ]
        self.assertEqual(len(changed), 1)
        self.assertIn(CURRENT_SOURCE, changed[0].current_upstream_fields)
        self.assertIn(FUTURE_SOURCE, changed[0].projected_upstream_fields)
        self.assertEqual(
            changed[0].current_downstream_fields,
            changed[0].projected_downstream_fields,
        )

    def test_25_forty_eight_current_paths_are_retained(self) -> None:
        self.assertEqual(len(self.graph.path_registry), 48)
        expected = {
            (
                tuple(item.node_keys),
                tuple(item.edge_ids),
            )
            for item in self.snapshot.lineage_paths
        }
        observed = {
            (
                item.current_node_keys,
                item.current_edge_ids,
            )
            for item in self.graph.path_registry
        }
        self.assertEqual(observed, expected)

    def test_26_projected_paths_rebase_source_only(self) -> None:
        for item in self.graph.path_registry:
            self.assertEqual(item.current_node_keys[0], CURRENT_SOURCE)
            self.assertEqual(item.projected_node_keys[0], FUTURE_SOURCE)
            self.assertEqual(
                item.projected_node_keys[1:],
                item.current_node_keys[1:],
            )

    def test_27_paths_are_counterfactual_structure_only(self) -> None:
        self.assertTrue(
            all(
                item.classification
                is FuturePathClassification.COUNTERFACTUAL_STRUCTURE
                and item.evaluation_state
                is RelationshipEvaluationState.NOT_EVALUATED
                for item in self.graph.path_registry
            )
        )

    def test_28_maximum_structural_depth_is_five(self) -> None:
        self.assertEqual(self.graph.maximum_structural_depth, 5)
        self.assertEqual(self.future_field(FUTURE_SOURCE).structural_depth, 0)

    def test_29_context_relationships_are_preserved(self) -> None:
        current = {
            item.relationship_id: item
            for item in self.snapshot.relationships
            if item.category is not RelationshipCategory.FIELD_LINEAGE
        }
        self.assertEqual(len(self.graph.context_relationship_registry), 225)
        self.assertEqual(
            {
                item.current_relationship_id
                for item in self.graph.context_relationship_registry
            },
            set(current),
        )
        for item in self.graph.context_relationship_registry:
            source = current[item.current_relationship_id]
            self.assertEqual(item.category, source.category)
            self.assertEqual(item.source_key, source.source_key)
            self.assertEqual(item.target_key, source.target_key)
            self.assertEqual(item.relationship_path, source.relationship_path)

    def test_30_governance_context_is_unchanged(self) -> None:
        categories = {
            RelationshipCategory.OWNERSHIP,
            RelationshipCategory.DOMAIN_ASSIGNMENT,
            RelationshipCategory.TAG_ASSIGNMENT,
            RelationshipCategory.GLOSSARY_ASSIGNMENT,
            RelationshipCategory.STRUCTURED_PROPERTY_ASSIGNMENT,
        }
        expected = Counter(
            item.category
            for item in self.snapshot.relationships
            if item.category in categories
        )
        observed = Counter(
            item.category
            for item in self.graph.context_relationship_registry
            if item.category in categories
        )
        self.assertEqual(observed, expected)

    def test_31_bi_context_is_unchanged(self) -> None:
        self.assert_category_count(
            RelationshipCategory.BI_REACHABLE_CONTEXT,
            15,
        )

    def test_32_pipeline_context_is_unchanged(self) -> None:
        self.assert_category_count(RelationshipCategory.PIPELINE_CONTEXT, 4)

    def test_33_data_product_and_document_context_is_unchanged(self) -> None:
        self.assert_category_count(
            RelationshipCategory.DATA_PRODUCT_MEMBERSHIP,
            4,
        )
        self.assert_category_count(
            RelationshipCategory.DOCUMENT_RELATIONSHIP,
            18,
        )

    def test_34_structured_property_definitions_are_preserved(self) -> None:
        self.assertEqual(len(self.graph.structured_property_registry), 5)
        self.assertEqual(
            {
                item.property_urn
                for item in self.graph.structured_property_registry
            },
            {
                item.property_urn
                for item in self.snapshot.structured_property_definitions
            },
        )

    def test_35_current_provenance_exists_for_every_graph_entity(self) -> None:
        registries = (
            self.graph.dataset_registry,
            self.graph.field_registry,
            self.graph.relationship_registry,
            self.graph.mapping_group_registry,
            self.graph.context_relationship_registry,
            self.graph.structured_property_registry,
        )
        for registry in registries:
            for item in registry:
                self.assertTrue(
                    any(
                        record.kind is ProvenanceKind.CURRENT_EVIDENCE
                        for record in self.provenance(item.provenance_ids)
                    )
                )

    def test_36_counterfactual_provenance_is_complete(self) -> None:
        records = [
            item
            for item in self.graph.provenance_registry
            if item.kind is ProvenanceKind.COUNTERFACTUAL_DERIVATION
        ]
        self.assertGreater(len(records), 0)
        for item in records:
            self.assertEqual(item.proposal_id, self.proposal.proposal_id)
            self.assertEqual(
                item.proposal_fingerprint,
                self.proposal.semantic_fingerprint,
            )
            self.assertEqual(
                item.semantic_contract_fingerprint,
                self.contract.semantic_fingerprint,
            )
            self.assertEqual(
                item.counterfactual_source_state_fingerprint,
                self.source_state.semantic_fingerprint,
            )
            self.assertIsNotNone(item.projection_classification)

    def test_37_every_graph_object_has_one_state_annotation(self) -> None:
        self.assertEqual(len(self.graph.state_annotations), 406)
        keys = {
            (item.object_type, item.object_key)
            for item in self.graph.state_annotations
        }
        self.assertEqual(len(keys), len(self.graph.state_annotations))
        self.assertEqual(
            Counter(item.object_type for item in self.graph.state_annotations),
            {
                "dataset": 21,
                "field": 26,
                "lineage_relationship": 27,
                "mapping_group": 28,
                "lineage_path": 48,
                "context_relationship": 225,
                "structured_property_definition": 5,
                "identity_mapping": 26,
            },
        )

    def test_38_no_impact_or_compatibility_state_exists(self) -> None:
        raw = json.dumps(self.graph.to_dict()).lower()
        state_values = {
            value
            for value in (
                item.object_state.value
                for item in self.graph.state_annotations
            )
        } | {
            item.evaluation_state.value
            for item in self.graph.state_annotations
            if item.evaluation_state is not None
        }
        self.assertTrue(state_values.isdisjoint(FORBIDDEN_STATES))
        for token in (
            '"broken"',
            '"impacted"',
            '"compatible"',
            '"incompatible"',
            '"safe"',
            '"risk"',
            '"requires_repair"',
            '"repair_required"',
        ):
            self.assertNotIn(token, raw)

    def test_39_no_downstream_field_is_renamed_added_or_removed(self) -> None:
        mappings = [
            item
            for item in self.graph.current_to_future_identity_mappings
            if item.current_identity != CURRENT_SOURCE
        ]
        self.assertEqual(len(mappings), 25)
        self.assertTrue(
            all(
                item.current_identity == item.future_identity
                for item in mappings
            )
        )

    def test_40_no_dataset_or_datahub_urn_is_fabricated(self) -> None:
        current_urns = {item.dataset_urn for item in self.snapshot.datasets}
        self.assertTrue(
            all(
                item.key.dataset_urn in current_urns
                for item in self.graph.field_registry
            )
        )
        self.assertIsNone(self.future_field(FUTURE_SOURCE).schema_field_urn)

    def test_41_current_snapshot_and_all_inputs_are_immutable(self) -> None:
        self.build(hour=2)
        for path, expected in self.input_hashes.items():
            self.assertEqual(
                hashlib.sha256(path.read_bytes()).hexdigest(),
                expected,
            )
        self.assertTrue(
            all(item.unchanged for item in self.graph.input_artifact_hashes)
        )

    def test_42_future_graph_is_a_separate_immutable_object(self) -> None:
        self.assertIsNot(self.graph, self.snapshot)
        with self.assertRaises(FrozenInstanceError):
            self.graph.created_at = "changed"  # type: ignore[misc]

    def test_43_deterministic_registry_ordering(self) -> None:
        self.assertEqual(
            [item.dataset_urn for item in self.graph.dataset_registry],
            sorted(item.dataset_urn for item in self.graph.dataset_registry),
        )
        self.assertEqual(
            [item.current_key.text for item in self.graph.field_registry],
            sorted(
                item.current_key.text for item in self.graph.field_registry
            ),
        )
        self.assertEqual(
            [
                item.current_edge_id
                for item in self.graph.relationship_registry
            ],
            sorted(
                item.current_edge_id
                for item in self.graph.relationship_registry
            ),
        )
        self.assertEqual(
            [item.group_id for item in self.graph.mapping_group_registry],
            sorted(item.group_id for item in self.graph.mapping_group_registry),
        )
        self.assertEqual(
            [item.provenance_id for item in self.graph.provenance_registry],
            sorted(
                item.provenance_id for item in self.graph.provenance_registry
            ),
        )

    def test_44_serialization_is_deterministic(self) -> None:
        first = self.build(hour=3)
        second = self.build(hour=3)
        self.assertEqual(first.to_json(), second.to_json())

    def test_45_timestamp_does_not_change_semantic_fingerprint(self) -> None:
        first = self.build(hour=4)
        second = self.build(hour=5)
        self.assertNotEqual(first.created_at, second.created_at)
        self.assertEqual(
            first.semantic_fingerprint,
            second.semantic_fingerprint,
        )
        self.assertTrue(first.semantically_equals(second))

    def test_46_candidate_source_change_changes_fingerprint(self) -> None:
        fields = tuple(
            replace(item, field_name="order_amount_probe")
            if item.key == FUTURE_SOURCE
            else item
            for item in self.graph.field_registry
        )
        changed = replace(self.graph, field_registry=fields)
        self.assert_fingerprint_changed(changed)

    def test_47_field_node_identity_change_changes_fingerprint(self) -> None:
        changed = self.with_rekeyed_downstream_field()
        self.assert_fingerprint_changed(changed)

    def test_48_structural_edge_change_changes_fingerprint(self) -> None:
        first = self.graph.relationship_registry[0]
        alternate = next(
            item.key
            for item in self.graph.field_registry
            if item.key not in {first.upstream, first.downstream}
        )
        relationships = (
            replace(first, downstream=alternate),
            *self.graph.relationship_registry[1:],
        )
        changed = replace(
            self.graph,
            relationship_registry=relationships,
        )
        self.assert_fingerprint_changed(changed)

    def test_49_dataset_registry_change_changes_fingerprint(self) -> None:
        first = self.graph.dataset_registry[0]
        datasets = (
            replace(first, display_identity="fingerprint probe"),
            *self.graph.dataset_registry[1:],
        )
        changed = replace(self.graph, dataset_registry=datasets)
        self.assert_fingerprint_changed(changed)

    def test_50_context_relationship_change_changes_fingerprint(self) -> None:
        first = self.graph.context_relationship_registry[0]
        context = (
            replace(first, current_state="fingerprint_probe"),
            *self.graph.context_relationship_registry[1:],
        )
        changed = replace(
            self.graph,
            context_relationship_registry=context,
        )
        self.assert_fingerprint_changed(changed)

    def test_51_state_annotation_change_changes_fingerprint(self) -> None:
        first = self.graph.state_annotations[0]
        annotations = (
            replace(first, rationale=first.rationale + " Probe."),
            *self.graph.state_annotations[1:],
        )
        changed = replace(self.graph, state_annotations=annotations)
        self.assert_fingerprint_changed(changed)

    def test_52_input_fingerprint_change_changes_fingerprint(self) -> None:
        changed = replace(
            self.graph,
            current_snapshot_fingerprint="sha256:" + ("0" * 64),
        )
        self.assert_fingerprint_changed(changed)

    def test_53_round_trip_serialization(self) -> None:
        restored = FutureMetadataGraph.from_json(self.graph.to_json())
        self.assertEqual(restored, self.graph)
        self.assertTrue(restored.semantically_equals(self.graph))

    def test_54_export_and_load_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "future.json"
            export_future_graph(self.graph, path)
            self.assertEqual(load_future_graph(path), self.graph)

    def test_55_generated_graph_contains_no_secrets(self) -> None:
        self.assertFalse(contains_secret(self.graph.to_dict()))

    def test_56_build_performs_no_datahub_or_network_request(self) -> None:
        with patch.object(
            socket,
            "create_connection",
            side_effect=AssertionError("network access attempted"),
        ):
            graph = build_future_metadata_graph(
                self.snapshot,
                self.proposal,
                self.validation,
                self.contract,
                self.certification,
                self.source_state,
                input_artifact_hashes=self.graph.input_artifact_hashes,
                clock=fixed_clock(6),
            )
        self.assertEqual(len(graph.field_registry), 26)

    def test_57_changed_input_hash_fails_closed(self) -> None:
        first, *rest = self.graph.input_artifact_hashes
        bad_hash = "f" * 64
        if first.before_sha256 == bad_hash:
            bad_hash = "e" * 64
        hashes = (
            InputArtifactHash(
                first.artifact_name,
                first.before_sha256,
                bad_hash,
            ),
            *rest,
        )
        with self.assertRaises(FutureGraphEntryPreconditionError):
            build_future_metadata_graph(
                self.snapshot,
                self.proposal,
                self.validation,
                self.contract,
                self.certification,
                self.source_state,
                input_artifact_hashes=hashes,
                clock=fixed_clock(7),
            )

    def test_58_public_validator_accepts_only_canonical_structure(self) -> None:
        validate_future_metadata_graph(
            self.graph,
            self.snapshot,
            self.proposal,
            self.validation,
            self.contract,
            self.certification,
            self.source_state,
        )

    def test_59_future_graph_artifact_matches_canonical_build(self) -> None:
        artifact = load_future_graph(FUTURE_GRAPH_PATH)
        self.assertTrue(artifact.semantically_equals(self.graph))

    def test_60_semantic_fingerprint_reproduces(self) -> None:
        self.assertEqual(
            future_graph_semantic_fingerprint(self.graph),
            self.graph.semantic_fingerprint,
        )

    def future_field(self, key: FieldMachineKey):
        return next(item for item in self.graph.field_registry if item.key == key)

    def source_edge(self):
        return next(
            item
            for item in self.graph.relationship_registry
            if item.current_upstream == CURRENT_SOURCE
        )

    def provenance(self, provenance_ids: tuple[str, ...]):
        by_id = {
            item.provenance_id: item
            for item in self.graph.provenance_registry
        }
        return tuple(by_id[value] for value in provenance_ids)

    def assert_category_count(
        self,
        category: RelationshipCategory,
        expected: int,
    ) -> None:
        current = sum(
            item.category is category for item in self.snapshot.relationships
        )
        future = sum(
            item.category is category
            for item in self.graph.context_relationship_registry
        )
        self.assertEqual(current, expected)
        self.assertEqual(future, expected)

    def assert_fingerprint_changed(self, changed: FutureMetadataGraph) -> None:
        self.assertNotEqual(
            changed.semantic_fingerprint,
            self.graph.semantic_fingerprint,
        )

    def with_rekeyed_downstream_field(self) -> FutureMetadataGraph:
        target = next(
            item for item in self.graph.field_registry
            if item.key != FUTURE_SOURCE
        )
        old = target.key
        new = FieldMachineKey(old.dataset_urn, old.field_path + "_fp_probe")

        def project(value: FieldMachineKey) -> FieldMachineKey:
            return new if value == old else value

        datasets = tuple(
            replace(
                item,
                active_lineage_field_keys=tuple(
                    project(value) for value in item.active_lineage_field_keys
                ),
            )
            for item in self.graph.dataset_registry
        )
        fields = tuple(
            replace(item, key=new, field_name=new.field_path)
            if item.key == old
            else item
            for item in self.graph.field_registry
        )
        relationships = tuple(
            replace(
                item,
                upstream=project(item.upstream),
                downstream=project(item.downstream),
            )
            for item in self.graph.relationship_registry
        )
        groups = tuple(
            replace(
                item,
                projected_upstream_fields=tuple(
                    project(value)
                    for value in item.projected_upstream_fields
                ),
                projected_downstream_fields=tuple(
                    project(value)
                    for value in item.projected_downstream_fields
                ),
            )
            for item in self.graph.mapping_group_registry
        )
        paths = tuple(
            replace(
                item,
                projected_node_keys=tuple(
                    project(value) for value in item.projected_node_keys
                ),
            )
            for item in self.graph.path_registry
        )
        mappings = tuple(
            replace(item, future_identity=new)
            if item.future_identity == old
            else item
            for item in self.graph.current_to_future_identity_mappings
        )
        old_mapping_key = f"{old.text}->{old.text}"
        new_mapping_key = f"{old.text}->{new.text}"
        annotations = tuple(
            replace(item, object_key=new.text)
            if item.object_type == "field" and item.object_key == old.text
            else (
                replace(item, object_key=new_mapping_key)
                if (
                    item.object_type == "identity_mapping"
                    and item.object_key == old_mapping_key
                )
                else item
            )
            for item in self.graph.state_annotations
        )
        return replace(
            self.graph,
            dataset_registry=datasets,
            field_registry=fields,
            relationship_registry=relationships,
            mapping_group_registry=groups,
            path_registry=paths,
            current_to_future_identity_mappings=mappings,
            state_annotations=annotations,
        )


if __name__ == "__main__":
    unittest.main()
