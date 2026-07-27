from __future__ import annotations

import inspect
import json
import unittest
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone

from chronos.datahub._transport import (
    ReadOnlyTransport,
    SchemaFieldMetadataObservation,
    SchemaMetadataObservation,
)
from chronos.datahub.errors import ConnectionError, FailureCode
from chronos.datahub.schema_types import NormalizedFieldType
from chronos.resolution.models import (
    CanonicalDatasetIdentity,
    ResolvedDatasetIdentity,
)
from chronos.schema import (
    DatasetSchemaRetriever,
    FieldLookupState,
    SchemaRetrievalState,
    SchemaValidationState,
)


POSTGRES_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:postgres,"
    "b2fd91.order_entry_db.order_entry.orders,PROD)"
)


class SchemaTransport:
    def __init__(
        self,
        observation: SchemaMetadataObservation | None = None,
    ) -> None:
        self.observation = observation
        self.error: Exception | None = None
        self.schema_read_count = 0

    def schema_metadata(
        self,
        urn: str,
    ) -> SchemaMetadataObservation | None:
        self.schema_read_count += 1
        if self.error is not None:
            raise self.error
        return self.observation


def canonical(
    *,
    platform: str = "PostgreSQL",
    qualified_name: str = "order_entry_db.order_entry.orders",
    logical_name: str = "orders",
) -> CanonicalDatasetIdentity:
    return CanonicalDatasetIdentity(
        platform=platform,
        qualified_name=qualified_name,
        environment="PROD",
        logical_name=logical_name,
        database="order_entry_db",
        schema="order_entry",
    )


def resolved(
    *,
    urn: str = POSTGRES_URN,
    platform: str = "postgres",
    qualified_name: str = "order_entry_db.order_entry.orders",
    logical_name: str = "orders",
) -> ResolvedDatasetIdentity:
    return ResolvedDatasetIdentity(
        urn=urn,
        urn_name=f"b2fd91.{qualified_name}",
        platform=platform,
        environment="PROD",
        qualified_name=qualified_name,
        logical_name=logical_name,
        platform_instance=None,
        properties_qualified_name=qualified_name,
    )


def field(
    field_path: str | None,
    *,
    datahub_type: str | None = "StringTypeClass",
    native_type: str | None = "TEXT",
    description: str | None = None,
    nullable: bool | None = True,
    is_part_of_key: bool | None = False,
    is_partitioning_key: bool | None = None,
    schema_field_urn: str | None = None,
) -> SchemaFieldMetadataObservation:
    return SchemaFieldMetadataObservation(
        field_path=field_path,
        datahub_type=datahub_type,
        native_type=native_type,
        description=description,
        nullable=nullable,
        is_part_of_key=is_part_of_key,
        is_partitioning_key=is_partitioning_key,
        json_path=None,
        label=None,
        recursive=False,
        schema_field_urn=schema_field_urn,
    )


def observation(
    fields: tuple[SchemaFieldMetadataObservation, ...] | None = None,
    *,
    dataset_urn: str = POSTGRES_URN,
    schema_name: str | None = "order_entry_db.order_entry.orders",
    platform: str | None = "urn:li:dataPlatform:postgres",
) -> SchemaMetadataObservation:
    return SchemaMetadataObservation(
        dataset_urn=dataset_urn,
        schema_name=schema_name,
        platform=platform,
        version=0,
        schema_hash="",
        fields=fields
        if fields is not None
        else (
            field("order_id", datahub_type="NumberTypeClass", native_type="BIGINT"),
            field(
                "order_total",
                datahub_type="NumberTypeClass",
                native_type="DOUBLE PRECISION",
            ),
        ),
        created_time=15353438779,
        last_modified_time=15353438779,
        dataset_reference=None,
        cluster=None,
        primary_keys=None,
    )


def retriever(
    transport: SchemaTransport,
    instant: datetime | None = None,
) -> DatasetSchemaRetriever:
    return DatasetSchemaRetriever(
        transport,  # type: ignore[arg-type]
        clock=lambda: instant
        or datetime(2026, 7, 26, 12, 0, tzinfo=timezone.utc),
    )


class DatasetSchemaRetrieverTests(unittest.TestCase):
    def test_successful_schema_retrieval(self) -> None:
        transport = SchemaTransport(observation())

        result = retriever(transport).retrieve(canonical(), resolved())

        self.assertEqual(result.state, SchemaRetrievalState.RETRIEVED)
        self.assertIsNotNone(result.snapshot)
        self.assertIsNone(result.failure)

    def test_missing_schema_metadata(self) -> None:
        result = retriever(SchemaTransport(None)).retrieve(
            canonical(),
            resolved(),
        )

        self.assertEqual(result.state, SchemaRetrievalState.NOT_FOUND)
        self.assertEqual(result.failure.code, FailureCode.SCHEMA_NOT_FOUND)

    def test_empty_schema_is_invalid(self) -> None:
        result = retriever(
            SchemaTransport(observation(fields=()))
        ).retrieve(canonical(), resolved())

        self.assertEqual(result.state, SchemaRetrievalState.INVALID_SCHEMA)
        self.assertEqual(result.failure.code, FailureCode.SCHEMA_EMPTY)

    def test_multiple_fields_are_preserved(self) -> None:
        result = retriever(SchemaTransport(observation())).retrieve(
            canonical(),
            resolved(),
        )

        self.assertEqual(result.snapshot.field_count, 2)
        self.assertEqual(
            tuple(item.field_path for item in result.snapshot.fields),
            ("order_id", "order_total"),
        )

    def test_field_ordering_and_positions_are_preserved(self) -> None:
        fields = (
            field("z_first"),
            field("a_second"),
            field("m_third"),
        )
        result = retriever(
            SchemaTransport(observation(fields=fields))
        ).retrieve(canonical(), resolved())

        self.assertEqual(
            tuple(item.field_path for item in result.snapshot.fields),
            ("z_first", "a_second", "m_third"),
        )
        self.assertEqual(
            tuple(item.position for item in result.snapshot.fields),
            (0, 1, 2),
        )

    def test_duplicate_field_path_is_rejected(self) -> None:
        duplicate = (field("order_id"), field("order_id"))
        result = retriever(
            SchemaTransport(observation(fields=duplicate))
        ).retrieve(canonical(), resolved())

        self.assertEqual(result.state, SchemaRetrievalState.INVALID_SCHEMA)
        self.assertEqual(
            result.failure.code,
            FailureCode.DUPLICATE_FIELD_PATH,
        )

    def test_empty_field_path_is_rejected(self) -> None:
        result = retriever(
            SchemaTransport(observation(fields=(field(""),)))
        ).retrieve(canonical(), resolved())

        self.assertEqual(result.failure.code, FailureCode.SCHEMA_MALFORMED)

    def test_whitespace_field_path_is_rejected(self) -> None:
        result = retriever(
            SchemaTransport(observation(fields=(field(" order_id "),)))
        ).retrieve(canonical(), resolved())

        self.assertEqual(result.failure.code, FailureCode.SCHEMA_MALFORMED)

    def test_native_type_is_preserved(self) -> None:
        result = retriever(SchemaTransport(observation())).retrieve(
            canonical(),
            resolved(),
        )

        lookup = result.snapshot.lookup_field("order_total")
        self.assertEqual(lookup.field.native_type, "DOUBLE PRECISION")

    def test_number_type_normalization(self) -> None:
        result = retriever(SchemaTransport(observation())).retrieve(
            canonical(),
            resolved(),
        )

        lookup = result.snapshot.lookup_field("order_total")
        self.assertEqual(
            lookup.field.normalized_type,
            NormalizedFieldType.NUMBER,
        )

    def test_string_type_normalization(self) -> None:
        fields = (field("order_mode"),)
        result = retriever(
            SchemaTransport(observation(fields=fields))
        ).retrieve(canonical(), resolved())

        self.assertEqual(
            result.snapshot.fields[0].normalized_type,
            NormalizedFieldType.STRING,
        )

    def test_unknown_type_is_safe_and_raw_value_is_observable(self) -> None:
        fields = (
            field(
                "future_type",
                datahub_type="FutureTypeClass",
                native_type="VENDOR_FUTURE",
            ),
        )
        result = retriever(
            SchemaTransport(observation(fields=fields))
        ).retrieve(canonical(), resolved())

        record = result.snapshot.fields[0]
        self.assertEqual(record.normalized_type, NormalizedFieldType.UNKNOWN)
        self.assertEqual(record.datahub_type, "FutureTypeClass")
        self.assertEqual(record.native_type, "VENDOR_FUTURE")

    def test_description_is_preserved(self) -> None:
        fields = (field("order_id", description="Order identifier"),)
        result = retriever(
            SchemaTransport(observation(fields=fields))
        ).retrieve(canonical(), resolved())

        self.assertEqual(
            result.snapshot.fields[0].description,
            "Order identifier",
        )

    def test_missing_description_remains_none(self) -> None:
        result = retriever(SchemaTransport(observation())).retrieve(
            canonical(),
            resolved(),
        )

        self.assertIsNone(result.snapshot.fields[0].description)

    def test_order_total_lookup_succeeds_without_another_read(self) -> None:
        transport = SchemaTransport(observation())
        result = retriever(transport).retrieve(canonical(), resolved())

        lookup = result.snapshot.lookup_field("order_total")

        self.assertEqual(lookup.state, FieldLookupState.FOUND)
        self.assertEqual(lookup.field.field_path, "order_total")
        self.assertEqual(transport.schema_read_count, 1)

    def test_absent_field_lookup_fails_deterministically(self) -> None:
        transport = SchemaTransport(observation())
        result = retriever(transport).retrieve(canonical(), resolved())

        first = result.snapshot.lookup_field("not_present")
        second = result.snapshot.lookup_field("not_present")

        self.assertEqual(first, second)
        self.assertEqual(first.state, FieldLookupState.NOT_FOUND)
        self.assertEqual(first.failure.code, FailureCode.FIELD_NOT_FOUND)
        self.assertEqual(transport.schema_read_count, 1)

    def test_dataset_urn_is_preserved(self) -> None:
        result = retriever(SchemaTransport(observation())).retrieve(
            canonical(),
            resolved(),
        )

        self.assertEqual(result.snapshot.dataset_urn, POSTGRES_URN)

    def test_schema_evidence_is_attached(self) -> None:
        result = retriever(SchemaTransport(observation())).retrieve(
            canonical(),
            resolved(),
        )

        evidence = result.snapshot.evidence
        self.assertEqual(evidence.dataset_urn, POSTGRES_URN)
        self.assertEqual(evidence.aspect, "SchemaMetadata")
        self.assertEqual(evidence.field_count, 2)
        self.assertEqual(
            evidence.validation_state,
            SchemaValidationState.VALID,
        )

    def test_snapshot_is_immutable(self) -> None:
        result = retriever(SchemaTransport(observation())).retrieve(
            canonical(),
            resolved(),
        )

        with self.assertRaises(FrozenInstanceError):
            result.snapshot.schema_name = "changed"  # type: ignore[misc]
        with self.assertRaises(FrozenInstanceError):
            result.snapshot.fields[0].native_type = "changed"  # type: ignore[misc]

    def test_semantic_comparison_ignores_observation_timestamp(self) -> None:
        first = retriever(
            SchemaTransport(observation()),
            datetime(2026, 7, 26, 12, 0, tzinfo=timezone.utc),
        ).retrieve(canonical(), resolved())
        second = retriever(
            SchemaTransport(observation()),
            datetime(2026, 7, 26, 13, 0, tzinfo=timezone.utc),
        ).retrieve(canonical(), resolved())

        self.assertNotEqual(
            first.snapshot.observed_at,
            second.snapshot.observed_at,
        )
        self.assertEqual(
            first.snapshot.semantic_key(),
            second.snapshot.semantic_key(),
        )
        self.assertTrue(first.snapshot.semantically_equals(second.snapshot))

    def test_semantic_comparison_detects_schema_change(self) -> None:
        first = retriever(SchemaTransport(observation())).retrieve(
            canonical(),
            resolved(),
        )
        changed = observation(
            fields=observation().fields + (field("new_field"),)
        )
        second = retriever(SchemaTransport(changed)).retrieve(
            canonical(),
            resolved(),
        )

        self.assertFalse(first.snapshot.semantically_equals(second.snapshot))

    def test_nullable_and_key_indicators_are_preserved(self) -> None:
        fields = (
            field(
                "order_id",
                nullable=False,
                is_part_of_key=True,
                is_partitioning_key=False,
            ),
        )
        result = retriever(
            SchemaTransport(observation(fields=fields))
        ).retrieve(canonical(), resolved())

        record = result.snapshot.fields[0]
        self.assertIs(record.nullable, False)
        self.assertIs(record.is_part_of_key, True)
        self.assertIs(record.is_partitioning_key, False)

    def test_unavailable_optional_values_remain_none(self) -> None:
        fields = (
            field(
                "opaque",
                datahub_type=None,
                native_type=None,
                nullable=None,
                is_part_of_key=None,
            ),
        )
        result = retriever(
            SchemaTransport(observation(fields=fields))
        ).retrieve(canonical(), resolved())

        record = result.snapshot.fields[0]
        self.assertIsNone(record.native_type)
        self.assertIsNone(record.nullable)
        self.assertIsNone(record.is_part_of_key)
        self.assertEqual(record.normalized_type, NormalizedFieldType.UNKNOWN)

    def test_schema_version_hash_and_source_times_are_preserved(self) -> None:
        result = retriever(SchemaTransport(observation())).retrieve(
            canonical(),
            resolved(),
        )

        snapshot = result.snapshot
        self.assertEqual(snapshot.schema_version, 0)
        self.assertEqual(snapshot.schema_hash, "")
        self.assertEqual(snapshot.created_time, 15353438779)
        self.assertEqual(snapshot.last_modified_time, 15353438779)

    def test_schema_field_urn_is_not_constructed(self) -> None:
        result = retriever(SchemaTransport(observation())).retrieve(
            canonical(),
            resolved(),
        )

        self.assertIsNone(result.snapshot.fields[0].schema_field_urn)

    def test_datahub_supplied_schema_field_urn_is_preserved(self) -> None:
        supplied = "urn:li:schemaField:(dataset,order_id)"
        fields = (field("order_id", schema_field_urn=supplied),)
        result = retriever(
            SchemaTransport(observation(fields=fields))
        ).retrieve(canonical(), resolved())

        self.assertEqual(
            result.snapshot.fields[0].schema_field_urn,
            supplied,
        )

    def test_unsupported_field_metadata_is_rejected(self) -> None:
        malformed = replace(field("order_id"), nullable="yes")  # type: ignore[arg-type]
        result = retriever(
            SchemaTransport(observation(fields=(malformed,)))
        ).retrieve(canonical(), resolved())

        self.assertEqual(
            result.failure.code,
            FailureCode.UNSUPPORTED_FIELD_METADATA,
        )

    def test_schema_identity_mismatch_is_rejected(self) -> None:
        wrong = observation(
            schema_name="other_db.other_schema.orders",
        )
        result = retriever(SchemaTransport(wrong)).retrieve(
            canonical(),
            resolved(),
        )

        self.assertEqual(result.failure.code, FailureCode.SCHEMA_MALFORMED)

    def test_retrieval_errors_redact_secrets(self) -> None:
        secret = "schema-secret-token"
        transport = SchemaTransport(observation())
        transport.error = ConnectionError(
            "unavailable",
            diagnostic=f"Authorization: Bearer {secret}",
        )

        result = retriever(transport).retrieve(canonical(), resolved())
        serialized = json.dumps(result.to_dict())

        self.assertEqual(result.state, SchemaRetrievalState.UNAVAILABLE)
        self.assertNotIn(secret, serialized)
        self.assertIn("<redacted>", serialized)

    def test_postgres_and_snowflake_schemas_bind_to_distinct_urns(self) -> None:
        snowflake_urn = (
            "urn:li:dataset:(urn:li:dataPlatform:snowflake,"
            "b2fd91.order_entry_db.order_entry.orders,PROD)"
        )
        snowflake_request = canonical(
            platform="Snowflake",
            qualified_name="ORDER_ENTRY_DB.ORDER_ENTRY.ORDERS",
            logical_name="ORDERS",
        )
        snowflake_dataset = resolved(
            urn=snowflake_urn,
            platform="snowflake",
        )
        snowflake_observation = observation(
            dataset_urn=snowflake_urn,
            platform="urn:li:dataPlatform:snowflake",
        )
        postgres_result = retriever(
            SchemaTransport(observation())
        ).retrieve(canonical(), resolved())
        snowflake_result = retriever(
            SchemaTransport(snowflake_observation)
        ).retrieve(snowflake_request, snowflake_dataset)

        self.assertNotEqual(
            postgres_result.snapshot.dataset_urn,
            snowflake_result.snapshot.dataset_urn,
        )

    def test_schema_boundary_is_read_only(self) -> None:
        public_methods = {
            name
            for name, value in inspect.getmembers(
                DatasetSchemaRetriever,
                predicate=callable,
            )
            if not name.startswith("_")
        }
        self.assertEqual(public_methods, {"retrieve"})

        transport_methods = {
            name
            for name, value in ReadOnlyTransport.__dict__.items()
            if callable(value) and not name.startswith("_")
        }
        forbidden = {
            "emit",
            "write",
            "create",
            "update",
            "delete",
            "patch",
            "upsert",
            "mutate",
            "rollback",
            "lineage",
        }
        self.assertFalse(
            any(
                marker in method.lower()
                for method in transport_methods
                for marker in forbidden
            )
        )


if __name__ == "__main__":
    unittest.main()
