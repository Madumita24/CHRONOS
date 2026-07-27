# CHRONOS Phase 1.3 — Integration Verification Result

**Demonstration:** `CHRONOS-DEMO-001`
**Verification date:** 2026-07-26
**Scope:** Deterministic, read-only, complete schema retrieval

## Final result

| Check | Observed result |
|---|---|
| Phase 1.1 readiness | `ready` |
| Phase 1.1 `can_continue` | `true` |
| Configuration source | `datahub_cli_profile` |
| GMS / SDK versions | `v1.5.0.6` / `1.6.0.15` |
| Phase 1.2 PostgreSQL resolution | `resolved`; 12 discovered, 1 exact |
| PostgreSQL schema retrieval | `retrieved` |
| PostgreSQL field count | `15` |
| Phase 1.2 Snowflake resolution | `resolved`; 14 discovered, 1 exact |
| Snowflake schema retrieval | `retrieved` |
| Snowflake field count | `15` |
| Repeated-read semantic comparison | Equal for both datasets |
| Phase 1.3 result | **PASS** |

The Phase 1.1 local Quickstart security warning remains in force:
authentication enforcement is disabled. This remains non-blocking only
because the endpoint is loopback and server metadata identifies
`quickstart` / `core`.

## PostgreSQL canonical schema

**Canonical identity:**
`PostgreSQL / order_entry_db / order_entry / orders`

| Evidence | Observed value |
|---|---|
| Resolved dataset URN | `urn:li:dataset:(urn:li:dataPlatform:postgres,b2fd91.order_entry_db.order_entry.orders,PROD)` |
| Schema retrieval state | `retrieved` |
| Schema name | `order_entry_db.order_entry.orders` |
| Source platform | `urn:li:dataPlatform:postgres` |
| Environment | `PROD` |
| Schema version | `0` |
| Schema hash | Empty string, preserved as observed |
| Field count | `15` |
| Validation state | `valid` |
| Evidence aspect | `SchemaMetadata` |
| Evidence interface | `DataHubGraph.get_aspect(SchemaMetadataClass)` |
| Observation time | `2026-07-26T22:46:45.202118+00:00` |

### Complete observed field inventory

Positions are zero-based and preserve the order in
`SchemaMetadata.fields`.

| Position | Field path | Native type | Normalized type |
|---:|---|---|---|
| 0 | `order_id` | `BIGINT` | `Number` |
| 1 | `order_date` | `TEXT` | `String` |
| 2 | `order_mode` | `TEXT` | `String` |
| 3 | `customer_id` | `BIGINT` | `Number` |
| 4 | `order_status` | `BIGINT` | `Number` |
| 5 | `order_total` | `DOUBLE PRECISION` | `Number` |
| 6 | `sales_rep_id` | `BIGINT` | `Number` |
| 7 | `promotion_id` | `DOUBLE PRECISION` | `Number` |
| 8 | `warehouse_id` | `BIGINT` | `Number` |
| 9 | `delivery_type` | `TEXT` | `String` |
| 10 | `cost_of_delivery` | `DOUBLE PRECISION` | `Number` |
| 11 | `wait_till_complete_yn` | `TEXT` | `String` |
| 12 | `billing_address_id` | `BIGINT` | `Number` |
| 13 | `delivery_address_id` | `BIGINT` | `Number` |
| 14 | `payment_method_code` | `TEXT` | `String` |

### `order_total` verification

Snapshot-local exact lookup returned:

| Property | Observed value |
|---|---|
| Field path | `order_total` |
| Field name | `order_total` |
| Native type | `DOUBLE PRECISION` |
| Raw DataHub type | `NumberTypeClass` |
| Normalized type | `Number` |
| Position | `5` |
| Nullable | `true` |
| Part of key | `false` |

This reproduces the frozen Phase 1.1 and Phase 1.2 baseline. The lookup used
the captured snapshot and did not issue another DataHub search or schema read.

## Missing or unavailable PostgreSQL metadata

These values were absent and remain `null`; none was inferred:

- field descriptions for all 15 fields;
- field schema URNs for all 15 fields;
- field JSON paths and labels;
- partitioning-key indicators;
- schema dataset reference;
- schema cluster;
- schema primary keys;
- resolved platform instance;
- `DatasetProperties.qualifiedName`.

`nullable=true`, `isPartOfKey=false`, and `recursive=false` were present for
every field and are preserved as observed. The aspect supplied created and
last-modified time `15353438779`; CHRONOS preserves the integer without
interpreting or correcting it.

## Structural validation

No validation findings were returned for the PostgreSQL schema:

- schema identity matched the resolved dataset;
- the field collection was non-empty;
- all 15 field paths were valid;
- no duplicate field paths were present;
- all observed field metadata representations were supported.

## Determinism check

The PostgreSQL schema was retrieved twice through the same readiness-gated
session. `semantic_key()` values were equal. Observation timestamps were
excluded from this comparison; source metadata and ordered field content were
included.

## Snowflake identity and schema isolation

**Canonical identity:**
`Snowflake / ORDER_ENTRY_DB / ORDER_ENTRY / ORDERS`

| Evidence | Observed value |
|---|---|
| Resolved dataset URN | `urn:li:dataset:(urn:li:dataPlatform:snowflake,b2fd91.order_entry_db.order_entry.orders,PROD)` |
| Schema retrieval state | `retrieved` |
| Schema name | `order_entry_db.order_entry.orders` |
| Source platform | `urn:li:dataPlatform:snowflake` |
| Environment | `PROD` |
| Schema version / hash | `0` / empty string |
| Field count | `15` |
| Validation state | `valid` |
| Observation time | `2026-07-26T22:46:45.701593+00:00` |

### Complete observed Snowflake inventory

| Position | Field path | Native type | Normalized type |
|---:|---|---|---|
| 0 | `order_id` | `NUMBER(38,0)` | `Number` |
| 1 | `order_date` | `VARCHAR(16777216)` | `String` |
| 2 | `order_mode` | `VARCHAR(16777216)` | `String` |
| 3 | `customer_id` | `NUMBER(38,0)` | `Number` |
| 4 | `order_status` | `NUMBER(38,0)` | `Number` |
| 5 | `order_total` | `FLOAT` | `Number` |
| 6 | `sales_rep_id` | `NUMBER(38,0)` | `Number` |
| 7 | `promotion_id` | `FLOAT` | `Number` |
| 8 | `warehouse_id` | `NUMBER(38,0)` | `Number` |
| 9 | `delivery_type` | `VARCHAR(16777216)` | `String` |
| 10 | `cost_of_delivery` | `FLOAT` | `Number` |
| 11 | `wait_till_complete_yn` | `VARCHAR(16777216)` | `String` |
| 12 | `billing_address_id` | `NUMBER(38,0)` | `Number` |
| 13 | `delivery_address_id` | `NUMBER(38,0)` | `Number` |
| 14 | `payment_method_code` | `VARCHAR(16777216)` | `String` |

The PostgreSQL and Snowflake schemas have similar field paths but are bound
to distinct, independently resolved DataHub URNs and platform aspects. No
lineage or relationship between the datasets was queried or inferred.

Snowflake had the same unavailable field description, schema-field URN, JSON
path, label, and partitioning-key metadata as PostgreSQL. Its resolved
`DatasetProperties.qualifiedName` was available as
`b2fd91.ORDER_ENTRY_DB.ORDER_ENTRY.ORDERS`.

## Automated verification

- Phase 1.1 unit tests: **23 passed**.
- Phase 1.2 unit tests: **15 passed**.
- Phase 1.3 unit tests: **31 passed**.
- Combined unit suite: **69 passed**.
- Live integration tests: **3 passed**.
- Python compilation check: **passed**.
- Git whitespace validation: **passed** before final commit.

The Phase 1.3 unit suite covers successful retrieval, missing and empty
schemas, complete field preservation and ordering, duplicate and malformed
paths, native and normalized types, unknown types, optional descriptions,
snapshot-local lookup, evidence, immutability, semantic determinism, optional
metadata, schema-field URN policy, unsupported metadata, secret redaction,
platform isolation, and the read-only boundary.

## Deviations from prior baselines

No Phase 0, Phase 1.1, or Phase 1.2 frozen baseline deviation was observed:

- the PostgreSQL dataset URN matched;
- `order_total` remained `DOUBLE PRECISION` → `Number`;
- Phase 1.1 readiness semantics were unchanged;
- Phase 1.2 resolution semantics were unchanged.

The first complete schema read established an actual field count of 15. This
is a live observation, not a documentation assumption.

No DataHub metadata was altered. Phase 1.4 was not started.
