from __future__ import annotations

import os
import unittest

from chronos.lineage import (
    FieldReferenceResolution,
    LineageRetrievalState,
    create_lineage_retrieval_session,
)
from chronos.resolution import (
    CanonicalDatasetIdentity,
    CanonicalSchemaFieldIdentity,
    ResolutionState,
)
from chronos.schema import SchemaRetrievalState


POSTGRES_ORDERS_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:postgres,"
    "b2fd91.order_entry_db.order_entry.orders,PROD)"
)
S3_ORDERS_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:s3,"
    "b2fd91.demo-data-bucket/order_entry/orders,PROD)"
)


@unittest.skipUnless(
    os.environ.get("CHRONOS_RUN_INTEGRATION") == "1",
    "Set CHRONOS_RUN_INTEGRATION=1 to test the live DataHub instance.",
)
class FieldLineageIntegrationTests(unittest.TestCase):
    def test_direct_and_complete_order_total_lineage(self) -> None:
        session = create_lineage_retrieval_session()
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
        self.assertEqual(
            dataset.state,
            ResolutionState.RESOLVED,
            dataset.to_dict(),
        )
        self.assertEqual(dataset.resolved.urn, POSTGRES_ORDERS_URN)

        field_request = CanonicalSchemaFieldIdentity(
            parent_dataset=dataset_request,
            field_path="order_total",
            field_name="order_total",
        )
        field = session.resolve_field(field_request, dataset.resolved)
        self.assertEqual(
            field.state,
            ResolutionState.RESOLVED,
            field.to_dict(),
        )
        self.assertEqual(field.resolved.native_type, "DOUBLE PRECISION")
        self.assertEqual(field.resolved.normalized_type, "Number")

        schema = session.retrieve_schema(
            dataset_request,
            dataset.resolved,
        )
        self.assertEqual(
            schema.state,
            SchemaRetrievalState.RETRIEVED,
            schema.to_dict(),
        )
        self.assertEqual(schema.snapshot.field_count, 15)

        direct = session.retrieve_direct_lineage(
            schema.snapshot,
            "order_total",
        )
        self.assertEqual(
            direct.state,
            LineageRetrievalState.RETRIEVED,
            direct.to_dict(),
        )
        self.assertEqual(direct.graph.downstream_field_count, 1)
        self.assertEqual(direct.graph.downstream_dataset_count, 1)
        self.assertEqual(direct.graph.maximum_field_depth, 1)
        self.assertEqual(len(direct.graph.mapping_groups), 1)
        self.assertEqual(len(direct.graph.edges), 1)
        direct_field = direct.graph.direct_downstream[0].reference
        self.assertEqual(direct_field.dataset_urn, S3_ORDERS_URN)
        self.assertEqual(direct_field.field_path, "order_total")

        complete = session.traverse_downstream_lineage(
            schema.snapshot,
            "order_total",
        )
        self.assertEqual(
            complete.state,
            LineageRetrievalState.RETRIEVED,
            complete.to_dict(),
        )

        # Acceptance values are checked only after independent traversal.
        self.assertEqual(complete.graph.downstream_field_count, 25)
        self.assertEqual(complete.graph.downstream_dataset_count, 20)
        self.assertEqual(complete.graph.maximum_field_depth, 5)

        self.assertEqual(len(complete.graph.mapping_groups), 28)
        self.assertEqual(len(complete.graph.edges), 27)
        self.assertEqual(len(complete.graph.cycles), 0)
        self.assertEqual(len(complete.graph.findings), 0)
        self.assertTrue(
            all(
                node.path_count >= 1
                for node in complete.graph.nodes
                if node.reference.key != complete.graph.source.key
            )
        )
        entity_only = tuple(
            node
            for node in complete.graph.nodes
            if node.reference.resolution
            is FieldReferenceResolution.SCHEMA_FIELD_ENTITY
        )
        self.assertEqual(len(entity_only), 5)

        repeated = session.traverse_downstream_lineage(
            schema.snapshot,
            "order_total",
        )
        self.assertTrue(
            complete.graph.semantically_equals(repeated.graph)
        )


if __name__ == "__main__":
    unittest.main()
