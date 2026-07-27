"""Deterministic, cached, read-only Phase 1.5 context retrieval."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Sequence

from chronos.datahub._transport import (
    BusinessIntelligenceEntityObservation,
    ContextLineageEntityObservation,
    ContextReadOnlyTransport,
    GovernanceAspectObservation,
    MetadataReferenceObservation,
)
from chronos.datahub.errors import (
    DataHubAccessError,
    FailureCode,
    UnexpectedContextError,
    redact_secrets,
)
from chronos.lineage.models import FieldKey, FieldLineageGraph

from .models import (
    AssetContext,
    AssetContextSnapshot,
    AssetIdentity,
    AssignmentScope,
    BusinessIntelligenceClassification,
    BusinessIntelligenceContext,
    ContextEvidence,
    ContextFailure,
    ContextFinding,
    ContextRetrievalResult,
    ContextRetrievalState,
    DataProductMembership,
    DocumentContext,
    DomainAssignment,
    GlossaryTermAssignment,
    MetadataState,
    OwnerAssignment,
    PipelineContext,
    StructuredPropertyAssignment,
    StructuredPropertyDefinition,
    TagAssignment,
)


Clock = Callable[[], datetime]


@dataclass
class _RetrievalContext:
    transport: ContextReadOnlyTransport
    graph: FieldLineageGraph
    observed_at: str
    scope_urns: frozenset[str]
    relevant_fields: dict[str, frozenset[str]]
    governance_cache: dict[str, GovernanceAspectObservation]
    reference_cache: dict[
        tuple[str, str],
        MetadataReferenceObservation,
    ]
    structured_assignment_cache: dict[str, Sequence[object]]
    product_cache: dict[str, Sequence[object]]
    document_cache: dict[str, Sequence[object]]
    pipeline_cache: dict[str, object | None]
    lineage_cache: dict[
        str,
        tuple[ContextLineageEntityObservation, ...],
    ]
    bi_entity_cache: dict[
        tuple[str, str],
        BusinessIntelligenceEntityObservation | None,
    ]
    findings: list[ContextFinding]
    finding_keys: set[tuple[FailureCode, str | None, str | None, str]]
    partial: bool


class AssetContextRetriever:
    """Collect stored governance and reachable context for one lineage graph."""

    def __init__(
        self,
        transport: ContextReadOnlyTransport,
        *,
        clock: Clock | None = None,
    ) -> None:
        self._transport = transport
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def retrieve(
        self,
        graph: FieldLineageGraph,
    ) -> ContextRetrievalResult:
        try:
            return self._retrieve(graph)
        except DataHubAccessError as exc:
            return _unavailable(exc)
        except Exception as exc:
            return _unavailable(
                UnexpectedContextError(
                    "Unexpected context retrieval failure.",
                    diagnostic=redact_secrets(exc),
                )
            )

    def _retrieve(
        self,
        graph: FieldLineageGraph,
    ) -> ContextRetrievalResult:
        observed_at = _timestamp(self._clock)
        scope_urns = frozenset(
            entry.dataset_urn for entry in graph.dataset_index
        )
        relevant_fields: dict[str, set[str]] = {}
        for node in graph.nodes:
            relevant_fields.setdefault(
                node.reference.dataset_urn,
                set(),
            ).add(node.reference.field_path)
        context = _RetrievalContext(
            transport=self._transport,
            graph=graph,
            observed_at=observed_at,
            scope_urns=scope_urns,
            relevant_fields={
                urn: frozenset(paths)
                for urn, paths in relevant_fields.items()
            },
            governance_cache={},
            reference_cache={},
            structured_assignment_cache={},
            product_cache={},
            document_cache={},
            pipeline_cache={},
            lineage_cache={},
            bi_entity_cache={},
            findings=[],
            finding_keys=set(),
            partial=False,
        )
        definitions = self._property_definitions(context)
        pipelines = self._pipeline_context(context)
        assets = tuple(
            self._asset_context(entry, pipelines, context)
            for entry in graph.dataset_index
        )
        bi_context = _deduplicate_bi(
            item for asset in assets for item in asset.bi_context
        )
        findings = tuple(
            sorted(
                context.findings,
                key=lambda item: (
                    item.code.value,
                    item.asset_urn or "",
                    item.reference_urn or "",
                    item.message,
                ),
            )
        )
        snapshot = AssetContextSnapshot(
            source_field=graph.source.key,
            assets=assets,
            structured_property_definitions=definitions,
            pipeline_context=pipelines,
            bi_context=bi_context,
            findings=findings,
            observed_at=observed_at,
        )
        return ContextRetrievalResult(
            state=(
                ContextRetrievalState.PARTIAL
                if context.partial
                else ContextRetrievalState.RETRIEVED
            ),
            snapshot=snapshot,
            findings=findings,
            failure=None,
        )

    def _property_definitions(
        self,
        context: _RetrievalContext,
    ) -> tuple[StructuredPropertyDefinition, ...]:
        try:
            observations = (
                context.transport.structured_property_definitions()
            )
        except DataHubAccessError as exc:
            _retrieval_finding(context, exc)
            return ()
        return tuple(
            StructuredPropertyDefinition(
                property_urn=item.property_urn,
                qualified_name=item.qualified_name,
                display_name=item.display_name,
                value_type=item.value_type,
                value_type_urn=item.value_type_urn,
                evidence=_evidence(
                    item.property_urn,
                    item.interface,
                    "structuredPropertyDefinition",
                    item.value_type_urn,
                    context.observed_at,
                ),
            )
            for item in sorted(
                observations,
                key=lambda item: item.property_urn,
            )
        )

    def _pipeline_context(
        self,
        context: _RetrievalContext,
    ) -> tuple[PipelineContext, ...]:
        related: dict[str, tuple[set[FieldKey], set[str]]] = {}
        for group in context.graph.mapping_groups:
            if group.source_entity_type != "DATA_JOB":
                continue
            fields, group_ids = related.setdefault(
                group.source_entity_urn,
                (set(), set()),
            )
            fields.update(item.key for item in group.upstream_fields)
            fields.update(item.key for item in group.downstream_fields)
            group_ids.add(group.group_id)
        result = []
        for job_urn in sorted(related):
            fields, group_ids = related[job_urn]
            observation = self._pipeline_observation(job_urn, context)
            if observation is None:
                result.append(
                    PipelineContext(
                        job_urn=job_urn,
                        job_name=None,
                        job_platform=None,
                        flow_urn=None,
                        flow_name=None,
                        flow_platform=None,
                        related_field_keys=tuple(sorted(fields)),
                        mapping_group_ids=tuple(sorted(group_ids)),
                        state=MetadataState.UNRESOLVED,
                        evidence=_evidence(
                            job_urn,
                            "GraphQL Query.dataJob",
                            "dataJobInputOutput",
                            None,
                            context.observed_at,
                        ),
                    )
                )
                continue
            result.append(
                PipelineContext(
                    job_urn=observation.job_urn,
                    job_name=observation.job_name,
                    job_platform=observation.job_platform,
                    flow_urn=observation.flow_urn,
                    flow_name=observation.flow_name,
                    flow_platform=observation.flow_platform,
                    related_field_keys=tuple(sorted(fields)),
                    mapping_group_ids=tuple(sorted(group_ids)),
                    state=MetadataState.PRESENT,
                    evidence=_evidence(
                        observation.job_urn,
                        observation.interface,
                        "dataJobInputOutput",
                        observation.flow_urn,
                        context.observed_at,
                    ),
                )
            )
        return tuple(result)

    def _pipeline_observation(
        self,
        job_urn: str,
        context: _RetrievalContext,
    ) -> object | None:
        if job_urn in context.pipeline_cache:
            return context.pipeline_cache[job_urn]
        try:
            observation = context.transport.pipeline_entity(job_urn)
        except DataHubAccessError as exc:
            _retrieval_finding(
                context,
                exc,
                asset_urn=job_urn,
            )
            observation = None
        context.pipeline_cache[job_urn] = observation
        return observation

    def _asset_context(
        self,
        entry: object,
        pipelines: tuple[PipelineContext, ...],
        context: _RetrievalContext,
    ) -> AssetContext:
        asset_urn = entry.dataset_urn
        identity = AssetIdentity(
            urn=asset_urn,
            entity_type="DATASET",
            platform=entry.platform,
            name=entry.dataset_name,
            environment=entry.environment,
        )
        governance = self._governance(asset_urn, context)
        if governance is None:
            owners: tuple[OwnerAssignment, ...] = ()
            domains: tuple[DomainAssignment, ...] = ()
            tags: tuple[TagAssignment, ...] = ()
            terms: tuple[GlossaryTermAssignment, ...] = ()
            governance_state = MetadataState.UNRESOLVED
        else:
            owners = self._owners(governance, context)
            domains = self._domains(governance, context)
            tags = self._tags(governance, context)
            terms = self._terms(governance, context)
            governance_state = MetadataState.PRESENT
        properties, properties_state = self._structured_properties(
            asset_urn,
            context,
        )
        products, product_state = self._products(asset_urn, context)
        documents, document_state = self._documents(asset_urn, context)
        asset_pipelines = tuple(
            item
            for item in pipelines
            if any(key[0] == asset_urn for key in item.related_field_keys)
        )
        bi_context, bi_state = self._bi_context(asset_urn, context)
        category_evidence: list[ContextEvidence] = []
        if governance is not None:
            category_evidence.extend(
                _evidence(
                    asset_urn,
                    governance.interface,
                    aspect,
                    None,
                    context.observed_at,
                )
                for aspect in (
                    "ownership",
                    "domains",
                    "globalTags",
                    "glossaryTerms",
                    "editableSchemaMetadata",
                )
            )
        if properties_state is not MetadataState.UNRESOLVED:
            category_evidence.append(
                _evidence(
                    asset_urn,
                    "GraphQL Dataset.structuredProperties",
                    "structuredProperties",
                    None,
                    context.observed_at,
                )
            )
        if product_state is not MetadataState.UNRESOLVED:
            category_evidence.append(
                _evidence(
                    asset_urn,
                    (
                        "GraphQL Dataset.relationships("
                        "DataProductContains,INCOMING)"
                    ),
                    "DataProductContains",
                    None,
                    context.observed_at,
                )
            )
        if document_state is not MetadataState.UNRESOLVED:
            category_evidence.append(
                _evidence(
                    asset_urn,
                    (
                        "DataHubGraph.get_related_entities("
                        "RelatedAsset,INCOMING)"
                    ),
                    "RelatedAsset",
                    None,
                    context.observed_at,
                )
            )
        if bi_state is not MetadataState.UNRESOLVED:
            category_evidence.append(
                _evidence(
                    asset_urn,
                    (
                        "GraphQL Query.scrollAcrossLineage("
                        "DOWNSTREAM,degree=1)"
                    ),
                    "downstreamLineage",
                    None,
                    context.observed_at,
                )
            )
        collected_evidence = category_evidence + [
            item.evidence
            for collection in (
                owners,
                domains,
                tags,
                terms,
                properties,
                products,
                documents,
                asset_pipelines,
                bi_context,
            )
            for item in collection
        ]
        evidence = _deduplicate_evidence(collected_evidence)
        return AssetContext(
            asset=identity,
            owners=owners,
            ownership_state=(
                governance_state
                if governance is None
                else _presence(owners)
            ),
            domains=domains,
            domain_state=(
                governance_state
                if governance is None
                else _presence(domains)
            ),
            tags=tags,
            tag_state=(
                governance_state
                if governance is None
                else _presence(tags)
            ),
            glossary_terms=terms,
            glossary_state=(
                governance_state
                if governance is None
                else _presence(terms)
            ),
            structured_properties=properties,
            structured_property_state=properties_state,
            data_products=products,
            data_product_state=product_state,
            documents=documents,
            document_state=document_state,
            pipeline_context=asset_pipelines,
            pipeline_state=_presence(asset_pipelines),
            bi_context=bi_context,
            bi_state=bi_state,
            evidence=evidence,
        )

    def _governance(
        self,
        asset_urn: str,
        context: _RetrievalContext,
    ) -> GovernanceAspectObservation | None:
        if asset_urn in context.governance_cache:
            return context.governance_cache[asset_urn]
        try:
            observation = context.transport.governance_aspects(asset_urn)
        except DataHubAccessError as exc:
            _retrieval_finding(
                context,
                exc,
                asset_urn=asset_urn,
            )
            return None
        context.governance_cache[asset_urn] = observation
        return observation

    def _owners(
        self,
        governance: GovernanceAspectObservation,
        context: _RetrievalContext,
    ) -> tuple[OwnerAssignment, ...]:
        result = []
        for item in governance.owners:
            reference = self._reference(
                item.owner_urn,
                item.owner_kind,
                governance.dataset_urn,
                context,
            )
            result.append(
                OwnerAssignment(
                    owner_urn=item.owner_urn,
                    owner_kind=item.owner_kind,
                    display_name=reference.name,
                    ownership_type=item.ownership_type,
                    ownership_type_urn=item.ownership_type_urn,
                    state=_reference_state(reference),
                    evidence=_evidence(
                        governance.dataset_urn,
                        governance.interface,
                        "ownership",
                        item.owner_urn,
                        context.observed_at,
                    ),
                )
            )
        return tuple(
            sorted(
                result,
                key=lambda item: (
                    item.owner_urn,
                    item.ownership_type or "",
                ),
            )
        )

    def _domains(
        self,
        governance: GovernanceAspectObservation,
        context: _RetrievalContext,
    ) -> tuple[DomainAssignment, ...]:
        result = []
        for urn in governance.domain_urns:
            reference = self._reference(
                urn,
                "DOMAIN",
                governance.dataset_urn,
                context,
            )
            result.append(
                DomainAssignment(
                    domain_urn=urn,
                    display_name=reference.name,
                    state=_reference_state(reference),
                    evidence=_evidence(
                        governance.dataset_urn,
                        governance.interface,
                        "domains",
                        urn,
                        context.observed_at,
                    ),
                )
            )
        return tuple(sorted(result, key=lambda item: item.domain_urn))

    def _tags(
        self,
        governance: GovernanceAspectObservation,
        context: _RetrievalContext,
    ) -> tuple[TagAssignment, ...]:
        result = [
            self._tag(
                governance.dataset_urn,
                urn,
                AssignmentScope.ENTITY,
                None,
                governance.interface,
                context,
            )
            for urn in governance.tag_urns
        ]
        relevant = context.relevant_fields.get(
            governance.dataset_urn,
            frozenset(),
        )
        for field in governance.field_governance:
            if field.field_path not in relevant:
                continue
            result.extend(
                self._tag(
                    governance.dataset_urn,
                    urn,
                    AssignmentScope.FIELD,
                    field.field_path,
                    governance.interface,
                    context,
                )
                for urn in field.tag_urns
            )
        return tuple(
            sorted(
                result,
                key=lambda item: (
                    item.scope.value,
                    item.field_path or "",
                    item.tag_urn,
                ),
            )
        )

    def _tag(
        self,
        asset_urn: str,
        tag_urn: str,
        scope: AssignmentScope,
        field_path: str | None,
        interface: str,
        context: _RetrievalContext,
    ) -> TagAssignment:
        reference = self._reference(
            tag_urn,
            "TAG",
            asset_urn,
            context,
        )
        return TagAssignment(
            tag_urn=tag_urn,
            name=reference.name,
            scope=scope,
            target_urn=asset_urn,
            field_path=field_path,
            state=_reference_state(reference),
            evidence=_evidence(
                asset_urn,
                interface,
                (
                    "editableSchemaMetadata.globalTags"
                    if scope is AssignmentScope.FIELD
                    else "globalTags"
                ),
                tag_urn,
                context.observed_at,
            ),
        )

    def _terms(
        self,
        governance: GovernanceAspectObservation,
        context: _RetrievalContext,
    ) -> tuple[GlossaryTermAssignment, ...]:
        result = [
            self._term(
                governance.dataset_urn,
                urn,
                AssignmentScope.ENTITY,
                None,
                governance.interface,
                context,
            )
            for urn in governance.term_urns
        ]
        relevant = context.relevant_fields.get(
            governance.dataset_urn,
            frozenset(),
        )
        for field in governance.field_governance:
            if field.field_path not in relevant:
                continue
            result.extend(
                self._term(
                    governance.dataset_urn,
                    urn,
                    AssignmentScope.FIELD,
                    field.field_path,
                    governance.interface,
                    context,
                )
                for urn in field.term_urns
            )
        return tuple(
            sorted(
                result,
                key=lambda item: (
                    item.scope.value,
                    item.field_path or "",
                    item.term_urn,
                ),
            )
        )

    def _term(
        self,
        asset_urn: str,
        term_urn: str,
        scope: AssignmentScope,
        field_path: str | None,
        interface: str,
        context: _RetrievalContext,
    ) -> GlossaryTermAssignment:
        reference = self._reference(
            term_urn,
            "GLOSSARY_TERM",
            asset_urn,
            context,
        )
        parent_name = None
        if reference.parent_urn:
            parent = self._reference(
                reference.parent_urn,
                "GLOSSARY_NODE",
                asset_urn,
                context,
            )
            parent_name = parent.name
        return GlossaryTermAssignment(
            term_urn=term_urn,
            name=reference.name,
            parent_node_urn=reference.parent_urn,
            parent_node_name=parent_name,
            scope=scope,
            target_urn=asset_urn,
            field_path=field_path,
            state=_reference_state(reference),
            evidence=_evidence(
                asset_urn,
                interface,
                (
                    "editableSchemaMetadata.glossaryTerms"
                    if scope is AssignmentScope.FIELD
                    else "glossaryTerms"
                ),
                term_urn,
                context.observed_at,
            ),
        )

    def _reference(
        self,
        urn: str,
        entity_type: str,
        asset_urn: str,
        context: _RetrievalContext,
    ) -> MetadataReferenceObservation:
        key = (urn, entity_type)
        if key not in context.reference_cache:
            try:
                context.reference_cache[key] = (
                    context.transport.metadata_reference(urn, entity_type)
                )
            except DataHubAccessError as exc:
                _retrieval_finding(
                    context,
                    exc,
                    asset_urn=asset_urn,
                    reference_urn=urn,
                )
                context.reference_cache[key] = (
                    MetadataReferenceObservation(
                        urn=urn,
                        entity_type=entity_type,
                        name=None,
                        parent_urn=None,
                        resolved=False,
                        interface="DataHubGraph.get_aspect",
                    )
                )
        reference = context.reference_cache[key]
        if not reference.resolved:
            _unresolved_finding(context, asset_urn, urn)
        return reference

    def _structured_properties(
        self,
        asset_urn: str,
        context: _RetrievalContext,
    ) -> tuple[tuple[StructuredPropertyAssignment, ...], MetadataState]:
        if asset_urn not in context.structured_assignment_cache:
            try:
                context.structured_assignment_cache[asset_urn] = (
                    context.transport.structured_property_assignments(
                        asset_urn
                    )
                )
            except DataHubAccessError as exc:
                _retrieval_finding(
                    context,
                    exc,
                    asset_urn=asset_urn,
                )
                return (), MetadataState.UNRESOLVED
        observations = context.structured_assignment_cache[asset_urn]
        assignments = tuple(
            StructuredPropertyAssignment(
                property_urn=item.property_urn,
                qualified_name=item.qualified_name,
                display_name=item.display_name,
                values=item.values,
                value_type=item.value_type,
                value_type_urn=item.value_type_urn,
                assignment_target=item.assignment_target,
                evidence=_evidence(
                    asset_urn,
                    item.interface,
                    "structuredProperties",
                    item.property_urn,
                    context.observed_at,
                ),
            )
            for item in sorted(
                observations,
                key=lambda item: item.property_urn,
            )
        )
        return assignments, _presence(assignments)

    def _products(
        self,
        asset_urn: str,
        context: _RetrievalContext,
    ) -> tuple[tuple[DataProductMembership, ...], MetadataState]:
        if asset_urn not in context.product_cache:
            try:
                context.product_cache[asset_urn] = (
                    context.transport.data_product_memberships(asset_urn)
                )
            except DataHubAccessError as exc:
                _retrieval_finding(
                    context,
                    exc,
                    asset_urn=asset_urn,
                )
                return (), MetadataState.UNRESOLVED
        observations = context.product_cache[asset_urn]
        memberships = tuple(
            DataProductMembership(
                product_urn=item.product_urn,
                name=item.name,
                asset_urn=item.asset_urn,
                relationship=item.relationship,
                evidence=_evidence(
                    item.product_urn,
                    item.interface,
                    item.relationship,
                    item.asset_urn,
                    context.observed_at,
                ),
            )
            for item in sorted(
                observations,
                key=lambda item: item.product_urn,
            )
        )
        return memberships, _presence(memberships)

    def _documents(
        self,
        asset_urn: str,
        context: _RetrievalContext,
    ) -> tuple[tuple[DocumentContext, ...], MetadataState]:
        if asset_urn not in context.document_cache:
            try:
                context.document_cache[asset_urn] = (
                    context.transport.related_documents(asset_urn)
                )
            except DataHubAccessError as exc:
                _retrieval_finding(
                    context,
                    exc,
                    asset_urn=asset_urn,
                )
                return (), MetadataState.UNRESOLVED
        observations = context.document_cache[asset_urn]
        documents = []
        for item in sorted(
            observations,
            key=lambda item: item.document_urn,
        ):
            state = (
                MetadataState.PRESENT
                if item.title is not None
                else MetadataState.UNRESOLVED
            )
            if state is MetadataState.UNRESOLVED:
                _unresolved_finding(
                    context,
                    asset_urn,
                    item.document_urn,
                )
            documents.append(
                DocumentContext(
                    document_urn=item.document_urn,
                    title=item.title,
                    related_asset_urn=item.related_asset_urn,
                    relationship=item.relationship,
                    state=state,
                    evidence=_evidence(
                        item.document_urn,
                        item.interface,
                        item.relationship,
                        item.related_asset_urn,
                        context.observed_at,
                    ),
                )
            )
        result = tuple(documents)
        return result, _presence(result)

    def _bi_context(
        self,
        asset_urn: str,
        context: _RetrievalContext,
    ) -> tuple[tuple[BusinessIntelligenceContext, ...], MetadataState]:
        queue: deque[tuple[str, tuple[str, ...]]] = deque(
            ((asset_urn, (asset_urn,)),)
        )
        best_path: dict[str, tuple[str, ...]] = {asset_urn: (asset_urn,)}
        found: dict[str, BusinessIntelligenceContext] = {}
        failed = False
        while queue:
            current, path = queue.popleft()
            neighbors = self._lineage_neighbors(current, context)
            if neighbors is None:
                failed = True
                continue
            for neighbor in neighbors:
                if neighbor.urn in path:
                    continue
                candidate_path = path + (neighbor.urn,)
                previous = best_path.get(neighbor.urn)
                if previous is not None and (
                    len(previous), previous
                ) <= (len(candidate_path), candidate_path):
                    continue
                best_path[neighbor.urn] = candidate_path
                if neighbor.entity_type == "DATASET":
                    queue.append((neighbor.urn, candidate_path))
                    continue
                observation = self._bi_entity(neighbor, context)
                if observation is None:
                    found[neighbor.urn] = _unresolved_bi(
                        neighbor,
                        candidate_path,
                        context.observed_at,
                    )
                else:
                    found[neighbor.urn] = (
                        BusinessIntelligenceContext(
                            urn=observation.urn,
                            entity_type=observation.entity_type,
                            platform=observation.platform,
                            name=observation.name,
                            qualified_name=(
                                f"{observation.platform} / "
                                f"{observation.name}"
                            ),
                            classification=(
                                BusinessIntelligenceClassification
                                .REACHABLE_CONTEXT
                            ),
                            relationship_path=candidate_path,
                            state=MetadataState.PRESENT,
                            evidence=_evidence(
                                asset_urn,
                                neighbor.interface,
                                "downstreamLineage",
                                observation.urn,
                                context.observed_at,
                                candidate_path,
                            ),
                        )
                    )
                if neighbor.entity_type == "CHART":
                    queue.append((neighbor.urn, candidate_path))
        result = tuple(
            sorted(
                found.values(),
                key=lambda item: (
                    item.entity_type,
                    item.urn,
                    item.relationship_path,
                ),
            )
        )
        if failed and not result:
            return (), MetadataState.UNRESOLVED
        return result, _presence(result)

    def _lineage_neighbors(
        self,
        urn: str,
        context: _RetrievalContext,
    ) -> tuple[ContextLineageEntityObservation, ...] | None:
        if urn in context.lineage_cache:
            return context.lineage_cache[urn]
        try:
            observations = tuple(
                context.transport.direct_context_lineage_entities(urn)
            )
        except DataHubAccessError as exc:
            _retrieval_finding(
                context,
                exc,
                asset_urn=urn,
            )
            return None
        context.lineage_cache[urn] = observations
        return observations

    def _bi_entity(
        self,
        lineage: ContextLineageEntityObservation,
        context: _RetrievalContext,
    ) -> BusinessIntelligenceEntityObservation | None:
        key = (lineage.urn, lineage.entity_type)
        if key in context.bi_entity_cache:
            return context.bi_entity_cache[key]
        try:
            observation = context.transport.business_intelligence_entity(
                lineage.urn,
                lineage.entity_type,
            )
        except DataHubAccessError as exc:
            _retrieval_finding(
                context,
                exc,
                asset_urn=lineage.urn,
            )
            observation = None
        context.bi_entity_cache[key] = observation
        return observation


def _reference_state(
    reference: MetadataReferenceObservation,
) -> MetadataState:
    return (
        MetadataState.PRESENT
        if reference.resolved
        else MetadataState.UNRESOLVED
    )


def _presence(values: Sequence[object]) -> MetadataState:
    return MetadataState.PRESENT if values else MetadataState.ABSENT


def _evidence(
    source_urn: str,
    interface: str,
    aspect_or_relationship: str,
    target_urn: str | None,
    observed_at: str,
    relationship_path: tuple[str, ...] = (),
) -> ContextEvidence:
    return ContextEvidence(
        source_urn=source_urn,
        interface=interface,
        aspect_or_relationship=aspect_or_relationship,
        target_urn=target_urn,
        relationship_path=relationship_path,
        observed_at=observed_at,
    )


def _unresolved_bi(
    lineage: ContextLineageEntityObservation,
    path: tuple[str, ...],
    observed_at: str,
) -> BusinessIntelligenceContext:
    return BusinessIntelligenceContext(
        urn=lineage.urn,
        entity_type=lineage.entity_type,
        platform=None,
        name=None,
        qualified_name=None,
        classification=(
            BusinessIntelligenceClassification.REACHABLE_CONTEXT
        ),
        relationship_path=path,
        state=MetadataState.UNRESOLVED,
        evidence=_evidence(
            path[0],
            lineage.interface,
            "downstreamLineage",
            lineage.urn,
            observed_at,
            path,
        ),
    )


def _deduplicate_evidence(
    values: object,
) -> tuple[ContextEvidence, ...]:
    result: dict[tuple[object, ...], ContextEvidence] = {}
    for item in values:
        key = (
            item.source_urn,
            item.interface,
            item.aspect_or_relationship,
            item.target_urn,
            item.relationship_path,
        )
        result[key] = item
    return tuple(
        sorted(
            result.values(),
            key=lambda item: (
                item.source_urn,
                item.interface,
                item.aspect_or_relationship,
                item.target_urn or "",
                item.relationship_path,
            ),
        )
    )


def _deduplicate_bi(
    values: object,
) -> tuple[BusinessIntelligenceContext, ...]:
    result: dict[str, BusinessIntelligenceContext] = {}
    for item in values:
        previous = result.get(item.urn)
        if previous is None or (
            len(item.relationship_path),
            item.relationship_path,
        ) < (
            len(previous.relationship_path),
            previous.relationship_path,
        ):
            result[item.urn] = item
    return tuple(result[key] for key in sorted(result))


def _retrieval_finding(
    context: _RetrievalContext,
    error: DataHubAccessError,
    *,
    asset_urn: str | None = None,
    reference_urn: str | None = None,
) -> None:
    context.partial = True
    _add_finding(
        context,
        error.code,
        error.safe_message,
        asset_urn,
        reference_urn,
    )


def _unresolved_finding(
    context: _RetrievalContext,
    asset_urn: str,
    reference_urn: str,
) -> None:
    _add_finding(
        context,
        FailureCode.UNRESOLVED_METADATA_REFERENCE,
        "Stored metadata reference could not be resolved.",
        asset_urn,
        reference_urn,
    )


def _add_finding(
    context: _RetrievalContext,
    code: FailureCode,
    message: str,
    asset_urn: str | None,
    reference_urn: str | None,
) -> None:
    safe_message = redact_secrets(message)
    key = (code, asset_urn, reference_urn, safe_message)
    if key in context.finding_keys:
        return
    context.finding_keys.add(key)
    context.findings.append(
        ContextFinding(
            code=code,
            message=safe_message,
            asset_urn=asset_urn,
            reference_urn=reference_urn,
        )
    )


def _unavailable(error: DataHubAccessError) -> ContextRetrievalResult:
    return ContextRetrievalResult(
        state=ContextRetrievalState.UNAVAILABLE,
        snapshot=None,
        findings=(),
        failure=ContextFailure(
            code=error.code,
            message=redact_secrets(error.safe_message),
            diagnostic=(
                redact_secrets(error.diagnostic)
                if error.diagnostic is not None
                else None
            ),
        ),
    )


def _timestamp(clock: Clock) -> str:
    value = clock()
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()
