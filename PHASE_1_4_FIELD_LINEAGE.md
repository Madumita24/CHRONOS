# CHRONOS Phase 1.4 — Fine-Grained Field Lineage

Phase 1.4 establishes current field-level dependency evidence for the verified
PostgreSQL `orders.order_total` field. It does not establish business,
dashboard, governance, or future-state impact.

## Installed representation

The pinned `acryl-datahub==1.6.0.15` SDK and local GMS `v1.5.0.6` were
inspected directly.

Fine-grained groups use `FineGrainedLineageClass`:

- `upstreamType`: `FIELD_SET`, `DATASET`, or `NONE`;
- `downstreamType`: `FIELD` or `FIELD_SET`;
- `upstreams`: optional list of URN strings;
- `downstreams`: optional list of URN strings;
- optional `transformOperation`;
- optional `confidenceScore`;
- optional `query`;
- optional `matchType`.

Dataset groups are stored in `UpstreamLineageClass.fineGrainedLineages` on
the downstream dataset. Spark job groups are stored in
`DataJobInputOutputClass.fineGrainedLineages` on the job. Upstream and
downstream field members are DataHub-supplied `schemaField` URNs whose parent
contains the dataset URN and whose second component is the field path.

Direction is explicit: group upstream members are dependencies; group
downstream members are outputs. A group can contain sets on either side and
is not assumed to be one scalar edge.

The installed SDK exposes an OpenAPI `scroll_lineage` helper, but the local
GMS does not provide its `/openapi/v3/lineage/scroll` route and returned HTTP
404 during inspection. The deployed GraphQL schema advertises and
successfully serves `Query.scrollAcrossLineage`, so Phase 1.4 uses that
read-only interface for one-hop container discovery and SDK aspect reads for
the raw fine-grained groups.

## Shared read-only boundary

`LineageRetrievalSession` creates one `DataHubSdkReadOnlyTransport` and shares
it across:

1. Phase 1.1 readiness;
2. Phase 1.2 dataset and field resolution;
3. Phase 1.3 schema retrieval;
4. Phase 1.4 lineage retrieval.

The original Phase 1.1–1.3 `ReadOnlyTransport` protocol remains unchanged.
Phase 1.4 adds a narrower protocol extension, `LineageReadOnlyTransport`, so
earlier public and test boundaries do not acquire lineage methods.

## Field machine identity

`FieldReference` is immutable. Its machine key is exactly:

`(dataset_urn, field_path)`

It also preserves platform, dataset name, environment, leaf field name,
canonical/display identity when available, and the schema-field URN only when
DataHub supplied it.

No dataset or schema-field URN is constructed by production traversal code.
DataHub-supplied schema-field URNs are parsed using the installed SDK.

Field reference resolution is explicit:

- `source_snapshot`: verified by the Phase 1.3 source snapshot;
- `schema_member`: exact path exists in parent `SchemaMetadata.fields`;
- `schema_field_entity_only`: exact DataHub-supplied schema-field URN exists,
  but its path is not in the parent schema aspect;
- `unverified`: internal pre-validation state; it is never emitted on an
  expanded graph node.

A missing parent `SchemaMetadata` or a field reference that is neither a
schema member nor an existing schema-field entity is unresolved and is not
expanded.

## Mapping-group expansion

Every relevant raw group is retained as an immutable
`LineageMappingGroup`, including:

- source entity and aspect;
- source group index;
- raw upstream and downstream URNs;
- parsed field references;
- upstream/downstream set types;
- transform, query, confidence, and match metadata;
- expansion state;
- observation time.

Expansion rules are:

| Cardinality | Explicit rooted field-edge behavior |
|---|---|
| 1 upstream → 1 downstream | Expand the verified dependency |
| 1 upstream → many downstreams | Expand one edge to each verified output |
| many upstreams → 1 downstream | Expand the edge from each currently reachable upstream; retain all co-inputs in the group |
| many upstreams → many downstreams | Retain as `ambiguous`; create no Cartesian edges |

Malformed or unresolved groups create no edge. Duplicate endpoint edges are
deduplicated while all contributing mapping-group IDs remain attached to the
single edge.

## Classification

Phase 1.4 classifies only what the group evidence supports:

- explicit `NONE`, `IDENTITY`, no-op, or `COPY...` transformation metadata:
  `direct`;
- explicit non-copy transformation text, or a verified many-to-one group:
  `derived`;
- absent transformation evidence: `unknown`.

Names such as `TOTAL_REVENUE` or `AVERAGE_ORDER_VALUE` are not hardcoded as
derived. Name differences alone are insufficient evidence.

Conflicting direct and derived evidence for one endpoint edge produces
`lineage_evidence_conflict` and the edge remains `unknown`.

## One-hop retrieval

`retrieve_direct(snapshot, field_path)`:

1. verifies the field in the supplied Phase 1.3 snapshot;
2. discovers degree-one downstream Dataset or Data Job containers with
   `scrollAcrossLineage`;
3. reads only their fine-grained lineage aspects;
4. selects groups containing the exact source machine key;
5. validates references and expands safe group cardinalities;
6. returns only depth-one field nodes.

It performs no fuzzy or global field search.

## Multi-hop traversal

`traverse_downstream(snapshot, field_path)` performs deterministic breadth-
first expansion over field keys.

- Each field node is expanded at most once.
- Direct downstream containers, aspects, schemas, and schema-field existence
  checks are cached within one retrieval.
- Cache keys are DataHub URNs and do not change graph semantics.
- Endpoint edges and nodes are deduplicated by machine keys.
- Cycles terminate because expanded field keys are never expanded twice.
- Cycle-closing evidence is retained separately.
- Output ordering is by depth, dataset URN, and field path.

The traversal contains no 25, 20, or 5 constant. Those values are integration
acceptance checks applied only after graph construction.

## Depth, counts, and paths

Depth is the shortest verified fine-grained field-edge distance:

- depth 0: source;
- depth 1: direct downstream field;
- depth N: N field-dependency edges from the source.

Downstream field count is the number of unique reachable field keys excluding
the source. Downstream dataset count is the number of unique parent dataset
URNs containing those fields, excluding the source dataset.

Jobs, flows, charts, dashboards, containers, governance entities, products,
and owners are not counted.

The graph stores all simple paths while practical, bounded at 128 paths per
field. Every node records captured path count and whether storage was
truncated. The live canonical graph did not reach the bound.

## Result states and errors

Result states are:

- `retrieved`;
- `no_lineage`;
- `partial`;
- `invalid_lineage`;
- `unavailable`.

Added error categories are:

- `fine_grained_lineage_unavailable`;
- `malformed_lineage_group`;
- `unresolved_field_reference`;
- `lineage_traversal_unavailable`;
- `lineage_evidence_conflict`;
- `unexpected_lineage_error`.

No observed lineage is distinct from an API or aspect-read failure.

## Determinism and immutability

Field references, groups, edges, nodes, paths, cycles, indexes, evidence, and
graphs are frozen dataclasses containing immutable tuples.

`FieldLineageGraph.semantic_key()` excludes observation timestamps but
includes identities, ordered nodes, edges, mapping groups, paths, cycles,
dataset index, and findings. Repeated reads of unchanged metadata are
semantically equal.

## Verification

Run all unit tests:

```powershell
.\.venv-datahub-310\Scripts\python.exe -m unittest discover -s tests\unit -v
```

Run the live readiness, resolution, schema, and lineage checks:

```powershell
$env:CHRONOS_RUN_INTEGRATION = "1"
.\.venv-datahub-310\Scripts\python.exe -m unittest discover -s tests\integration -v
```

The observed graph is recorded in `PHASE_1_4_INTEGRATION_RESULT.md`. A
debugging-only edge artifact is in `PHASE_1_4_FIELD_LINEAGE_GRAPH.md`.

## Read-only and scope guarantee

Phase 1.4 exposes only direct retrieval and downstream traversal. It contains
no MCP/MCE write, mutation, emitter, create, update, delete, patch, upsert,
rollback, lineage write, chart/dashboard traversal, governance enrichment,
impact scoring, Future Graph, repair recommendation, agent, or frontend.
