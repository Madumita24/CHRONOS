from __future__ import annotations

from datetime import datetime, timezone

from chronos.context.models import (
    AssetContext,
    AssetContextSnapshot,
    AssetIdentity,
    AssignmentScope,
    BusinessIntelligenceClassification,
    BusinessIntelligenceContext,
    ContextEvidence,
    ContextRetrievalResult,
    ContextRetrievalState,
    MetadataState,
    OwnerAssignment,
    PipelineContext,
    StructuredPropertyAssignment,
    StructuredPropertyDefinition,
    TagAssignment,
)
from chronos.datahub.models import (
    AuthenticationResult,
    AuthenticationState,
    CanonicalSourceResult,
    CapabilityReport,
    ConfigurationSource,
    ConnectivityResult,
    EnvironmentInformation,
    ReadinessResult,
    ReadinessState,
)
from chronos.datahub.schema_types import NormalizedFieldType
from chronos.lineage.models import (
    DatasetLineageIndexEntry,
    FieldLineageEdge,
    FieldLineageGraph,
    FieldLineageNode,
    FieldReference,
    FieldReferenceResolution,
    LineageEvidence,
    LineageMappingGroup,
    LineagePath,
    LineageRelationshipClassification,
    LineageRetrievalResult,
    LineageRetrievalState,
    LineageValidationState,
    MappingExpansionState,
)
from chronos.resolution.models import (
    CanonicalDatasetIdentity,
    CanonicalSchemaFieldIdentity,
    DatasetResolutionResult,
    FieldResolutionResult,
    ResolutionEvidence,
    ResolutionState,
    ResolvedDatasetIdentity,
    ResolvedSchemaFieldIdentity,
)
from chronos.schema.models import (
    DatasetSchemaSnapshot,
    SchemaEvidence,
    SchemaFieldRecord,
    SchemaRetrievalResult,
    SchemaRetrievalState,
    SchemaValidationState,
)
from chronos.snapshot import SnapshotCompositionInputs


SOURCE_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:postgres,"
    "b2fd91.order_entry_db.order_entry.orders,PROD)"
)
OBSERVED_AT = "2026-07-26T00:00:00+00:00"


def dataset_urn(index: int) -> str:
    return (
        "urn:li:dataset:(urn:li:dataPlatform:test,"
        f"b2fd91.scope.dataset_{index},PROD)"
    )


def context_evidence(
    source_urn: str,
    aspect: str,
    target_urn: str | None = None,
) -> ContextEvidence:
    return ContextEvidence(
        source_urn=source_urn,
        interface="unit-fixture",
        aspect_or_relationship=aspect,
        target_urn=target_urn,
        relationship_path=(),
        observed_at=OBSERVED_AT,
    )


def reference(
    urn: str,
    path: str,
    *,
    platform: str = "test",
    dataset_name: str | None = None,
    resolution: FieldReferenceResolution = (
        FieldReferenceResolution.SCHEMA_MEMBER
    ),
) -> FieldReference:
    return FieldReference(
        dataset_urn=urn,
        field_path=path,
        field_name=path,
        platform=platform,
        dataset_name=dataset_name or urn,
        environment="PROD",
        canonical_identity=None,
        display_identity=f"{platform} / {dataset_name or urn} / {path}",
        schema_field_urn=f"urn:li:schemaField:({urn},{path})",
        resolution=resolution,
    )


def inputs() -> SnapshotCompositionInputs:
    canonical_dataset = CanonicalDatasetIdentity(
        platform="PostgreSQL",
        qualified_name="order_entry_db.order_entry.orders",
        environment="PROD",
        logical_name="orders",
        database="order_entry_db",
        schema="order_entry",
        display_identity="PostgreSQL / order_entry_db / order_entry / orders",
    )
    canonical_field = CanonicalSchemaFieldIdentity(
        parent_dataset=canonical_dataset,
        field_path="order_total",
        field_name="order_total",
    )
    resolved_dataset = ResolvedDatasetIdentity(
        urn=SOURCE_URN,
        urn_name="b2fd91.order_entry_db.order_entry.orders",
        platform="postgres",
        environment="PROD",
        qualified_name="order_entry_db.order_entry.orders",
        logical_name="orders",
        platform_instance=None,
        properties_qualified_name=None,
    )
    resolved_field = ResolvedSchemaFieldIdentity(
        parent_dataset_urn=SOURCE_URN,
        field_path="order_total",
        field_name="order_total",
        native_type="DOUBLE PRECISION",
        normalized_type="Number",
        description=None,
        schema_field_urn=None,
    )
    dataset_resolution = DatasetResolutionResult(
        state=ResolutionState.RESOLVED,
        requested=canonical_dataset,
        discovered_candidate_count=1,
        verified_candidate_count=1,
        resolved=resolved_dataset,
        candidates=(resolved_dataset,),
        evidence=ResolutionEvidence(
            method="candidate_search_then_exact_aspect_verification",
            interfaces=("DataHubGraph.get_urns_by_filter",),
            canonical_request=canonical_dataset.display_identity or "",
            resolved_urn=SOURCE_URN,
            verified_attributes=(),
            observed_at=OBSERVED_AT,
            snapshot_context="unit fixture",
        ),
        failure=None,
    )
    field_resolution = FieldResolutionResult(
        state=ResolutionState.RESOLVED,
        requested=canonical_field,
        parent_dataset=resolved_dataset,
        verified_candidate_count=1,
        resolved=resolved_field,
        candidates=(resolved_field,),
        evidence=ResolutionEvidence(
            method="exact_parent_schema_field_verification",
            interfaces=("SchemaMetadata.fields",),
            canonical_request="orders.order_total",
            resolved_urn=SOURCE_URN,
            verified_attributes=(),
            observed_at=OBSERVED_AT,
            snapshot_context="unit fixture",
        ),
        failure=None,
    )
    schema = _schema(canonical_dataset, resolved_dataset)
    graph = _graph(canonical_field)
    context = _context(graph)
    readiness = ReadinessResult(
        state=ReadinessState.READY,
        can_continue=True,
        configuration_source=ConfigurationSource.DATAHUB_CLI_PROFILE,
        security_warning="local test",
        connectivity=ConnectivityResult(
            reachable=True,
            healthy=True,
            endpoint="http://localhost:8080",
            latency_ms=1.0,
            http_status=200,
            diagnostic="healthy",
        ),
        authentication=AuthenticationResult(
            state=AuthenticationState.NOT_ENFORCED,
            principal="urn:li:corpuser:__datahub_system",
            diagnostic="local",
        ),
        environment=EnvironmentInformation(
            endpoint="http://localhost:8080",
            observed_gms_version="v1.5.0.6",
            expected_gms_version="v1.5.0.6",
            observed_sdk_version="1.6.0.15",
            expected_sdk_version="1.6.0.15",
            server_type="quickstart",
            server_environment="core",
            version_notes=(),
        ),
        capabilities=CapabilityReport(checks=()),
        canonical_source=CanonicalSourceResult(
            dataset_found=True,
            resolved_dataset_urn=SOURCE_URN,
            canonical_display_identity=canonical_dataset.display_identity or "",
            field_found=True,
            field_name="order_total",
            observed_field_type="Number",
            expected_field_type="Number",
            native_field_type="DOUBLE PRECISION",
            satisfies_frozen_baseline=True,
            diagnostic="verified",
        ),
        failures=(),
    )
    return SnapshotCompositionInputs(
        readiness=readiness,
        dataset_resolution=dataset_resolution,
        field_resolution=field_resolution,
        schema_retrieval=SchemaRetrievalResult(
            state=SchemaRetrievalState.RETRIEVED,
            requested=canonical_dataset,
            dataset=resolved_dataset,
            snapshot=schema,
            findings=(),
            failure=None,
        ),
        lineage_retrieval=LineageRetrievalResult(
            state=LineageRetrievalState.RETRIEVED,
            graph=graph,
            findings=(),
            failure=None,
        ),
        context_retrieval=ContextRetrievalResult(
            state=ContextRetrievalState.RETRIEVED,
            snapshot=context,
            findings=(),
            failure=None,
        ),
    )


def fixed_clock(day: int = 26):
    return lambda: datetime(2026, 7, day, tzinfo=timezone.utc)


def _schema(
    canonical: CanonicalDatasetIdentity,
    resolved: ResolvedDatasetIdentity,
) -> DatasetSchemaSnapshot:
    names = (
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
    string_fields = {
        "order_date",
        "order_mode",
        "delivery_type",
        "wait_till_complete_yn",
        "payment_method_code",
    }
    double_fields = {"order_total", "promotion_id", "cost_of_delivery"}
    records = []
    for position, name in enumerate(names):
        if name in string_fields:
            native = "TEXT"
            normalized = NormalizedFieldType.STRING
            datahub_type = "StringTypeClass"
        elif name in double_fields:
            native = "DOUBLE PRECISION"
            normalized = NormalizedFieldType.NUMBER
            datahub_type = "NumberTypeClass"
        else:
            native = "BIGINT"
            normalized = NormalizedFieldType.NUMBER
            datahub_type = "NumberTypeClass"
        records.append(
            SchemaFieldRecord(
                position=position,
                field_path=name,
                field_name=name,
                native_type=native,
                normalized_type=normalized,
                datahub_type=datahub_type,
                description=None,
                nullable=True,
                is_part_of_key=False,
                is_partitioning_key=None,
                json_path=None,
                label=None,
                recursive=False,
                schema_field_urn=None,
            )
        )
    evidence = SchemaEvidence(
        dataset_urn=SOURCE_URN,
        aspect="SchemaMetadata",
        interface="DataHubGraph.get_aspect",
        observed_at=OBSERVED_AT,
        schema_name="order_entry_db.order_entry.orders",
        schema_version=0,
        schema_hash="",
        field_count=15,
        validation_state=SchemaValidationState.VALID,
    )
    return DatasetSchemaSnapshot(
        dataset=resolved,
        canonical_identity=canonical,
        schema_name=evidence.schema_name,
        platform="postgres",
        source_platform="urn:li:dataPlatform:postgres",
        environment="PROD",
        schema_version=0,
        schema_hash="",
        fields=tuple(records),
        observed_at=OBSERVED_AT,
        evidence=evidence,
        created_time=None,
        last_modified_time=None,
        dataset_reference=None,
        cluster=None,
        primary_keys=None,
    )


def _graph(
    canonical_field: CanonicalSchemaFieldIdentity,
) -> FieldLineageGraph:
    source = reference(
        SOURCE_URN,
        "order_total",
        platform="postgres",
        dataset_name="orders",
        resolution=FieldReferenceResolution.SOURCE_SNAPSHOT,
    )
    source = FieldReference(
        **{
            **source.__dict__,
            "canonical_identity": canonical_field,
            "schema_field_urn": None,
        }
    )
    downstream = []
    for index in range(1, 21):
        downstream.append(
            reference(
                dataset_urn(index),
                "order_total",
                platform="other" if index == 2 else "test",
                dataset_name="shared_name" if index in (1, 2) else f"dataset_{index}",
            )
        )
    for index in range(1, 6):
        downstream.append(
            reference(
                dataset_urn(index),
                f"metric_{index}",
                platform="other" if index == 2 else "test",
                dataset_name=f"dataset_{index}",
            )
        )

    parent_by_key: dict[FieldKey, FieldReference] = {}
    depth_by_key: dict[FieldKey, int] = {}
    previous = source
    for depth, item in enumerate(downstream[:5], start=1):
        parent_by_key[item.key] = previous
        depth_by_key[item.key] = depth
        previous = item
    for item in downstream[5:]:
        parent_by_key[item.key] = source
        depth_by_key[item.key] = 1

    edge_pairs = [(parent_by_key[item.key], item) for item in downstream]
    edge_pairs.extend(
        [
            (downstream[0], downstream[5]),
            (downstream[1], downstream[6]),
        ]
    )
    groups = []
    edges = []
    for index, (upstream, downstream_item) in enumerate(edge_pairs):
        group_id = f"group-{index:02d}"
        groups.append(_group(group_id, index, upstream, downstream_item))
        edges.append(
            FieldLineageEdge(
                upstream=upstream,
                downstream=downstream_item,
                classification=LineageRelationshipClassification.UNKNOWN,
                mapping_group_ids=(group_id,),
                source_entity_urns=(f"urn:li:dataJob:job-{index}",),
                source_aspects=("dataJobInputOutput",),
                transform_operations=(),
                confidence_scores=(0.5,),
                observed_at=OBSERVED_AT,
            )
        )
    duplicate = _group("group-27", 27, *edge_pairs[0])
    groups.append(duplicate)
    edges[0] = FieldLineageEdge(
        **{
            **edges[0].__dict__,
            "mapping_group_ids": ("group-00", "group-27"),
            "confidence_scores": (0.5, 0.8),
        }
    )

    nodes = [
        FieldLineageNode(
            reference=source,
            depth=0,
            path_count=1,
            paths_truncated=False,
        )
    ]
    for item in downstream:
        nodes.append(
            FieldLineageNode(
                reference=item,
                depth=depth_by_key[item.key],
                path_count=2 if item in downstream[5:7] else 1,
                paths_truncated=False,
            )
        )
    paths = []
    for item in downstream:
        chain = [item]
        cursor = item
        while cursor.key != source.key:
            cursor = parent_by_key[cursor.key]
            chain.append(cursor)
        chain.reverse()
        path_edges = tuple(
            (chain[index].key, chain[index + 1].key)
            for index in range(len(chain) - 1)
        )
        paths.append(LineagePath(nodes=tuple(chain), edge_keys=path_edges))
    paths.append(
        LineagePath(
            nodes=(source, downstream[0], downstream[5]),
            edge_keys=(
                (source.key, downstream[0].key),
                (downstream[0].key, downstream[5].key),
            ),
        )
    )

    by_dataset: dict[str, list[FieldKey]] = {SOURCE_URN: [source.key]}
    platform_by_dataset = {SOURCE_URN: "postgres"}
    for item in downstream:
        by_dataset.setdefault(item.dataset_urn, []).append(item.key)
        platform_by_dataset[item.dataset_urn] = item.platform
    index = [
        DatasetLineageIndexEntry(
            dataset_urn=urn,
            platform=platform_by_dataset[urn],
            dataset_name="orders" if urn == SOURCE_URN else "shared_name",
            environment="PROD",
            field_keys=tuple(sorted(keys)),
        )
        for urn, keys in sorted(by_dataset.items())
    ]
    return FieldLineageGraph(
        source=source,
        nodes=tuple(sorted(nodes, key=lambda node: node.reference.key)),
        edges=tuple(sorted(edges, key=lambda edge: edge.key)),
        mapping_groups=tuple(groups),
        paths=tuple(paths),
        cycles=(),
        dataset_index=tuple(index),
        evidence=LineageEvidence(
            source_field=source.key,
            interfaces=("GraphQL.scrollAcrossLineage",),
            observed_at=OBSERVED_AT,
            candidate_dataset_count=21,
            aspect_entity_count=22,
            mapping_group_count=28,
            explicit_edge_count=27,
            downstream_field_count=25,
            downstream_dataset_count=20,
            maximum_field_depth=5,
            validation_state=LineageValidationState.VALID,
        ),
        findings=(),
    )


def _group(
    group_id: str,
    index: int,
    upstream: FieldReference,
    downstream: FieldReference,
) -> LineageMappingGroup:
    return LineageMappingGroup(
        group_id=group_id,
        source_entity_urn=f"urn:li:dataJob:job-{index}",
        source_entity_type="DATA_JOB",
        source_aspect="dataJobInputOutput",
        source_interface="DataHubGraph.get_aspect",
        source_group_index=index,
        upstream_type="FIELD_SET",
        downstream_type="FIELD_SET",
        raw_upstream_references=(upstream.schema_field_urn or upstream.key[1],),
        raw_downstream_references=(
            downstream.schema_field_urn or downstream.key[1],
        ),
        upstream_fields=(upstream,),
        downstream_fields=(downstream,),
        transform_operation=None,
        confidence_score=0.5,
        query=None,
        match_type=None,
        expansion_state=MappingExpansionState.EXPANDED,
        ambiguity_reason=None,
        observed_at=OBSERVED_AT,
    )


def _context(graph: FieldLineageGraph) -> AssetContextSnapshot:
    pipeline = PipelineContext(
        job_urn="urn:li:dataJob:fixture-export",
        job_name="fixture export",
        job_platform="spark",
        flow_urn="urn:li:dataFlow:fixture",
        flow_name="fixture flow",
        flow_platform="spark",
        related_field_keys=(graph.source.key, graph.nodes[1].reference.key),
        mapping_group_ids=("group-00",),
        state=MetadataState.PRESENT,
        evidence=context_evidence(
            "urn:li:dataJob:fixture-export",
            "dataJobInputOutput",
        ),
    )
    dashboard = BusinessIntelligenceContext(
        urn="urn:li:dashboard:(test,fixture)",
        entity_type="DASHBOARD",
        platform="test",
        name="Order Entry Dashboard",
        qualified_name="Test / Order Entry Dashboard",
        classification=(
            BusinessIntelligenceClassification.REACHABLE_CONTEXT
        ),
        relationship_path=(
            dataset_urn(20),
            "urn:li:chart:(test,fixture)",
            "urn:li:dashboard:(test,fixture)",
        ),
        state=MetadataState.PRESENT,
        evidence=ContextEvidence(
            source_urn=dataset_urn(20),
            interface="GraphQL.scrollAcrossLineage",
            aspect_or_relationship="downstream_lineage",
            target_urn="urn:li:dashboard:(test,fixture)",
            relationship_path=(
                dataset_urn(20),
                "urn:li:chart:(test,fixture)",
                "urn:li:dashboard:(test,fixture)",
            ),
            observed_at=OBSERVED_AT,
        ),
    )
    assets = []
    for entry in graph.dataset_index:
        source = entry.dataset_urn == SOURCE_URN
        first_downstream = entry.dataset_urn == dataset_urn(1)
        owners = (
            (
                OwnerAssignment(
                    owner_urn="urn:li:corpuser:fixture",
                    owner_kind="corporate_user",
                    display_name="Fixture Owner",
                    ownership_type="TECHNICAL_OWNER",
                    ownership_type_urn=None,
                    state=MetadataState.PRESENT,
                    evidence=context_evidence(
                        entry.dataset_urn,
                        "ownership",
                        "urn:li:corpuser:fixture",
                    ),
                ),
            )
            if source
            else ()
        )
        tags = (
            (
                TagAssignment(
                    tag_urn="urn:li:tag:unresolved",
                    name=None,
                    scope=AssignmentScope.ENTITY,
                    target_urn=entry.dataset_urn,
                    field_path=None,
                    state=MetadataState.UNRESOLVED,
                    evidence=context_evidence(
                        entry.dataset_urn,
                        "globalTags",
                        "urn:li:tag:unresolved",
                    ),
                ),
            )
            if first_downstream
            else ()
        )
        structured = (
            StructuredPropertyAssignment(
                property_urn="urn:li:structuredProperty:fixture.score",
                qualified_name="fixture.score",
                display_name="Fixture Score",
                values=(90.0,),
                value_type="NUMBER",
                value_type_urn="urn:li:dataType:datahub.number",
                assignment_target=entry.dataset_urn,
                evidence=context_evidence(
                    entry.dataset_urn,
                    "structuredProperties",
                    "urn:li:structuredProperty:fixture.score",
                ),
            ),
        )
        base_evidence = (
            context_evidence(entry.dataset_urn, "ownership"),
            context_evidence(entry.dataset_urn, "domains"),
            context_evidence(entry.dataset_urn, "globalTags"),
            context_evidence(entry.dataset_urn, "glossaryTerms"),
        )
        assets.append(
            AssetContext(
                asset=AssetIdentity(
                    urn=entry.dataset_urn,
                    entity_type="DATASET",
                    platform=entry.platform,
                    name=entry.dataset_name,
                    environment=entry.environment,
                ),
                owners=owners,
                ownership_state=(
                    MetadataState.PRESENT
                    if owners
                    else MetadataState.ABSENT
                ),
                domains=(),
                domain_state=MetadataState.ABSENT,
                tags=tags,
                tag_state=(
                    MetadataState.UNRESOLVED
                    if tags
                    else MetadataState.ABSENT
                ),
                glossary_terms=(),
                glossary_state=MetadataState.ABSENT,
                structured_properties=structured,
                structured_property_state=MetadataState.PRESENT,
                data_products=(),
                data_product_state=MetadataState.ABSENT,
                documents=(),
                document_state=MetadataState.ABSENT,
                pipeline_context=(pipeline,) if source else (),
                pipeline_state=(
                    MetadataState.PRESENT
                    if source
                    else MetadataState.ABSENT
                ),
                bi_context=(dashboard,) if entry.dataset_urn == dataset_urn(20) else (),
                bi_state=(
                    MetadataState.PRESENT
                    if entry.dataset_urn == dataset_urn(20)
                    else MetadataState.ABSENT
                ),
                evidence=base_evidence,
            )
        )
    definition = StructuredPropertyDefinition(
        property_urn="urn:li:structuredProperty:fixture.score",
        qualified_name="fixture.score",
        display_name="Fixture Score",
        value_type="NUMBER",
        value_type_urn="urn:li:dataType:datahub.number",
        evidence=context_evidence(
            "urn:li:structuredProperty:fixture.score",
            "structuredPropertyDefinition",
        ),
    )
    return AssetContextSnapshot(
        source_field=graph.source.key,
        assets=tuple(assets),
        structured_property_definitions=(definition,),
        pipeline_context=(pipeline,),
        bi_context=(dashboard,),
        findings=(),
        observed_at=OBSERVED_AT,
    )
