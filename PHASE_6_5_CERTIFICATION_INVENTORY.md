# CHRONOS Phase 6.5 Certification Inventory

## Inspection boundary and repository state

This inventory was created before Phase 6.5 certification implementation. The
inspection covered the Phase 6.1-6.4 engines, public exports, CLI, immutable
proposal models, artifact and manifest contracts, certification routines,
parser/editor/rule registries, examples, tests, documentation, package
metadata, frozen artifacts, Phase 5 presentation boundary, and Git state.

Verified starting state:

- branch: `main`;
- source commit: `3c7e1f1520e97a63975a58b23cc7efafe7ec9d4a`;
- local `main` and `origin/main` matched;
- one pre-existing unrelated modification:
  `frontend/next-env.d.ts`, changing the generated Next.js route declaration
  from `.next/types/routes.d.ts` to `.next/dev/types/routes.d.ts`;
- no Phase 6.5 implementation or certification output existed;
- Python observed in the project environment: 3.10.19;
- package requirement: Python 3.10 or newer;
- SQLGlot observed and pinned: 30.13.0;
- PyYAML observed and pinned: 6.0.3.

The unrelated frontend declaration is not a Phase 6.5 deliverable and must be
preserved and classified explicitly in the final working-tree audit.

## Phase 6 public capability inventory

### Phase 6.1 - deterministic structural counterfactual analysis

Supported operations are `FIELD_RENAME`, `FIELD_DELETE`, and
`FIELD_TYPE_CHANGE`. One shared engine resolves one exact DataHub dataset and
field from a frozen snapshot, applies operation-specific counterfactual
invariants, evaluates structural compatibility, propagates impact, and exports
one certified 14-artifact package.

Support is bounded by the supplied snapshot. It does not parse repositories,
SQL, dbt, or runtime behavior and does not prove consumer execution.

### Phase 6.2 - deterministic SQL/dbt semantic analysis

Supported semantic deltas are aggregation, filter, join type, join predicate,
joined relation, derived expression, and structural output changes within one
logical model. SQL is parsed with SQLGlot 30.13.0. dbt support is limited to
bounded static `ref()`/`source()` resolution; Jinja is not executed. Structural
and semantic compatibility remain separate. Output is one certified
18-artifact package.

It does not execute SQL/dbt, infer expected metric definitions, or certify
runtime/data equivalence.

### Phase 6.3 - deterministic multi-file repository analysis

Supported intake is a bounded local Git range or exported PR bundle. The
engine classifies and statically parses SQL/dbt models, dbt schema, bounded
YAML/JSON contract/configuration, static Python DAG forms, and documentation.
It correlates exact file evidence into logical groups, detects coherence and
conflicts, creates composite counterfactual repository/metadata state, builds
one Future Graph, propagates multiple roots, and exports one certified
26-artifact package.

It distinguishes observed DataHub evidence, code-derived evidence, and
counterfactual derivation. Unsupported/dynamic files remain visible. It does
not execute repository code or invent graph edges.

### Phase 6.4 - deterministic repair-candidate generation

The engine consumes one complete certified Phase 6.3 package plus the exact
matching repository bundle. It revalidates predecessor trust, classifies roots,
creates an immutable Repair Plan, uses an explicit rule/editor registry,
generates isolated candidate files and portable unified diffs, validates
protected semantics, and statically reruns unchanged Phase 6.3. Output is 27
semantic JSON artifacts plus `repairs/`.

Supported candidates are exact evidence-backed stale static reference
alignment, strict approved structured deletion, declaration-only approved type
alignment, and bounded protected SQL/static edits. It never applies a patch,
executes code, chooses between conflicts, approves semantic intent, or certifies
runtime correctness.

## Public Python APIs

| API | Owning phase | Input boundary | Result boundary |
| --- | --- | --- | --- |
| `analyze_structural_change` | 6.1 | strict structural proposal, frozen snapshot, contained output | certified `StructuralAnalysisResult`, 14 artifacts |
| `analyze_semantic_code_change` | 6.2 | strict semantic proposal, exact repository-relative BEFORE/AFTER references, frozen snapshot | certified `SemanticAnalysisResult`, 18 artifacts |
| `analyze_pull_request` | 6.3 | strict PR proposal plus exactly one local Git or bundle intake | certified `PullRequestAnalysisResult`, 26 artifacts |
| `analyze_pull_request_bundle` | 6.3 | strict PR proposal and exported bundle | same certified PR result through the shared pipeline |
| `generate_repair` | 6.4 | certified Phase 6.3 package, matching bundle, strict repair proposal | certified static repair result, 27 artifacts plus review files |

## Public CLI commands

- `chronos analyze-structural-change`;
- `chronos analyze-semantic-change`;
- `chronos analyze-pr`;
- `chronos generate-repair`.

All use `argparse`, require explicit inputs and contained outputs, emit concise
sorted JSON on success, and return exit status 2 with bounded JSON on normal
failure. The repair command does not print raw patch or candidate source.
Phase 6.5 must certify these contracts without adding product functionality.

## Proposal families

### StructuralChangeProposal discriminated union

Common required properties are proposal ID, analysis ID, operation, dataset
URN, current field path, and source snapshot fingerprint. `FIELD_RENAME`
requires a proposed field path. `FIELD_DELETE` adds no operation field.
`FIELD_TYPE_CHANGE` requires proposed native and normalized types and permits
bounded precision, scale, and length. Unknown keys and coercion are rejected.

### SemanticCodeChangeProposal

Requires proposal/analysis IDs, `SEMANTIC_CODE_CHANGE`, model Dataset URN, SQL
dialect, exact BEFORE/AFTER repository-relative references, and snapshot
fingerprint. Optional dbt manifest and model mapping fields are bounded.
Unknown keys and absolute/mismatched code paths are rejected.

### PullRequestAnalysisProposal

Requires proposal/analysis IDs, `MULTI_FILE_PR_CHANGE`, snapshot fingerprint,
strict repository identity, distinct BASE/HEAD revisions, and either
`LOCAL_GIT_RANGE` or `EXPORTED_PR_BUNDLE`. File/model mappings require safe
POSIX paths and exact DataHub Dataset URNs. Unknown properties are rejected.

### RepairGenerationProposal

Requires proposal/repair/predecessor IDs, `GENERATE_REPAIR`, predecessor
manifest fingerprint, repository identity, BASE/HEAD, and one of
`ALL_SUPPORTED`, `SELECTED_ROOTS`, or `SELECTED_GROUPS`. Selected modes require
the matching bounded ID list. Unknown keys, duplicate IDs, malformed
fingerprints, commands, prompts, and execution fields are rejected.

## Artifact package and certification inventory

### Phase 6.1 - 14 semantic JSON files

`proposal.json`, `proposal_validation.json`,
`change_semantic_contract.json`, `counterfactual_source_state.json`,
`future_metadata_graph.json`, `dependency_propagation.json`,
`compatibility_evaluation.json`, `technical_impact_analysis.json`,
`business_context_propagation.json`, `severity_criticality_analysis.json`,
`impact_synthesis.json`, `explanation_bundle.json`,
`analysis_certification.json`, and `manifest.json`.

### Phase 6.2 - 18 semantic JSON files

`semantic_change_proposal.json`, `proposal_validation.json`,
`before_parsed_model.json`, `after_parsed_model.json`, `semantic_diff.json`,
`entity_resolution.json`, `code_change_set.json`,
`counterfactual_semantic_state.json`, `future_metadata_graph.json`,
`dependency_propagation.json`, `compatibility_evaluation.json`,
`technical_impact_analysis.json`, `business_context_propagation.json`,
`severity_criticality_analysis.json`, `impact_synthesis.json`,
`explanation_bundle.json`, `analysis_certification.json`, and `manifest.json`.

### Phase 6.3 - 26 semantic JSON files

The package contains proposal validation, repository identity, changed-file
inventory/classification/parsing, four typed change sets, entity resolution,
logical groups, coherence, composite change/counterfactual state, Future Graph,
propagation, compatibility/impact/context/severity/synthesis/explanation,
analysis certification, and manifest. Exact names are defined by
`PR_ARTIFACT_FILENAMES` and checked for set and order closure.

### Phase 6.4 - 27 semantic JSON files plus `repairs/`

The package contains proposal/predecessor trust, selection/classification/rule
evaluation, plan/actions/files/fingerprints, patch records, static/protected
validation, projected Phase 6.3 state, comparison/remaining findings/Phase 7
requirements/explanation, repair certification, and manifest. Raw candidate
and patch bytes are contained under `repairs/` and fingerprinted from JSON.

Each engine uses deterministic JSON serialization, semantic SHA-256
fingerprints, exact manifest closure, atomic staging, recognized-overwrite
checks, and contained relative paths. Phase 6.5 must independently replay and
cross-check rather than accept self-declared certification fields.

## Certification types

- Phase 6.1 structural `analysis_certification`;
- Phase 6.2 semantic `analysis_certification`;
- Phase 6.3 PR `analysis_certification`;
- Phase 6.4 `repair_certification`;
- frozen Phase 2, Phase 3, and Phase 4 top-level certification artifacts;
- Phase 5 presentation loaders that reconstruct and validate the frozen Phase
  4 package before exposing review data.

Phase 6.5 must add a separate release certification type; it must not reuse an
engine's self-certification as the sole release claim.

## Cross-phase trust handoffs

1. Phase 6.1 structural operation/identity/counterfactual concepts are imported
   or semantically reused by Phase 6.3 structural PR analysis.
2. Phase 6.2 SQLGlot parser and semantic delta models are imported by Phase 6.3
   SQL/dbt parsing and change-set construction.
3. Phase 6.3's complete certified package, manifest fingerprint, repository,
   snapshot, BASE/HEAD, file, group, and root identities are revalidated by the
   Phase 6.4 predecessor trust gate.
4. Phase 6.4 candidate previews are inserted into an isolated bundle and
   passed back through the unchanged Phase 6.3 analysis pipeline as
   `STATIC_PROJECTED` evidence.

No handoff is authorized by prose alone. Phase 6.5 must bind producer and
consumer identities, versions, manifests, artifact fingerprints, and snapshot
and repository identities.

## Parser, rule, and editor versions

- structural engine: 6.1.0, artifact schema 1.0;
- semantic engine: 6.2.0, artifact schema 1.0;
- SQL parser: SQLGlot 30.13.0;
- PR engine: 6.3.0, artifact schema 1.0;
- PR SQL parser: `6.3.0/sqlglot-30.13.0`;
- PR YAML/config parser: `6.3.0/pyyaml-6.0.3`;
- PR Python parsing: standard-library AST, static forms only;
- repair engine: 6.4.0, artifact schema 1.0;
- repair SQL editor: `6.4.0/sqlglot-30.13.0`;
- repair structured editor: `6.4.0/pyyaml-6.0.3-json-stdlib`;
- repair DAG editor: `6.4.0/python-ast-source-span`;
- six registered editor names and ten registered repair rules;
- five explicit structural compatibility rules.

## Frozen root artifact hashes

The 16 frozen root JSON files were present and byte-hashed before Phase 6.5:

| Artifact | SHA-256 |
| --- | --- |
| `business_context_propagation.json` | `2a5886861f25eb4dd5bdc97da934c5ce365ab3ec6a498df6e1a3b27ca3204b7d` |
| `change_proposal.json` | `ad3840820c1a6db6d588fafab73f23763862105df6db44efe6d1e22b0ecc6bee` |
| `change_proposal_validation.json` | `9b06df69bbcd4a889f24ecf3f749fcab9ec17cdbbeff50e97038803b387a7db4` |
| `change_semantic_contract.json` | `986139696a57b5a30a6772a0004799ebb213c4085c8da82d0e53c3996f79bee6` |
| `compatibility_evaluation.json` | `547afbb5aebb1142ea04b51808724b856c663bbddfd4c094ec35ab9cbca71964` |
| `counterfactual_source_state.json` | `ba2e86a261f5c9bc66731543a9a3bcbb6ac2c60a10f34d57764f5577868dce80` |
| `current_metadata_snapshot.json` | `0f2df1e0f842d95296078f6e533b197b8a35a34683f31fb1c6cebe0cc3d2362e` |
| `dependency_propagation.json` | `e3691abd236d1142a307029627c8e6144367f813d319ec89e846931c467b54ae` |
| `explanation_bundle.json` | `f9f97b48a667a9ed74657dac1555af09fcc681364fa1c9c8b35491f4ef3e4b1d` |
| `future_metadata_graph.json` | `d298ec6e68fe2b85c79e32a790d9a697c37effaae910b2eca3105a752af9fa40` |
| `impact_synthesis.json` | `27875791ab87745806b7b77e45ad37dfe3322914466d7b546b96ac4826690058` |
| `phase_2_certification.json` | `f08a56932898707a22e727a607d5bf0280a86c19eada3dca8d8f0b1be1ef12f2` |
| `phase_3_certification.json` | `f43b73e896934a3df0492d32f4cfa4d60c4e788b3ca4822046b1027b0d64629e` |
| `phase_4_certification.json` | `5dc730bae390908fa14f5ee5dc5d6a2b6a71382eecf664950bf60f76a74c94e8` |
| `severity_criticality_analysis.json` | `26ea2b4d85bc7e8cd89464f7d825ffe0f0baae707796b799d3efcbea1f952df4` |
| `technical_impact_analysis.json` | `1fb4301567c94b7557036a9521b556b751ec3f1a71483dd2f908d2b0058e64d5` |

The Phase 4 semantic fingerprint is
`sha256:3e8444ec904e0ba1c55c5ae22d69edfa8e722310f51ab30fc783b8175a87ac4a`.

## Known skipped tests at inspection time

Seven tests are conditionally skipped unless `CHRONOS_RUN_INTEGRATION=1`:

1. Phase 1 live reconstruction certification;
2. live DataHub readiness;
3. live canonical entity resolution;
4. live schema retrieval;
5. live field-lineage retrieval;
6. live asset-context retrieval;
7. live current-metadata-snapshot reconstruction.

They require a running, matching showcase DataHub instance and CLI profile.
Offline deterministic fixtures cover serialization, identity, retrieval-state,
snapshot, engine, artifact, tamper, presentation, and certification behavior,
but cannot replace a live service integration assertion. Phase 6.5 must report
the skip risk and must not claim live DataHub revalidation when these remain
skipped.

## Known limits and exclusions

- maximum Phase 6.3 changed files: 200;
- maximum Phase 6.3 source file: 1 MiB;
- maximum Phase 6.4 predecessor artifact: 5 MiB;
- maximum repair actions: 500;
- maximum patch hunks: 500;
- static supported parsers only; dynamic framework behavior is unresolved;
- no SQL, dbt, orchestration, pipeline, or consumer execution;
- no runtime correctness, safe-to-merge, or business-approval claim;
- no automatic semantic-intent repair;
- no automatic conflict resolution;
- no DataHub writes;
- no frontend computation of analysis or repair semantics;
- Phase 7 must independently apply and execute in an authorized disposable
  environment.

## Documentation consistency findings

- The corrected Phase 6.4 result states the backend total accurately as 1,392
  discovered tests: 1,385 passed, 7 intentionally skipped, and 0 failed.
- Phase 6.3 architecture/result documents say Phase 6.4 was not started. Those
  statements are historical non-goal records for the Phase 6.3 delivery, not
  claims about the current repository. Phase 6.5 documentation must make the
  time boundary explicit when citing them.
- `STATIC_PROJECTED` and `PROJECTED_POST_REPAIR` are used consistently for
  static repair projection. No artifact claims a verified repair, execution
  pass, or safe-to-merge status.
- Artifact counts are consistent at 14, 18, 26, and 27 plus `repairs/`.
- The current aggregate baseline will change when Phase 6.5 tests are added;
  final documentation must use the rerun values, not copy this inventory.

No certification blocker or unexplained production change was identified by
the pre-implementation inspection. This is an inventory finding, not the Phase
6.5 certification decision.
