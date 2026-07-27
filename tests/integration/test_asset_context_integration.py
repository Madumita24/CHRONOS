from __future__ import annotations

import os
import unittest

from chronos.context import (
    AssignmentScope,
    BusinessIntelligenceClassification,
    ContextRetrievalState,
    MetadataState,
    create_context_retrieval_session,
)
from chronos.lineage import LineageRetrievalState
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
DBT_ORDER_DETAILS_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:dbt,"
    "b2fd91.ORDER_ENTRY_DB.analytics.order_details,PROD)"
)
SNOWFLAKE_ORDER_DETAILS_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:snowflake,"
    "b2fd91.order_entry_db.analytics.order_details,PROD)"
)


@unittest.skipUnless(
    os.environ.get("CHRONOS_RUN_INTEGRATION") == "1",
    "Set CHRONOS_RUN_INTEGRATION=1 to test the live DataHub instance.",
)
class AssetContextIntegrationTests(unittest.TestCase):
    def test_complete_verified_context_scope(self) -> None:
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

        schema = session.retrieve_schema(
            dataset_request,
            dataset.resolved,
        )
        self.assertEqual(
            schema.state,
            SchemaRetrievalState.RETRIEVED,
            schema.to_dict(),
        )

        lineage = session.traverse_downstream_lineage(
            schema.snapshot,
            "order_total",
        )
        self.assertEqual(
            lineage.state,
            LineageRetrievalState.RETRIEVED,
            lineage.to_dict(),
        )
        graph = lineage.graph
        self.assertEqual(graph.downstream_field_count, 25)
        self.assertEqual(graph.downstream_dataset_count, 20)
        self.assertEqual(graph.maximum_field_depth, 5)

        context = session.retrieve_context(graph)
        self.assertEqual(
            context.state,
            ContextRetrievalState.RETRIEVED,
            context.to_dict(),
        )
        snapshot = context.snapshot
        self.assertEqual(snapshot.dataset_count, 21)
        self.assertEqual(
            len(snapshot.structured_property_definitions),
            5,
        )
        self.assertEqual(len(snapshot.pipeline_context), 2)
        self.assertEqual(len(snapshot.bi_context), 15)
        self.assertEqual(
            sum(
                1
                for item in snapshot.bi_context
                if item.entity_type == "CHART"
            ),
            12,
        )

        dashboards = {
            item.qualified_name
            for item in snapshot.bi_context
            if item.entity_type == "DASHBOARD"
        }
        self.assertEqual(
            dashboards,
            {
                "Looker / Order Entry Dashboard",
                "Power BI / datahub_order_entries",
                "Tableau / Order Entry Dashboard",
            },
        )
        self.assertTrue(
            all(
                item.classification
                is BusinessIntelligenceClassification.REACHABLE_CONTEXT
                for item in snapshot.bi_context
            )
        )

        by_urn = {item.asset.urn: item for item in snapshot.assets}
        source = by_urn[POSTGRES_ORDERS_URN]
        self.assertEqual(source.owners, ())
        self.assertEqual(source.ownership_state, MetadataState.ABSENT)
        self.assertEqual(source.domains, ())
        self.assertEqual(source.domain_state, MetadataState.ABSENT)
        self.assertEqual(len(source.structured_properties), 5)
        self.assertEqual(len(source.documents), 2)
        self.assertEqual(len(source.pipeline_context), 1)
        self.assertFalse(
            any(
                item.scope is AssignmentScope.FIELD
                for item in source.glossary_terms
            )
        )

        dbt = by_urn[DBT_ORDER_DETAILS_URN]
        self.assertEqual(len(dbt.owners), 12)
        self.assertEqual(
            {item.display_name for item in dbt.domains},
            {"Data Platform Team"},
        )
        self.assertEqual(
            {item.name for item in dbt.tags},
            {"PII_Data", "Authoritative Source"},
        )
        self.assertEqual(
            sum(
                1
                for item in dbt.glossary_terms
                if item.scope is AssignmentScope.ENTITY
            ),
            5,
        )
        self.assertEqual(
            {
                item.name
                for item in dbt.glossary_terms
                if item.scope is AssignmentScope.FIELD
                and item.field_path == "order_total"
            },
            {"PII", "Order Total"},
        )
        self.assertEqual(len(dbt.structured_properties), 5)
        self.assertEqual(
            {item.name for item in dbt.data_products},
            {"Order Entry Analytics"},
        )
        self.assertEqual(len(dbt.documents), 2)

        snowflake = by_urn[SNOWFLAKE_ORDER_DETAILS_URN]
        self.assertEqual(len(snowflake.owners), 3)
        self.assertEqual(
            {item.display_name for item in snowflake.domains},
            {"Ecommerce Operations"},
        )
        self.assertEqual(len(snowflake.tags), 2)
        self.assertEqual(
            sum(
                1
                for item in snowflake.glossary_terms
                if item.scope is AssignmentScope.ENTITY
            ),
            4,
        )
        self.assertEqual(
            {
                item.name
                for item in snowflake.glossary_terms
                if item.scope is AssignmentScope.FIELD
                and item.field_path == "order_total"
            },
            {"Order Total"},
        )
        self.assertEqual(len(snowflake.structured_properties), 5)
        self.assertEqual(
            {item.name for item in snowflake.data_products},
            {"Promotions Performance"},
        )
        self.assertEqual(len(snowflake.documents), 3)

        repeated = session.retrieve_context(graph)
        self.assertEqual(
            repeated.state,
            ContextRetrievalState.RETRIEVED,
            repeated.to_dict(),
        )
        self.assertTrue(
            snapshot.semantically_equals(repeated.snapshot)
        )


if __name__ == "__main__":
    unittest.main()
