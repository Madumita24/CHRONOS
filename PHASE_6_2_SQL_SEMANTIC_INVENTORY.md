# CHRONOS Phase 6.2 SQL/DBT Semantic Inventory

## Inspection gate

This inventory was created before Phase 6.2 production-code changes. The
inspection covered the Phase 6.1 public API, proposal and identity models,
operation adapters, graph/artifact builders, compatibility registry,
certification and CLI; the immutable snapshot and golden artifacts; tests;
repository SQL/dbt evidence; and installed dependencies.

The only pre-existing working-tree change is the generated
`frontend/next-env.d.ts` import from `.next/types` to `.next/dev/types`.
Phase 6.2 will preserve and exclude that unrelated change.

## Frozen baselines

- Golden Phase 4 fingerprint:
  `sha256:3e8444ec904e0ba1c55c5ae22d69edfa8e722310f51ab30fc783b8175a87ac4a`
- The 16 root golden artifacts remain the immutable Phase 1-5 package.
- Phase 6.1 is commit `915bd4b` on `main`; its structural proposal, resolver,
  adapters, CLI command, isolated export, and certification must remain green.
- Phase 5 remains intentionally bound to `CHRONOS-DEMO-001`.

## Reusable Phase 6.1 components

- `CurrentMetadataSnapshot` and `load_snapshot` provide certified datasets,
  schema fields, field nodes, lineage edges and paths, mapping groups,
  relationships, evidence, snapshot identity, and semantic fingerprint.
- `structural_engine.serialization` provides deterministic JSON,
  `sha256:` semantic fingerprints, and stable semantic IDs.
- `structural_engine.engine` provides repository-contained staged export,
  explicit overwrite protection, manifest conventions, and concise result
  packaging patterns.
- The Phase 6.1 reachable-edge traversal, dependency metrics, connected
  business-context selection, existing severity vocabulary, and
  `impact_synthesis.evaluate_decision` are reusable concepts.
- The structural compatibility registry demonstrates explicit rule records
  with rule identity, required evidence, result, reason, and explanation.
- The CLI already has a safe subcommand boundary and normal JSON error output.

## Missing semantic capabilities

The repository has no SQL parser, parsed-model DTO, SQL canonicalizer, SQL/dbt
input gate, semantic proposal, semantic-delta union, relation/column resolver,
semantic compatibility dimension, semantic graph overlay, or semantic
analysis certification. Phase 6.1 treats only source schema fields and cannot
safely represent model-wide row-set or join semantics.

The structural engine cannot be reused by pretending a semantic change is a
rename/type/delete. In particular:

- output identity preservation is not semantic compatibility;
- model-level filters and joins do not have one source-schema field origin;
- code-derived references are not observed DataHub lineage;
- structural type compatibility rules say nothing about metric definitions;
- the Phase 6.1 source resolver requires the source schema dataset, while
  Phase 6.2 must resolve any exact model dataset present in the snapshot;
- semantic packages require 18 different artifacts and separate
  certification, so they must not be passed through the structural adapter
  union.

## Parser selection

No suitable parser is installed or declared. Phase 6.2 selects SQLGlot
`30.13.0`, pinned exactly. PyPI identifies it as a production/stable SQL
parser/transpiler requiring Python 3.9 or later, and the official API exposes
AST parsing through `parse_one`. The version and dialect will be part of
semantic identity and parsed artifacts.

Official references:

- https://pypi.org/project/sqlglot/30.13.0/
- https://sqlglot.com/sqlglot.html

Regex will be limited to rejecting/recognizing bounded Jinja and unsafe input
forms. SQL meaning will be derived from the SQLGlot AST.

## Available real DataHub evidence

The certified snapshot contains real dbt and Snowflake model datasets,
including:

- dbt `ORDER_ENTRY_DB.analytics.order_details`;
- dbt `ORDER_ENTRY_DB.analytics.order_history`;
- Snowflake `order_entry_db.analytics.order_details`;
- Snowflake `order_entry_db.analytics.order_details_replica`;
- Snowflake `order_entry_db.analytics.order_history`;
- Snowflake `order_entry_db.order_entry.orders`;
- PostgreSQL `order_entry_db.order_entry.orders`.

The certified field graph contains `order_total` on the dbt `order_details`
model and an observed downstream edge to Snowflake `order_details`, followed
by further certified reach. The PostgreSQL source schema contains 15 fields,
including `order_total`, `order_status`, `customer_id`, and other usable code
references.

Mapping groups contain query URNs and a bounded transform string for a replica
copy, but no query text. They therefore prove query/entity provenance, not the
SQL semantics needed for BEFORE/AFTER comparison.

## Available repository code/dbt evidence

Before Phase 6.2 there are:

- no `.sql` files;
- no `dbt_project.yml`;
- no dbt `manifest.json`, catalog, or run results;
- no compiled SQL;
- no embedded query source text;
- no SQL parser imports.

Consequently the four required examples must be explicitly labeled CHRONOS
fixtures. They may bind to real snapshot Dataset URNs and fields, but must not
claim their SQL was retrieved from DataHub or a live dbt repository.

## Safe example choice

The primary target will be the real dbt `order_details` Dataset and its real
`order_total` output. The fixture can compare `SUM(order_total)` with
`AVG(order_total)` while preserving that real output identity. Propagation can
start from the certified dbt field node and use only observed downstream
edges. Filter, join, and expression fixtures will use real snapshot relations
where resolution is possible and retain unresolved code references explicitly
where the snapshot lacks a full model schema.

## Required separation

Phase 6.2 will live in a new `chronos.semantic_engine` package and compose with
stable serialization/decision conventions without modifying the frozen
builders. It will:

- analyze exactly one SELECT model;
- parse but never execute SQL;
- accept plain or compiled SQL;
- permit raw dbt only through bounded static `ref()`/`source()` resolution
  against a supplied repository-contained manifest;
- reject unsupported Jinja, dynamic SQL, multiple statements, ambiguity, and
  unsafe paths;
- distinguish structural deltas, semantic deltas, execution validity, and
  semantic compatibility;
- overlay semantics on certified topology without inventing edges;
- write a separate 18-file package.

## Final verification obligations

Completion requires parser-backed positive, negative, equivalence,
generalization, deterministic, Phase 6.1, golden, API, and frontend gates. No
SQL/dbt execution, Jinja execution, network fetch, repair, PR analysis, LLM,
DataHub write, credential, or absolute semantic path may be introduced.
