# CHRONOS Phase 6.2 Semantic Change Architecture

## Scope and evidence boundary

Phase 6.2 adds deterministic analysis for one logical model with explicit
BEFORE and AFTER SQL. It is a backend knowledge and analysis capability, not
a pull-request workflow. It does not execute SQL, Jinja, dbt, macros, Python,
or shell commands; query DataHub; mutate metadata; generate repairs; or alter
the Phase 5 frontend.

The engine combines two evidence classes without confusing them:

- code-derived evidence: parser-normalized relations, outputs, expressions,
  predicates, joins, and deltas;
- observed DataHub evidence: the exact model, schemas, field identities,
  business context, and lineage edges in the supplied certified snapshot.

Counterfactual graph state and decisions are explicitly labeled derivations.
Missing contracts or execution evidence remain missing; they are never
inferred from names, topology, or parser output.

## Pre-implementation findings

The required inspection preceded production changes and is recorded in
`PHASE_6_2_SQL_SEMANTIC_INVENTORY.md`. Phase 6.1 supplied reusable canonical
serialization, immutable result packaging, deterministic decision vocabulary,
safe export, and certification patterns. It did not contain a SQL AST, dbt
intake, semantic delta types, output-to-schema resolution, or semantic
compatibility rules. Its structural operation assumptions were therefore not
reused as semantic facts.

Repository and snapshot inspection found real dbt, Snowflake, and PostgreSQL
entities and observed field lineage for `order_total`. It found no model SQL,
compiled dbt SQL, or manifest. Consequently, the checked examples are clearly
labeled repository fixtures mapped to real DataHub identities; they are not
claimed to be metadata retrieved from DataHub.

## Parser and intake

SQLGlot is pinned at `30.13.0`. The selection was verified against the
[official SQLGlot parser API](https://sqlglot.com/sqlglot.html) and the
[published package release](https://pypi.org/project/sqlglot/). Its mature,
dialect-aware AST lets CHRONOS compare meaning-bearing syntax without using
regex as a SQL parser.

The accepted input modes are:

1. plain SQL;
2. compiled dbt SQL, treated as plain SQL;
3. bounded raw dbt SQL containing only static `ref('name')` and
   `source('source', 'table')` expressions, with a supplied manifest.

For the third mode, narrowly scoped regular expressions recognize only the
two allowed Jinja expression shapes. Manifest metadata supplies one static
relation identity, which is substituted before SQL parsing. Jinja blocks,
comments, macros, variables, dynamic arguments, ambiguous manifest matches,
and unresolved expressions fail closed. The regex is not used to interpret
SQL. Repository-relative path containment prevents network, absolute,
traversal, command-substitution, and backtick references.

The parser accepts exactly one SELECT model. It rejects multiple statements,
commands, and dynamic SQL. Canonical AST serialization removes comments,
formatting, harmless case differences, line-ending differences, alias quote
differences, and redundant parentheses while preserving operator precedence.
The parsed DTO records:

- source relations, aliases, and CTEs;
- ordered outputs and stable output identities;
- input column references and source relations;
- aggregation function, distinctness, inputs, and grouping;
- filters, filter columns, literals, and comparison/logical operators;
- join type, relation, predicate, and predicate references;
- functions, literals, operators, CASE, windows, ordering, and unresolved
  stars;
- canonical SQL and canonical AST fingerprint.

## Proposal, resolution, and identity

`SEMANTIC_CODE_CHANGE` is a strict discriminated proposal. It requires exact
model Dataset URN, dialect, repository-relative BEFORE/AFTER references, and
source snapshot fingerprint. Unknown keys and inconsistent API/CLI overrides
are rejected.

Resolution first proves the proposed model exists exactly once in the
snapshot. Optional `model_relation` is validated rather than trusted. Parsed
relations are mapped to DataHub Datasets by platform/dialect and normalized
qualified relation identity. Aliases and qualified columns must resolve
unambiguously. Unqualified columns resolve only when certified schemas make
the match unique. Unresolved code references are retained as such; ambiguous
ones stop the analysis.

`SELECT *` expansion is allowed only for one resolved relation with a
certified schema. Multi-source or uncertified stars fail closed. Output
mapping distinguishes current, counterfactual, removed, new, unresolved, and
`IDENTITY_PRESERVED_SEMANTICS_CHANGED` state. Reusing an output name is never
treated as proof of semantic compatibility.

## Delta model

Structural output deltas remain separate from semantic deltas:

- structural: output rename, addition, removal, and order change;
- semantic: aggregation, filter, join type, join predicate, joined relation,
  and derived expression changes.

Each immutable, discriminated delta contains deterministic identity, scope,
model and optional output, BEFORE/AFTER representation, input references,
evidence references, certainty, explicit change components, and explanation.
Components distinguish aggregation function/distinct/input/grouping and
addition/removal; filter addition/removal/literal/operator/reference;
join type/predicate/relation; and expression function/operator/literal/CASE.

Filter and join deltas are model-wide. Aggregation and derived-expression
deltas are output-field scoped. A model may contain several deltas at once;
the pipeline does not split them into independent model runs.

## Counterfactual state, graph, and propagation

The counterfactual state retains every output and records current/future
expression fingerprints, semantic delta IDs, and output mapping. The graph
starts only from resolved affected outputs. Field-scoped deltas start from
their output; model-wide deltas start from all resolved model outputs.

Traversal uses only supplied `SnapshotLineageEdge` records reachable from
those origins. It never fabricates a relation from a parsed SQL reference.
Deterministic paths retain observed edge, transform, mapping group, and
evidence references. Propagation counts direct/transitive/multipath fields,
datasets, paths, relationships, and depth from that graph.

## Compatibility, impact, and decision

An explicit rule registry evaluates every semantic delta. Structural and
semantic compatibility are separate dimensions. No-change is semantically
compatible. A detected semantic change is semantically changed, but downstream
compatibility remains unknown unless a supplied contract or execution result
proves more. Phase 6.2 does not manufacture either form of evidence.

Rules declare rule ID, required evidence, inputs, semantic state, certainty,
reason, and explanation. Aggregation, filter, join, and expression changes
have distinct questions and evidence requirements. Compatibility does not
depend on output-name preservation.

Technical impact is derived from delta scope, observed propagation, and rule
results. Root causes are shared per actual delta rather than fabricated per
descendant. Connected snapshot relationships are carried as context only and
are not labeled broken, critical, or sensitive without explicit evidence.
Severity and final disposition reuse the established deterministic CHRONOS
vocabularies. No change may proceed; an unresolved semantic change with
observed downstream reach holds for review. This is evidence gating, not a
claim that a consumer has failed.

## Artifact and certification boundary

Every run produces exactly 18 isolated JSON artifacts:

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

Certification checks package shape, snapshot and proposal identity, pinned
parser state, delta integrity, operation semantics, resolution, graph/path
integrity, rule-to-impact-to-decision traceability, evidence classes, and
portable secret-free output. Artifact fingerprints preserve auditability.
The selected semantic analysis fingerprint excludes output location,
configured timestamps, comments, formatting, and raw line endings.

Export is staged and atomically moved to a repository-contained directory.
Existing output is rejected unless explicit overwrite targets a known prior
semantic package. The golden root artifact directory is never a valid target.

## Interfaces and future boundary

Python exposes `chronos.analyze_semantic_code_change`; the CLI exposes
`chronos analyze-semantic-change`. Both return or print certified identity,
disposition, semantic compatibility, delta count, fingerprint, and package
location. Normal invalid input is reported as bounded failure without an
ordinary stack trace.

A future presentation selector may read only validated manifests and load an
analysis by identity. It must not recompute parser, graph, compatibility, or
decision logic in the browser. That selector, Phase 6.3 PR intake, repair
generation, execution verification, DataHub writes, and frontend redesign are
outside Phase 6.2.
