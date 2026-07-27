from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from chronos.context import (
    ContextRetrievalState,
    create_context_retrieval_session,
)
from chronos.lineage import LineageRetrievalState
from chronos.resolution import (
    CanonicalDatasetIdentity,
    CanonicalSchemaFieldIdentity,
    ResolutionState,
)
from chronos.schema import SchemaRetrievalState
from chronos.snapshot import (
    CurrentMetadataSnapshotAssembler,
    SnapshotBuildState,
    SnapshotCompositionInputs,
    SnapshotValidationState,
    export_snapshot,
    load_snapshot,
)


POSTGRES_ORDERS_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:postgres,"
    "b2fd91.order_entry_db.order_entry.orders,PROD)"
)


@unittest.skipUnless(
    os.environ.get("CHRONOS_RUN_INTEGRATION") == "1",
    "Set CHRONOS_RUN_INTEGRATION=1 to test the live DataHub instance.",
)
class CurrentMetadataSnapshotIntegrationTests(unittest.TestCase):
    def test_live_snapshot_validation_determinism_and_round_trip(self) -> None:
        session = create_context_retrieval_session()
        readiness = session.check_readiness()
        self.assertTrue(readiness.can_continue, readiness.to_dict())

        dataset_request = CanonicalDatasetIdentity(
            platform="PostgreSQL",
            qualified_name="order_entry_db.order_entry.orders",
            environment="PROD",
            database="order_entry_db",
            schema="order_entry",
            logical_name="orders",
            display_identity=(
                "PostgreSQL / order_entry_db / order_entry / orders"
            ),
        )
        dataset = session.resolve_dataset(dataset_request)
        self.assertEqual(dataset.state, ResolutionState.RESOLVED)
        self.assertEqual(dataset.resolved.urn, POSTGRES_ORDERS_URN)

        field_request = CanonicalSchemaFieldIdentity(
            parent_dataset=dataset_request,
            field_path="order_total",
            field_name="order_total",
        )
        field = session.resolve_field(field_request, dataset.resolved)
        self.assertEqual(field.state, ResolutionState.RESOLVED)

        schema = session.retrieve_schema(dataset_request, dataset.resolved)
        self.assertEqual(
            schema.state,
            SchemaRetrievalState.RETRIEVED,
            schema.to_dict(),
        )
        lineage = session.traverse_downstream_lineage(
            schema.snapshot,
            field.resolved.field_path,
        )
        self.assertEqual(
            lineage.state,
            LineageRetrievalState.RETRIEVED,
            lineage.to_dict(),
        )
        context = session.retrieve_context(lineage.graph)
        self.assertEqual(
            context.state,
            ContextRetrievalState.RETRIEVED,
            context.to_dict(),
        )
        composition = SnapshotCompositionInputs(
            readiness=readiness,
            dataset_resolution=dataset,
            field_resolution=field,
            schema_retrieval=schema,
            lineage_retrieval=lineage,
            context_retrieval=context,
        )
        first_observation = datetime.now(timezone.utc)
        second_observation = first_observation + timedelta(seconds=1)
        first = CurrentMetadataSnapshotAssembler(
            clock=lambda: first_observation
        ).assemble(composition)
        second = CurrentMetadataSnapshotAssembler(
            clock=lambda: second_observation
        ).assemble(composition)
        self.assertEqual(first.state, SnapshotBuildState.VALIDATED)
        self.assertEqual(second.state, SnapshotBuildState.VALIDATED)
        snapshot = first.snapshot
        repeated = second.snapshot
        self.assertEqual(
            snapshot.validation_result.state,
            SnapshotValidationState.VALID,
            snapshot.validation_result.findings,
        )
        self.assertNotEqual(
            snapshot.metadata.snapshot_id,
            repeated.metadata.snapshot_id,
        )
        self.assertEqual(
            snapshot.semantic_fingerprint,
            repeated.semantic_fingerprint,
        )
        self.assertEqual(snapshot.semantic_json(), repeated.semantic_json())

        summary = snapshot.summary()
        self.assertEqual(summary.dataset_count, 21)
        self.assertEqual(summary.source_schema_field_count, 15)
        self.assertEqual(summary.lineage_field_node_count, 26)
        self.assertEqual(summary.downstream_field_count, 25)
        self.assertEqual(summary.downstream_dataset_count, 20)
        self.assertEqual(summary.maximum_field_depth, 5)
        self.assertEqual(summary.lineage_edge_count, 27)
        self.assertEqual(summary.mapping_group_count, 28)
        self.assertEqual(summary.ownership_assignment_count, 27)
        self.assertEqual(summary.dashboard_context_count, 3)
        self.assertEqual(summary.data_product_membership_count, 4)
        self.assertEqual(summary.document_relationship_count, 18)
        self.assertEqual(summary.unresolved_reference_count, 1)

        configured_artifact = os.environ.get(
            "CHRONOS_SNAPSHOT_ARTIFACT"
        )
        if configured_artifact:
            artifact = export_snapshot(snapshot, configured_artifact)
            reloaded = load_snapshot(artifact)
        else:
            with tempfile.TemporaryDirectory() as directory:
                artifact = export_snapshot(
                    snapshot,
                    Path(directory) / "current_metadata_snapshot.json",
                )
                reloaded = load_snapshot(artifact)
        self.assertTrue(snapshot.semantically_equals(reloaded))
        self.assertEqual(
            snapshot.semantic_fingerprint,
            reloaded.semantic_fingerprint,
        )
        self.assertEqual(snapshot.summary(), reloaded.summary())


if __name__ == "__main__":
    unittest.main()
