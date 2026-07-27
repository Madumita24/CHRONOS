from __future__ import annotations

import inspect
import json
import unittest
from collections import Counter
from datetime import datetime, timezone

from datahub.metadata.urns import DatasetUrn, SchemaFieldUrn

from chronos.datahub._transport import (
    FineGrainedLineageAspectObservation,
    FineGrainedLineageGroupObservation,
    LineageEntityObservation,
    LineageReadOnlyTransport,
    SchemaFieldMetadataObservation,
    SchemaMetadataObservation,
)
from chronos.datahub.errors import ConnectionError, FailureCode
from chronos.datahub.schema_types import (
    NormalizedFieldType,
)
from chronos.lineage import (
    FieldLineageRetriever,
    FieldReferenceResolution,
    LineageRelationshipClassification,
    LineageRetrievalState,
    MappingExpansionState,
)
from chronos.resolution.models import (
    CanonicalDatasetIdentity,
    ResolvedDatasetIdentity,
)
from chronos.schema.models import (
    DatasetSchemaSnapshot,
    SchemaEvidence,
    SchemaFieldRecord,
    SchemaValidationState,
)


def dataset_urn(
    name: str,
    *,
    platform: str = "postgres",
) -> str:
    return str(
        DatasetUrn(
            platform=f"urn:li:dataPlatform:{platform}",
            name=name,
            env="PROD",
        )
    )


A = dataset_urn("test.a")
B = dataset_urn("test.b")
C = dataset_urn("test.c")
D = dataset_urn("test.d")
X = dataset_urn("test.x")
SNOW = dataset_urn("test.same", platform="snowflake")


def field_urn(parent: str, path: str) -> str:
    return str(SchemaFieldUrn(parent=parent, field_path=path))


def raw_field(path: str) -> SchemaFieldMetadataObservation:
    return SchemaFieldMetadataObservation(
        field_path=path,
        datahub_type="NumberTypeClass",
        native_type="BIGINT",
        description=None,
        nullable=True,
        is_part_of_key=False,
        is_partitioning_key=None,
        json_path=None,
        label=None,
        recursive=False,
    )


def schema(
    urn: str,
    *field_paths: str,
) -> SchemaMetadataObservation:
    parsed = DatasetUrn.from_string(urn)
    return SchemaMetadataObservation(
        dataset_urn=urn,
        schema_name=parsed.name,
        platform=str(parsed.platform),
        version=0,
        schema_hash="",
        fields=tuple(raw_field(path) for path in field_paths),
        created_time=None,
        last_modified_time=None,
        dataset_reference=None,
        cluster=None,
        primary_keys=None,
    )


def source_snapshot(field_path: str = "source") -> DatasetSchemaSnapshot:
    canonical = CanonicalDatasetIdentity(
        platform="PostgreSQL",
        qualified_name="test.a",
        environment="PROD",
        logical_name="a",
        display_identity="PostgreSQL / test / a",
    )
    resolved = ResolvedDatasetIdentity(
        urn=A,
        urn_name="test.a",
        platform="postgres",
        environment="PROD",
        qualified_name="test.a",
        logical_name="a",
        platform_instance=None,
        properties_qualified_name=None,
    )
    record = SchemaFieldRecord(
        position=0,
        field_path=field_path,
        field_name=field_path,
        native_type="BIGINT",
        normalized_type=NormalizedFieldType.NUMBER,
        datahub_type="NumberTypeClass",
        description=None,
        nullable=True,
        is_part_of_key=False,
        is_partitioning_key=None,
        json_path=None,
        label=None,
        recursive=False,
        schema_field_urn=None,
    )
    observed_at = "2026-07-26T12:00:00+00:00"
    evidence = SchemaEvidence(
        dataset_urn=A,
        aspect="SchemaMetadata",
        interface="test",
        observed_at=observed_at,
        schema_name="test.a",
        schema_version=0,
        schema_hash="",
        field_count=1,
        validation_state=SchemaValidationState.VALID,
    )
    return DatasetSchemaSnapshot(
        dataset=resolved,
        canonical_identity=canonical,
        schema_name="test.a",
        platform="postgres",
        source_platform="urn:li:dataPlatform:postgres",
        environment="PROD",
        schema_version=0,
        schema_hash="",
        fields=(record,),
        observed_at=observed_at,
        evidence=evidence,
        created_time=None,
        last_modified_time=None,
        dataset_reference=None,
        cluster=None,
        primary_keys=None,
    )


def group(
    container: str,
    index: int,
    upstreams: tuple[object, ...],
    downstreams: tuple[object, ...],
    *,
    entity_type: str = "DATASET",
    transform: object | None = None,
    confidence: object | None = 1.0,
) -> FineGrainedLineageGroupObservation:
    return FineGrainedLineageGroupObservation(
        source_entity_urn=container,
        source_entity_type=entity_type,
        source_aspect=(
            "upstreamLineage"
            if entity_type == "DATASET"
            else "dataJobInputOutput"
        ),
        group_index=index,
        upstream_type="FIELD_SET",
        downstream_type="FIELD",
        upstreams=upstreams,
        downstreams=downstreams,
        transform_operation=transform,
        confidence_score=confidence,
        query=None,
        match_type=None,
    )


class LineageTransport:
    def __init__(self) -> None:
        self.direct: dict[str, tuple[LineageEntityObservation, ...]] = {}
        self.aspects: dict[
            tuple[str, str],
            FineGrainedLineageAspectObservation | None,
        ] = {}
        self.schemas: dict[str, SchemaMetadataObservation | None] = {
            A: schema(A, "source")
        }
        self.existing_schema_fields: set[str] = set()
        self.error: Exception | None = None
        self.calls: Counter[tuple[str, str]] = Counter()

    def direct_downstream_lineage_entities(
        self,
        dataset_urn: str,
    ) -> tuple[LineageEntityObservation, ...]:
        self.calls[("direct", dataset_urn)] += 1
        if self.error is not None:
            raise self.error
        return self.direct.get(dataset_urn, ())

    def fine_grained_lineage(
        self,
        entity_urn: str,
        entity_type: str,
    ) -> FineGrainedLineageAspectObservation | None:
        self.calls[("aspect", entity_urn)] += 1
        return self.aspects.get((entity_type, entity_urn))

    def schema_metadata(
        self,
        urn: str,
    ) -> SchemaMetadataObservation | None:
        self.calls[("schema", urn)] += 1
        return self.schemas.get(urn)

    def schema_field_exists(self, schema_field_urn: str) -> bool:
        self.calls[("exists", schema_field_urn)] += 1
        return schema_field_urn in self.existing_schema_fields


def configure(
    transport: LineageTransport,
    source_dataset: str,
    container: str,
    groups: tuple[FineGrainedLineageGroupObservation, ...],
    *,
    entity_type: str = "DATASET",
) -> None:
    current = list(transport.direct.get(source_dataset, ()))
    observation = LineageEntityObservation(
        urn=container,
        entity_type=entity_type,
        degree=1,
    )
    if observation not in current:
        current.append(observation)
    transport.direct[source_dataset] = tuple(current)
    existing = transport.aspects.get((entity_type, container))
    existing_groups = existing.groups if existing is not None else ()
    transport.aspects[(entity_type, container)] = (
        FineGrainedLineageAspectObservation(
            source_entity_urn=container,
            source_entity_type=entity_type,
            source_aspect=(
                "upstreamLineage"
                if entity_type == "DATASET"
                else "dataJobInputOutput"
            ),
            interface="test.get_aspect",
            groups=existing_groups + groups,
        )
    )


def retriever(
    transport: LineageTransport,
    instant: datetime | None = None,
) -> FieldLineageRetriever:
    return FieldLineageRetriever(
        transport,  # type: ignore[arg-type]
        clock=lambda: instant
        or datetime(2026, 7, 26, 12, 0, tzinfo=timezone.utc),
    )


def one_to_one(
    transport: LineageTransport,
    source_dataset: str,
    source_path: str,
    target_dataset: str,
    target_path: str,
    *,
    index: int = 0,
    transform: object | None = None,
) -> FineGrainedLineageGroupObservation:
    transport.schemas.setdefault(
        target_dataset,
        schema(target_dataset, target_path),
    )
    return group(
        target_dataset,
        index,
        (field_urn(source_dataset, source_path),),
        (field_urn(target_dataset, target_path),),
        transform=transform,
    )


class FieldLineageRetrieverTests(unittest.TestCase):
    def test_one_hop_one_to_one_dependency(self) -> None:
        transport = LineageTransport()
        mapping = one_to_one(transport, A, "source", B, "target")
        configure(transport, A, B, (mapping,))

        result = retriever(transport).retrieve_direct(
            source_snapshot(),
            "source",
        )

        self.assertEqual(result.state, LineageRetrievalState.RETRIEVED)
        self.assertEqual(result.graph.downstream_field_count, 1)
        self.assertEqual(result.graph.edges[0].downstream.key, (B, "target"))

    def test_one_hop_one_to_many_dependency(self) -> None:
        transport = LineageTransport()
        transport.schemas[B] = schema(B, "left")
        transport.schemas[C] = schema(C, "right")
        mapping = group(
            B,
            0,
            (field_urn(A, "source"),),
            (field_urn(C, "right"), field_urn(B, "left")),
        )
        configure(transport, A, B, (mapping,))

        result = retriever(transport).retrieve_direct(
            source_snapshot(),
            "source",
        )

        self.assertEqual(result.graph.downstream_field_count, 2)
        self.assertEqual(
            tuple(edge.downstream.key for edge in result.graph.edges),
            ((B, "left"), (C, "right")),
        )

    def test_many_to_one_preserves_group_and_expands_reachable_input(self) -> None:
        transport = LineageTransport()
        transport.schemas[X] = schema(X, "other")
        transport.schemas[B] = schema(B, "combined")
        mapping = group(
            B,
            0,
            (field_urn(X, "other"), field_urn(A, "source")),
            (field_urn(B, "combined"),),
        )
        configure(transport, A, B, (mapping,))

        result = retriever(transport).retrieve_direct(
            source_snapshot(),
            "source",
        )

        self.assertEqual(len(result.graph.mapping_groups[0].upstream_fields), 2)
        self.assertEqual(len(result.graph.edges), 1)
        self.assertEqual(
            result.graph.edges[0].classification,
            LineageRelationshipClassification.DERIVED,
        )

    def test_many_to_many_does_not_claim_cartesian_edges(self) -> None:
        transport = LineageTransport()
        transport.schemas[X] = schema(X, "other")
        transport.schemas[B] = schema(B, "left")
        transport.schemas[C] = schema(C, "right")
        mapping = group(
            B,
            0,
            (field_urn(A, "source"), field_urn(X, "other")),
            (field_urn(B, "left"), field_urn(C, "right")),
        )
        configure(transport, A, B, (mapping,))

        result = retriever(transport).retrieve_direct(
            source_snapshot(),
            "source",
        )

        self.assertEqual(result.state, LineageRetrievalState.PARTIAL)
        self.assertEqual(len(result.graph.edges), 0)
        self.assertEqual(
            result.graph.mapping_groups[0].expansion_state,
            MappingExpansionState.AMBIGUOUS,
        )

    def test_zero_downstream_fields_is_malformed(self) -> None:
        transport = LineageTransport()
        mapping = group(
            B,
            0,
            (field_urn(A, "source"),),
            (),
        )
        configure(transport, A, B, (mapping,))

        result = retriever(transport).retrieve_direct(
            source_snapshot(),
            "source",
        )

        self.assertEqual(result.state, LineageRetrievalState.PARTIAL)
        self.assertEqual(
            result.findings[0].code,
            FailureCode.MALFORMED_LINEAGE_GROUP,
        )

    def test_two_hop_traversal(self) -> None:
        transport = LineageTransport()
        first = one_to_one(transport, A, "source", B, "middle")
        second = one_to_one(transport, B, "middle", C, "end")
        configure(transport, A, B, (first,))
        configure(transport, B, C, (second,))

        result = retriever(transport).traverse_downstream(
            source_snapshot(),
            "source",
        )

        self.assertEqual(result.graph.downstream_field_count, 2)
        self.assertEqual(result.graph.maximum_field_depth, 2)

    def test_multiple_paths_to_same_field_are_preserved(self) -> None:
        transport = LineageTransport()
        transport.schemas[B] = schema(B, "b")
        transport.schemas[C] = schema(C, "c")
        split = group(
            B,
            0,
            (field_urn(A, "source"),),
            (field_urn(B, "b"), field_urn(C, "c")),
        )
        to_d_from_b = one_to_one(transport, B, "b", D, "d")
        to_d_from_c = one_to_one(
            transport,
            C,
            "c",
            D,
            "d",
            index=1,
        )
        configure(transport, A, B, (split,))
        configure(transport, B, D, (to_d_from_b,))
        configure(transport, C, D, (to_d_from_c,))

        result = retriever(transport).traverse_downstream(
            source_snapshot(),
            "source",
        )

        node = next(
            item for item in result.graph.nodes if item.reference.key == (D, "d")
        )
        self.assertEqual(node.path_count, 2)
        self.assertEqual(len(result.graph.paths_to((D, "d"))), 2)

    def test_duplicate_endpoint_edge_retains_both_group_ids(self) -> None:
        transport = LineageTransport()
        first = one_to_one(transport, A, "source", B, "target", index=0)
        second = one_to_one(transport, A, "source", B, "target", index=1)
        configure(transport, A, B, (second, first))

        result = retriever(transport).retrieve_direct(
            source_snapshot(),
            "source",
        )

        self.assertEqual(len(result.graph.edges), 1)
        self.assertEqual(len(result.graph.edges[0].mapping_group_ids), 2)
        self.assertEqual(len(result.graph.mapping_groups), 2)

    def test_duplicate_field_node_is_deduplicated(self) -> None:
        transport = LineageTransport()
        first = one_to_one(transport, A, "source", B, "target", index=0)
        second = one_to_one(transport, A, "source", B, "target", index=1)
        configure(transport, A, B, (first, second))

        result = retriever(transport).retrieve_direct(
            source_snapshot(),
            "source",
        )

        self.assertEqual(len(result.graph.nodes), 2)

    def test_depth_zero_is_source_and_depth_one_is_direct(self) -> None:
        transport = LineageTransport()
        mapping = one_to_one(transport, A, "source", B, "target")
        configure(transport, A, B, (mapping,))

        graph = retriever(transport).retrieve_direct(
            source_snapshot(),
            "source",
        ).graph

        self.assertEqual(graph.nodes[0].reference.key, (A, "source"))
        self.assertEqual(graph.nodes[0].depth, 0)
        self.assertEqual(graph.direct_downstream[0].depth, 1)

    def test_source_is_excluded_from_downstream_count(self) -> None:
        transport = LineageTransport()
        mapping = one_to_one(transport, A, "source", B, "target")
        configure(transport, A, B, (mapping,))

        graph = retriever(transport).retrieve_direct(
            source_snapshot(),
            "source",
        ).graph

        self.assertEqual(len(graph.nodes), 2)
        self.assertEqual(graph.downstream_field_count, 1)

    def test_unique_dataset_count(self) -> None:
        transport = LineageTransport()
        transport.schemas[B] = schema(B, "left", "right")
        mapping = group(
            B,
            0,
            (field_urn(A, "source"),),
            (field_urn(B, "left"), field_urn(B, "right")),
        )
        configure(transport, A, B, (mapping,))

        graph = retriever(transport).retrieve_direct(
            source_snapshot(),
            "source",
        ).graph

        self.assertEqual(graph.downstream_field_count, 2)
        self.assertEqual(graph.downstream_dataset_count, 1)

    def test_cross_platform_same_field_name_remains_distinct(self) -> None:
        transport = LineageTransport()
        transport.schemas[B] = schema(B, "same")
        transport.schemas[SNOW] = schema(SNOW, "same")
        mapping = group(
            B,
            0,
            (field_urn(A, "source"),),
            (field_urn(B, "same"), field_urn(SNOW, "same")),
        )
        configure(transport, A, B, (mapping,))

        graph = retriever(transport).retrieve_direct(
            source_snapshot(),
            "source",
        ).graph

        self.assertEqual(graph.downstream_field_count, 2)
        self.assertEqual(
            {node.reference.platform for node in graph.direct_downstream},
            {"postgres", "snowflake"},
        )

    def test_cycle_terminates_and_retains_closing_evidence(self) -> None:
        transport = LineageTransport()
        ab = one_to_one(transport, A, "source", B, "middle")
        bc = one_to_one(transport, B, "middle", C, "end")
        transport.schemas[A] = schema(A, "source")
        ca = group(
            A,
            0,
            (field_urn(C, "end"),),
            (field_urn(A, "source"),),
        )
        configure(transport, A, B, (ab,))
        configure(transport, B, C, (bc,))
        configure(transport, C, A, (ca,))

        graph = retriever(transport).traverse_downstream(
            source_snapshot(),
            "source",
        ).graph

        self.assertEqual(graph.downstream_field_count, 2)
        self.assertEqual(graph.maximum_field_depth, 2)
        self.assertEqual(len(graph.cycles), 1)
        self.assertEqual(len(graph.edges), 3)

    def test_missing_fine_grained_lineage_is_no_lineage(self) -> None:
        transport = LineageTransport()
        transport.direct[A] = (
            LineageEntityObservation(B, "DATASET", 1),
        )
        transport.aspects[("DATASET", B)] = None

        result = retriever(transport).retrieve_direct(
            source_snapshot(),
            "source",
        )

        self.assertEqual(result.state, LineageRetrievalState.NO_LINEAGE)
        self.assertEqual(result.graph.downstream_field_count, 0)

    def test_malformed_mapping_group(self) -> None:
        transport = LineageTransport()
        malformed = group(B, 0, (), (field_urn(B, "target"),))
        configure(transport, A, B, (malformed,))

        result = retriever(transport).retrieve_direct(
            source_snapshot(),
            "source",
        )

        self.assertEqual(result.state, LineageRetrievalState.PARTIAL)
        self.assertEqual(
            result.graph.mapping_groups[0].expansion_state,
            MappingExpansionState.MALFORMED,
        )

    def test_unresolved_downstream_dataset_schema(self) -> None:
        transport = LineageTransport()
        mapping = group(
            B,
            0,
            (field_urn(A, "source"),),
            (field_urn(B, "missing"),),
        )
        configure(transport, A, B, (mapping,))

        result = retriever(transport).retrieve_direct(
            source_snapshot(),
            "source",
        )

        self.assertEqual(result.state, LineageRetrievalState.PARTIAL)
        self.assertEqual(
            result.findings[0].code,
            FailureCode.UNRESOLVED_FIELD_REFERENCE,
        )

    def test_schema_field_entity_only_reference_is_preserved(self) -> None:
        transport = LineageTransport()
        transport.schemas[B] = schema(B, "different")
        reference = field_urn(B, "lineage_only")
        transport.existing_schema_fields.add(reference)
        mapping = group(
            B,
            0,
            (field_urn(A, "source"),),
            (reference,),
        )
        configure(transport, A, B, (mapping,))

        result = retriever(transport).retrieve_direct(
            source_snapshot(),
            "source",
        )

        self.assertEqual(result.state, LineageRetrievalState.RETRIEVED)
        self.assertEqual(
            result.graph.direct_downstream[0].reference.resolution,
            FieldReferenceResolution.SCHEMA_FIELD_ENTITY,
        )

    def test_deterministic_ordering(self) -> None:
        transport = LineageTransport()
        transport.schemas[B] = schema(B, "z", "a")
        mapping = group(
            B,
            0,
            (field_urn(A, "source"),),
            (field_urn(B, "z"), field_urn(B, "a")),
        )
        configure(transport, A, B, (mapping,))

        graph = retriever(transport).retrieve_direct(
            source_snapshot(),
            "source",
        ).graph

        self.assertEqual(
            tuple(node.reference.field_path for node in graph.direct_downstream),
            ("a", "z"),
        )

    def test_evidence_is_retained(self) -> None:
        transport = LineageTransport()
        mapping = one_to_one(
            transport,
            A,
            "source",
            B,
            "target",
            transform="COPY source",
        )
        configure(transport, A, B, (mapping,))

        graph = retriever(transport).retrieve_direct(
            source_snapshot(),
            "source",
        ).graph

        self.assertEqual(graph.evidence.mapping_group_count, 1)
        self.assertEqual(graph.evidence.explicit_edge_count, 1)
        self.assertIn("test.get_aspect", graph.evidence.interfaces)
        self.assertEqual(
            graph.edges[0].transform_operations,
            ("COPY source",),
        )

    def test_read_only_boundary(self) -> None:
        public = {
            name
            for name, value in inspect.getmembers(
                FieldLineageRetriever,
                predicate=callable,
            )
            if not name.startswith("_")
        }
        self.assertEqual(
            public,
            {"retrieve_direct", "traverse_downstream"},
        )
        methods = {
            name
            for name, value in LineageReadOnlyTransport.__dict__.items()
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
        }
        self.assertFalse(
            any(
                marker in method.casefold()
                for method in methods
                for marker in forbidden
            )
        )

    def test_no_chart_dashboard_or_governance_traversal(self) -> None:
        methods = {
            name.casefold()
            for name, value in LineageReadOnlyTransport.__dict__.items()
            if callable(value) and not name.startswith("_")
        }
        self.assertFalse(
            methods
            & {
                "charts",
                "dashboards",
                "ownership",
                "tags",
                "glossary",
                "domains",
                "products",
            }
        )

    def test_graph_semantics_ignore_observation_time(self) -> None:
        first_transport = LineageTransport()
        first_mapping = one_to_one(
            first_transport,
            A,
            "source",
            B,
            "target",
        )
        configure(first_transport, A, B, (first_mapping,))
        second_transport = LineageTransport()
        second_mapping = one_to_one(
            second_transport,
            A,
            "source",
            B,
            "target",
        )
        configure(second_transport, A, B, (second_mapping,))

        first = retriever(
            first_transport,
            datetime(2026, 7, 26, 12, tzinfo=timezone.utc),
        ).retrieve_direct(source_snapshot(), "source")
        second = retriever(
            second_transport,
            datetime(2026, 7, 26, 13, tzinfo=timezone.utc),
        ).retrieve_direct(source_snapshot(), "source")

        self.assertNotEqual(
            first.graph.evidence.observed_at,
            second.graph.evidence.observed_at,
        )
        self.assertTrue(first.graph.semantically_equals(second.graph))

    def test_direct_classification_requires_transform_evidence(self) -> None:
        transport = LineageTransport()
        mapping = one_to_one(
            transport,
            A,
            "source",
            B,
            "target",
            transform="COPY source",
        )
        configure(transport, A, B, (mapping,))

        edge = retriever(transport).retrieve_direct(
            source_snapshot(),
            "source",
        ).graph.edges[0]

        self.assertEqual(
            edge.classification,
            LineageRelationshipClassification.DIRECT,
        )

    def test_derived_classification_requires_transform_evidence(self) -> None:
        transport = LineageTransport()
        mapping = one_to_one(
            transport,
            A,
            "source",
            B,
            "target",
            transform="SUM(source)",
        )
        configure(transport, A, B, (mapping,))

        edge = retriever(transport).retrieve_direct(
            source_snapshot(),
            "source",
        ).graph.edges[0]

        self.assertEqual(
            edge.classification,
            LineageRelationshipClassification.DERIVED,
        )

    def test_missing_transform_evidence_is_unknown(self) -> None:
        transport = LineageTransport()
        mapping = one_to_one(transport, A, "source", B, "target")
        configure(transport, A, B, (mapping,))

        edge = retriever(transport).retrieve_direct(
            source_snapshot(),
            "source",
        ).graph.edges[0]

        self.assertEqual(
            edge.classification,
            LineageRelationshipClassification.UNKNOWN,
        )

    def test_invalid_starting_field_is_rejected(self) -> None:
        result = retriever(LineageTransport()).retrieve_direct(
            source_snapshot(),
            "absent",
        )

        self.assertEqual(result.state, LineageRetrievalState.INVALID_LINEAGE)
        self.assertEqual(
            result.failure.code,
            FailureCode.UNRESOLVED_FIELD_REFERENCE,
        )

    def test_transport_failure_is_distinct_from_no_lineage(self) -> None:
        transport = LineageTransport()
        transport.error = ConnectionError("unavailable")

        result = retriever(transport).retrieve_direct(
            source_snapshot(),
            "source",
        )

        self.assertEqual(result.state, LineageRetrievalState.UNAVAILABLE)
        self.assertEqual(result.failure.code, FailureCode.CONNECTION_ERROR)

    def test_lineage_error_diagnostics_redact_secrets(self) -> None:
        transport = LineageTransport()
        secret = "lineage-secret-token"
        transport.error = ConnectionError(
            "unavailable",
            diagnostic=f"Authorization: Bearer {secret}",
        )

        result = retriever(transport).retrieve_direct(
            source_snapshot(),
            "source",
        )
        serialized = json.dumps(result.to_dict())

        self.assertNotIn(secret, serialized)
        self.assertIn("<redacted>", serialized)

    def test_request_local_caches_do_not_change_graph_semantics(self) -> None:
        transport = LineageTransport()
        transport.schemas[B] = schema(B, "b1", "b2")
        transport.schemas[C] = schema(C, "c1", "c2")
        split = group(
            B,
            0,
            (field_urn(A, "source"),),
            (field_urn(B, "b1"), field_urn(B, "b2")),
        )
        first = group(
            C,
            0,
            (field_urn(B, "b1"),),
            (field_urn(C, "c1"),),
        )
        second = group(
            C,
            1,
            (field_urn(B, "b2"),),
            (field_urn(C, "c2"),),
        )
        configure(transport, A, B, (split,))
        configure(transport, B, C, (first, second))

        graph = retriever(transport).traverse_downstream(
            source_snapshot(),
            "source",
        ).graph

        self.assertEqual(graph.downstream_field_count, 4)
        self.assertEqual(transport.calls[("direct", B)], 1)
        self.assertEqual(transport.calls[("aspect", C)], 1)
        self.assertEqual(transport.calls[("schema", C)], 1)


if __name__ == "__main__":
    unittest.main()
