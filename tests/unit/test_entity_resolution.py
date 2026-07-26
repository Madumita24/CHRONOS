from __future__ import annotations

import inspect
import json
import unittest
from datetime import datetime, timezone

from chronos.datahub._transport import (
    DatasetMetadataObservation,
    ReadOnlyTransport,
    SchemaFieldObservation,
)
from chronos.datahub.errors import ConnectionError, FailureCode
from chronos.resolution import (
    CanonicalDatasetIdentity,
    CanonicalEntityResolver,
    CanonicalSchemaFieldIdentity,
    FieldResolutionResult,
    ResolutionState,
)
from chronos.resolution.models import (
    ResolvedDatasetIdentity,
    ResolvedSchemaFieldIdentity,
)


POSTGRES_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:postgres,"
    "runtime-prefix.order_entry_db.order_entry.orders,PROD)"
)
SNOWFLAKE_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:snowflake,"
    "runtime-prefix.order_entry_db.order_entry.orders,PROD)"
)
FIELD_URN = f"urn:li:schemaField:({POSTGRES_URN},order_total)"


def postgres_request() -> CanonicalDatasetIdentity:
    return CanonicalDatasetIdentity(
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


def snowflake_request() -> CanonicalDatasetIdentity:
    return CanonicalDatasetIdentity(
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


def postgres_observation(urn: str = POSTGRES_URN) -> DatasetMetadataObservation:
    return DatasetMetadataObservation(
        urn=urn,
        platform="postgres",
        environment="PROD",
        urn_name="runtime-prefix.order_entry_db.order_entry.orders",
        logical_name="orders",
        schema_name="order_entry_db.order_entry.orders",
        properties_qualified_name=None,
        platform_instance=None,
    )


def snowflake_observation() -> DatasetMetadataObservation:
    return DatasetMetadataObservation(
        urn=SNOWFLAKE_URN,
        platform="snowflake",
        environment="PROD",
        urn_name="runtime-prefix.order_entry_db.order_entry.orders",
        logical_name="ORDERS",
        schema_name="order_entry_db.order_entry.orders",
        properties_qualified_name=(
            "runtime-prefix.ORDER_ENTRY_DB.ORDER_ENTRY.ORDERS"
        ),
        platform_instance=None,
    )


class ResolutionTransport:
    def __init__(self) -> None:
        self.search_results = (POSTGRES_URN,)
        self.metadata = {POSTGRES_URN: postgres_observation()}
        self.fields = {
            POSTGRES_URN: (
                SchemaFieldObservation(
                    name="order_total",
                    normalized_type="Number",
                    native_type="DOUBLE PRECISION",
                    description="Total order value.",
                    schema_field_urn=FIELD_URN,
                ),
            )
        }
        self.search_error: Exception | None = None
        self.metadata_reads: list[str] = []

    def search_dataset_urns(self, **_: str) -> tuple[str, ...]:
        if self.search_error is not None:
            raise self.search_error
        return self.search_results

    def dataset_metadata(self, urn: str) -> DatasetMetadataObservation:
        self.metadata_reads.append(urn)
        return self.metadata[urn]

    def schema_fields(self, urn: str) -> tuple[SchemaFieldObservation, ...]:
        return self.fields.get(urn, ())


def resolver(transport: ResolutionTransport) -> CanonicalEntityResolver:
    return CanonicalEntityResolver(
        transport,  # type: ignore[arg-type]
        clock=lambda: datetime(2026, 7, 26, tzinfo=timezone.utc),
    )


class CanonicalEntityResolverTests(unittest.TestCase):
    def test_exact_canonical_dataset_resolution(self) -> None:
        transport = ResolutionTransport()
        result = resolver(transport).resolve_dataset(postgres_request())

        self.assertEqual(result.state, ResolutionState.RESOLVED)
        self.assertEqual(result.verified_candidate_count, 1)
        self.assertEqual(transport.metadata_reads, [POSTGRES_URN])

    def test_dataset_not_found(self) -> None:
        transport = ResolutionTransport()
        transport.search_results = ()

        result = resolver(transport).resolve_dataset(postgres_request())

        self.assertEqual(result.state, ResolutionState.NOT_FOUND)
        self.assertEqual(result.failure.code, FailureCode.ENTITY_NOT_FOUND)

    def test_multiple_exact_datasets_are_ambiguous(self) -> None:
        transport = ResolutionTransport()
        second_urn = POSTGRES_URN.replace("runtime-prefix", "other-prefix")
        transport.search_results = (POSTGRES_URN, second_urn)
        transport.metadata[second_urn] = postgres_observation(second_urn)

        result = resolver(transport).resolve_dataset(postgres_request())

        self.assertEqual(result.state, ResolutionState.AMBIGUOUS)
        self.assertIsNone(result.resolved)
        self.assertEqual(len(result.candidates), 2)
        self.assertEqual(result.failure.code, FailureCode.ENTITY_AMBIGUOUS)

    def test_postgres_and_snowflake_orders_remain_distinct(self) -> None:
        transport = ResolutionTransport()
        transport.search_results = (POSTGRES_URN, SNOWFLAKE_URN)
        transport.metadata[SNOWFLAKE_URN] = snowflake_observation()
        entity_resolver = resolver(transport)

        postgres = entity_resolver.resolve_dataset(postgres_request())
        snowflake = entity_resolver.resolve_dataset(snowflake_request())

        self.assertEqual(postgres.state, ResolutionState.RESOLVED)
        self.assertEqual(snowflake.state, ResolutionState.RESOLVED)
        self.assertNotEqual(postgres.resolved.urn, snowflake.resolved.urn)
        self.assertNotEqual(
            postgres.resolved.platform,
            snowflake.resolved.platform,
        )

    def test_exact_field_resolution_is_scoped_to_parent(self) -> None:
        transport = ResolutionTransport()
        dataset = resolver(transport).resolve_dataset(postgres_request())
        request = CanonicalSchemaFieldIdentity(
            parent_dataset=postgres_request(),
            field_path="order_total",
            field_name="order_total",
        )

        result = resolver(transport).resolve_field(request, dataset.resolved)

        self.assertEqual(result.state, ResolutionState.RESOLVED)
        self.assertEqual(result.resolved.parent_dataset_urn, POSTGRES_URN)
        self.assertEqual(result.resolved.field_name, "order_total")

    def test_absent_field_returns_not_found(self) -> None:
        transport = ResolutionTransport()
        dataset = resolver(transport).resolve_dataset(postgres_request())
        request = CanonicalSchemaFieldIdentity(
            parent_dataset=postgres_request(),
            field_path="missing_field",
            field_name="missing_field",
        )

        result = resolver(transport).resolve_field(request, dataset.resolved)

        self.assertEqual(result.state, ResolutionState.NOT_FOUND)
        self.assertEqual(result.failure.code, FailureCode.FIELD_NOT_FOUND)

    def test_native_type_is_preserved(self) -> None:
        result = self._resolved_field()
        self.assertEqual(result.resolved.native_type, "DOUBLE PRECISION")

    def test_normalized_type_is_preserved(self) -> None:
        result = self._resolved_field()
        self.assertEqual(result.resolved.normalized_type, "Number")

    def test_datahub_provided_urns_are_preserved_exactly(self) -> None:
        result = self._resolved_field()
        self.assertEqual(result.parent_dataset.urn, POSTGRES_URN)
        self.assertEqual(result.resolved.schema_field_urn, FIELD_URN)

    def test_canonical_and_resolved_identity_are_separate_types(self) -> None:
        transport = ResolutionTransport()
        result = resolver(transport).resolve_dataset(postgres_request())

        self.assertIsInstance(result.requested, CanonicalDatasetIdentity)
        self.assertIsInstance(result.resolved, ResolvedDatasetIdentity)
        self.assertNotIsInstance(result.requested, ResolvedDatasetIdentity)

    def test_resolution_evidence_is_retained(self) -> None:
        transport = ResolutionTransport()
        result = resolver(transport).resolve_dataset(postgres_request())

        self.assertIsNotNone(result.evidence)
        self.assertEqual(result.evidence.resolved_urn, POSTGRES_URN)
        self.assertTrue(
            all(
                attribute.matched
                for attribute in result.evidence.verified_attributes
            )
        )
        self.assertEqual(
            result.evidence.observed_at,
            "2026-07-26T00:00:00+00:00",
        )

    def test_invalid_canonical_identity(self) -> None:
        invalid = CanonicalDatasetIdentity(
            platform="PostgreSQL",
            qualified_name="order_entry_db.order_entry.orders",
            environment="PROD",
            logical_name="customers",
        )

        result = resolver(ResolutionTransport()).resolve_dataset(invalid)

        self.assertEqual(result.state, ResolutionState.INVALID_IDENTITY)
        self.assertEqual(
            result.failure.code,
            FailureCode.INVALID_CANONICAL_IDENTITY,
        )

    def test_datahub_unavailable_during_resolution(self) -> None:
        transport = ResolutionTransport()
        transport.search_error = ConnectionError("unavailable")

        result = resolver(transport).resolve_dataset(postgres_request())

        self.assertEqual(result.state, ResolutionState.UNAVAILABLE)
        self.assertEqual(
            result.failure.code,
            FailureCode.RESOLUTION_UNAVAILABLE,
        )

    def test_resolution_errors_redact_secrets(self) -> None:
        secret = "resolution-secret-token"
        transport = ResolutionTransport()
        transport.search_error = ConnectionError(
            "unavailable",
            diagnostic=f"Authorization: Bearer {secret}",
        )

        result = resolver(transport).resolve_dataset(postgres_request())

        serialized = json.dumps(result.to_dict())
        self.assertNotIn(secret, serialized)
        self.assertIn("<redacted>", serialized)

    def test_resolution_boundary_is_read_only(self) -> None:
        public_methods = {
            name
            for name, value in inspect.getmembers(
                CanonicalEntityResolver,
                predicate=callable,
            )
            if not name.startswith("_")
        }
        self.assertEqual(
            public_methods,
            {"resolve_dataset", "resolve_field"},
        )

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

    def _resolved_field(self) -> FieldResolutionResult:
        transport = ResolutionTransport()
        entity_resolver = resolver(transport)
        dataset = entity_resolver.resolve_dataset(postgres_request())
        request = CanonicalSchemaFieldIdentity(
            parent_dataset=postgres_request(),
            field_path="order_total",
            field_name="order_total",
        )
        result = entity_resolver.resolve_field(request, dataset.resolved)
        self.assertIsInstance(
            result.resolved,
            ResolvedSchemaFieldIdentity,
        )
        return result


if __name__ == "__main__":
    unittest.main()
