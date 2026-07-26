# CHRONOS Phase 1.2 — Canonical Entity Resolution

This phase establishes identity for `CHRONOS-DEMO-001`. It does not establish
impact and contains no lineage traversal, graph construction, future-state
projection, recommendations, agents, frontend, or DataHub writes.

## Identity concepts

**Canonical Identity** is the CHRONOS request. For a dataset it contains a
platform, qualified name, environment, and logical name, plus database and
schema only when those values are supplied by the request and supported by
the metadata. For a schema field it contains a parent canonical dataset,
field path, and field name.

**Resolved DataHub Identity** is the verified entity returned after reading
DataHub metadata. It contains the DataHub-provided URN, URN name, platform,
environment, schema name, logical name, and available platform-instance or
properties-qualified-name values.

**Display Identity** is presentation text such as:

`PostgreSQL / order_entry_db / order_entry / orders`

Display text is never used as machine identity.

The entity-type model reserves identifiers for future Data Job, Data Flow,
Chart, Dashboard, Domain, Tag, Glossary Term, Data Product, Document,
Corporate User, and Corporate Group resolvers. Phase 1.2 implements retrieval
only for Dataset and Schema Field.

## Resolution strategy

Dataset resolution is deterministic:

1. Validate the canonical identity.
2. Discover bounded candidates through DataHub dataset search using platform,
   environment, and logical name.
3. Read every discovered candidate's `DatasetProperties`,
   `DataPlatformInstance`, and `SchemaMetadata` aspects.
4. Verify platform, environment, schema qualified name, and logical name.
5. Return `not_found` for zero exact matches, `resolved` for exactly one, or
   `ambiguous` for multiple exact matches.

Search results are candidate discovery only. Search ranking and result order
never establish identity, and the resolver never silently selects the first
result.

## Matching semantics

- Platform matching is case-insensitive. The explicit human alias
  `PostgreSQL` normalizes to DataHub platform `postgres`; `Snowflake`
  normalizes to `snowflake`.
- Environment matching is case-insensitive and candidate discovery uses the
  uppercase DataHub fabric value.
- Dataset qualified-name and logical-name verification is case-insensitive.
  This is necessary because the verified Snowflake properties preserve
  uppercase identifiers while `SchemaMetadata.schemaName` is lowercase.
- Field path and field name matching is exact and case-sensitive.
- Surrounding whitespace, empty qualified-name segments, conflicting
  database/schema values, and inconsistent field path/name values are invalid.
- No fuzzy, substring, prefix, edit-distance, or search-ranking match is used
  for final verification.
- Original DataHub values are preserved in the resolved identity and evidence.

## Platform qualification and URN policy

Platform is mandatory. PostgreSQL `orders` and Snowflake `ORDERS` cannot
collide even though their schema names normalize to the same text.

The resolver never constructs a dataset or schema-field URN. Candidate URNs
come from DataHub search and are preserved byte-for-byte. If the parent
`SchemaMetadata` aspect does not expose a schema-field URN, the resolved field
reports `schema_field_urn: null`; CHRONOS does not guess one from DataHub's URN
format.

## Field identity

A field is resolved only from `SchemaMetadata.fields` on its already-resolved
parent dataset. No global field result can substitute for parent-scoped
verification. The result preserves:

- parent dataset URN;
- field path and field name;
- native and normalized types;
- description when present;
- schema-field URN only when DataHub supplied one.

Zero exact fields return `not_found`. Duplicate exact paths return
`ambiguous` and no field is selected.

## Resolution states and evidence

Typed states are:

- `resolved`
- `not_found`
- `ambiguous`
- `invalid_identity`
- `unavailable`

Successful evidence records the method, DataHub interfaces, canonical request,
resolved URN, requested and observed identity attributes, match results, UTC
observation time, and snapshot context. Evidence is retained in the result so
identity can be explained without rerunning resolution.

## Readiness and read-only guarantee

`create_resolution_session()` uses the existing Phase 1.1 configuration,
authentication, logging, health, capability, and client boundary. Resolution
is blocked unless cached Phase 1.1 readiness returns `can_continue: true`.

The resolver adds only dataset search, dataset-aspect reads, and parent schema
reads to the existing private transport. It exposes no DataHub client,
emitter, mutation, create, update, delete, patch, upsert, rollback, or lineage
operation.

## Run verification

Unit tests do not require DataHub:

```powershell
.\.venv-datahub-310\Scripts\python.exe -m unittest discover -s tests\unit -v
```

Live integration uses the existing DataHub CLI profile and first reruns the
Phase 1.1 readiness gate:

```powershell
$env:CHRONOS_RUN_INTEGRATION = "1"
.\.venv-datahub-310\Scripts\python.exe -m unittest discover -s tests\integration -v
```

The authoritative local result is recorded in
`PHASE_1_2_INTEGRATION_RESULT.md`.
