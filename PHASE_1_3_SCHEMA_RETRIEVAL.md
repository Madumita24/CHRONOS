# CHRONOS Phase 1.3 — Schema and Field Retrieval

Phase 1.3 establishes the current schema state verified by DataHub for an
already-resolved dataset identity. It does not establish impact and contains
no lineage traversal, graph construction, Future Graph, governance
enrichment, repair logic, frontend, agent behavior, or DataHub write.

## Read path

`SchemaRetrievalSession` constructs one `DataHubSdkReadOnlyTransport` and
shares it across:

1. the Phase 1.1 readiness gate;
2. the Phase 1.2 canonical entity resolver;
3. the Phase 1.3 schema retriever.

The schema read uses the official Python SDK call:

`DataHubGraph.get_aspect(dataset_urn, SchemaMetadataClass)`

The transport exposes the complete observed `SchemaMetadata` through an
immutable internal observation. It does not construct dataset or schema-field
URNs.

## Installed SDK representation inspected

The installed and pinned `acryl-datahub==1.6.0.15` classes were inspected
directly before implementation.

`SchemaMetadataClass` requires `schemaName`, `platform`, `version`, `hash`,
`platformSchema`, and `fields`. It can additionally contain `created`,
`lastModified`, `deleted`, `dataset`, `cluster`, `primaryKeys`,
`foreignKeysSpecs`, and `foreignKeys`.

`SchemaFieldClass` requires `fieldPath`, `type`, and `nativeDataType`. Its
optional values include `jsonPath`, `nullable`, `description`, `label`,
`created`, `lastModified`, `recursive`, tags, glossary terms, key indicators,
and JSON properties.

The live canonical aspects supplied `SchemaMetadataClass` with 15 ordered
`SchemaFieldClass` values. Phase 1.3 captures the properties needed by its
strict scope and preserves absence rather than deriving replacements.

## Typed schema state

`DatasetSchemaSnapshot` is frozen and contains:

- the Phase 1.2 `ResolvedDatasetIdentity`;
- the supplied `CanonicalDatasetIdentity`;
- schema name, platform, environment, version, and hash;
- every field in the order returned by DataHub;
- the UTC observation time;
- aspect/interface evidence;
- DataHub-created and last-modified times when present;
- dataset reference, cluster, and primary keys when present.

`SchemaFieldRecord` is also frozen. It contains:

- zero-based position in `SchemaMetadata.fields`;
- field path and derived leaf name;
- native type;
- normalized DataHub type category;
- raw DataHub type-class name;
- description;
- nullability;
- key and partitioning-key indicators;
- JSON path, label, and recursive indicator;
- schema-field URN only when supplied by DataHub.

The snapshot owns a tuple of frozen field records. Captured evidence therefore
cannot be modified in place.

## Available, absent, and unknown values

The model does not fabricate optional metadata:

- `None` means the corresponding DataHub value was absent or unavailable.
- `False` remains distinct from `None` for boolean indicators.
- an empty schema hash remains `""` because that is the observed value.
- `NormalizedFieldType.UNKNOWN` means the raw DataHub type was absent or was
  not in the centralized mapping.
- a supplied schema-field URN is preserved; an absent one remains `None`.

No value is marked “not applicable” unless DataHub supplies such a
distinction. The installed SDK aspect does not expose a separate
not-applicable state for these fields.

## Type normalization

All mapping is centralized in
`chronos.datahub.schema_types.normalize_datahub_type`. Native SQL text is
never used to guess a normalized category.

The canonical live schema currently exercises:

| Raw DataHub type | CHRONOS normalized type |
|---|---|
| `NumberTypeClass` | `Number` |
| `StringTypeClass` | `String` |

The mapping also recognizes DataHub's generic Boolean, Date, Time, Bytes,
Map, Array, Record, and Null type classes. Any other class maps to `Unknown`,
while its raw class name and native type remain available for inspection.

The frozen baseline remains:

`DOUBLE PRECISION` → `Number`

## Structural validation

A snapshot is created only after all of these checks pass:

- the resolved and canonical identities match;
- the returned dataset URN is the requested resolved URN;
- schema name and platform are present and agree with the resolved identity;
- the schema contains at least one field;
- schema version and hash representations are supported;
- every field path is non-empty and has no surrounding whitespace;
- no exact field path is duplicated;
- optional text and boolean field metadata has the expected representation.

Malformed metadata is reported and is never repaired. Stable error categories
are:

- `schema_not_found`
- `schema_empty`
- `schema_malformed`
- `duplicate_field_path`
- `unsupported_field_metadata`
- `schema_retrieval_unavailable`

Existing connection, authentication, authorization, and other Phase 1 errors
remain available when they are the more precise cause.

## Field lookup

`DatasetSchemaSnapshot.lookup_field(field_path)` performs an exact,
case-sensitive scan of the already-captured field tuple. It never calls
DataHub and never performs a global field search.

The result is typed as `found` or `not_found`. An absent field returns the
stable `field_not_found` failure category.

## Determinism

`DatasetSchemaSnapshot.semantic_key()` includes resolved identity, canonical
identity, schema metadata, ordered field content, and optional source
metadata. It deliberately excludes the snapshot and evidence observation
timestamps.

`semantically_equals()` compares these keys. Repeated retrievals of unchanged
metadata are therefore semantically equal even though they were observed at
different times. This is a deterministic comparison representation, not a
cryptographic integrity mechanism.

## Evidence

Every valid snapshot records:

- exact dataset URN;
- aspect: `SchemaMetadata`;
- interface:
  `DataHubGraph.get_aspect(SchemaMetadataClass)`;
- UTC observation timestamp;
- schema name, version, and hash;
- field count;
- validation state: `valid`.

Invalid retrieval results contain typed validation findings and no snapshot.

## Verification

Run unit tests without DataHub:

```powershell
.\.venv-datahub-310\Scripts\python.exe -m unittest discover -s tests\unit -v
```

Run all live checks against the configured local Quickstart:

```powershell
$env:CHRONOS_RUN_INTEGRATION = "1"
.\.venv-datahub-310\Scripts\python.exe -m unittest discover -s tests\integration -v
```

The authoritative observed result is recorded in
`PHASE_1_3_INTEGRATION_RESULT.md`.

## Read-only boundary

The Phase 1.3 retriever exposes only `retrieve`. The snapshot exposes only
local lookup and comparison operations. The private transport adds only a
`schema_metadata` read.

There is no Metadata Change Proposal, Metadata Change Event, emitter,
GraphQL mutation, REST write, create, update, delete, patch, upsert, rollback,
or lineage operation in Phase 1.3.
