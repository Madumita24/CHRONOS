from __future__ import annotations

import json
import unittest
from collections import Counter
from dataclasses import replace
from pathlib import Path

from chronos.datahub._transport import (
    ContextReadOnlyTransport,
    LineageReadOnlyTransport,
    ReadOnlyTransport,
)
from chronos.snapshot import (
    CurrentMetadataSnapshot,
    EvidenceClassification,
    FieldMachineKey,
    RelationshipCategory,
    SnapshotValidationState,
    contains_secret,
    load_snapshot,
    semantic_fingerprint,
)


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "artifacts" / "current_metadata_snapshot.json"
SOURCE_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:postgres,"
    "b2fd91.order_entry_db.order_entry.orders,PROD)"
)
SNOWFLAKE_ORDERS_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:snowflake,"
    "b2fd91.order_entry_db.order_entry.orders,PROD)"
)
SOURCE_KEY = FieldMachineKey(SOURCE_URN, "order_total")
FORBIDDEN_CURRENT_TERMS = (
    "order_amount",
    "broken",
    "impacted",
    "high_risk",
    "requires_repair",
    "fixed",
    "future",
    "predicted_failure",
)
SECRET_TERMS = (
    "datahub_token",
    "authorization",
    "bearer",
    "password",
    "access_token",
)


class Phase1CertificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw = ARTIFACT.read_text(encoding="utf-8")
        cls.snapshot = load_snapshot(ARTIFACT)
        cls.summary = cls.snapshot.summary()
        cls.datasets = cls.snapshot.dataset_by_urn()
        cls.fields = cls.snapshot.field_by_key()
        cls.evidence = cls.snapshot.evidence_by_id()
        cls.relationship_counts = Counter(
            item.category for item in cls.snapshot.relationships
        )

    def test_01_artifact_loads_through_public_deserializer(self) -> None:
        self.assertIsInstance(self.snapshot, CurrentMetadataSnapshot)

    def test_02_snapshot_schema_version_is_supported(self) -> None:
        self.assertEqual(self.snapshot.metadata.snapshot_schema_version, "1.0")

    def test_03_embedded_validation_is_valid(self) -> None:
        self.assertEqual(
            self.snapshot.validation_result.state,
            SnapshotValidationState.VALID,
        )
        self.assertEqual(self.snapshot.validation_result.findings, ())

    def test_04_scoped_dataset_count(self) -> None:
        self.assertEqual(self.summary.dataset_count, 21)

    def test_05_complete_source_schema_count(self) -> None:
        self.assertEqual(self.summary.source_schema_field_count, 15)

    def test_06_lineage_field_node_count(self) -> None:
        self.assertEqual(self.summary.lineage_field_node_count, 26)

    def test_07_unique_downstream_field_count(self) -> None:
        self.assertEqual(self.summary.downstream_field_count, 25)

    def test_08_unique_downstream_dataset_count(self) -> None:
        self.assertEqual(self.summary.downstream_dataset_count, 20)

    def test_09_maximum_field_depth(self) -> None:
        self.assertEqual(self.summary.maximum_field_depth, 5)

    def test_10_source_identity_exists_exactly_once(self) -> None:
        self.assertEqual(self.snapshot.source_dataset_urn, SOURCE_URN)
        self.assertEqual(self.snapshot.source_field_key, SOURCE_KEY)
        self.assertEqual(
            sum(item.dataset_urn == SOURCE_URN for item in self.snapshot.datasets),
            1,
        )
        self.assertEqual(
            sum(item.key == SOURCE_KEY for item in self.snapshot.fields),
            1,
        )

    def test_11_dataset_and_field_machine_keys_are_unique(self) -> None:
        self.assertEqual(len(self.datasets), len(self.snapshot.datasets))
        self.assertEqual(len(self.fields), len(self.snapshot.fields))

    def test_12_postgres_and_snowflake_orders_are_distinct(self) -> None:
        self.assertIn(SOURCE_URN, self.datasets)
        self.assertIn(SNOWFLAKE_ORDERS_URN, self.datasets)
        self.assertNotEqual(SOURCE_URN, SNOWFLAKE_ORDERS_URN)
        self.assertEqual(self.datasets[SOURCE_URN].platform, "postgres")
        self.assertEqual(
            self.datasets[SNOWFLAKE_ORDERS_URN].platform,
            "snowflake",
        )

    def test_13_display_names_are_not_machine_keys(self) -> None:
        self.assertTrue(
            all(item.dataset_urn.startswith("urn:li:dataset:") for item in self.snapshot.datasets)
        )
        self.assertTrue(
            all(item.key.dataset_urn.startswith("urn:li:dataset:") for item in self.snapshot.fields)
        )
        self.assertTrue(
            all(
                item.display_identity != item.dataset_urn
                for item in self.snapshot.datasets
                if item.display_identity is not None
            )
        )

    def test_14_every_field_parent_dataset_exists(self) -> None:
        self.assertEqual(
            [
                item.key.text
                for item in self.snapshot.fields
                if item.key.dataset_urn not in self.datasets
            ],
            [],
        )

    def test_15_complete_source_schema_inventory_matches_phase_1_3(self) -> None:
        expected = (
            "order_id",
            "order_date",
            "order_mode",
            "customer_id",
            "order_status",
            "order_total",
            "sales_rep_id",
            "promotion_id",
            "warehouse_id",
            "delivery_type",
            "cost_of_delivery",
            "wait_till_complete_yn",
            "billing_address_id",
            "delivery_address_id",
            "payment_method_code",
        )
        self.assertEqual(
            tuple(item.field_path for item in self.snapshot.source_schema.fields),
            expected,
        )
        self.assertEqual(
            tuple(item.position for item in self.snapshot.source_schema.fields),
            tuple(range(15)),
        )

    def test_16_order_total_schema_evidence_is_exact(self) -> None:
        observed = [
            item
            for item in self.snapshot.source_schema.fields
            if item.field_path == "order_total"
        ]
        self.assertEqual(len(observed), 1)
        field = observed[0]
        self.assertEqual(field.position, 5)
        self.assertEqual(field.native_type, "DOUBLE PRECISION")
        self.assertEqual(field.normalized_type, "Number")
        self.assertIs(field.nullable, True)
        self.assertIs(field.is_part_of_key, False)
        self.assertIsNone(field.description)
        self.assertIsNone(field.schema_field_urn)
        self.assertTrue(
            all(
                item.description is None
                for item in self.snapshot.source_schema.fields
            )
        )
        self.assertTrue(
            all(
                item.schema_field_urn is None
                for item in self.snapshot.source_schema.fields
            )
        )

    def test_17_source_node_is_depth_zero_and_not_a_descendant(self) -> None:
        self.assertEqual(self.fields[SOURCE_KEY].lineage_depth, 0)
        descendants = {
            item.key
            for item in self.snapshot.fields
            if item.key != SOURCE_KEY
        }
        self.assertNotIn(SOURCE_KEY, descendants)
        self.assertEqual(len(descendants), 25)

    def test_18_explicit_edge_and_mapping_group_counts(self) -> None:
        self.assertEqual(len(self.snapshot.lineage_edges), 27)
        self.assertEqual(len(self.snapshot.mapping_groups), 28)

    def test_19_all_edge_endpoints_are_graph_fields(self) -> None:
        self.assertTrue(
            all(
                item.upstream in self.fields and item.downstream in self.fields
                for item in self.snapshot.lineage_edges
            )
        )

    def test_20_paths_are_structurally_valid_and_multiple_paths_remain(self) -> None:
        edge_ids = {item.edge_id for item in self.snapshot.lineage_edges}
        self.assertEqual(len(self.snapshot.lineage_paths), 48)
        self.assertTrue(
            all(
                key in self.fields
                for path in self.snapshot.lineage_paths
                for key in path.node_keys
            )
        )
        self.assertTrue(
            all(
                edge_id in edge_ids
                for path in self.snapshot.lineage_paths
                for edge_id in path.edge_ids
            )
        )
        targets = Counter(path.node_keys[-1] for path in self.snapshot.lineage_paths)
        self.assertEqual(sum(count > 1 for count in targets.values()), 21)

    def test_21_mapping_group_provenance_is_resolved(self) -> None:
        groups = {item.group_id: item for item in self.snapshot.mapping_groups}
        self.assertTrue(
            all(
                group_id in groups
                for edge in self.snapshot.lineage_edges
                for group_id in edge.mapping_group_ids
            )
        )
        self.assertTrue(
            all(item.evidence_ids for item in self.snapshot.mapping_groups)
        )
        self.assertTrue(
            all(
                evidence_id in self.evidence
                for item in self.snapshot.mapping_groups
                for evidence_id in item.evidence_ids
            )
        )

    def test_22_lineage_classification_is_not_strengthened(self) -> None:
        classifications = Counter(
            item.classification for item in self.snapshot.lineage_edges
        )
        self.assertEqual(classifications, {"direct": 5, "unknown": 22})
        direct = [
            item
            for item in self.snapshot.lineage_edges
            if item.classification == "direct"
        ]
        unknown = [
            item
            for item in self.snapshot.lineage_edges
            if item.classification == "unknown"
        ]
        self.assertTrue(all(item.transform_operations for item in direct))
        self.assertTrue(all(not item.transform_operations for item in unknown))
        self.assertEqual(
            sorted(
                {
                    value
                    for item in self.snapshot.lineage_edges
                    for value in item.confidence_scores
                }
            ),
            [0.4, 0.5, 0.9, 1.0],
        )

    def test_23_charts_and_dashboards_are_not_field_lineage(self) -> None:
        fields = {item.key.text for item in self.snapshot.fields}
        field_lineage = [
            item
            for item in self.snapshot.relationships
            if item.category is RelationshipCategory.FIELD_LINEAGE
        ]
        self.assertEqual(len(field_lineage), 27)
        self.assertTrue(
            all(item.source_key in fields and item.target_key in fields for item in field_lineage)
        )
        self.assertTrue(
            all(
                "chart" not in item.source_key.casefold()
                and "dashboard" not in item.source_key.casefold()
                and "chart" not in item.target_key.casefold()
                and "dashboard" not in item.target_key.casefold()
                for item in field_lineage
            )
        )

    def test_24_governance_counts_match_authoritative_snapshot(self) -> None:
        expected = {
            RelationshipCategory.OWNERSHIP: 27,
            RelationshipCategory.DOMAIN_ASSIGNMENT: 6,
            RelationshipCategory.TAG_ASSIGNMENT: 8,
            RelationshipCategory.GLOSSARY_ASSIGNMENT: 38,
            RelationshipCategory.STRUCTURED_PROPERTY_ASSIGNMENT: 105,
            RelationshipCategory.DATA_PRODUCT_MEMBERSHIP: 4,
            RelationshipCategory.DOCUMENT_RELATIONSHIP: 18,
        }
        for category, count in expected.items():
            self.assertEqual(self.relationship_counts[category], count)
        self.assertEqual(
            len(self.snapshot.structured_property_definitions),
            5,
        )

    def test_25_governance_is_machine_bound_and_not_propagated(self) -> None:
        known_subjects = set(self.datasets) | {
            item.key.text for item in self.snapshot.fields
        }
        governance_categories = {
            RelationshipCategory.OWNERSHIP,
            RelationshipCategory.DOMAIN_ASSIGNMENT,
            RelationshipCategory.TAG_ASSIGNMENT,
            RelationshipCategory.GLOSSARY_ASSIGNMENT,
            RelationshipCategory.STRUCTURED_PROPERTY_ASSIGNMENT,
        }
        governance = [
            item
            for item in self.snapshot.relationships
            if item.category in governance_categories
        ]
        self.assertTrue(
            all(item.source_key in known_subjects for item in governance)
        )
        source_states = {
            item.name: item.values[0]
            for item in self.datasets[SOURCE_URN].metadata_states
        }
        self.assertEqual(source_states["ownership"], "absent")
        self.assertEqual(source_states["domain"], "absent")
        self.assertEqual(source_states["tag"], "absent")
        self.assertFalse(
            any(
                item.category is RelationshipCategory.OWNERSHIP
                and item.source_key == SOURCE_URN
                for item in self.snapshot.relationships
            )
        )

    def test_26_context_categories_and_counts_are_separate(self) -> None:
        expected_categories = set(RelationshipCategory)
        self.assertEqual(
            {item.category for item in self.snapshot.relationships},
            expected_categories,
        )
        self.assertEqual(
            self.relationship_counts[RelationshipCategory.PIPELINE_CONTEXT],
            4,
        )
        self.assertEqual(
            self.relationship_counts[
                RelationshipCategory.BI_REACHABLE_CONTEXT
            ],
            15,
        )
        dashboards = [
            item
            for item in self.snapshot.relationships
            if item.category is RelationshipCategory.BI_REACHABLE_CONTEXT
            and any(
                attribute.name == "entity_type"
                and attribute.values == ("DASHBOARD",)
                for attribute in item.attributes
            )
        ]
        self.assertEqual(len(dashboards), 3)
        self.assertTrue(
            all(
                any(
                    attribute.name == "classification"
                    and attribute.values == ("reachable_context",)
                    for attribute in item.attributes
                )
                for item in dashboards
            )
        )

    def test_27_unresolved_reference_is_preserved_without_guess(self) -> None:
        unresolved = [
            item for item in self.snapshot.relationships if item.state == "unresolved"
        ]
        self.assertEqual(len(unresolved), 1)
        self.assertEqual(
            unresolved[0].target_key,
            "urn:li:tag:b2fd91.ecommerce",
        )
        self.assertEqual(
            unresolved[0].category,
            RelationshipCategory.TAG_ASSIGNMENT,
        )

    def test_28_all_important_components_have_valid_evidence(self) -> None:
        collections = (
            self.snapshot.datasets,
            self.snapshot.fields,
            self.snapshot.lineage_edges,
            self.snapshot.mapping_groups,
            self.snapshot.structured_property_definitions,
            self.snapshot.relationships,
        )
        self.assertTrue(
            all(item.evidence_ids for collection in collections for item in collection)
        )
        self.assertTrue(
            all(
                evidence_id in self.evidence
                for collection in collections
                for item in collection
                for evidence_id in item.evidence_ids
            )
        )

    def test_29_evidence_classification_counts_are_exact(self) -> None:
        classifications = Counter(
            item.classification for item in self.snapshot.evidence
        )
        self.assertEqual(
            classifications[EvidenceClassification.VERIFIED],
            560,
        )
        self.assertEqual(
            classifications[EvidenceClassification.UNKNOWN],
            1,
        )
        self.assertEqual(
            classifications[EvidenceClassification.DERIVED],
            0,
        )

    def test_30_future_field_is_absent_from_current_metadata(self) -> None:
        self.assertNotIn("order_amount", self.raw.casefold())
        self.assertNotIn(
            "order_amount",
            {item.field_path.casefold() for item in self.snapshot.source_schema.fields},
        )
        self.assertNotIn(
            "order_amount",
            {item.key.field_path.casefold() for item in self.snapshot.fields},
        )

    def test_31_forbidden_semantics_are_absent(self) -> None:
        artifact = self.raw.casefold()
        for term in FORBIDDEN_CURRENT_TERMS:
            self.assertNotIn(term, artifact)

    def test_32_serialized_artifact_contains_no_secret(self) -> None:
        raw = self.raw.casefold()
        for term in SECRET_TERMS:
            self.assertNotIn(term, raw)
        self.assertFalse(contains_secret(json.loads(self.raw)))

    def test_33_datahub_runtime_protocols_are_read_only(self) -> None:
        write_verbs = {
            "create",
            "update",
            "delete",
            "patch",
            "upsert",
            "emit",
            "rollback",
            "mutate",
            "mutation",
        }
        for protocol in (
            ReadOnlyTransport,
            LineageReadOnlyTransport,
            ContextReadOnlyTransport,
        ):
            public_methods = {
                name
                for name, value in protocol.__dict__.items()
                if callable(value) and not name.startswith("_")
            }
            self.assertTrue(public_methods.isdisjoint(write_verbs))

    def test_34_recorded_semantic_fingerprint_reproduces(self) -> None:
        self.assertEqual(
            semantic_fingerprint(self.snapshot),
            self.snapshot.semantic_fingerprint,
        )
        self.assertEqual(
            self.snapshot.semantic_fingerprint,
            "sha256:774185f19c6fea113ef7adfc5e14583e05e7e08a1fad0c59bd6c6fad755db72c",
        )

    def test_35_deterministic_serialization(self) -> None:
        self.assertEqual(self.snapshot.to_json(), self.snapshot.to_json())
        self.assertEqual(
            self.snapshot.semantic_json(),
            self.snapshot.semantic_json(),
        )

    def test_36_serialization_round_trip_preserves_semantics(self) -> None:
        reloaded = CurrentMetadataSnapshot.from_json(self.snapshot.to_json())
        self.assertTrue(self.snapshot.semantically_equals(reloaded))
        self.assertEqual(
            self.snapshot.dataset_by_urn(),
            reloaded.dataset_by_urn(),
        )
        self.assertEqual(
            self.snapshot.field_by_key(),
            reloaded.field_by_key(),
        )
        self.assertEqual(self.snapshot.relationships, reloaded.relationships)
        self.assertEqual(self.snapshot.evidence, reloaded.evidence)

    def test_37_observation_times_do_not_change_fingerprint(self) -> None:
        changed = replace(
            self.snapshot,
            metadata=replace(
                self.snapshot.metadata,
                snapshot_id="snapshot-certification-observation",
                created_at="2030-01-01T00:00:00+00:00",
            ),
            evidence=tuple(
                replace(item, observed_at="2030-01-01T00:00:00+00:00")
                for item in self.snapshot.evidence
            ),
        )
        self.assertEqual(
            semantic_fingerprint(changed),
            self.snapshot.semantic_fingerprint,
        )

    def test_38_no_dangling_relationship_or_mapping_reference(self) -> None:
        field_keys = {item.key.text for item in self.snapshot.fields}
        group_ids = {item.group_id for item in self.snapshot.mapping_groups}
        self.assertTrue(
            all(
                group_id in group_ids
                for edge in self.snapshot.lineage_edges
                for group_id in edge.mapping_group_ids
            )
        )
        self.assertTrue(
            all(
                item.source_key in field_keys
                and item.target_key in field_keys
                for item in self.snapshot.relationships
                if item.category is RelationshipCategory.FIELD_LINEAGE
            )
        )


if __name__ == "__main__":
    unittest.main()
