# CHRONOS Phase 6.2 Semantic Change Result

## Final result

Phase 6.2 is complete. CHRONOS now performs deterministic, certified semantic
change analysis for one logical model from explicit BEFORE and AFTER SQL. It
supports plain SQL, compiled dbt SQL, and a deliberately bounded raw dbt
subset using a supplied manifest. It resolves exact DataHub entities from the
frozen snapshot, emits structural and semantic deltas separately, overlays
only observed lineage, and writes an isolated 18-artifact package.

No SQL or Jinja was executed. No live DataHub query or write, pull-request
intake, repair, verification run, Phase 6.3 workflow, or frontend feature was
added.

## Inspection-first evidence

Before production code changed, the Phase 1-6.1 packages, proposal/snapshot
models, lineage and context records, certification logic, serialization,
CLI, frontend boundary, repository SQL/dbt evidence, and installed dependency
state were inspected. The findings are frozen in
`PHASE_6_2_SQL_SEMANTIC_INVENTORY.md`.

Verified repository facts were:

- Phase 6.1 canonical serialization, safe export, immutable result, and
  certification patterns were reusable;
- Phase 6.1 had no safe SQL/dbt parser or semantic compatibility model;
- the snapshot contains real dbt, Snowflake, and PostgreSQL Datasets and
  observed `order_total` field lineage;
- the repository contained no model SQL, compiled dbt SQL, or manifest before
  Phase 6.2.

Accordingly, the examples are authored fixtures tied to real snapshot
identities. They are not represented as query text retrieved from DataHub.

## Implementation

`src/chronos/semantic_engine` now contains:

- strict proposal parsing and typed failures;
- safe repository-contained SQL and manifest intake;
- bounded static dbt `ref()` and `source()` resolution without Jinja
  execution;
- SQLGlot-based dialect-aware parsing and canonical AST contracts;
- immutable discriminated structural and semantic deltas;
- exact model, relation, column, star, and output resolution;
- counterfactual semantic state;
- observed-edge-only graph and deterministic path projection;
- dependency propagation;
- aggregation, filter, join, expression, and no-change compatibility rules;
- technical impact, connected context, severity, decision, questions,
  evidence requirements, and explanation builders;
- generalized package certification and safe atomic export;
- one public Python API and CLI command.

The parser dependency is pinned to `sqlglot==30.13.0`, and the installed
version was verified as `30.13.0`. Parser selection and official sources are
documented in `PHASE_6_2_SEMANTIC_CHANGE_ARCHITECTURE.md`.

## Semantic coverage

Verified deltas include:

- `SUM` to `AVG`;
- `COUNT` to `COUNT(DISTINCT ...)`;
- aggregation input, grouping, addition, and removal;
- filter addition/removal, literal, operator, and referenced-column changes;
- `LEFT` to `INNER` join;
- join predicate and joined relation changes;
- expression operator, function, literal, and CASE changes;
- output rename, addition, removal, and order changes as structural deltas.

Formatting, comments, harmless keyword/case differences, quote-normalized
aliases, line endings, and redundant parentheses do not create semantic
deltas. Output-name preservation is represented as identity preservation, not
as semantic compatibility.

## Resolution and evidence behavior

The target model must resolve exactly once in the supplied snapshot. Relation
and field references resolve from parsed code against certified DataHub
identities. Ambiguous unqualified columns, unknown aliases or relations, and
unsafe multi-source star expansion fail closed. A star expands only for one
resolved source with a certified schema.

Code-derived unresolved references remain explicit. Parsed SQL relationships
are never converted into invented DataHub lineage. The semantic future graph
contains only reachable supplied snapshot edges. Field-scoped changes start
from the changed output; model-wide changes start from every resolved output.
All propagation metrics are derived from that graph.

Compatibility rules expose required evidence, inputs, result, certainty,
reason, and explanation. A semantic change without certified contract or
execution evidence remains `SEMANTIC_COMPATIBILITY_UNKNOWN`; CHRONOS does not
claim a failure. Questions and evidence requirements differ by aggregation,
filter, join, and expression semantics. Business relationships remain context
unless explicit evidence gives them stronger meaning.

## Package contract

Each certified run contains exactly:

1. `semantic_change_proposal.json`
2. `proposal_validation.json`
3. `before_parsed_model.json`
4. `after_parsed_model.json`
5. `semantic_diff.json`
6. `entity_resolution.json`
7. `code_change_set.json`
8. `counterfactual_semantic_state.json`
9. `future_metadata_graph.json`
10. `dependency_propagation.json`
11. `compatibility_evaluation.json`
12. `technical_impact_analysis.json`
13. `business_context_propagation.json`
14. `severity_criticality_analysis.json`
15. `impact_synthesis.json`
16. `explanation_bundle.json`
17. `analysis_certification.json`
18. `manifest.json`

Certification verifies package and identity contracts, parser version,
semantic delta integrity, resolution, graph/path closure, rule and decision
traceability, evidence classes, portability, artifact fingerprints, and
manifest consistency. Credential-shaped data and absolute repository paths
are excluded from generated packages.

## Interfaces and examples

Python:

`from chronos import analyze_semantic_code_change`

CLI:

`chronos analyze-semantic-change --snapshot ... --proposal ... --before ... --after ... --output ...`

The CLI returns bounded JSON on success and normal invalid input. The public
result exposes analysis identity, certification state, disposition, semantic
compatibility, semantic fingerprint, typed deltas, resolved model, affected
outputs, manifest, artifact paths, and loaded artifacts.

Four example directories cover aggregation, filter, join, and derived
expression changes. The aggregation directory also includes a combined
aggregation-and-filter change, proving multiple deltas coexist in one model.

## Final determinism results

Every final example was run twice through the public CLI to distinct output
directories after the last implementation change. The pairs matched:

- aggregation: `sha256:2fad35e7bcc1358535ac85786068261ed1a7d17f919536ede0213dcb864f848a`;
- combined aggregation and filter:
  `sha256:5e88d3d6ead93f20681e8179446c5f08a8f12b360772ff0134c65e5a52e3fa07`;
- filter: `sha256:f77a65b0678265ae7cff744684478c3945ec2b28250612f4d57333ad7dc11f7e`;
- join: `sha256:7606503e4570cb13686a6ec0a47acf715f8766135ca6c4afaa46443501fb0897`;
- expression: `sha256:74d2e450b368a49e9206e74b155b85a70669729c695e7829aa76a8b53cee88cc`.

All five dispositions are `hold_for_review`, not confirmed failure, because
the fixture supplies observed downstream lineage but no certified semantic
contract or execution evidence. Configured timestamps, output directories,
comments, formatting, and line endings do not affect semantic fingerprints.

## Negative and generalization testing

The 73 Phase 6.2 tests pass. Positive tests cover the full semantic matrix,
all examples, combined changes, dbt `ref()` and `source()`, single-source star
expansion, output identity, evidence-specific questions, observed graph
closure, path-derived metrics, deterministic packaging, CLI behavior, and a
different real field/model path.

Negative tests cover malformed and unknown proposal properties, invalid SQL,
multiple statements, dynamic commands, unsupported Jinja, raw dbt without a
manifest, unresolved and ambiguous relations/columns/stars, unknown aliases,
snapshot/model/dialect mismatch, absolute/URL/traversal paths, external output,
uncontrolled overwrite, artifact tampering, and dangling graph endpoints.

## Frozen baseline preservation

The 16 root `artifacts/*.json` files were not regenerated. Final physical
SHA-256 comparison matched all pre-change values. The frozen Phase 4 artifact
remains byte-identical at:

`5dc730bae390908fa14f5ee5dc5d6a2b6a71382eecf664950bf60f76a74c94e8`

Its stored semantic fingerprint remains:

`sha256:3e8444ec904e0ba1c55c5ae22d69edfa8e722310f51ab30fc783b8175a87ac4a`

All 44 Phase 6.1 tests remain included in the passing unit regression. The
Phase 5 presentation DTOs, API behavior, and frontend were not changed.

## Exact regression totals

- Backend unit: **890 run, 890 passed**; includes 73 Phase 6.2 tests and the
  full Phase 6.1/golden unit coverage.
- Backend certification: **241 run, 240 passed, 1 skipped**; the skip is the
  existing environment-dependent case.
- Backend API: **95 run, 95 passed**.
- Backend integration: **6 run, 0 failed, 6 skipped** because live integration
  services were not configured.
- Backend total: **1,232 run, 1,225 passed, 7 skipped, 0 failed**.
- Frontend Vitest: **9 files, 186 tests passed, 0 failed**.
- Frontend TypeScript typecheck: passed.
- Frontend ESLint: passed.
- Next.js production build: passed; `/`, `/_not-found`, and `/review` were
  generated as static routes.

The initial frontend command attempt was blocked by the managed filesystem
sandbox while Node resolved the user profile. The identical validation
commands passed when rerun with scoped permission; this was not a product test
failure.

## Known boundaries and future questions

Verified boundaries, not implementation assumptions:

- only one logical SELECT model is supported per analysis;
- dbt macro execution and arbitrary Jinja are intentionally unsupported;
- live repository, PR, and DataHub intake are not implemented;
- semantic contracts and execution results are not available in the frozen
  snapshot and therefore cannot prove consumer compatibility;
- parsed joins/relations are code evidence, not observed lineage;
- no repair, approval, or write-back workflow exists;
- the frontend still consumes only the frozen Phase 5 certified scenario.

Questions for a separately approved future phase include how contract and
execution evidence will be represented, how multi-model changes will be
bounded, which SQL dialects require additional conformance fixtures, and how
a UI selector will validate and load manifests without re-deriving analysis.
None was assumed or implemented in Phase 6.2.
