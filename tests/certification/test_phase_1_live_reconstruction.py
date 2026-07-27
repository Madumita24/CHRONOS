from __future__ import annotations

import os
import unittest
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
    load_snapshot,
)


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "artifacts" / "current_metadata_snapshot.json"


@unittest.skipUnless(
    os.environ.get("CHRONOS_RUN_INTEGRATION") == "1",
    "Set CHRONOS_RUN_INTEGRATION=1 for live reconstruction certification.",
)
class Phase1LiveReconstructionCertificationTests(unittest.TestCase):
    def test_fresh_snapshot_matches_certified_semantics(self) -> None:
        certified = load_snapshot(ARTIFACT)
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
        field_request = CanonicalSchemaFieldIdentity(
            parent_dataset=dataset_request,
            field_path="order_total",
            field_name="order_total",
        )
        field = session.resolve_field(field_request, dataset.resolved)
        self.assertEqual(field.state, ResolutionState.RESOLVED)
        schema = session.retrieve_schema(dataset_request, dataset.resolved)
        self.assertEqual(schema.state, SchemaRetrievalState.RETRIEVED)
        lineage = session.traverse_downstream_lineage(
            schema.snapshot,
            field.resolved.field_path,
        )
        self.assertEqual(lineage.state, LineageRetrievalState.RETRIEVED)
        context = session.retrieve_context(lineage.graph)
        self.assertEqual(context.state, ContextRetrievalState.RETRIEVED)

        rebuilt = CurrentMetadataSnapshotAssembler().assemble(
            SnapshotCompositionInputs(
                readiness=readiness,
                dataset_resolution=dataset,
                field_resolution=field,
                schema_retrieval=schema,
                lineage_retrieval=lineage,
                context_retrieval=context,
            )
        )
        self.assertEqual(rebuilt.state, SnapshotBuildState.VALIDATED)
        self.assertIsNotNone(rebuilt.snapshot)
        self.assertNotEqual(
            rebuilt.snapshot.metadata.snapshot_id,
            certified.metadata.snapshot_id,
        )
        self.assertEqual(
            rebuilt.snapshot.semantic_fingerprint,
            certified.semantic_fingerprint,
        )
        self.assertEqual(
            rebuilt.snapshot.semantic_json(),
            certified.semantic_json(),
        )


if __name__ == "__main__":
    unittest.main()
