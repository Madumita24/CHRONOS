# CHRONOS Phase 6.4 Repair Inventory

## Inspection timing and scope

This inventory was completed before Phase 6.4 production implementation. The
inspection covered the committed Phase 6.1 structural engine, Phase 6.2
semantic SQL/dbt engine, Phase 6.3 multi-file PR engine, frozen snapshot and
certification conventions, parser boundaries, output controls, tests, and the
Phase 5 frontend boundary. A temporary Phase 6.3 package was generated from the
primary fixture using only the existing deterministic static analyzer. No
fixture code was executed and no analyzed repository content was modified.

Verified repository state at inspection time:

- `main` was at `d11ba9c` (`feat: add multi-file PR analysis`).
- The only pre-existing uncommitted change was `frontend/next-env.d.ts`; it is
  outside Phase 6.4 and must be preserved.
- SQLGlot is pinned at `30.13.0` and PyYAML at `6.0.3`.
- The Phase 6.3 primary package certified with semantic fingerprint
  `sha256:612c05df17c97b33afdae40b683a7fc9be12e434c2e79658c7e2de2bdc910aba`.
- The primary package contains four changed files, seven roots, two exact stale
  references, no conflicts, and repository coherence `INCONSISTENT`.

## Reusable predecessor contracts

### Phase 6.1

The structural engine provides strict immutable proposals, deterministic
identities, typed rename/delete/type-change operations, compatibility rules,
counterfactual state, graph propagation, certification, artifact
fingerprints, atomic export, and overwrite protection. Its 14-file package is
certified and portable.

Phase 6.1 does not generally provide a repository identity, certified BASE and
HEAD revisions, changed-file inventory, HEAD file fingerprints, parsed source
locations, or candidate target contents. Therefore a normal Phase 6.1 package
is not sufficient by itself for a Phase 6.4 file repair. It may be accepted
only if a future explicit adapter proves a complete file-level target contract
equivalent to the Phase 6.3 evidence. The current implementation must fail
closed otherwise.

### Phase 6.2

The semantic engine provides SQLGlot AST parsing, bounded static dbt
`ref()`/`source()` resolution without Jinja execution, structural and semantic
deltas, protected semantic representations, DataHub resolution, deterministic
certification, and an 18-file package.

Phase 6.2 code references and AST fingerprints are useful supporting evidence,
but the package does not generally certify a repository-wide BASE/HEAD
identity, changed-file inventory, exact HEAD raw-content fingerprint, or
cross-file logical group. It therefore cannot normally authorize coordinated
file edits by itself. It may be accepted only where an explicit adapter can
prove all missing file-level evidence; otherwise the trust gate must fail
closed.

### Phase 6.3

Phase 6.3 is the primary predecessor because its 26-file package provides:

- one certified analysis identity and manifest;
- repository fingerprint plus BASE and HEAD identities;
- changed-file IDs, paths, statuses, categories, sizes, and normalized content
  fingerprints;
- parser names and versions;
- parsed BASE and HEAD representations;
- typed structural, semantic, pipeline, contract, and quality deltas;
- exact logical groups and contributing files;
- coherence findings, explicit conflicts, and stale current/future identities;
- DataHub-observed and counterfactual entity records;
- counterfactual repository and metadata state;
- one Future Graph, root causes, propagation, decisions, questions, and
  required-evidence records;
- artifact fingerprints and package certification.

The primary fixture proves the exact repair evidence required by the acceptance
scenario. SQL and dbt schema establish the single field transition
`order_total` to `order_amount`; the DAG parsed HEAD contains one static
`output_field="order_total"`; and the quality parsed HEAD contains one static
`quality.checks[0].field: order_total`. The semantic root records the independent
`SUM` to `AVG` change and remains unresolved.

## Repairable root types

The following roots are repairable only when the rule registry verifies exact
current value, one coherent future value, one logical group, supported parser
evidence, one unambiguous target, matching HEAD fingerprint, and no competing
claim:

- `STALE_PIPELINE_OR_QUALITY_REFERENCE`: exact field or dataset scalar in a
  supported DAG, quality, or pipeline configuration.
- `STRUCTURAL_CHANGE`: safe rename propagation when file-level stale-reference
  evidence identifies a supported target; the structural root alone is not an
  edit authorization.
- `FIELD_REFERENCE_CHANGED`, `DATASET_REFERENCE_CHANGED`, and
  `CONFIGURATION_CHANGED`: only when the root participates in a certified
  coherent identity transition and the target location is exact.
- `CONTRACT_CHANGE`: exact bounded contract field or declared-type alignment
  when the intended future field/type is explicit and independently supported.
- `QUALITY_EXPECTATION_CHANGED`: exact quality target alignment or a strict
  deletion case where the stale declaration has no independent purpose.
- Explicit output removal: only removal of a supported stale structured
  reference; never automatic removal of a SQL expression or DAG task.

Repair categories that can be implemented with the current parser evidence are
stale field/dataset reference alignment, dbt schema declaration alignment,
bounded contract field/type alignment, quality reference alignment, static DAG
argument alignment, pipeline configuration alignment, model-file reference
alignment, strict structured stale-reference removal, and declaration-only
type alignment.

## Non-repairable and blocked root types

The following are not automatic repairs without additional separately
certified intent:

- `SEMANTIC_DEFINITION_CHANGED`, including aggregation, filter, join,
  expression, CASE, threshold, retention, or metric-definition changes;
- `CONFLICTING_FUTURE_FIELD_IDENTITIES` or any logical group with more than one
  future identity;
- unresolved or ambiguous DataHub identity where the repair rule requires it;
- dynamic Python references, loop-generated tasks, f-strings, environment
  values, computed values, arbitrary Jinja, macros, or runtime-generated
  references;
- unsupported file categories or unknown YAML/JSON keys;
- uncertain deletion replacement or a deletion whose target has independent
  semantics;
- casts, precision/truncation conversions, or type policies that are not
  explicitly certified;
- missing product intent, business contract, owner approval, execution
  comparison, downstream semantic test, or Phase 7 runtime evidence.

These must be represented as `MANUAL_DECISION_REQUIRED`, `UNSUPPORTED`,
`BLOCKED_BY_CONFLICT`, or `BLOCKED_BY_MISSING_EVIDENCE`. A HOLD predecessor is
not itself evidence that a root is repairable.

## Available exact repository evidence

Phase 6.3 exposes the following exact evidence chain:

1. `manifest.json` names all 26 artifacts and binds their semantic
   fingerprints to the analysis, repository, BASE, HEAD, snapshot, proposal,
   and decision.
2. `analysis_certification.json` binds the pre-certification artifact
   fingerprints and analysis semantic fingerprint.
3. `changed_file_inventory.json` supplies file IDs, portable paths, categories,
   byte sizes, and normalized BASE/HEAD content fingerprints.
4. `file_analysis_results.json` and
   `counterfactual_repository_state.json` supply parser assignments and parsed
   HEAD structures without raw source content.
5. `logical_change_groups.json` supplies exact current/future identities,
   contributing file IDs, delta IDs, group coherence, and conflict candidates.
6. `coherence_evaluation.json` supplies exact stale-reference findings and
   explicit competing claims.
7. `technical_impact_analysis.json` supplies typed roots with file, group,
   delta, entity, and scope traceability.
8. `impact_synthesis.json` supplies missing evidence and blocking questions.
9. The corresponding exported bundle supplies the certified HEAD bytes. Its
   `bundle.json` fingerprints can be checked against both the bytes and the
   predecessor inventory.

Raw source content is deliberately absent from predecessor JSON artifacts. A
repair generator must load it only from the separately supplied certified
bundle or Git evidence and must not copy it into semantic JSON artifacts.

## Missing intent and execution evidence

The inspected packages do not establish:

- product or model-owner approval for `SUM` to `AVG`;
- runtime SQL correctness, data quality, dbt compilation, task execution, or
  consumer compatibility;
- safe merge status;
- a general conversion policy for casts, precision, truncation, nullability,
  accepted values, or retention semantics;
- authoritative resolution for conflicting future identities;
- behavior of dynamic Python or Jinja constructs.

Phase 6.4 may project static coherence after a candidate patch, but it must
label the result `STATIC_PROJECTED` / `PROJECTED_POST_REPAIR` and require Phase
7 validation. It must never use `VERIFIED`, `SAFE_TO_MERGE`, or execution-pass
language.

## Reusable parser and serializer components

- `ParserRegistry` provides deterministic file classification and parser
  assignment.
- `SqlModelParser` reuses Phase 6.2 SQLGlot parsing, bounded dbt substitution,
  semantic delta detection, and entity resolution.
- `DbtSchemaParser` uses `yaml.safe_load` and a strict `version`/`models`
  boundary.
- `BoundedConfigParser` uses safe YAML/JSON parsing, rejects Jinja, applies an
  allowlist of static reference keys, and has a strict generic-contract shape.
- `PythonDagParser` uses `ast.parse`, records exact static string arguments,
  dependencies, and dynamic constructs without executing Python.
- `canonicalize`, `pretty_json`, `semantic_fingerprint`, and `stable_id`
  provide deterministic serialization and identifiers.
- Phase 6.3 intake provides normalized line-ending fingerprints, byte and file
  limits, portable path validation, Git regular-object checks, exported-bundle
  fingerprint checks, and credential detection.
- Phase 6.3 analysis can be rerun against an isolated repaired bundle for a
  deterministic projected result rather than being forked or reimplemented.

No current component performs source-preserving edits. Phase 6.4 therefore
needs an explicit editor registry and must keep classification, planning,
editing, validation, and certification separate.

## Safe editing strategy by file category

### SQL and bounded dbt SQL

Parse with SQLGlot 30.13.0 and target a resolved identifier, relation, or output
alias node. Compare protected aggregation, filter, join, expression, source,
and output fingerprints before and after. Raw dbt source is editable only when
bounded static substitution has an exact reversible source mapping; otherwise
the action is unsupported. Never execute Jinja or use global string
replacement.

### dbt schema YAML

Use safe structured parsing to locate one exact model/column/type/test path.
Prefer a source-span scalar edit when the exact occurrence is unique. If
canonical YAML serialization is required, disclose comment/format loss and
verify all untargeted bounded values remain equivalent.

### Contract, pipeline, and quality YAML/JSON

Use only allowlisted structured paths already recognized by the Phase 6.3
parser. JSON must reject duplicate keys and serialize deterministically. YAML
must use `safe_load`, reject Jinja, and never infer semantics for unknown keys.
Deletion is allowed only for one exact declaration or mapping/list member
proved to serve solely the removed identity.

### Python DAG

Use `ast.parse` and source-position evidence to replace exactly one static
string constant belonging to a supported keyword argument. Preserve all other
source bytes where practical and verify task IDs, operators, and dependency
edges are unchanged. Dynamic nodes are never patched.

### Plain file/model references

Allow only an exact, parser-confirmed scalar or path field in a supported
configuration or DAG argument. A Git rename or coherent logical identity must
establish the new value. Arbitrary prose and unparsed source are unsupported.

## Patch-security risks and controls

- **Tampered predecessor:** recompute every artifact fingerprint, certification
  fingerprint, manifest relationship, and analysis/repository/base/head/snapshot
  identity before planning.
- **Mismatched repository evidence:** validate bundle manifest, normalized HEAD
  fingerprints, file IDs, status, category, and size against the predecessor.
- **Path traversal and external output:** require portable POSIX relative paths,
  resolve targets under the certified HEAD copy, reject `..`, drive prefixes,
  backslashes, generated/vendor/VCS paths, symlinks, and external output.
- **Resource exhaustion:** retain Phase 6.3 limits of 200 files and 1 MiB per
  file and bound generated hunks/artifacts.
- **Ambiguous target:** require exactly one parser-confirmed structured or AST
  target and an exact current-value match.
- **Credential leakage:** reject credential-shaped paths/content before parsing,
  inspect generated candidates/diffs/artifacts, and keep raw contents out of
  semantic JSON.
- **Patch smuggling:** generate deterministic `a/` and `b/` relative headers,
  reject undeclared paths or unexpected hunks, and test the diff only against
  an isolated certified HEAD copy.
- **Semantic drift:** fingerprint protected SQL regions, YAML/JSON untargeted
  structure, and DAG task/dependency structure before and after.
- **Overwrite/destructive export:** require a new repository-contained output
  directory; overwrite only a recognized complete repair package when
  explicitly requested; stage atomically and clean temporary workspaces.
- **Execution:** parse only. Never import or execute analyzed Python, SQL, dbt,
  Airflow, Dagster, Prefect, Jinja, scripts, tests, or jobs.

## Assumptions that must not be introduced

Phase 6.4 must not assume:

- that a similar string is the intended replacement;
- that one file type has precedence unless a certified rule explicitly states
  it;
- that a semantic change is erroneous or approved;
- that HOLD means an automatic repair exists;
- that a deleted field has no consumers or replacement;
- that differing types authorize a cast;
- that a static parse proves runtime behavior;
- that a DataHub entity exists when resolution is missing;
- that a dynamic reference has a predictable runtime value;
- that comments, formatting, ordering, or unknown keys may be discarded without
  disclosure;
- that a generated patch is applied, verified, safe to merge, or approved;
- that Phase 6.4 may write to DataHub, Git, the source bundle, the analyzed
  worktree, predecessor artifacts, frozen artifacts, or the frontend.

Production implementation may begin only within these verified boundaries.
