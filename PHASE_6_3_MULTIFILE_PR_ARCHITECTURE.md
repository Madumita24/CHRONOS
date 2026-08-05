# CHRONOS Phase 6.3 Multi-file PR Architecture

## Problem and scope

Phase 6.3 analyzes one coordinated repository BASE-to-HEAD transition. A pull
request is treated as a set of evidence-bearing claims about one proposed
future, not as unrelated file diffs. The engine inventories files, assigns
bounded parsers, reuses structural and semantic analysis, resolves certified
DataHub identities, correlates exact claims, preserves contradictions,
constructs one composite future state and graph, propagates all roots, and
selects one deterministic review disposition.

It does not fetch GitHub, check out proposed code, execute repository content,
run SQL/dbt/DAGs, write DataHub, generate a repair or patch, approve/merge a
PR, or alter the Phase 5 frontend. Phase 6.4 is not started.

## Intake modes

Both modes produce the same immutable `PullRequestInput` contract.

### Local Git range

Inputs are one exact Git repository root and proposal-matching base/head
revisions. The adapter uses Git 2.53 through `subprocess.run` with an argument
array, `shell=False`, repository `cwd`, disabled prompting/optional locks, a
30-second command timeout, and a fixed read-only command set:

- `rev-parse --show-toplevel`;
- `rev-parse --verify <revision>^{commit}`;
- `diff --name-status -z -M -C <base-sha> <head-sha>`;
- `ls-tree`, `cat-file -s`, and `show <sha>:<path>`.

Revisions reject option prefixes, ranges, control/unbounded syntax, and must
resolve to one commit SHA before use. NUL-delimited Git paths are containment
validated. Blob modes must be regular files. There is no checkout, hook,
remote operation, arbitrary config, shell interpolation, or code execution.

### Exported PR bundle

An offline bundle contains strict `bundle.json`, `base/`, and `head/` trees.
The manifest fixes repository identity, deterministic base/head IDs, status,
logical paths, and normalized content fingerprints. Every record has an exact
shape. Paths cannot leave their side directory; evidence must be regular,
non-symlink files. Missing or fingerprint-mismatched content fails closed.
Certification therefore requires neither GitHub nor Git.

Optional PR number/title/author-style metadata is inert proposal context. No
token, private clone URL, comment, approval, or write action is accepted.

## Proposal and repository identity

`PullRequestAnalysisProposal` is strict and immutable. It requires proposal
and analysis IDs, `MULTI_FILE_PR_CHANGE`, snapshot fingerprint, repository
name/optional namespace, base/head revisions, and intake mode. Optional fields
include snapshot ID, PR number, scenario, title, description, creation time,
string metadata, and exact per-file SQL model mappings. Unknown properties and
equal base/head identities are rejected.

Repository artifacts contain supplied public name/namespace, resolved or
fixture base/head identities, `analysis_root: "."`, and a semantic repository
fingerprint. Absolute clone location, remotes, credentials, and tokens are
excluded. Clone location is not semantic identity.

## Changed-file inventory and safety

Statuses are `ADDED`, `MODIFIED`, `DELETED`, `RENAMED`, and `COPIED` when Git
or bundle evidence supports them. `UNSUPPORTED` is a category/analysis state,
not a fabricated Git status. Each record includes deterministic ID, base/head
path, status, category, normalized content fingerprints, sizes, binary state,
parser, and warnings. Timestamps are excluded.

The certified limits are 200 files and 1 MiB per side per file. The intake
rejects traversal, absolute/non-portable paths, `.git`, dependency/vendor and
generated directories, symlinks, special Git object modes, hidden credential
files, private-key extensions, strict UTF-8 failures, and credential-shaped
content. Binary files are isolated as unsupported and never parsed.

No raw file content is serialized to the artifact package.

## Parser registry and categories

`ParserRegistry` assigns one isolated adapter. Filename/path proposes a parser;
bounded content validation establishes the supported category.

- `SQL_MODEL` / `DBT_MODEL`: Phase 6.2 adapter;
- `DBT_SCHEMA`: safe dbt schema YAML;
- `SCHEMA_CONTRACT`: explicit bounded `contract` YAML/JSON;
- `PIPELINE_DAG`: Python AST-only static DAG;
- `PIPELINE_CONFIG` / `QUALITY_CONFIG`: allowlisted static YAML/JSON
  references;
- `DOCUMENTATION_ONLY`: non-technical evidence;
- `UNSUPPORTED`: retained without interpretation.

An unsupported or partial file cannot silently disappear; every changed file
has one typed result with parser version, parsed base/head representation,
deltas, resolution, evidence, warnings, and status.

## SQL and dbt reuse

The SQL adapter calls the Phase 6.2 `parse_model`, `detect_deltas`, bounded dbt
resolver, parsed DTO serializer, and entity resolver. SQLGlot remains exactly
30.13.0. No second SQL parser exists.

Plain and compiled SQL are parsed directly. Raw dbt accepts only static
`ref()`/`source()` with a mapped manifest contained in the change set; Jinja is
never executed. Formatting, comments, line endings, equivalent casing, alias
quotes, and redundant parentheses remain non-semantic.

The shared Phase 6.2 delta detector now treats a unique same-position output
identity change as a rename even when its expression also changes. Thus a
single model can correctly produce both `order_total -> order_amount` and
`SUM -> AVG`, without losing either structural or semantic evidence.

## Schema, contract, and quality parsing

PyYAML is explicitly pinned at 6.0.3 and only `yaml.safe_load` is used. Jinja
in YAML/JSON is rejected.

The dbt parser extracts static models, columns, data types, descriptions,
tests/data tests, constraints, contract enforcement, metadata, and tags. It
separates model/column structural changes, declared-type and contract changes,
quality/constraint changes, and documentation-only descriptions. A unique
removed/added schema column pair is a rename candidate only for later
cross-file correlation; it is not independently declared a rename.

The generic contract adapter requires exactly one `contract` root and an
allowlisted dataset/model contract vocabulary. Arbitrary YAML is not a
contract. Pipeline/quality adapters recursively extract only documented
static dataset, field, model-file, contract-file, dependency, validation, and
expected-type keys. Other structures are not assigned semantics.

## Python DAG boundary

Python uses standard-library `ast.parse`; files are never imported or
executed. The supported subset is:

- static operator calls assigned to one variable;
- static `task_id`;
- allowlisted static string arguments such as input/output dataset, table,
  field, SQL/model file, and contract file;
- `task_a >> task_b`;
- `set_downstream` and `set_upstream` with simple names.

Loops/comprehensions, runtime calls, f-strings, computed task IDs/references,
and complex dependencies remain explicit unresolved dynamic constructs. A
partial parse does not become a confirmed failure.

## Shared identity and DataHub resolution

The cross-file vocabulary includes repository file IDs, task IDs, dbt/model
names, normalized relations, exact DataHub Dataset URNs, DataHub field keys,
and CHRONOS counterfactual field keys. SQL model mappings are explicit
proposal evidence. Phase 6.2 resolves relations, columns, and outputs against
the supplied snapshot. Config/DAG field claims correlate only after an exact
model/field transition exists. No URN is fabricated.

Resolution states remain observed/resolved, counterfactual, ambiguous, not
found, or insufficient. Ambiguity fails closed; code-only unknowns remain
unresolved.

## Correlation, logical groups, and precedence

Correlation uses exact evidence: model mapping, current field, proposed field,
schema model/column claims, and statically parsed references. Similar strings,
file proximity, and parser order are not correlation evidence.

`LogicalChangeGroup` retains contributing files, structural/semantic/pipeline/
contract delta IDs, current and counterfactual entities, evidence, coherence,
warnings, and root candidates. Several groups and several roots may coexist.

SQL and contract claims have equal evidentiary standing. When they disagree,
both alternatives are preserved and a conflict is emitted. Neither overwrites
the other because it was parsed later.

## Coherence and incomplete migrations

Repository coherence is one independent dimension:

- `COHERENT`: supported files agree on the proposed identity;
- `PARTIALLY_COHERENT`: supported static claims agree but dynamic evidence is
  unresolved;
- `INCONSISTENT`: explicit future claims conflict or a supported static file
  retains the correlated current identity;
- `UNRESOLVED`: there is not enough cross-file identity evidence.

Stale DAG/quality references are precise repository findings, not automatic
claims that the entire runtime is broken. Explicit competing future names are
conflicts. Coherence never proves execution correctness.

## Composite change and future states

`CompositeChangeSet` joins inventory, results, groups, typed deltas, observed
and counterfactual identities, unresolved references, conflicts, warnings,
and evidence summaries. Documentation-only and unsupported changes do not
manufacture impact. A transition with zero supported material deltas yields
`no_material_change`.

Counterfactual repository state records active head paths, removals/renames,
head fingerprints, parsed head representations, and unresolved constructs,
without mutating the current repository. Counterfactual metadata state records
current entities, proposed entities, removed entities, adapted/stale
references, and conflicting alternatives. A conflict produces `CONFLICTED`
state rather than one invented future.

## Composite Future Graph

The graph retains distinct edge kinds:

- `OBSERVED_DATAHUB_EDGE`: supplied snapshot lineage, with current edge ID;
- `CODE_DERIVED_PROPOSED_EDGE`: a supported static head reference whose
  endpoint is an explicit counterfactual identity;
- `COUNTERFACTUAL_EDGE`: current-to-proposed identity mapping;
- `REMOVED_EDGE`: an evidenced output removal, retaining the current origin;
- `UNRESOLVED_REFERENCE`: a supported stale repository reference.

Only observed snapshot edges drive downstream DataHub traversal. Proposed
edges require a supported parser, explicit endpoint identities, and retained
file evidence. The observed graph is never erased.

## Multiple roots, propagation, and traceability

Every material delta, stale reference, and explicit conflict retains a root
cause with files, deltas, entities, evidence state, compatibility state, and
scope. Roots are not collapsed into “the PR changed.”

Traversal starts from every resolved current model field root. Downstream
nodes and paths are deduplicated; findings aggregate all roots and files that
reach the same target. Metrics include roots, fields, datasets, paths,
relationships, multipath targets, and depth. Each finding links target, root,
files, and paths, keeping observed/code-derived/counterfactual provenance.

## Compatibility, impact, context, and decision

Structural rename/delete evaluations call Phase 6.1 compatibility rules.
Semantic aggregation/filter/join/expression evaluations call Phase 6.2 rules.
Repository coherence and execution validity (`UNVERIFIED`) remain separate.

Technical consequences derive from roots, not file count. Certified DataHub
relationships connected to graph datasets are reused as context only; they
are not called broken, critical, or sensitive. Severity uses explicit
conflict/materiality, observed breadth, certainty, and connected context—not
number of changed files.

Decision precedence is explicit:

1. confirmed conflicting future claims -> `block_confirmed_incompatibility`;
2. material unresolved structural/semantic/coherence evidence ->
   `hold_for_review`;
3. zero supported material data deltas -> `no_material_change`.

Per-root findings remain visible. Questions and evidence requirements are
derived by root type and are labeled evidence, not repairs. Runtime failure
count remains zero without execution proof.

## Packaging and certification

Every run atomically exports exactly 26 JSON artifacts, from strict proposal
through file inventory/results, four change sets, resolution, groups,
coherence, composite/counterfactual states, graph/propagation, compatibility,
impact/context/severity/decision, explanations, certification, and manifest.

Certification is count-independent. It verifies shared identity, snapshot and
base/head identity, unique file/delta/group/root IDs, fingerprints, parser
coverage/version, delta references, correlation/coherence/conflict closure,
graph endpoints and paths, root/file/target traceability, rule/decision IDs,
evidence classification, manifest fingerprints, portability, and absence of
credentials/absolute paths.

The semantic fingerprint excludes output directory, creation time, clone
location, and non-semantic line-ending/presentation differences. Output must
remain inside CHRONOS, cannot target the root/golden artifact directory, and
can overwrite only a recognized prior 26-file package.

## Frontend and future boundary

The Phase 5 presentation and frontend remain on certified
`CHRONOS-DEMO-001`. A later selector may enumerate validated Phase 6.3
manifests and load one by analysis ID. It must not parse repositories or
recompute graph, compatibility, impact, or decision logic in the browser. No
fake PR upload interface is part of Phase 6.3.
