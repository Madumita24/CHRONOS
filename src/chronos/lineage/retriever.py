"""Deterministic read-only downstream fine-grained lineage traversal."""

from __future__ import annotations

import logging
from collections import defaultdict, deque
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Callable

from datahub.metadata.urns import DatasetUrn, SchemaFieldUrn

from chronos.datahub._transport import (
    FineGrainedLineageAspectObservation,
    FineGrainedLineageGroupObservation,
    LineageEntityObservation,
    LineageReadOnlyTransport,
    SchemaMetadataObservation,
)
from chronos.datahub.errors import (
    DataHubAccessError,
    FailureCode,
    LineageEvidenceConflict,
    MalformedLineageGroup,
    UnexpectedLineageError,
    UnresolvedFieldReference,
    redact_secrets,
)
from chronos.datahub.logging_utils import log_event
from chronos.resolution.models import CanonicalSchemaFieldIdentity
from chronos.schema.models import DatasetSchemaSnapshot, FieldLookupState

from .models import (
    DatasetLineageIndexEntry,
    EdgeKey,
    FieldKey,
    FieldLineageEdge,
    FieldLineageGraph,
    FieldLineageNode,
    FieldReference,
    FieldReferenceResolution,
    LineageCycle,
    LineageEvidence,
    LineageFailure,
    LineageFinding,
    LineageMappingGroup,
    LineagePath,
    LineageRelationshipClassification,
    LineageRetrievalResult,
    LineageRetrievalState,
    LineageValidationState,
    MappingExpansionState,
)


Clock = Callable[[], datetime]
_MAX_PATHS_PER_FIELD = 128
_LINEAGE_GRAPHQL_INTERFACE = "GraphQL Query.scrollAcrossLineage"


@dataclass
class _TraversalContext:
    transport: LineageReadOnlyTransport
    source_snapshot: DatasetSchemaSnapshot
    source: FieldReference
    observed_at: str
    candidate_cache: dict[str, tuple[LineageEntityObservation, ...]]
    aspect_cache: dict[
        tuple[str, str],
        FineGrainedLineageAspectObservation | None,
    ]
    schema_cache: dict[str, SchemaMetadataObservation | None]
    field_path_cache: dict[str, frozenset[str] | None]
    schema_field_exists_cache: dict[str, bool]
    references: dict[FieldKey, FieldReference]
    groups: dict[str, LineageMappingGroup]
    edge_group_ids: dict[EdgeKey, set[str]]
    findings: list[LineageFinding]
    finding_keys: set[tuple[object, ...]]
    interfaces: set[str]


class FieldLineageRetriever:
    """Retrieve direct or complete downstream field dependency evidence."""

    def __init__(
        self,
        transport: LineageReadOnlyTransport,
        *,
        logger: logging.Logger | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._transport = transport
        self._logger = logger or logging.getLogger("chronos.lineage")
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def retrieve_direct(
        self,
        source_snapshot: DatasetSchemaSnapshot,
        field_path: str,
    ) -> LineageRetrievalResult:
        """Retrieve only one verified field-dependency hop."""

        return self._retrieve(
            source_snapshot,
            field_path,
            recursive=False,
        )

    def traverse_downstream(
        self,
        source_snapshot: DatasetSchemaSnapshot,
        field_path: str,
    ) -> LineageRetrievalResult:
        """Traverse all reachable verified fine-grained field dependencies."""

        return self._retrieve(
            source_snapshot,
            field_path,
            recursive=True,
        )

    def _retrieve(
        self,
        source_snapshot: DatasetSchemaSnapshot,
        field_path: str,
        *,
        recursive: bool,
    ) -> LineageRetrievalResult:
        source_result = source_snapshot.lookup_field(field_path)
        if source_result.state is not FieldLookupState.FOUND:
            return LineageRetrievalResult(
                state=LineageRetrievalState.INVALID_LINEAGE,
                graph=None,
                findings=(),
                failure=LineageFailure(
                    code=FailureCode.UNRESOLVED_FIELD_REFERENCE,
                    message=(
                        "The starting field is absent from the verified "
                        "source schema snapshot."
                    ),
                    diagnostic=f"Requested field path: {field_path}.",
                ),
            )
        assert source_result.field is not None

        observed_at = _timestamp(self._clock)
        source_identity = CanonicalSchemaFieldIdentity(
            parent_dataset=source_snapshot.canonical_identity,
            field_path=source_result.field.field_path,
            field_name=source_result.field.field_name,
            display_identity=(
                f"{source_snapshot.canonical_identity.display_identity} / "
                f"{source_result.field.field_path}"
                if source_snapshot.canonical_identity.display_identity
                else None
            ),
        )
        source = FieldReference(
            dataset_urn=source_snapshot.dataset_urn,
            field_path=source_result.field.field_path,
            field_name=source_result.field.field_name,
            platform=source_snapshot.platform,
            dataset_name=source_snapshot.dataset.qualified_name,
            environment=source_snapshot.environment,
            canonical_identity=source_identity,
            display_identity=source_identity.display_identity,
            schema_field_urn=source_result.field.schema_field_urn,
            resolution=FieldReferenceResolution.SOURCE_SNAPSHOT,
        )
        context = _TraversalContext(
            transport=self._transport,
            source_snapshot=source_snapshot,
            source=source,
            observed_at=observed_at,
            candidate_cache={},
            aspect_cache={},
            schema_cache={},
            field_path_cache={
                source_snapshot.dataset_urn: frozenset(
                    field.field_path for field in source_snapshot.fields
                )
            },
            schema_field_exists_cache={},
            references={source.key: source},
            groups={},
            edge_group_ids=defaultdict(set),
            findings=[],
            finding_keys=set(),
            interfaces={_LINEAGE_GRAPHQL_INTERFACE},
        )

        log_event(
            self._logger,
            logging.INFO,
            "field_lineage_retrieval_started",
            source_dataset_urn=source.dataset_urn,
            source_field_path=source.field_path,
            recursive=recursive,
        )
        try:
            queue: deque[FieldKey] = deque((source.key,))
            expanded: set[FieldKey] = set()
            while queue:
                current_key = queue.popleft()
                if current_key in expanded:
                    continue
                expanded.add(current_key)
                current = context.references[current_key]
                discovered = self._expand_one_hop(current, context)
                if recursive:
                    for reference in discovered:
                        if reference.key not in expanded:
                            queue.append(reference.key)
                else:
                    break
            graph = _build_graph(context)
        except DataHubAccessError as exc:
            return _unavailable_result(exc)
        except Exception as exc:
            return _unavailable_result(
                UnexpectedLineageError(
                    "Lineage retrieval failed unexpectedly.",
                    diagnostic=redact_secrets(exc),
                )
            )

        if context.findings or any(
            group.expansion_state is not MappingExpansionState.EXPANDED
            for group in context.groups.values()
        ):
            state = LineageRetrievalState.PARTIAL
        elif graph.downstream_field_count == 0:
            state = LineageRetrievalState.NO_LINEAGE
        else:
            state = LineageRetrievalState.RETRIEVED

        log_event(
            self._logger,
            logging.INFO,
            "field_lineage_retrieval_finished",
            source_dataset_urn=source.dataset_urn,
            source_field_path=source.field_path,
            recursive=recursive,
            state=state.value,
            downstream_field_count=graph.downstream_field_count,
            downstream_dataset_count=graph.downstream_dataset_count,
            maximum_field_depth=graph.maximum_field_depth,
        )
        return LineageRetrievalResult(
            state=state,
            graph=graph,
            findings=graph.findings,
            failure=None,
        )

    def _expand_one_hop(
        self,
        current: FieldReference,
        context: _TraversalContext,
    ) -> tuple[FieldReference, ...]:
        discovered: dict[FieldKey, FieldReference] = {}
        for entity in _direct_entities(current.dataset_urn, context):
            aspect = _lineage_aspect(entity, context)
            if aspect is None:
                continue
            context.interfaces.add(aspect.interface)
            for raw_group in aspect.groups:
                result = _materialize_group(
                    raw_group,
                    aspect,
                    current,
                    context,
                )
                if result is None:
                    continue
                group, downstream = result
                context.groups[group.group_id] = group
                if group.expansion_state is not MappingExpansionState.EXPANDED:
                    continue
                for target in downstream:
                    edge_key = (current.key, target.key)
                    context.edge_group_ids[edge_key].add(group.group_id)
                    existing = context.references.get(target.key)
                    if existing is None:
                        context.references[target.key] = target
                        existing = target
                    discovered[target.key] = existing
        return tuple(discovered[key] for key in sorted(discovered))


def _direct_entities(
    dataset_urn: str,
    context: _TraversalContext,
) -> tuple[LineageEntityObservation, ...]:
    if dataset_urn not in context.candidate_cache:
        context.candidate_cache[dataset_urn] = tuple(
            context.transport.direct_downstream_lineage_entities(dataset_urn)
        )
    return context.candidate_cache[dataset_urn]


def _lineage_aspect(
    entity: LineageEntityObservation,
    context: _TraversalContext,
) -> FineGrainedLineageAspectObservation | None:
    key = (entity.entity_type, entity.urn)
    if key not in context.aspect_cache:
        context.aspect_cache[key] = context.transport.fine_grained_lineage(
            entity.urn,
            entity.entity_type,
        )
    return context.aspect_cache[key]


def _materialize_group(
    raw: FineGrainedLineageGroupObservation,
    aspect: FineGrainedLineageAspectObservation,
    current: FieldReference,
    context: _TraversalContext,
) -> tuple[LineageMappingGroup, tuple[FieldReference, ...]] | None:
    group_id = (
        f"{raw.source_entity_urn}|{raw.source_aspect}|"
        f"{raw.group_index}"
    )
    raw_upstream = tuple(_raw_reference_text(item) for item in raw.upstreams)
    raw_downstream = tuple(
        _raw_reference_text(item) for item in raw.downstreams
    )
    preliminary_upstream = tuple(
        _field_reference(item, context, record_error=False)
        for item in raw.upstreams
        if isinstance(item, str)
    )
    preliminary_upstream = tuple(
        item for item in preliminary_upstream if item is not None
    )

    if not raw.upstreams:
        error = MalformedLineageGroup(
            "Fine-grained lineage group has no upstream fields.",
        )
        _add_finding(context, error, group_id=group_id)
        group = _group(
            raw,
            aspect,
            group_id,
            raw_upstream,
            raw_downstream,
            (),
            (),
            MappingExpansionState.MALFORMED,
            error.safe_message,
            context.observed_at,
        )
        return group, ()

    if current.key not in {
        reference.key for reference in preliminary_upstream
    }:
        return None

    malformed_reason = _validate_group_metadata(raw)
    if not raw.downstreams and malformed_reason is None:
        malformed_reason = (
            "Fine-grained lineage group has no downstream fields."
        )
    if malformed_reason is not None:
        error = MalformedLineageGroup(malformed_reason)
        _add_finding(context, error, group_id=group_id)
        group = _group(
            raw,
            aspect,
            group_id,
            raw_upstream,
            raw_downstream,
            preliminary_upstream,
            (),
            MappingExpansionState.MALFORMED,
            malformed_reason,
            context.observed_at,
        )
        return group, ()

    unresolved = False
    upstream_fields: list[FieldReference] = []
    downstream_fields: list[FieldReference] = []
    for raw_reference in raw.upstreams:
        reference = (
            _field_reference(
                raw_reference,
                context,
                group_id=group_id,
            )
            if isinstance(raw_reference, str)
            else None
        )
        verified = (
            _verify_field(reference, context, group_id)
            if reference is not None
            else None
        )
        if verified is None:
            unresolved = True
        else:
            upstream_fields.append(verified)
    for raw_reference in raw.downstreams:
        reference = (
            _field_reference(
                raw_reference,
                context,
                group_id=group_id,
            )
            if isinstance(raw_reference, str)
            else None
        )
        verified = (
            _verify_field(reference, context, group_id)
            if reference is not None
            else None
        )
        if verified is None:
            unresolved = True
        else:
            downstream_fields.append(verified)

    upstream = tuple(
        sorted(
            _deduplicate_references(upstream_fields).values(),
            key=lambda item: item.key,
        )
    )
    downstream = tuple(
        sorted(
            _deduplicate_references(downstream_fields).values(),
            key=lambda item: item.key,
        )
    )
    if unresolved:
        reason = (
            "One or more fine-grained lineage field references could not "
            "be verified."
        )
        group = _group(
            raw,
            aspect,
            group_id,
            raw_upstream,
            raw_downstream,
            upstream,
            downstream,
            MappingExpansionState.UNRESOLVED,
            reason,
            context.observed_at,
        )
        return group, ()

    if len(upstream) > 1 and len(downstream) > 1:
        reason = (
            "Many-to-many group retained without Cartesian field-edge "
            "expansion."
        )
        group = _group(
            raw,
            aspect,
            group_id,
            raw_upstream,
            raw_downstream,
            upstream,
            downstream,
            MappingExpansionState.AMBIGUOUS,
            reason,
            context.observed_at,
        )
        return group, ()

    group = _group(
        raw,
        aspect,
        group_id,
        raw_upstream,
        raw_downstream,
        upstream,
        downstream,
        MappingExpansionState.EXPANDED,
        None,
        context.observed_at,
    )
    return group, downstream


def _validate_group_metadata(
    raw: FineGrainedLineageGroupObservation,
) -> str | None:
    for name, value in (
        ("transform operation", raw.transform_operation),
        ("query", raw.query),
        ("match type", raw.match_type),
    ):
        if value is not None and not isinstance(value, str):
            return f"Fine-grained lineage {name} is malformed."
    if raw.confidence_score is not None:
        confidence = raw.confidence_score
        if (
            isinstance(confidence, bool)
            or not isinstance(confidence, (int, float))
            or not 0 <= float(confidence) <= 1
        ):
            return "Fine-grained lineage confidence is malformed."
    if any(not isinstance(item, str) for item in raw.upstreams):
        return "Fine-grained lineage upstream reference is malformed."
    if any(not isinstance(item, str) for item in raw.downstreams):
        return "Fine-grained lineage downstream reference is malformed."
    return None


def _group(
    raw: FineGrainedLineageGroupObservation,
    aspect: FineGrainedLineageAspectObservation,
    group_id: str,
    raw_upstream: tuple[str, ...],
    raw_downstream: tuple[str, ...],
    upstream: tuple[FieldReference, ...],
    downstream: tuple[FieldReference, ...],
    state: MappingExpansionState,
    reason: str | None,
    observed_at: str,
) -> LineageMappingGroup:
    return LineageMappingGroup(
        group_id=group_id,
        source_entity_urn=raw.source_entity_urn,
        source_entity_type=raw.source_entity_type,
        source_aspect=raw.source_aspect,
        source_interface=aspect.interface,
        source_group_index=raw.group_index,
        upstream_type=raw.upstream_type,
        downstream_type=raw.downstream_type,
        raw_upstream_references=raw_upstream,
        raw_downstream_references=raw_downstream,
        upstream_fields=upstream,
        downstream_fields=downstream,
        transform_operation=(
            raw.transform_operation
            if isinstance(raw.transform_operation, str)
            else None
        ),
        confidence_score=(
            float(raw.confidence_score)
            if isinstance(raw.confidence_score, (int, float))
            and not isinstance(raw.confidence_score, bool)
            else None
        ),
        query=raw.query if isinstance(raw.query, str) else None,
        match_type=(
            raw.match_type if isinstance(raw.match_type, str) else None
        ),
        expansion_state=state,
        ambiguity_reason=reason,
        observed_at=observed_at,
    )


def _field_reference(
    raw_reference: str,
    context: _TraversalContext,
    *,
    group_id: str | None = None,
    record_error: bool = True,
) -> FieldReference | None:
    try:
        schema_field = SchemaFieldUrn.from_string(raw_reference)
        dataset = DatasetUrn.from_string(schema_field.parent)
    except Exception:
        if record_error:
            error = UnresolvedFieldReference(
                "Fine-grained lineage contains a malformed field reference.",
                diagnostic=redact_secrets(raw_reference),
            )
            _add_finding(
                context,
                error,
                group_id=group_id,
                field_reference=redact_secrets(raw_reference),
            )
        return None
    platform = str(dataset.platform)
    if platform.startswith("urn:li:dataPlatform:"):
        platform = platform.rsplit(":", 1)[-1]
    canonical = (
        context.source.canonical_identity
        if (schema_field.parent, schema_field.field_path)
        == context.source.key
        else None
    )
    display_identity = (
        context.source.display_identity
        if canonical is not None
        else None
    )
    return FieldReference(
        dataset_urn=schema_field.parent,
        field_path=schema_field.field_path,
        field_name=_field_leaf_name(schema_field.field_path),
        platform=platform,
        dataset_name=dataset.name,
        environment=dataset.env,
        canonical_identity=canonical,
        display_identity=display_identity,
        schema_field_urn=raw_reference,
        resolution=FieldReferenceResolution.UNVERIFIED,
    )


def _verify_field(
    reference: FieldReference,
    context: _TraversalContext,
    group_id: str,
) -> FieldReference | None:
    if reference.key == context.source.key:
        return replace(
            reference,
            canonical_identity=context.source.canonical_identity,
            display_identity=context.source.display_identity,
            resolution=FieldReferenceResolution.SOURCE_SNAPSHOT,
        )
    dataset_urn = reference.dataset_urn
    if dataset_urn not in context.field_path_cache:
        if dataset_urn not in context.schema_cache:
            context.schema_cache[dataset_urn] = (
                context.transport.schema_metadata(dataset_urn)
            )
        schema = context.schema_cache[dataset_urn]
        context.field_path_cache[dataset_urn] = (
            frozenset(
                field.field_path
                for field in schema.fields
                if isinstance(field.field_path, str) and field.field_path
            )
            if schema is not None
            else None
        )
    field_paths = context.field_path_cache[dataset_urn]
    if field_paths is None:
        error = UnresolvedFieldReference(
            "Downstream dataset SchemaMetadata is absent.",
            diagnostic=f"Dataset URN: {dataset_urn}.",
        )
        _add_finding(
            context,
            error,
            group_id=group_id,
            field_reference=reference.schema_field_urn,
        )
        return None
    if reference.field_path in field_paths:
        return replace(
            reference,
            resolution=FieldReferenceResolution.SCHEMA_MEMBER,
        )
    schema_field_urn = reference.schema_field_urn
    if schema_field_urn is not None:
        if schema_field_urn not in context.schema_field_exists_cache:
            context.schema_field_exists_cache[schema_field_urn] = (
                context.transport.schema_field_exists(schema_field_urn)
            )
        if context.schema_field_exists_cache[schema_field_urn]:
            return replace(
                reference,
                resolution=FieldReferenceResolution.SCHEMA_FIELD_ENTITY,
            )
    if reference.field_path not in field_paths:
        error = UnresolvedFieldReference(
            "Lineage field is absent from its parent dataset schema.",
            diagnostic=f"Field reference: {reference.schema_field_urn}.",
        )
        _add_finding(
            context,
            error,
            group_id=group_id,
            field_reference=reference.schema_field_urn,
        )
        return None
    return replace(
        reference,
        resolution=FieldReferenceResolution.SCHEMA_MEMBER,
    )


def _deduplicate_references(
    references: list[FieldReference],
) -> dict[FieldKey, FieldReference]:
    result: dict[FieldKey, FieldReference] = {}
    for reference in references:
        result[reference.key] = reference
    return result


def _build_graph(context: _TraversalContext) -> FieldLineageGraph:
    group_by_id = context.groups
    edges: list[FieldLineageEdge] = []
    for edge_key in sorted(context.edge_group_ids):
        group_ids = tuple(sorted(context.edge_group_ids[edge_key]))
        groups = tuple(group_by_id[item] for item in group_ids)
        classifications = {
            classification
            for classification in (
                _group_classification(group) for group in groups
            )
            if classification is not LineageRelationshipClassification.UNKNOWN
        }
        if len(classifications) > 1:
            error = LineageEvidenceConflict(
                "Lineage groups conflict on relationship classification.",
                diagnostic=f"Mapping groups: {', '.join(group_ids)}.",
            )
            _add_finding(context, error, group_id=",".join(group_ids))
            classification = LineageRelationshipClassification.UNKNOWN
        elif classifications:
            classification = next(iter(classifications))
        else:
            classification = LineageRelationshipClassification.UNKNOWN
        upstream_key, downstream_key = edge_key
        edges.append(
            FieldLineageEdge(
                upstream=context.references[upstream_key],
                downstream=context.references[downstream_key],
                classification=classification,
                mapping_group_ids=group_ids,
                source_entity_urns=tuple(
                    sorted({group.source_entity_urn for group in groups})
                ),
                source_aspects=tuple(
                    sorted({group.source_aspect for group in groups})
                ),
                transform_operations=tuple(
                    sorted(
                        {
                            group.transform_operation
                            for group in groups
                            if group.transform_operation is not None
                        }
                    )
                ),
                confidence_scores=tuple(
                    sorted(
                        {
                            group.confidence_score
                            for group in groups
                            if group.confidence_score is not None
                        }
                    )
                ),
                observed_at=context.observed_at,
            )
        )
    edge_tuple = tuple(edges)
    depths = _shortest_depths(context.source.key, edge_tuple)
    paths, path_truncated = _paths(
        context.source.key,
        context.references,
        edge_tuple,
    )
    path_counts: dict[FieldKey, int] = defaultdict(int)
    for path in paths:
        if path.nodes:
            path_counts[path.nodes[-1].key] += 1
    nodes = tuple(
        FieldLineageNode(
            reference=context.references[key],
            depth=depth,
            path_count=1 if key == context.source.key else path_counts[key],
            paths_truncated=path_truncated.get(key, False),
        )
        for key, depth in sorted(
            depths.items(),
            key=lambda item: (item[1], item[0][0], item[0][1]),
        )
    )
    reachable_references = {
        node.reference.key: node.reference for node in nodes
    }
    dataset_index = _dataset_index(tuple(reachable_references.values()))
    cycles = _cycles(
        context.source.key,
        reachable_references,
        edge_tuple,
    )
    findings = tuple(
        sorted(
            context.findings,
            key=lambda item: (
                item.code.value,
                item.group_id or "",
                item.field_reference or "",
                item.message,
            ),
        )
    )
    validation = (
        LineageValidationState.PARTIAL
        if findings
        or any(
            group.expansion_state is not MappingExpansionState.EXPANDED
            for group in context.groups.values()
        )
        else LineageValidationState.VALID
    )
    downstream_fields = sum(
        1 for node in nodes if node.reference.key != context.source.key
    )
    downstream_datasets = len(
        {
            node.reference.dataset_urn
            for node in nodes
            if node.reference.key != context.source.key
            and node.reference.dataset_urn != context.source.dataset_urn
        }
    )
    maximum_depth = max((node.depth for node in nodes), default=0)
    evidence = LineageEvidence(
        source_field=context.source.key,
        interfaces=tuple(sorted(context.interfaces)),
        observed_at=context.observed_at,
        candidate_dataset_count=len(context.candidate_cache),
        aspect_entity_count=len(context.aspect_cache),
        mapping_group_count=len(context.groups),
        explicit_edge_count=len(edge_tuple),
        downstream_field_count=downstream_fields,
        downstream_dataset_count=downstream_datasets,
        maximum_field_depth=maximum_depth,
        validation_state=validation,
    )
    return FieldLineageGraph(
        source=context.source,
        nodes=nodes,
        edges=edge_tuple,
        mapping_groups=tuple(
            context.groups[key] for key in sorted(context.groups)
        ),
        paths=paths,
        cycles=cycles,
        dataset_index=dataset_index,
        evidence=evidence,
        findings=findings,
    )


def _group_classification(
    group: LineageMappingGroup,
) -> LineageRelationshipClassification:
    if group.expansion_state is not MappingExpansionState.EXPANDED:
        return LineageRelationshipClassification.UNKNOWN
    if len(group.upstream_fields) > 1 and len(group.downstream_fields) == 1:
        return LineageRelationshipClassification.DERIVED
    operation = (group.transform_operation or "").strip()
    if not operation:
        return LineageRelationshipClassification.UNKNOWN
    normalized = operation.casefold()
    if normalized in {"none", "identity", "noop", "no_op"}:
        return LineageRelationshipClassification.DIRECT
    if normalized.startswith("copy"):
        return LineageRelationshipClassification.DIRECT
    return LineageRelationshipClassification.DERIVED


def _shortest_depths(
    source: FieldKey,
    edges: tuple[FieldLineageEdge, ...],
) -> dict[FieldKey, int]:
    adjacency: dict[FieldKey, list[FieldKey]] = defaultdict(list)
    for edge in edges:
        adjacency[edge.upstream.key].append(edge.downstream.key)
    for neighbors in adjacency.values():
        neighbors.sort()
    depths = {source: 0}
    queue: deque[FieldKey] = deque((source,))
    while queue:
        current = queue.popleft()
        for downstream in adjacency.get(current, ()):
            candidate = depths[current] + 1
            if downstream not in depths or candidate < depths[downstream]:
                depths[downstream] = candidate
                queue.append(downstream)
    return depths


def _paths(
    source: FieldKey,
    references: dict[FieldKey, FieldReference],
    edges: tuple[FieldLineageEdge, ...],
) -> tuple[tuple[LineagePath, ...], dict[FieldKey, bool]]:
    adjacency: dict[FieldKey, list[FieldKey]] = defaultdict(list)
    for edge in edges:
        adjacency[edge.upstream.key].append(edge.downstream.key)
    for neighbors in adjacency.values():
        neighbors.sort()
    reachable = _shortest_depths(source, edges)
    collected: list[LineagePath] = []
    truncated: dict[FieldKey, bool] = {}
    for target in sorted(key for key in reachable if key != source):
        target_paths: list[tuple[FieldKey, ...]] = []
        was_truncated = False

        def visit(
            current: FieldKey,
            path: tuple[FieldKey, ...],
            visited: frozenset[FieldKey],
        ) -> None:
            nonlocal was_truncated
            if current == target:
                if len(target_paths) >= _MAX_PATHS_PER_FIELD:
                    was_truncated = True
                    return
                target_paths.append(path)
                return
            for downstream in adjacency.get(current, ()):
                if downstream in visited:
                    continue
                visit(
                    downstream,
                    path + (downstream,),
                    visited | {downstream},
                )
                if was_truncated:
                    return

        visit(source, (source,), frozenset((source,)))
        truncated[target] = was_truncated
        for path in target_paths:
            collected.append(
                LineagePath(
                    nodes=tuple(references[key] for key in path),
                    edge_keys=tuple(zip(path, path[1:])),
                )
            )
    return (
        tuple(
            sorted(
                collected,
                key=lambda item: tuple(node.key for node in item.nodes),
            )
        ),
        truncated,
    )


def _cycles(
    source: FieldKey,
    references: dict[FieldKey, FieldReference],
    edges: tuple[FieldLineageEdge, ...],
) -> tuple[LineageCycle, ...]:
    adjacency: dict[FieldKey, list[FieldKey]] = defaultdict(list)
    for edge in edges:
        adjacency[edge.upstream.key].append(edge.downstream.key)
    for neighbors in adjacency.values():
        neighbors.sort()
    visited: set[FieldKey] = set()
    stack: list[FieldKey] = []
    stack_set: set[FieldKey] = set()
    found: dict[tuple[FieldKey, ...], LineageCycle] = {}

    def visit(current: FieldKey) -> None:
        visited.add(current)
        stack.append(current)
        stack_set.add(current)
        for downstream in adjacency.get(current, ()):
            if downstream in stack_set:
                index = stack.index(downstream)
                cycle_keys = tuple(stack[index:] + [downstream])
                found[cycle_keys] = LineageCycle(
                    nodes=tuple(references[key] for key in cycle_keys),
                    closing_edge=(current, downstream),
                )
            elif downstream not in visited:
                visit(downstream)
        stack.pop()
        stack_set.remove(current)

    visit(source)
    return tuple(found[key] for key in sorted(found))


def _dataset_index(
    references: tuple[FieldReference, ...],
) -> tuple[DatasetLineageIndexEntry, ...]:
    grouped: dict[str, list[FieldReference]] = defaultdict(list)
    for reference in references:
        grouped[reference.dataset_urn].append(reference)
    result = []
    for dataset_urn in sorted(grouped):
        fields = sorted(grouped[dataset_urn], key=lambda item: item.key)
        first = fields[0]
        result.append(
            DatasetLineageIndexEntry(
                dataset_urn=dataset_urn,
                platform=first.platform,
                dataset_name=first.dataset_name,
                environment=first.environment,
                field_keys=tuple(item.key for item in fields),
            )
        )
    return tuple(result)


def _add_finding(
    context: _TraversalContext,
    error: DataHubAccessError,
    *,
    group_id: str | None = None,
    field_reference: str | None = None,
) -> None:
    key = (
        error.code,
        error.safe_message,
        group_id,
        field_reference,
    )
    if key in context.finding_keys:
        return
    context.finding_keys.add(key)
    context.findings.append(
        LineageFinding(
            code=error.code,
            message=redact_secrets(error.safe_message),
            group_id=group_id,
            field_reference=(
                redact_secrets(field_reference)
                if field_reference is not None
                else None
            ),
        )
    )


def _unavailable_result(
    error: DataHubAccessError,
) -> LineageRetrievalResult:
    return LineageRetrievalResult(
        state=LineageRetrievalState.UNAVAILABLE,
        graph=None,
        findings=(),
        failure=LineageFailure(
            code=error.code,
            message=redact_secrets(error.safe_message),
            diagnostic=(
                redact_secrets(error.diagnostic)
                if error.diagnostic is not None
                else None
            ),
        ),
    )


def _raw_reference_text(value: object) -> str:
    return value if isinstance(value, str) else repr(value)


def _field_leaf_name(field_path: str) -> str:
    return field_path.rsplit(".", 1)[-1]


def _timestamp(clock: Clock) -> str:
    value = clock()
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()
