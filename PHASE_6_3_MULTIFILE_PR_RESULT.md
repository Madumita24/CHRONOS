# CHRONOS Phase 6.3 Multi-file PR Result

## Final result

Phase 6.3 is complete. CHRONOS now analyzes one bounded multi-file repository
BASE-to-HEAD transition through local Git-range or offline exported-bundle
intake. It parses supported files deterministically, reuses Phase 6.1 and 6.2,
correlates exact cross-file claims, preserves contradictions, builds one
composite repository/metadata future and Future Graph, propagates multiple
roots, derives one review decision, and certifies an isolated 26-file package.

No analyzed repository content, SQL, dbt, Jinja, DAG, or pipeline was executed.
No repository was checked out or modified. No GitHub network dependency,
DataHub write, patch, repair, PR comment, approval, merge, frontend workflow,
LLM decision, or Phase 6.4 work was introduced.

## Repository inspection

The required inspection preceded production code. Findings are frozen in
`PHASE_6_3_PR_INTAKE_INVENTORY.md`. Phase 6.1 provided reusable strict
proposals, serialization, structural operations/compatibility, graph/context,
decision vocabularies, safe export, and certification. Phase 6.2 provided the
single SQLGlot parser, bounded dbt resolver, semantic/structural output deltas,
entity resolution, semantic compatibility, and evidence separation.

Missing capabilities were Git/bundle intake, file safety/inventory, parser
registry, YAML/JSON/Python-AST parsers, cross-file correlation/coherence,
conflict preservation, composite states, proposed/removed edges, multi-root
propagation, and PR certification. These were added in a separate
`chronos.pr_engine` composition package without redirecting golden or
presentation imports.

Verified tool/dependency state: Git 2.53.0, no GitPython or Dulwich, PyYAML
6.0.3 installed, and SQLGlot exactly 30.13.0. PyYAML 6.0.3 is now an explicit
pinned dependency.

## Intake modes

Local Git range resolves validated base/head revisions to commit SHAs, reads a
NUL-delimited name/status diff, verifies regular blob modes/sizes, and reads
blob objects. A real local smoke analysis over `915bd4b..4c77188` certified 44
changed files, including 18 supported and 26 explicitly retained unsupported
files.

Exported bundle mode strictly validates `bundle.json`, public repository
identity, fixture base/head IDs, statuses, logical paths, normalized content
fingerprints, and regular contained base/head evidence. All final examples use
this network-independent judging mode.

Both produce the same `PullRequestInput` and analysis pipeline.

## Git implementation and security boundary

The local adapter uses only fixed read-only Git commands via
`subprocess.run([...], shell=False)`, bounded repository `cwd`, disabled
prompting/optional locks, and a timeout. Revisions reject option/range syntax
and must resolve to one commit. There is no shell interpolation, checkout,
hook, remote, arbitrary config, or proposed-code execution.

The intake enforces 200 changed files, 1 MiB per file side, portable paths,
strict UTF-8, NUL/binary isolation, regular non-symlink files, repository-side
containment, generated/vendor/VCS exclusion, credential filename/content
rejection, and no raw content serialization. Outputs remain repository
contained and atomically replace only recognized packages.

## Proposal and repository identity

`PullRequestAnalysisProposal` is immutable and rejects unknown properties. It
requires proposal/analysis IDs, `MULTI_FILE_PR_CHANGE`, snapshot fingerprint,
repository identity, distinct base/head, and intake mode. Optional public PR
metadata and exact per-file SQL model mappings are inert evidence—not command
configuration.

Repository artifacts contain public name/namespace, semantic repository
fingerprint, base/head identities, and portable analysis root. Clone location,
remote URL, token, and credentials are absent.

## Changed-file inventory

The inventory supports added, modified, deleted, renamed, and Git-evidenced
copied files. Each record has stable ID, paths, status, category, base/head
fingerprints, sizes, binary state, parser, and warnings. Unsupported/binary
files remain visible and are never silently discarded. File timestamps do not
participate in identity.

## Parser registry and supported files

Four isolated adapters are registered:

- Phase 6.2 SQL/dbt adapter;
- safe bounded dbt schema YAML;
- bounded contract/pipeline/quality YAML/JSON;
- Python AST-only static DAG.

Documentation and unsupported files receive explicit non-material/unsupported
results. Filename/path is only a parser hint; bounded content structure
establishes support. Arbitrary YAML is not interpreted as a contract/config.

## SQL/dbt analysis reuse

Phase 6.3 directly reuses Phase 6.2 `parse_model`, `detect_deltas`, bounded
`ref()`/`source()`, DTO serialization, and DataHub resolution. There is no
second SQL parser. The shared delta matcher was generalized to retain a unique
same-position rename while also comparing the changed expression. The primary
fixture therefore emits both `OUTPUT_COLUMN_RENAME` and `AGGREGATION_CHANGE`
for `order_total -> order_amount` plus `SUM -> AVG`.

Formatting, comments, casing, aliases, line endings, and safe parenthesis
normalization remain false-positive protected.

## Schema and contract analysis

The dbt parser safely extracts static models, columns, types, descriptions,
tests, constraints, contract enforcement, metadata, and tags. It emits model/
column add/remove, declared type, contract enforcement, quality expectation,
and documentation-only deltas. Removed/added columns become rename candidates
only when exact cross-file evidence supports correlation.

The bounded generic contract requires one explicit `contract` root and
allowlisted model/dataset guarantees. The focused suite verifies contract type
change handling and arbitrary/invalid JSON rejection.

## DAG and configuration analysis

Python `ast.parse` extracts static task IDs/operator names, allowlisted literal
dataset/field/file references, `>>`, `set_downstream`, and `set_upstream`.
Imports are not followed. Runtime calls, loops/comprehensions, computed task
IDs/references, and complex dependencies remain unresolved/partial.

Pipeline/quality YAML/JSON extracts only allowlisted static dataset, field,
model, contract, dependency, validation, and expected-type keys. Static
reference addition/removal is typed; other text becomes non-material
documentation evidence.

## File-level results and delta union

Every inventory record has one result containing parser/version, base/head
fingerprints and canonical representations, typed deltas, resolved entities,
unresolved references, evidence records, warnings, and analysis status.

The discriminated union composes `StructuralFieldDelta`, `SemanticSqlDelta`,
`ModelContractDelta`, `QualityExpectationDelta`, `PipelineTaskDelta`,
`PipelineDependencyDelta`, `DatasetReferenceDelta`, `FieldReferenceDelta`,
`ConfigurationDelta`, `DocumentationOnlyDelta`, and `UnsupportedFileDelta`.
Phase 6.1/6.2 structural/semantic meanings are reused rather than duplicated.

## Entity resolution

SQL model mappings carry exact DataHub Dataset URN, relation, and dialect.
Phase 6.2 validates target model, input relations/fields, and outputs against
the certified snapshot. Current fields are observed DataHub evidence; proposed
fields are CHRONOS counterfactual identities. Static config/DAG claims resolve
through an exact correlated model/field transition. Ambiguity fails closed and
unknown code remains insufficient metadata. No DataHub URN is fabricated.

## Cross-file correlation and logical groups

Correlation uses exact mapped model, current/future field, dbt schema model/
column pair, and supported static reference evidence. String similarity, edit
proximity, and parser order are excluded.

Logical groups retain all contributing files, delta categories/IDs, observed
and counterfactual entities, evidence, warnings, coherence, and root
candidates. The primary produces two groups: the correlated rename/semantic/
schema/reference migration and an independently retained contract-enforcement
change.

## Coherence and incomplete migrations

The engine distinguishes `COHERENT`, `PARTIALLY_COHERENT`, `INCONSISTENT`, and
`UNRESOLVED`. Primary SQL/schema agree on `order_amount`, but exact static DAG
and quality head representations retain `order_total`, so it is
`INCONSISTENT`. The coherent fixture updates both references. A dynamic DAG
reference yields `PARTIALLY_COHERENT`, while a standalone change without exact
cross-file identity evidence remains `UNRESOLVED`.

Inconsistency is a repository-state finding, not a claim of confirmed runtime
failure.

## Conflict detection and precedence

The conflict fixture has SQL `order_amount`, schema `total_amount`, and DAG
`order_total`. Both future claims are retained in an explicit
`CONFLICTING_FUTURE_FIELD_IDENTITIES` record. Code and contract claims are
separate; neither overwrites the other based on parse order. This confirmed
repository contradiction has decision precedence over unresolved material
findings.

## Composite Change Set and counterfactual states

The immutable Composite Change Set joins PR/repository/base/head identity,
inventory/results, groups, all typed deltas, observed/counterfactual entities,
unresolved references, coherence, conflicts, warnings, and evidence summary.

Counterfactual repository state records active/removed/renamed head files,
fingerprints, parsed representations, and unresolved constructs without
mutating current files. Counterfactual metadata state records current,
proposed, and removed entities, adapted/stale references, semantic/contract
groups, and conflicts. Conflicting claims produce `CONFLICTED`, not an
invented single future.

## Composite Future Graph and multi-root propagation

The graph distinguishes `OBSERVED_DATAHUB_EDGE`,
`CODE_DERIVED_PROPOSED_EDGE`, `COUNTERFACTUAL_EDGE`, `REMOVED_EDGE`, and
`UNRESOLVED_REFERENCE`. Observed edges retain snapshot IDs. Coherent static
updates point to explicit counterfactual endpoints. Output deletion preserves
the current origin plus a removed edge and uses Phase 6.1 deletion
compatibility. Stale references are unresolved repository edges.

Every material delta, stale reference, and conflict retains its own root with
files, deltas, entities, scope, evidence, and compatibility. Observed lineage
is traversed from all resolved roots. Shared downstream fields and paths are
deduplicated; each target aggregates all reaching roots/files and supporting
paths. Root-to-target-file traceability is certified.

## Compatibility, impact, context, severity, and decision

Structural rename/delete rules are Phase 6.1 rules. Aggregation/filter/join/
expression rules are Phase 6.2 rules. Repository coherence and execution
validity remain independent. Execution stays `UNVERIFIED`.

PR technical consequences derive from actual roots: structural adaptation,
semantic definition, stale references, contract/quality, pipeline/config, and
explicit conflicts. Certified DataHub relationships are reused only as
connected context. File count does not select severity.

Decision precedence is deterministic:

1. explicit contradictory future identities ->
   `block_confirmed_incompatibility`;
2. material unresolved evidence -> `hold_for_review`;
3. zero supported material data deltas -> `no_material_change`.

There is no numeric risk score. All examples retain zero confirmed runtime
failures because no execution evidence exists.

## Blocking questions and required evidence

Questions are emitted per structural, semantic, stale-reference, or conflict
root and carry exact files/entities/scope. Evidence requirements include
approved definitions, explicit mappings, contracts, compile/test/execution or
consumer validation as applicable. Every requirement is labeled
`EVIDENCE_NOT_REPAIR`; no file modification is proposed.

## Explanation and artifact package

Explanations exist at PR, file, logical-group, root, downstream-target, and
decision levels. Every run exports exactly 26 JSON artifacts specified in the
Phase 6.3 task. Certification verifies identity, inventory/fingerprint,
parser/result, delta, group/correlation/conflict, state, graph/path, root/file/
target, compatibility/decision, evidence, portability, and manifest closure.

No package contains raw analyzed contents, credentials, tokens, private paths,
or machine-specific repository locations.

## Python API and CLI

Public APIs:

- `chronos.analyze_pull_request`;
- `chronos.analyze_pull_request_bundle`.

CLI:

- `chronos analyze-pr --repo ... --base ... --head ...`;
- `chronos analyze-pr --bundle ...`.

The CLI enforces mutually exclusive intake, bounded failures/non-zero status,
concise JSON, no content/secret output, and controlled overwrite.

## Final examples and determinism

Each final bundle was executed twice through the public CLI to different
output directories after the last code change. Fingerprints matched:

- primary: `sha256:612c05df17c97b33afdae40b683a7fc9be12e434c2e79658c7e2de2bdc910aba`;
- coherent: `sha256:116d18943cfca658d4a072b9a11ed0d46452d21c0ff00fe66dc2f83da7b23621`;
- no material: `sha256:3e755795e55b832a1b464be7a7ca2dad28ac2829d2fdcb4c0a44347a4180ca23`;
- conflict: `sha256:c3d58ad7f89cc5d0269eaa5dc23681fecb87136f71958ecfe06e646959280a6a`.

Primary: 4 files, 7 roots, 0 conflicts, `INCONSISTENT`, hold. Coherent:
4 files, 9 roots, 0 conflicts, `COHERENT`, hold. No material: 4 files,
0 roots, `COHERENT`, no-material decision. Conflict: 3 files, 5 roots,
1 conflict, `INCONSISTENT`, block.

Output location, configured timestamp, clone location, comments/formatting,
line endings, and safe YAML ordering do not affect semantic identity.

## Tests

The 75 Phase 6.3 tests pass. They cover the 25 required positive areas, both
intake modes, all parser/delta types, correlation, groups, stale/inconsistent/
partial/unresolved/coherent states, conflicts, no-material behavior, proposed/
removed/unresolved/observed edges, multi-root deduplication, traceability,
API/CLI, determinism, and 26-artifact export.

Negative coverage includes invalid repository/revision/base-head, bundle
identity/fingerprint/path/duplicate/missing evidence, symlinks, binary/size,
invalid YAML/JSON/Python, dynamic DAG, unsupported Jinja, DataHub ambiguity,
snapshot/unknown proposal mismatch, dangling group/edge/path, overwrite,
external output, credential-shaped content, and certification tampering.

False-positive tests prove SQL formatting/comments, YAML key order,
documentation descriptions, Python comments, and unsupported files do not
manufacture material impact.

## Phase 6.1, Phase 6.2, golden, and frontend regression

- Phase 6.1 focused: **44/44 passed**.
- Phase 6.2 focused: **73/73 passed**; SQLGlot remains 30.13.0.
- All 16 root JSON artifacts are byte-identical to their pre-change hashes.
- Phase 4 physical hash remains
  `5dc730bae390908fa14f5ee5dc5d6a2b6a71382eecf664950bf60f76a74c94e8`.
- Phase 4 semantic fingerprint remains
  `sha256:3e8444ec904e0ba1c55c5ae22d69edfa8e722310f51ab30fc783b8175a87ac4a`.
- Phase 5 presentation/API behavior remains golden-only.
- Frontend typecheck, ESLint, Vitest, and production build passed. Routes
  remain `/`, `/_not-found`, and `/review`; no PR UI was added.

## Exact regression totals

- Backend unit: **965 run, 965 passed**; includes 75 Phase 6.3, 73 Phase 6.2,
  44 Phase 6.1, and all golden unit coverage.
- Backend certification: **241 run, 240 passed, 1 existing environment skip**.
- Backend API: **95 run, 95 passed**.
- Backend integration: **6 run, 0 failed, 6 skipped** because live services
  were not configured.
- Backend total: **1,307 run, 1,300 passed, 7 skipped, 0 failed**.
- Frontend: **9 Vitest files, 186 tests passed**, typecheck passed, ESLint
  passed, production build passed.

## Security audit

Verified controls cover Git argument construction, revision/path containment,
bundle regular-file/fingerprint validation, symlinks, byte/file-count limits,
strict UTF-8/binary isolation, YAML safe loading, Python AST-only parsing,
Jinja rejection, no checkout/execution, output/overwrite containment,
credential/token/private-key rejection, raw-content exclusion, portable
artifacts, bounded errors, and certification tamper checks.

## Known limitations and warnings

- One repository and one BASE/HEAD transition per analysis.
- Static bounded file forms only; arbitrary framework/config semantics are not
  inferred.
- Dynamic DAG/dbt/Jinja constructs require external evidence or compiled SQL.
- The frozen snapshot does not contain PR, compile, test, contract-execution,
  row-count, cardinality, or consumer-test results.
- Repository coherence does not prove structural/semantic compatibility or
  execution validity.
- DataHub topology is current observation; proposed repository edges remain
  explicitly code-derived/counterfactual.
- Local repository name/namespace is supplied public identity rather than
  inferred from a potentially secret-bearing remote URL.
- The frontend does not yet select Phase 6.3 manifests.

These are explicit Phase 6.3 boundaries. Phase 6.4 repairs and Phase 7
execution verification remain unimplemented.
