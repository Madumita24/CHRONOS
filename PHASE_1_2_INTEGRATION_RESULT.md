# CHRONOS Phase 1.2 — Integration Verification Result

**Demonstration:** `CHRONOS-DEMO-001`<br>
**Verification date:** 2026-07-26<br>
**Scope:** Deterministic read-only Dataset and Schema Field identity resolution

## Authoritative final result

| Check | Result |
|---|---|
| Phase 1.1 prerequisite | `ready` |
| Phase 1.1 `can_continue` | `true` |
| Configuration source | `datahub_cli_profile` |
| Dataset resolution | `resolved` |
| Field resolution | `resolved` |
| PostgreSQL/Snowflake collision | Distinct machine identities |
| Phase 1.2 result | **PASS** |

Phase 1.1 retained its local Quickstart security warning. No Phase 1.1
readiness or security behavior was weakened.

## PostgreSQL canonical dataset

**Canonical request:**

`PostgreSQL / order_entry_db / order_entry / orders`

| Evidence | Observed value |
|---|---|
| Search-discovered candidates | `12` |
| Exact verified candidates | `1` |
| Resolution state | `resolved` |
| Resolved URN | `urn:li:dataset:(urn:li:dataPlatform:postgres,b2fd91.order_entry_db.order_entry.orders,PROD)` |
| DataHub platform | `postgres` |
| Environment | `PROD` |
| Qualified name | `order_entry_db.order_entry.orders` |
| Logical name | `orders` |
| Resolution method | `candidate_search_then_exact_aspect_verification` |
| Interfaces | `DataHubGraph.get_urns_by_filter`, `DatasetProperties`, `DataPlatformInstance`, `SchemaMetadata` |
| Evidence observation | `2026-07-26T22:35:49.518785+00:00` |

All verified platform, environment, qualified-name, and logical-name evidence
attributes matched. The runtime URN independently reproduced the frozen
baseline and was preserved exactly as returned by DataHub.

## Parent-scoped field

**Canonical field:** `order_total`

| Evidence | Observed value |
|---|---|
| Parent dataset URN | `urn:li:dataset:(urn:li:dataPlatform:postgres,b2fd91.order_entry_db.order_entry.orders,PROD)` |
| Exact verified fields | `1` |
| Resolution state | `resolved` |
| Field path | `order_total` |
| Field name | `order_total` |
| Native type | `DOUBLE PRECISION` |
| Normalized type | `Number` |
| Description | Not present in `SchemaMetadata` |
| Schema-field URN | Not provided by the parent `SchemaMetadata` read; not fabricated |
| Resolution method | `exact_parent_schema_field_verification` |
| Interface | `SchemaMetadata.fields` |
| Evidence observation | `2026-07-26T22:35:49.539091+00:00` |

## PostgreSQL versus Snowflake

The Snowflake identity was independently requested as:

`Snowflake / ORDER_ENTRY_DB / ORDER_ENTRY / ORDERS`

| Attribute | PostgreSQL | Snowflake |
|---|---|---|
| Search-discovered candidates | `12` | `14` |
| Exact verified candidates | `1` | `1` |
| Platform | `postgres` | `snowflake` |
| Environment | `PROD` | `PROD` |
| Qualified name | `order_entry_db.order_entry.orders` | `order_entry_db.order_entry.orders` |
| DataHub URN | `urn:li:dataset:(urn:li:dataPlatform:postgres,b2fd91.order_entry_db.order_entry.orders,PROD)` | `urn:li:dataset:(urn:li:dataPlatform:snowflake,b2fd91.order_entry_db.order_entry.orders,PROD)` |

The normalized qualified names are identical, but platform qualification and
the DataHub-provided URNs make the machine identities distinct. No lineage
relationship between them was queried.

## Tests and deviations

- Phase 1.1 unit regressions: **23 passed**.
- Phase 1.2 unit tests: **15 passed**.
- Combined unit suite: **38 passed**.
- Live integration tests: **2 passed**.
- Python compilation check: passed.
- Frozen PostgreSQL dataset URN: matched.
- Frozen native and normalized field types: matched.
- Deviation: no schema-field URN or field description was present in the
  parent `SchemaMetadata` response. Both are reported as unavailable rather
  than inferred.

No DataHub write, lineage traversal, blast-radius calculation, graph
construction, Future Graph, impact analysis, governance analysis, repair
recommendation, frontend, or agent behavior was implemented.
