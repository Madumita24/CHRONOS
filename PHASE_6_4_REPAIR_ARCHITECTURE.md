# CHRONOS Phase 6.4 Repair Architecture

## Objective and scope

Phase 6.4 converts a certified analysis finding into an isolated, deterministic,
reviewable candidate patch when—and only when—the predecessor proves one exact
repository inconsistency and one supported correction. It does not modify the
analyzed repository, apply a patch, execute project code, approve semantic
intent, or certify runtime correctness.

The certified path is:

1. validate a strict `RepairGenerationProposal`;
2. reproduce trust in a certified Phase 6.3 package;
3. bind the package to matching HEAD repository evidence;
4. classify every selected predecessor root;
5. construct one immutable Repair Plan;
6. apply typed actions to in-memory HEAD contents with registered editors;
7. generate portable diffs and candidate previews in an isolated workspace;
8. statically validate targets, candidates, protected semantics, and patches;
9. rerun Phase 6.3 against an isolated repaired bundle;
10. compare original and projected states;
11. certify and atomically export 27 semantic JSON artifacts plus `repairs/`.

The output is a repair candidate requiring human review and Phase 7 execution
validation. It is never a merge approval.

## Predecessor trust gate

Phase 6.3 is the primary predecessor because it carries repository identity,
BASE/HEAD identity, file fingerprints, parsed file evidence, logical groups,
conflicts, coherence, roots, and a certified manifest. A normal Phase 6.1 or
6.2 package lacks the complete repository-wide file target contract and is
therefore rejected unless a future adapter can prove equivalent evidence.

The trust gate:

- requires exactly the 26 Phase 6.3 artifacts and no copied summaries;
- rejects symlinked, oversized, invalid, duplicate-key, secret-shaped, or
  absolute-path artifacts;
- recomputes the repair proposal's predecessor-manifest fingerprint;
- reconstructs the Phase 6.3 identity;
- recomputes every pre-certification artifact fingerprint;
- reruns Phase 6.3 certification and requires byte-equivalent semantic content;
- validates the analysis, snapshot, repository, BASE, HEAD, root, group,
  conflict, and coherence identities;
- re-runs exported-bundle intake and compares every HEAD fingerprint;
- reclassifies and reparses every file, requiring equivalence to the certified
  `file_analysis_results.json`.

Any mismatch fails closed before planning. Raw prose cannot authorize an edit.

## Repair proposal

`RepairGenerationProposal` is immutable and rejects unknown properties. Its
required fields are:

- `proposal_id`;
- `repair_analysis_id`;
- `operation: GENERATE_REPAIR`;
- `predecessor_analysis_id`;
- `predecessor_manifest_fingerprint`;
- strict repository name, namespace, and optional repository fingerprint;
- exact `base_revision` and `head_revision`;
- `repair_mode`.

Modes are `ALL_SUPPORTED`, `SELECTED_ROOTS`, and `SELECTED_GROUPS`. Selected
modes require exactly their corresponding ID list. The proposal contains no
command, prompt, script, arbitrary code, or execution option.

## Repairability model

Every selected root receives exactly one classification:

- `AUTO_REPAIRABLE`;
- `CONDITIONALLY_REPAIRABLE`;
- `MANUAL_DECISION_REQUIRED`;
- `UNSUPPORTED`;
- `BLOCKED_BY_CONFLICT`;
- `BLOCKED_BY_MISSING_EVIDENCE`.

Each record names its rule, supporting evidence, preconditions, eligible file
categories, reason, and remaining uncertainty. A predecessor HOLD decision is
not itself a repair signal.

### Automatic repairs

Automatic stale-reference alignment requires all six certified conditions:

1. one exact current static value;
2. one correlated logical group;
3. one coherent counterfactual identity;
4. no competing identity;
5. one parser-confirmed target;
6. no unrelated semantic alteration.

The primary fixture meets this boundary for one DAG keyword string and one
quality YAML scalar.

### Conditional repairs

Deletion and type alignment expose—and verify—their additional preconditions.
The delete rule requires an explicit certified no-replacement deletion plus a
structured reference with no independent purpose. The type rule requires one
explicit approved declaration transition and produces no cast. Unsatisfied
preconditions become `BLOCKED_BY_MISSING_EVIDENCE`, not recommendations.

### Manual semantic intent

Aggregation, filter, join, expression, CASE, threshold, retention, and metric
definition changes remain manual unless a separately certified expected
semantic definition establishes the result. The primary `SUM` to `AVG` root is
retained and `AVG` is neither reverted nor legitimized by repair generation.

## Conflict and dynamic-reference boundaries

Competing future identities are `BLOCKED_BY_CONFLICT`. Every claim and its
supporting files remain in the Repair Plan; no editor is invoked for that
group.

F-strings, environment-derived values, loops, computed Python expressions,
arbitrary Jinja, macros, runtime functions, and computed YAML values are never
text-patched. They are `UNSUPPORTED` or `BLOCKED_BY_MISSING_EVIDENCE`.

## Repair-rule registry

`RepairRuleRegistry` is the sole mapping from roots and file categories to
typed edit strategies. Every rule declares:

- stable rule ID;
- supported root types and file categories;
- required evidence and preconditions;
- typed edit operation;
- editor assignment;
- post-generation checks;
- remaining Phase 7 evidence;
- human explanation template;
- whether the rule is conditional.

Rules cover static DAG fields, quality and pipeline config fields, dataset/model
references, dbt schema columns, bounded contract fields, SQL identifiers,
bounded dbt/model references, strict structured deletion, and declaration-only
type alignment. Repair logic is not scattered through unregistered string
conditionals.

## Repair Plan and actions

The immutable Repair Plan exists before editor invocation. It contains selected
roots, classifications, typed actions, non-repairable and blocked roots,
affected files, dependencies, deterministic application order, projected
coherence intent, compatibility limits, required decisions, Phase 7
validations, and warnings.

Every action binds:

- rule, root, and logical-group IDs;
- changed-file ID and portable target path;
- parser and editor evidence;
- exact HEAD fingerprint and current value;
- exact intended counterfactual value;
- typed edit operation and target location;
- expected identity transition;
- dependencies and confidence;
- preconditions, static checks, remaining evidence, and explanation.

Actions in a logical group are ordered by deterministic category precedence.
Dependencies are topologically sorted and cycles fail planning.

## Editor registry

`EditorRegistry` exposes six named adapters:

- `sqlglot_ast_editor`;
- `dbt_schema_editor`;
- `structured_contract_editor`;
- `structured_config_editor`;
- `python_dag_static_editor`;
- `static_reference_editor`.

An action must name a registered editor and supported typed operation. Every
editor returns candidate content, target provenance, formatting disclosures,
and protected-semantic fingerprints. No editor executes content.

## SQL and dbt editing

The SQL editor parses exactly one statement with SQLGlot 30.13.0, locates one
column, relation, or output-alias AST node, mutates only that node, and
serializes in the configured dialect. A normalized placeholder AST proves that
aggregation, filter, join, and expression structure is unchanged. SQLGlot
formatting is disclosed separately.

Raw dbt SQL permits only bounded static `ref()`/`source()` string replacement
with one exact source span and no residual or control-flow Jinja. Arbitrary
macros and unsafe round trips are rejected. Jinja is never executed.

## YAML and JSON editing

YAML uses a duplicate-key-rejecting SafeLoader plus the existing Phase 6.3
bounded parser. Exact scalar updates use PyYAML node source spans and preserve
surrounding text. Unique list-value deletion removes only the parser-located
line. Canonical serialization is a disclosed fallback when a precise safe span
does not exist.

JSON uses the standard library with duplicate-key rejection, an exact
structured path, deterministic serialization, and an untargeted-structure
comparison. Raw global replacement is forbidden for both formats.

## Python DAG editing

The DAG editor calls `ast.parse` and locates exactly one static string keyword
argument in the expected task call. It replaces only the string literal source
span. The before/after protected record proves task identities, operator types,
and dependency edges are unchanged. Dynamic expressions, loops, imports, task
logic, and framework behavior are not modified or inferred.

## Coordinated multi-file repair

Actions share one logical group and one selected future identity. The primary
plan identifies SQL/dbt schema as the identity-establishing evidence, then
aligns DAG and quality consumers. The action order and dependencies are
portable and deterministic. Semantic questions remain attached to the same
package rather than being silently treated as repaired.

## Patch workspace and packaging

Candidate generation occurs in memory and in a repository-contained temporary
workspace. Only affected HEAD files are copied into the projected bundle.
Original fixture and predecessor bytes are never changed.

The exported `repairs/` directory contains:

```text
repairs/
  patches/
    combined.patch
    files/<relative-path>.patch
    groups/<logical-group>.patch
  repaired_files/<relative-path>
  repair_actions.json
  repair_plan.json
```

Diffs use deterministic `a/` and `b/` relative headers, no timestamps, and no
absolute paths. Raw patches and candidate files are outside the 27 semantic
JSON artifacts; JSON records contain their paths and fingerprints.

## Static patch validation

Generation validates:

- exact current HEAD fingerprint;
- one registered parser/editor target;
- valid SQL, YAML, JSON, or Python candidate syntax;
- intended value present and untargeted bounded structure equivalent;
- deterministic unified-diff regeneration;
- clean hunk application to the certified HEAD lines;
- declared paths and expected hunks only;
- credential and absolute-path absence;
- action/file/patch/candidate fingerprint traceability.

These are static checks. They do not execute SQL, dbt, DAGs, or application
code.

## Protected semantic regions

Editor-specific protected records cover SQL AST structure, YAML/JSON untargeted
structure, Python task/operator identity, and DAG dependency edges. A repair
candidate that alters a protected region fails generation and is not exported.

## Projected Phase 6.3 reanalysis

Candidate files are placed into a temporary exported bundle whose HEAD
fingerprints are regenerated. The unchanged Phase 6.3 pipeline reparses and
reanalyzes that bundle. Its projected file analysis, logical groups, conflicts,
composite state, graph, propagation, roots, and decision are packaged with
`STATIC_PROJECTED` labels.

Repair-scope coherence is computed from the same Phase 6.3 group, stale-finding,
and conflict records. For the primary fixture the targeted identity group moves
from `INCONSISTENT` to `COHERENT` and stale references move from two to zero.
The raw global Phase 6.3 state remains separately disclosed as `UNRESOLVED`
because unrelated contract/semantic questions remain. Neither state is runtime
verification.

Phase 6.3 necessarily records the candidate edits as new change deltas relative
to BASE. These are listed as repair-action-derived roots. They are not counted
as new unresolved defects only when their types and contributing file IDs map
exactly to certified actions. Any unexplained new root or any new conflict fails
repair certification.

## Repair disposition

The repair decision is separate from the predecessor PR decision:

- `REPAIR_CANDIDATE_READY_FOR_REVIEW`;
- `PARTIAL_REPAIR_CANDIDATE`;
- `NO_SUPPORTED_AUTOMATIC_REPAIR`;
- `REPAIR_BLOCKED_BY_CONFLICT`;
- `REPAIR_GENERATION_FAILED`.

Completeness is independently reported as fully addressed repairable selected
roots, partially addressed selected roots, or no supported repair. Human review
is mandatory for every generated candidate.

## Certification

The 27-file package certifies proposal and predecessor trust, selected-root
validity, rule/action/file traceability, exact current and replacement evidence,
editor assignment, candidate and patch fingerprints, clean patch application,
protected semantics, static syntax, non-repairable boundaries, projected
reanalysis, absence of new unresolved roots/conflicts, remaining findings,
Phase 7 requirements, manifest completeness, portability, and secret absence.

Certification scope is explicitly
`deterministic_candidate_generation_and_static_projection` and
`runtime_correctness_certified` is always false.

## Security

The implementation retains Phase 6.3 limits of 200 files and 1 MiB per source
file, limits predecessor artifacts to 5 MiB each, and limits actions and patch
hunks to 500. It rejects traversal, drive-prefixed paths, symlinks, non-regular
Git objects, binary repair targets, generated/vendor/VCS paths, invalid UTF-8,
credentials, private keys, unrecognized overwrite targets, and output outside
the repository.

Repair output is also forbidden under frozen `artifacts/`, `src/`, `tests/`,
`examples/`, `frontend/`, or `.git`. Atomic staging is cleaned on failure. No
analyzed code executes and no artifact is written to DataHub.

## Frontend boundary

Phase 5 remains unchanged on CHRONOS-DEMO-001. A future repair-review screen
could read `manifest.json`, `repair_actions.json`, file patch records, unified
diffs, repair comparison, and remaining findings. Phase 6.4 adds no UI and does
not change frontend behavior.

## Non-goals

Phase 6.4 does not apply patches, write to the analyzed repository, commit,
branch, push, open or comment on pull requests, execute SQL/dbt/Python/DAGs,
run consumer projects, write to DataHub, infer business intent, use an LLM in
the certified path, redesign the frontend, or begin Phase 6.5/7.
