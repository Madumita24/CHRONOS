# CHRONOS Phase 1.6 — Current Metadata Snapshot

## Purpose

`CurrentMetadataSnapshot` is the immutable, evidence-backed representation of
the current DataHub metadata required for `CHRONOS-DEMO-001`.

It composes the public typed results of:

1. Phase 1.1 readiness and environment verification;
2. Phase 1.2 canonical Dataset and Schema Field resolution;
3. Phase 1.3 complete canonical source schema retrieval;
4. Phase 1.4 downstream fine-grained field lineage;
5. Phase 1.5 governance and business-context retrieval.

The assembler performs no DataHub request. Missing, partial, or inconsistent
phase results fail closed.

## What the snapshot is not

The snapshot is not:

- the complete DataHub showcase graph;
- a proposed rename or other mutation;
- a Future Graph;
- an impact, severity, or risk assessment;
- a repair recommendation;
- a DataHub write;
- an autonomous-agent implementation.

The proposed `order_total` to `order_amount` change is not represented or
applied.

## Boundary

The boundary is the verified Phase 1.4 field-lineage scope and its Phase 1.5
context:

- the canonical PostgreSQL `orders` source dataset;
- the canonical `order_total` source field;
- 20 downstream datasets;
- 25 downstream field nodes;
- all explicit field-lineage edges, mapping groups, and captured paths;
- the complete 15-field canonical PostgreSQL source schema;
- stored governance on the 21 scoped datasets and relevant graph fields;
- pipeline and BI reachable context;
- scoped Data Products and Documents;
- evidence and unresolved stored references.

Charts, Dashboards, Data Jobs, Data Flows, Data Products, Documents, owners,
domains, tags, glossary terms, and structured properties do not become
lineage field nodes.

## Machine identity

Dataset identity is the exact DataHub Dataset URN. Datasets are never merged
by name.

Graph-field identity is:

```text
(dataset URN, exact field path)
```

Same-name fields on different datasets remain distinct. The complete source
schema is preserved separately from the bounded 26-node field-lineage graph:
the source schema contains all 15 observed fields, while the graph registry
contains the source `order_total` node and its 25 verified descendants.

## Relationship categories

The snapshot uses explicit categories:

- `FIELD_LINEAGE`
- `PIPELINE_CONTEXT`
- `BI_REACHABLE_CONTEXT`
- `DATA_PRODUCT_MEMBERSHIP`
- `DOCUMENT_RELATIONSHIP`
- `OWNERSHIP`
- `DOMAIN_ASSIGNMENT`
- `TAG_ASSIGNMENT`
- `GLOSSARY_ASSIGNMENT`
- `STRUCTURED_PROPERTY_ASSIGNMENT`

Field lineage retains explicit endpoints, classification, mapping-group IDs,
source entities and aspects, transform operations, and confidence values.
Mapping groups remain independent evidence records. Captured paths remain
ordered graph paths, so multiple routes to one descendant are not flattened.

Pipeline and BI relationships are separate from field lineage. No relationship
category represents impact, breakage, or repair.

## Governance semantics

Governance assignments remain attached only to the exact asset or field where
DataHub stored them. CHRONOS does not propagate owners, domains, tags, or
glossary terms through lineage.

Successful empty reads are preserved in each dataset's metadata states. An
absent owner collection remains `absent`; it is not converted into risk.
Unresolved stored references retain the supplied URN and the `unresolved`
state.

## Evidence registry

Evidence IDs are deterministic references to normalized source facts. Evidence
records retain:

- `verified`, `derived`, or `unknown` classification;
- source phase;
- subject machine key;
- interface;
- aspect or relationship;
- source and target URNs where applicable;
- relationship path;
- observation time;
- small structured attributes needed to explain the fact.

Observation time is retained for auditability but excluded from semantic
fingerprinting. Phase 1.6 does not duplicate large raw DataHub responses.

The current live artifact contains overwhelmingly `verified` evidence. The one
`unknown` evidence record preserves the unresolved Phase 1.5 context finding;
it does not invent a replacement identity.

## Snapshot identity

Snapshot identity and semantic identity are intentionally different.

The snapshot ID is:

```text
snapshot-<first 20 hexadecimal characters of SHA-256>
```

Its input contains the demonstration ID, `created_at`, DataHub endpoint, and
semantic fingerprint. Two observations at different times therefore receive
different snapshot IDs even when their metadata semantics are equal.

The ID is deterministic for the same inputs. It is an identifier, not a
security claim.

## Deterministic serialization

The artifact is canonical JSON:

- dataclasses become objects;
- enums use their string values;
- tuples become arrays;
- registries and relationships are sorted by stable machine keys;
- JSON object keys are sorted;
- compact separators are fixed;
- UTF-8 is used.

`to_json()` includes observation metadata and is byte-stable for one snapshot.
`semantic_json()` removes explicitly volatile fields and is byte-stable across
semantically unchanged observations.

## Semantic fingerprint

The fingerprint is the SHA-256 digest of `semantic_json()` prefixed by
`sha256:`. It is used for reproducibility and metadata-change detection, not
for cryptographic authenticity.

The fingerprint includes:

- environment identity and version information;
- source-phase result states;
- source identity and complete source schema;
- dataset and graph-field registries;
- lineage edges, mapping groups, and paths;
- typed governance and business-context relationships;
- structured-property definitions;
- evidence classifications, sources, interfaces, aspects, relationship paths,
  attributes, and deterministic evidence IDs.

It excludes:

- `snapshot_id`;
- `created_at`;
- every `observed_at`;
- the fingerprint field itself;
- the derived validation result.

Request latency, runtime object identity, credentials, authorization headers,
and tokens are not captured. The fingerprint changes when meaningful schema,
lineage, governance, or context content changes.

## Validation

Validation is read-only and never repairs the candidate snapshot. It checks:

- demonstration and canonical source identity;
- source dataset and source field presence;
- source-field parent binding;
- complete 15-field source schema;
- exact `order_total` native and normalized types;
- unique Dataset URN and field machine keys;
- 21 scoped datasets and 26 lineage field nodes;
- 25 unique downstream fields;
- 20 unique downstream datasets;
- maximum depth 5;
- known field parents;
- known lineage and mapping-group endpoints;
- unique edge, mapping-group, relationship, and evidence IDs;
- no dangling evidence references;
- typed and scoped context relationships;
- no credential-shaped keys or bearer values.

A failure contains the invariant, expected value, observed value, evidence IDs,
and affected key when available. An invalid candidate is not exported as an
authoritative snapshot.

## Persistence and round trip

Phase 1.6 is in-memory first and requires no database. The optional export is:

```text
artifacts/current_metadata_snapshot.json
```

Reloading verifies the stored fingerprint before returning an object.
Round-trip verification compares semantic JSON, fingerprint, graph counts,
machine identities, and evidence references rather than Python object identity.

## Consumption rule for later phases

Later phases should accept a validated `CurrentMetadataSnapshot` as their
current-state input. They should not independently re-query DataHub for the
same frozen facts during the same reasoning run.

**Later phases MUST NOT mutate `CurrentMetadataSnapshot` in place.**

All snapshot dataclasses are frozen and all stored collections are tuples.
Any later future-state representation must be a separate object with explicit
provenance back to this current-state snapshot.
