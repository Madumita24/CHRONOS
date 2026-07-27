from __future__ import annotations

import os
import unittest

from chronos.resolution import CanonicalDatasetIdentity, ResolutionState
from chronos.schema import (
    FieldLookupState,
    NormalizedFieldType,
    SchemaRetrievalState,
    create_schema_retrieval_session,
)


POSTGRES_ORDERS_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:postgres,"
    "b2fd91.order_entry_db.order_entry.orders,PROD)"
)
SNOWFLAKE_ORDERS_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:snowflake,"
    "b2fd91.order_entry_db.order_entry.orders,PROD)"
)

POSTGRES_FIELDS = (
    ("order_id", "BIGINT", NormalizedFieldType.NUMBER),
    ("order_date", "TEXT", NormalizedFieldType.STRING),
    ("order_mode", "TEXT", NormalizedFieldType.STRING),
    ("customer_id", "BIGINT", NormalizedFieldType.NUMBER),
    ("order_status", "BIGINT", NormalizedFieldType.NUMBER),
    ("order_total", "DOUBLE PRECISION", NormalizedFieldType.NUMBER),
    ("sales_rep_id", "BIGINT", NormalizedFieldType.NUMBER),
    ("promotion_id", "DOUBLE PRECISION", NormalizedFieldType.NUMBER),
    ("warehouse_id", "BIGINT", NormalizedFieldType.NUMBER),
    ("delivery_type", "TEXT", NormalizedFieldType.STRING),
    ("cost_of_delivery", "DOUBLE PRECISION", NormalizedFieldType.NUMBER),
    ("wait_till_complete_yn", "TEXT", NormalizedFieldType.STRING),
    ("billing_address_id", "BIGINT", NormalizedFieldType.NUMBER),
    ("delivery_address_id", "BIGINT", NormalizedFieldType.NUMBER),
    ("payment_method_code", "TEXT", NormalizedFieldType.STRING),
)

SNOWFLAKE_FIELDS = (
    ("order_id", "NUMBER(38,0)", NormalizedFieldType.NUMBER),
    ("order_date", "VARCHAR(16777216)", NormalizedFieldType.STRING),
    ("order_mode", "VARCHAR(16777216)", NormalizedFieldType.STRING),
    ("customer_id", "NUMBER(38,0)", NormalizedFieldType.NUMBER),
    ("order_status", "NUMBER(38,0)", NormalizedFieldType.NUMBER),
    ("order_total", "FLOAT", NormalizedFieldType.NUMBER),
    ("sales_rep_id", "NUMBER(38,0)", NormalizedFieldType.NUMBER),
    ("promotion_id", "FLOAT", NormalizedFieldType.NUMBER),
    ("warehouse_id", "NUMBER(38,0)", NormalizedFieldType.NUMBER),
    ("delivery_type", "VARCHAR(16777216)", NormalizedFieldType.STRING),
    ("cost_of_delivery", "FLOAT", NormalizedFieldType.NUMBER),
    (
        "wait_till_complete_yn",
        "VARCHAR(16777216)",
        NormalizedFieldType.STRING,
    ),
    ("billing_address_id", "NUMBER(38,0)", NormalizedFieldType.NUMBER),
    ("delivery_address_id", "NUMBER(38,0)", NormalizedFieldType.NUMBER),
    (
        "payment_method_code",
        "VARCHAR(16777216)",
        NormalizedFieldType.STRING,
    ),
)


@unittest.skipUnless(
    os.environ.get("CHRONOS_RUN_INTEGRATION") == "1",
    "Set CHRONOS_RUN_INTEGRATION=1 to test the live DataHub instance.",
)
class SchemaRetrievalIntegrationTests(unittest.TestCase):
    def test_complete_postgres_and_isolated_snowflake_schemas(self) -> None:
        session = create_schema_retrieval_session()
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
        postgres_identity = session.resolve_dataset(postgres_request)
        self.assertEqual(
            postgres_identity.state,
            ResolutionState.RESOLVED,
            postgres_identity.to_dict(),
        )
        self.assertEqual(postgres_identity.resolved.urn, POSTGRES_ORDERS_URN)

        postgres = session.retrieve_schema(
            postgres_request,
            postgres_identity.resolved,
        )
        self.assertEqual(
            postgres.state,
            SchemaRetrievalState.RETRIEVED,
            postgres.to_dict(),
        )
        self.assertEqual(postgres.snapshot.field_count, len(POSTGRES_FIELDS))
        self.assertEqual(
            tuple(
                (
                    item.field_path,
                    item.native_type,
                    item.normalized_type,
                )
                for item in postgres.snapshot.fields
            ),
            POSTGRES_FIELDS,
        )
        order_total = postgres.snapshot.lookup_field("order_total")
        self.assertEqual(order_total.state, FieldLookupState.FOUND)
        self.assertEqual(order_total.field.native_type, "DOUBLE PRECISION")
        self.assertEqual(
            order_total.field.normalized_type,
            NormalizedFieldType.NUMBER,
        )

        repeated = session.retrieve_schema(
            postgres_request,
            postgres_identity.resolved,
        )
        self.assertTrue(
            postgres.snapshot.semantically_equals(repeated.snapshot)
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
        snowflake_identity = session.resolve_dataset(snowflake_request)
        self.assertEqual(
            snowflake_identity.state,
            ResolutionState.RESOLVED,
            snowflake_identity.to_dict(),
        )
        self.assertEqual(
            snowflake_identity.resolved.urn,
            SNOWFLAKE_ORDERS_URN,
        )
        snowflake = session.retrieve_schema(
            snowflake_request,
            snowflake_identity.resolved,
        )
        self.assertEqual(
            snowflake.state,
            SchemaRetrievalState.RETRIEVED,
            snowflake.to_dict(),
        )
        self.assertEqual(
            tuple(
                (
                    item.field_path,
                    item.native_type,
                    item.normalized_type,
                )
                for item in snowflake.snapshot.fields
            ),
            SNOWFLAKE_FIELDS,
        )
        self.assertNotEqual(
            postgres.snapshot.dataset_urn,
            snowflake.snapshot.dataset_urn,
        )


if __name__ == "__main__":
    unittest.main()
