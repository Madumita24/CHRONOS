# CHRONOS Phase 1.4 — Integration Verification Result

**Demonstration:** `CHRONOS-DEMO-001`
**Verification date:** 2026-07-26 America/Phoenix
**Scope:** Read-only downstream fine-grained field dependency evidence

## Final result

| Check | Observed result |
|---|---|
| Phase 1.1 readiness | `ready`; `can_continue=true` |
| Phase 1.2 dataset resolution | `resolved` |
| Phase 1.2 field resolution | `resolved` |
| Phase 1.3 schema retrieval | `retrieved`; 15 source fields |
| Direct lineage | `retrieved` |
| Complete traversal | `retrieved` |
| Validation findings | 0 |
| Phase 1.4 result | **PASS** |

The local Quickstart authentication warning remains unchanged:
authentication enforcement is disabled and is accepted only for the verified
loopback `quickstart` / `core` environment.

## Source

| Property | Verified value |
|---|---|
| Dataset URN | `urn:li:dataset:(urn:li:dataPlatform:postgres,b2fd91.order_entry_db.order_entry.orders,PROD)` |
| Field path | `order_total` |
| Native type | `DOUBLE PRECISION` |
| Normalized type | `Number` |
| Starting reference | Phase 1.3 snapshot; no fuzzy search |

## Interfaces and raw representation

Reachable lineage used:

- `GraphQL Query.scrollAcrossLineage` for degree-one downstream Dataset and
  Data Job container discovery;
- `DataHubGraph.get_aspect(DataJobInputOutputClass)` for job mapping groups;
- `DataHubGraph.get_aspect(UpstreamLineageClass)` for dataset mapping groups;
- `SchemaMetadataClass` and exact schema-field entity existence reads for
  reference validation.

The installed SDK's newer OpenAPI `scroll_lineage` route was unavailable on
GMS `v1.5.0.6` and returned HTTP 404. No fallback write or unapproved
inference was used; the deployed GraphQL lineage capability had already been
verified by Phase 1.1.

Each raw `FineGrainedLineageClass` group can contain upstream and downstream
sets. All 28 source-reachable groups had safe one-to-one cardinality after
exact reference parsing. No many-to-many group was expanded.

## Direct downstream result

The exact one-hop result is:

| Depth | Platform | Dataset URN | Field | Classification |
|---:|---|---|---|---|
| 1 | S3 | `urn:li:dataset:(urn:li:dataPlatform:s3,b2fd91.demo-data-bucket/order_entry/orders,PROD)` | `order_total` | `unknown` |

Direct downstream fields: **1**
Direct downstream datasets: **1**

The supporting mapping group is:

| Property | Observed value |
|---|---|
| Source entity | `urn:li:dataJob:(urn:li:dataFlow:(spark,b2fd91.export_table_orders_to_s3,b2fd91.default),b2fd91.export_table_orders_to_s3)` |
| Aspect | `dataJobInputOutput` |
| Group index | `5` |
| Upstream type | `FIELD_SET` |
| Downstream type | `FIELD_SET` |
| Upstream members | One: PostgreSQL `orders.order_total` schema-field URN |
| Downstream members | One: S3 `orders.order_total` schema-field URN |
| Transform operation | Absent |
| Confidence | `0.5` |
| Query / match type | Absent / absent |
| Expansion state | `expanded` |

Because transform metadata is absent, the relationship remains `unknown`; a
same-name field is not enough to label it direct.

## Complete graph summary

| Metric | Observed |
|---|---:|
| Parent datasets queried for downstream containers | 21 |
| Fine-grained aspect entities read | 22 |
| Relevant raw mapping groups | 28 |
| Expanded groups | 28 |
| Ambiguous groups | 0 |
| Malformed groups | 0 |
| Unresolved groups | 0 |
| Unique explicit endpoint edges | 27 |
| Direct-classified edges | 5 |
| Derived-classified edges | 0 |
| Unknown-classified edges | 22 |
| Unique downstream fields | 25 |
| Unique downstream datasets | 20 |
| Maximum field depth | 5 |
| Captured simple paths | 48 |
| Cycles | 0 |
| Validation findings | 0 |
| Observation time | `2026-07-27T00:02:37.037174+00:00` |

Two mapping groups on Snowflake `ANALYTICS.ORDER_HISTORY` prove the same
endpoint edge with confidence `1.0` and `0.4`. They remain two raw evidence
groups attached to one deduplicated edge, explaining 28 groups versus 27
edges.

## Dataset aliases

Aliases below make the path evidence readable; the URNs remain the machine
identity.

| Alias | Platform | Dataset URN |
|---|---|---|
| `S3O` | S3 | `urn:li:dataset:(urn:li:dataPlatform:s3,b2fd91.demo-data-bucket/order_entry/orders,PROD)` |
| `SFO` | Snowflake | `urn:li:dataset:(urn:li:dataPlatform:snowflake,b2fd91.order_entry_db.order_entry.orders,PROD)` |
| `DBTS` | dbt | `urn:li:dataset:(urn:li:dataPlatform:dbt,b2fd91.order_entry_db.order_entry.orders,PROD)` |
| `SFOD` | Snowflake | `urn:li:dataset:(urn:li:dataPlatform:snowflake,b2fd91.order_entry_db.analytics.order_details,PROD)` |
| `DBTM` | dbt | `urn:li:dataset:(urn:li:dataPlatform:dbt,b2fd91.ORDER_ENTRY_DB.analytics.order_details,PROD)` |
| `DBTH` | dbt | `urn:li:dataset:(urn:li:dataPlatform:dbt,b2fd91.ORDER_ENTRY_DB.analytics.order_history,PROD)` |
| `LKV` | Looker | `urn:li:dataset:(urn:li:dataPlatform:looker,b2fd91.order-entry-looker.view.order_details,PROD)` |
| `PBCAM` | Power BI | `urn:li:dataset:(urn:li:dataPlatform:powerbi,b2fd91.datahub_order_entries.Customer_Analytics_Measures,PROD)` |
| `PBEKM` | Power BI | `urn:li:dataset:(urn:li:dataPlatform:powerbi,b2fd91.datahub_order_entries.Essential_KPI_Measures,PROD)` |
| `PBGEO` | Power BI | `urn:li:dataset:(urn:li:dataPlatform:powerbi,b2fd91.datahub_order_entries.Geographic_Measures,PROD)` |
| `PBOD` | Power BI | `urn:li:dataset:(urn:li:dataPlatform:powerbi,b2fd91.datahub_order_entries.ORDER_DETAILS,PROD)` |
| `PBPROD` | Power BI | `urn:li:dataset:(urn:li:dataPlatform:powerbi,b2fd91.datahub_order_entries.Product_Perfromance_Measures,PROD)` |
| `PBTIME` | Power BI | `urn:li:dataset:(urn:li:dataPlatform:powerbi,b2fd91.datahub_order_entries.Time_Inteligence_Measures,PROD)` |
| `SFREP` | Snowflake | `urn:li:dataset:(urn:li:dataPlatform:snowflake,b2fd91.order_entry_db.analytics.order_details_replica,PROD)` |
| `SFHIST` | Snowflake | `urn:li:dataset:(urn:li:dataPlatform:snowflake,b2fd91.order_entry_db.analytics.order_history,PROD)` |
| `T37` | Tableau | `urn:li:dataset:(urn:li:dataPlatform:tableau,b2fd91.37fcfb15-34ae-973a-5ae3-cf63691d48e3,PROD)` |
| `T8` | Tableau | `urn:li:dataset:(urn:li:dataPlatform:tableau,b2fd91.8bfe7483-1c9a-a0e1-ec84-57207dd37a15,PROD)` |
| `LKEXP` | Looker | `urn:li:dataset:(urn:li:dataPlatform:looker,b2fd91.order-entry.explore.order_details,PROD)` |
| `TB9` | Tableau | `urn:li:dataset:(urn:li:dataPlatform:tableau,b2fd91.b980a8c5-28eb-119e-f6ca-4da32732e5be,PROD)` |
| `TC0` | Tableau | `urn:li:dataset:(urn:li:dataPlatform:tableau,b2fd91.c067553a-127e-a871-14a0-5f32cb032c78,PROD)` |

## Complete downstream field inventory

`entity only` means the exact DataHub-supplied schema-field URN exists even
though that path is absent from the parent schema aspect.

| Depth | Alias | Field path | Reference validation | Incoming classification | Paths |
|---:|---|---|---|---|---:|
| 1 | `S3O` | `order_total` | schema member | unknown | 1 |
| 2 | `SFO` | `order_total` | schema member | unknown | 1 |
| 3 | `DBTS` | `order_total` | schema member | unknown | 1 |
| 3 | `SFOD` | `order_total` | schema member | direct | 2 |
| 4 | `DBTM` | `order_total` | schema member | unknown | 1 |
| 4 | `DBTH` | `order_total` | schema member | unknown | 2 |
| 4 | `LKV` | `order_total` | schema member | unknown | 2 |
| 4 | `PBCAM` | `ORDER_TOTAL` | entity only | unknown | 2 |
| 4 | `PBEKM` | `ORDER_TOTAL` | entity only | unknown | 2 |
| 4 | `PBEKM` | `Total Revenue` | schema member | unknown | 2 |
| 4 | `PBGEO` | `ORDER_TOTAL` | entity only | unknown | 2 |
| 4 | `PBOD` | `ORDER_TOTAL` | schema member | unknown | 2 |
| 4 | `PBPROD` | `ORDER_TOTAL` | entity only | unknown | 2 |
| 4 | `PBTIME` | `ORDER_TOTAL` | entity only | unknown | 2 |
| 4 | `SFREP` | `order_total` | schema member | direct | 2 |
| 4 | `SFHIST` | `order_total` | schema member | direct | 4 |
| 4 | `T37` | `AVERAGE_ORDER_VALUE` | schema member | unknown | 2 |
| 4 | `T37` | `TOTAL_REVENUE` | schema member | unknown | 2 |
| 4 | `T8` | `AVERAGE_ORDER_VALUE` | schema member | unknown | 2 |
| 4 | `T8` | `TOTAL_REVENUE` | schema member | unknown | 2 |
| 5 | `LKEXP` | `order_details.order_total` | schema member | unknown | 2 |
| 5 | `TB9` | `AVERAGE_ORDER_VALUE` | schema member | unknown | 2 |
| 5 | `TB9` | `TOTAL_REVENUE` | schema member | unknown | 2 |
| 5 | `TC0` | `AVERAGE_ORDER_VALUE` | schema member | unknown | 2 |
| 5 | `TC0` | `TOTAL_REVENUE` | schema member | unknown | 2 |

No Tableau or Power BI measure was labeled derived solely from its name.
Their reachable dependency is verified, but their fine-grained groups do not
provide transform text.

## Path evidence for every descendant

`SRC` means PostgreSQL `orders.order_total`. One verified shortest path is
shown per descendant; the inventory above records the number of all captured
simple paths.

| Descendant | One verified path |
|---|---|
| `S3O.order_total` | `SRC → S3O.order_total` |
| `SFO.order_total` | `SRC → S3O.order_total → SFO.order_total` |
| `DBTS.order_total` | `SRC → S3O.order_total → SFO.order_total → DBTS.order_total` |
| `SFOD.order_total` | `SRC → S3O.order_total → SFO.order_total → SFOD.order_total` |
| `DBTM.order_total` | `SRC → S3O.order_total → SFO.order_total → DBTS.order_total → DBTM.order_total` |
| `DBTH.order_total` | `SRC → S3O.order_total → SFO.order_total → SFOD.order_total → DBTH.order_total` |
| `LKV.order_total` | `SRC → S3O.order_total → SFO.order_total → SFOD.order_total → LKV.order_total` |
| `PBCAM.ORDER_TOTAL` | `SRC → S3O.order_total → SFO.order_total → SFOD.order_total → PBCAM.ORDER_TOTAL` |
| `PBEKM.ORDER_TOTAL` | `SRC → S3O.order_total → SFO.order_total → SFOD.order_total → PBEKM.ORDER_TOTAL` |
| `PBEKM.Total Revenue` | `SRC → S3O.order_total → SFO.order_total → SFOD.order_total → PBEKM.Total Revenue` |
| `PBGEO.ORDER_TOTAL` | `SRC → S3O.order_total → SFO.order_total → SFOD.order_total → PBGEO.ORDER_TOTAL` |
| `PBOD.ORDER_TOTAL` | `SRC → S3O.order_total → SFO.order_total → SFOD.order_total → PBOD.ORDER_TOTAL` |
| `PBPROD.ORDER_TOTAL` | `SRC → S3O.order_total → SFO.order_total → SFOD.order_total → PBPROD.ORDER_TOTAL` |
| `PBTIME.ORDER_TOTAL` | `SRC → S3O.order_total → SFO.order_total → SFOD.order_total → PBTIME.ORDER_TOTAL` |
| `SFREP.order_total` | `SRC → S3O.order_total → SFO.order_total → SFOD.order_total → SFREP.order_total` |
| `SFHIST.order_total` | `SRC → S3O.order_total → SFO.order_total → SFOD.order_total → SFHIST.order_total` |
| `T37.AVERAGE_ORDER_VALUE` | `SRC → S3O.order_total → SFO.order_total → SFOD.order_total → T37.AVERAGE_ORDER_VALUE` |
| `T37.TOTAL_REVENUE` | `SRC → S3O.order_total → SFO.order_total → SFOD.order_total → T37.TOTAL_REVENUE` |
| `T8.AVERAGE_ORDER_VALUE` | `SRC → S3O.order_total → SFO.order_total → SFOD.order_total → T8.AVERAGE_ORDER_VALUE` |
| `T8.TOTAL_REVENUE` | `SRC → S3O.order_total → SFO.order_total → SFOD.order_total → T8.TOTAL_REVENUE` |
| `LKEXP.order_details.order_total` | `SRC → S3O.order_total → SFO.order_total → SFOD.order_total → LKV.order_total → LKEXP.order_details.order_total` |
| `TB9.AVERAGE_ORDER_VALUE` | `SRC → S3O.order_total → SFO.order_total → SFOD.order_total → T8.AVERAGE_ORDER_VALUE → TB9.AVERAGE_ORDER_VALUE` |
| `TB9.TOTAL_REVENUE` | `SRC → S3O.order_total → SFO.order_total → SFOD.order_total → T8.TOTAL_REVENUE → TB9.TOTAL_REVENUE` |
| `TC0.AVERAGE_ORDER_VALUE` | `SRC → S3O.order_total → SFO.order_total → SFOD.order_total → T37.AVERAGE_ORDER_VALUE → TC0.AVERAGE_ORDER_VALUE` |
| `TC0.TOTAL_REVENUE` | `SRC → S3O.order_total → SFO.order_total → SFOD.order_total → T37.TOTAL_REVENUE → TC0.TOTAL_REVENUE` |

Twenty-one descendants have multiple paths. This comes primarily from
`SFO.order_total` reaching `SFOD.order_total` directly and through
`DBTS → DBTM`, with all later branches inheriting both routes.
`SFHIST.order_total` has four simple paths because it is reachable directly
from `SFOD` and through `DBTH`, on top of the two routes into `SFOD`.

## Reference reconciliation

Five Power BI `ORDER_TOTAL` lineage references are absent from their parent
`SchemaMetadata.fields`:

- `PBCAM.ORDER_TOTAL`
- `PBEKM.ORDER_TOTAL`
- `PBGEO.ORDER_TOTAL`
- `PBPROD.ORDER_TOTAL`
- `PBTIME.ORDER_TOTAL`

Each exact DataHub-supplied schema-field URN was independently verified to
exist as a current `schemaField` entity. They are therefore retained as
`schema_field_entity_only`, not silently treated as schema members and not
called unresolved.

`PBOD.ORDER_TOTAL` is an exact parent-schema member. `PBEKM.Total Revenue` is
also a parent-schema member.

## Baseline comparison

The acceptance values were not used by traversal.

| Metric | Observed | Expected | Result |
|---|---:|---:|---|
| Unique downstream fields | 25 | 25 | Match |
| Unique downstream datasets | 20 | 20 | Match |
| Maximum field depth | 5 | 5 | Match |

No traversal adjustment or hardcoded field was required.

## Determinism, tests, and deviations

- Repeated live traversals were semantically equal after excluding
  observation timestamps.
- Phase 1.1 unit tests: **23 passed**.
- Phase 1.2 unit tests: **15 passed**.
- Phase 1.3 unit tests: **31 passed**.
- Phase 1.4 unit tests: **30 passed**.
- Combined unit suite: **99 passed**.
- Live integration tests: **4 passed**.
- Python compilation: passed.
- Cycles: none observed.
- Ambiguous groups: none observed.
- Unresolved references: none after schema-field entity reconciliation.
- Chart/dashboard/governance traversal: none.
- DataHub writes: none.

The only implementation-interface deviation is the unavailable newer OpenAPI
scroll route; the server-supported GraphQL scroll interface was used instead.
The five Power BI entity-only field references are a verified metadata-model
distinction, not synthetic repair.

Phase 1.5 was not started.
