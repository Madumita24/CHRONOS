from __future__ import annotations

import os
import unittest

from chronos.resolution import (
    CanonicalDatasetIdentity,
    CanonicalSchemaFieldIdentity,
    ResolutionState,
    create_resolution_session,
)


POSTGRES_ORDERS_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:postgres,"
    "b2fd91.order_entry_db.order_entry.orders,PROD)"
)


@unittest.skipUnless(
    os.environ.get("CHRONOS_RUN_INTEGRATION") == "1",
    "Set CHRONOS_RUN_INTEGRATION=1 to test the live DataHub instance.",
)
class CanonicalEntityResolutionIntegrationTests(unittest.TestCase):
    def test_live_canonical_dataset_field_and_platform_collision(self) -> None:
        session = create_resolution_session()
        readiness = session.check_readiness()
        self.assertTrue(readiness.can_continue, readiness.to_dict())

        postgres_request = CanonicalDatasetIdentity(
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
        postgres = session.resolve_dataset(postgres_request)
        self.assertEqual(
            postgres.state,
            ResolutionState.RESOLVED,
            postgres.to_dict(),
        )
        self.assertEqual(postgres.verified_candidate_count, 1)
        self.assertEqual(postgres.resolved.urn, POSTGRES_ORDERS_URN)
        self.assertEqual(postgres.resolved.platform, "postgres")
        self.assertEqual(postgres.resolved.environment, "PROD")

        field_request = CanonicalSchemaFieldIdentity(
            parent_dataset=postgres_request,
            field_path="order_total",
            field_name="order_total",
            display_identity=(
                "PostgreSQL / order_entry_db / order_entry / orders / "
                "order_total"
            ),
        )
        field = session.resolve_field(field_request, postgres.resolved)
        self.assertEqual(
            field.state,
            ResolutionState.RESOLVED,
            field.to_dict(),
        )
        self.assertEqual(field.resolved.field_name, "order_total")
        self.assertEqual(field.resolved.native_type, "DOUBLE PRECISION")
        self.assertEqual(field.resolved.normalized_type, "Number")
        self.assertEqual(
            field.resolved.parent_dataset_urn,
            postgres.resolved.urn,
        )

        snowflake_request = CanonicalDatasetIdentity(
            platform="Snowflake",
            qualified_name="ORDER_ENTRY_DB.ORDER_ENTRY.ORDERS",
            environment="PROD",
            database="ORDER_ENTRY_DB",
            schema="ORDER_ENTRY",
            logical_name="ORDERS",
            display_identity=(
                "Snowflake / ORDER_ENTRY_DB / ORDER_ENTRY / ORDERS"
            ),
        )
        snowflake = session.resolve_dataset(snowflake_request)
        self.assertEqual(
            snowflake.state,
            ResolutionState.RESOLVED,
            snowflake.to_dict(),
        )
        self.assertEqual(snowflake.verified_candidate_count, 1)
        self.assertEqual(snowflake.resolved.platform, "snowflake")
        self.assertNotEqual(postgres.resolved.urn, snowflake.resolved.urn)


if __name__ == "__main__":
    unittest.main()
