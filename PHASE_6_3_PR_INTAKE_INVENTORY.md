# CHRONOS Phase 6.3 PR Intake Inventory

## Inspection timing and scope

This inventory was created before any Phase 6.3 production module, dependency,
fixture, or test was added. The inspection covered the Phase 6.1 structural
engine, Phase 6.2 semantic engine, snapshot models, serializers, proposal and
certification patterns, graph/context/decision builders, CLI, dependencies,
Git state, examples, tests, presentation boundary, and frontend.

The repository was on `main` at Phase 6.2 commit `4c77188`, synchronized with
`origin/main`. One unrelated user change existed in `frontend/next-env.d.ts`;
it is outside Phase 6.3 and must remain untouched.

## Reusable Phase 6.1 components

Verified reusable capabilities are:

- strict immutable discriminated proposals with unknown-key rejection;
- canonical JSON, semantic hashing, stable IDs, and timestamp exclusion;
- exact snapshot and field resolution;
- `FIELD_RENAME`, `FIELD_DELETE`, and `FIELD_TYPE_CHANGE` operation semantics;
- conservative structural compatibility rules for rename, delete, and type
  changes;
- observed-lineage traversal and deterministic path construction;
- connected business-context propagation;
- established technical-consequence, certainty, breadth, severity, and
  disposition vocabularies;
- safe staged artifact export, repository containment, overwrite protection,
  manifest validation, and generalized certification.

Phase 6.1 proposals and results are single-field analyses. Their operation
models can be composed or referenced, but their pipeline cannot represent a
repository range, file evidence, several roots, or conflicting claims.

## Reusable Phase 6.2 components

Verified reusable capabilities are:

- SQLGlot `30.13.0` parsing and canonical AST fingerprints;
- bounded raw dbt `ref()` and `source()` resolution without Jinja execution;
- parsed model DTOs for outputs, relations, columns, aggregations, filters,
  joins, expressions, grouping, windows, ordering, and stars;
- structural output deltas and semantic aggregation/filter/join/expression
  deltas;
- exact model/relation/column/output resolution against the certified
  snapshot;
- separate observed, code-derived, counterfactual, missing, and decision
  evidence classes;
- output identity states including identity-preserved semantic change;
- semantic compatibility rules, root-specific questions, required evidence,
  graph propagation, impact, decision, packaging, and certification;
- the public API/CLI error and result patterns.

Phase 6.3 must import and adapt the Phase 6.2 parser and delta detector. It
must not fork or reimplement SQL semantics. Phase 6.2's public engine assumes
repository-relative files in the CHRONOS repository and one proposal/model,
so Phase 6.3 needs an in-memory adapter around `parse_model`, `detect_deltas`,
and the shared entity-resolution vocabulary rather than invoking its package
export once per file.

## Missing multi-file capabilities

No inspected module currently provides:

- local Git-range or exported-bundle intake;
- repository identity or changed-file inventory;
- file-size, binary, symlink, generated/vendor, or credential-file policy;
- parser registry across SQL, YAML/JSON, and Python AST;
- dbt schema, bounded contract, pipeline/config, quality, or DAG parsing;
- file-level result and cross-file delta unions;
- deterministic correlation, logical change groups, coherence, incomplete
  migration detection, or contradictory-claim preservation;
- composite repository/metadata state;
- proposed/removed/unresolved repository edges;
- multi-root propagation and root-to-file-to-target traceability;
- PR-level aggregation and 26-artifact certification.

These capabilities require a separate `chronos.pr_engine` composition layer.
Existing Phase 6.1, Phase 6.2, golden, presentation, and frontend paths must
remain unchanged.

## Available Git integration options

Verified local environment:

- Git CLI: `2.53.0.windows.1`;
- GitPython: not installed;
- Dulwich: not installed;
- the repository has a normal `.git` directory and HTTPS `origin`;
- no Git network access is required for analysis or certification.

Selected option for Phase 6.3: a bounded Git CLI adapter using
`subprocess.run` with an argument list, `shell=False`, repository-contained
`cwd`, no checkout, and a fixed command registry. The only required commands
are commit resolution, repository-root discovery, name/status diff, and
object content reads. Revisions will be syntax validated and resolved to
commit SHAs before use. Paths come from NUL-delimited Git output and are
validated before content access. No hooks, worktree mutation, remote command,
arbitrary config, command interpolation, or analyzed script will run.

Bundle mode can be certified without Git or GitHub. Optional exported GitHub
metadata is inert proposal/manifest data. Tokens, authenticated clone URLs,
comments, approvals, and merge actions are not inputs or outputs.

## Supported file formats and parser assignment

The bounded Phase 6.3 registry will support:

- `.sql`: SQL model / compiled dbt SQL; raw dbt only for the existing static
  `ref()`/`source()` boundary with supplied static identity evidence;
- dbt `schema.yml` / `schema.yaml`: safely loaded dbt schema model, column,
  contract, constraint, test, tag, and metadata records;
- explicit bounded contract `.yml`, `.yaml`, or `.json`: only a documented
  `contract` root and allowlisted fields;
- bounded pipeline/quality `.yml`, `.yaml`, or `.json`: only documented static
  reference keys;
- DAG `.py`: Python `ast` parsing only, with static operator constructors,
  task IDs, allowlisted string reference keywords, `>>`, `set_downstream`,
  and `set_upstream`;
- documentation files: inventory and documentation-only evidence;
- every other file: `UNSUPPORTED`, retained in inventory and never
  interpreted.

PyYAML `6.0.3` is installed transitively through the pinned DataHub package.
Phase 6.3 should make it an explicit exact dependency and use only
`yaml.safe_load`. Standard-library `json` and `ast` are sufficient for JSON
and Python. SQLGlot remains pinned at `30.13.0`.

Category assignment cannot rely on filename alone: extension/path proposes a
parser, while successful bounded structural validation establishes the final
category. An arbitrary YAML object is not a contract or pipeline definition.

## Repository and snapshot evidence

The certified snapshot remains:

- snapshot ID: `snapshot-4981780a1e7123349ef6`;
- snapshot fingerprint:
  `sha256:774185f19c6fea113ef7adfc5e14583e05e7e08a1fad0c59bd6c6fad755db72c`;
- 21 datasets, 26 field nodes, 27 observed field-lineage edges, and 252
  context relationships;
- real dbt model:
  `urn:li:dataset:(urn:li:dataPlatform:dbt,b2fd91.ORDER_ENTRY_DB.analytics.order_details,PROD)`;
- real current model field: `order_total`;
- real PostgreSQL input:
  `urn:li:dataset:(urn:li:dataPlatform:postgres,b2fd91.order_entry_db.order_entry.orders,PROD)`.

No multi-file repository code, manifest, PR, DAG, schema YAML, or quality
configuration was retrieved from DataHub. Phase 6.3 examples must therefore
be disclosed as authored code fixtures mapped to real certified identities.
No synthetic DataHub URN or lineage edge is permitted.

## Security risks and selected controls

- **Revision/option injection:** reject leading `-`, ranges, control
  characters, and unbounded revision strings; resolve each revision as one
  commit before diffing.
- **Shell injection:** argument arrays and `shell=False`; fixed Git commands
  only.
- **Checkout/code execution:** read Git objects or bundle files only; never
  checkout, import, compile, test, or execute analyzed content.
- **Path traversal:** normalized POSIX repository paths; reject absolute,
  empty, dot-segment, `.git`, device, and containment escapes.
- **Symlinks/special files:** reject symlinks and non-regular files in bundle
  evidence; Git object reads never follow a working-tree symlink target.
- **Resource exhaustion:** enforce a documented per-file byte limit and total
  changed-file limit before decoding/parsing.
- **Binary/encoding hazards:** NUL detection and strict UTF-8; retain binary or
  undecodable records as unsupported without semantic parsing.
- **Generated/vendor noise:** isolate `.git`, dependency, build, cache, and
  vendor directories unless a future explicit allowlist is approved.
- **Credentials:** reject hidden credential filenames and credential-shaped
  keys or bearer/private-key content; never serialize raw file contents.
- **Unsafe YAML/Jinja:** `yaml.safe_load`; reject YAML tags and Jinja outside
  the already bounded dbt SQL expressions.
- **Dynamic Python:** parse with `ast.parse`; never import, evaluate, execute,
  or resolve runtime expressions.
- **Output damage:** reuse repository containment, known-package overwrite,
  staging, atomic rename, and golden-root exclusion.
- **Error leakage:** typed errors and bounded CLI JSON; no file contents,
  secrets, or stack traces for normal failures.

## Evidence limitations

- Static repository agreement proves coherence, not runtime correctness.
- SQL parsing proves supported AST differences, not executed row values.
- YAML declarations are contract/config claims, not proof of enforcement.
- Python AST extracts only allowlisted static forms; dynamic references remain
  unresolved.
- DataHub snapshot edges are current observations. Parsed relationships are
  separately labeled proposed/counterfactual evidence.
- The frozen snapshot has no PR, compile, test, execution, row-count,
  cardinality, or downstream consumer-test evidence.
- A current output can have an observed DataHub identity; a proposed rename
  must use a CHRONOS counterfactual identity until observed metadata exists.
- Coherence, structural compatibility, semantic compatibility, execution
  validity, certainty, severity, and disposition remain separate dimensions.

## Assumptions that must not be introduced

Phase 6.3 must not assume:

- every changed file is material or supported;
- filenames alone establish parser semantics or DataHub identity;
- similar strings or edit proximity prove correlation;
- a schema/contract claim overrides SQL, or SQL overrides a contract;
- an unchanged old reference is stale without an evidenced correlated rename;
- a coherent PR is executable, compatible, or approved;
- an unresolved/dynamic reference is a confirmed failure;
- file count determines risk or severity;
- code-derived edges are observed DataHub lineage;
- one root owns a target reached by several roots;
- output-name preservation proves semantic compatibility;
- the snapshot contains SQL, DAG, PR, contract, or execution evidence it does
  not actually contain;
- a Git remote, GitHub token, live service, LLM, repair, or frontend workflow
  is available or required.

This inventory authorizes only deterministic analysis, evidence, decision,
certification, fixtures, tests, and documentation for Phase 6.3. Phase 6.4
repair work remains out of scope.
