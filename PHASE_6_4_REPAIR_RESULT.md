# CHRONOS Phase 6.4 Repair Result

## Final result

Phase 6.4 is implemented and verified as a deterministic, fail-closed repair-
candidate generator. It consumes one complete certified Phase 6.3 analysis,
revalidates the matching repository bundle, classifies selected roots, builds
an immutable Repair Plan, produces isolated review patches and candidate-file
previews, and reruns Phase 6.3 statically against the projected repository.

The implementation does **not** apply a patch, alter the analyzed repository,
execute SQL/dbt/Python/DAG code, write to DataHub, certify runtime correctness,
approve business intent, commit, or push. Every non-empty result requires human
review and Phase 7 execution evidence.

## Repository inspection and repair inventory

Inspection was completed before production implementation and is recorded in
`PHASE_6_4_REPAIR_INVENTORY.md`. The repair engine reuses Phase 6.1 immutable
models and certification conventions, Phase 6.2 SQLGlot and bounded dbt
semantics, and the complete Phase 6.3 repository-wide evidence contract. It
does not modify any Phase 6.1, 6.2, or 6.3 implementation module.

Phase 6.3 is the required predecessor because its 26-artifact package contains
the repository, BASE, HEAD, changed-file, parser, logical-group, conflict,
coherence, root-cause, and manifest identities needed to authorize an exact
file target. Ordinary Phase 6.1 or 6.2 outputs do not contain that complete
file-level contract and fail closed.

## Predecessor trust gate

Before a Repair Plan is created, the engine:

- validates the strict repair proposal and expected manifest fingerprint;
- requires the exact complete Phase 6.3 artifact set;
- reconstructs and reruns Phase 6.3 certification;
- recomputes every artifact semantic fingerprint;
- checks analysis, snapshot, repository, BASE, HEAD, root, group, conflict, and
  coherence identities;
- reparses the matching exported bundle and compares every HEAD fingerprint;
- rejects traversal, symlinks, absolute paths, binary/oversized input,
  duplicate-key JSON/YAML, secrets, and unsupported targets.

Copied summaries, prose, an uncertified analysis, a tampered package, or a
different checkout cannot authorize candidate generation.

## Proposal, classification, and Repair Plan

`RepairGenerationProposal` is immutable, rejects unknown properties, and
supports `ALL_SUPPORTED`, `SELECTED_ROOTS`, and `SELECTED_GROUPS`. Selected
modes require their exact bounded ID lists; commands, scripts, prompts, and
execution options are not accepted.

Every selected root receives exactly one repairability classification:
`AUTO_REPAIRABLE`, `CONDITIONALLY_REPAIRABLE`, `MANUAL_DECISION_REQUIRED`,
`UNSUPPORTED`, `BLOCKED_BY_CONFLICT`, or `BLOCKED_BY_MISSING_EVIDENCE`.

The Repair Plan is built before any editor runs. It contains root and logical-
group bindings, typed actions, non-repairable and blocked roots, exact HEAD
fingerprints and current values, intended counterfactual values, affected
files, dependencies, deterministic application order, expected coherence,
static checks, unresolved decisions, warnings, and Phase 7 requirements.

## Repair rules and editor registry

The explicit repair-rule registry covers exact static field/dataset/model
reference alignment, bounded dbt schema/contract/configuration alignment,
strict structured deletion, declaration-only type alignment, and protected
SQL identifier changes. A root is not repair authorization unless every rule
precondition and exact target check is satisfied.

The explicit editor registry contains:

- `sqlglot_ast_editor`;
- `dbt_schema_editor`;
- `structured_contract_editor`;
- `structured_config_editor`;
- `python_dag_static_editor`;
- `static_reference_editor`.

The SQL editor changes one parser-confirmed SQLGlot node and proves protected
aggregation, filter, join, expression, and statement structure unchanged.
Bounded dbt editing accepts only one exact static `ref()` or `source()` span;
arbitrary Jinja is rejected and never executed.

YAML uses duplicate-key-rejecting safe parsing and parser node source spans;
JSON uses duplicate-key rejection and exact structured paths. Untargeted
structure is compared before and after. Python DAG edits use `ast.parse` and
replace one exact static string keyword span while protecting task identity,
operator type, and dependency edges. Dynamic values, environment expressions,
loops, generated tasks, and runtime framework behavior are unsupported.

## Workspace, patches, and previews

All edits occur in memory and in a repository-contained temporary workspace.
The analyzed fixture, predecessor package, source tree, tests, frontend, and
frozen artifacts are not changed. Export is rejected under `artifacts/`,
`src/`, `tests/`, `examples/`, `frontend/`, or `.git`.

The output includes deterministic portable unified diffs with `a/` and `b/`
relative headers, per-file and per-logical-group patches, one combined patch,
candidate-file previews, action/plan records, and exact fingerprints. Patches
have no timestamps or absolute paths. Static validation regenerates each diff,
checks exact HEAD applicability and expected hunks, reparses the candidate,
and compares editor-specific protected semantic regions.

## Projected analysis and disposition

Candidate files are inserted only into an isolated exported bundle. The
unchanged Phase 6.3 pipeline is rerun and packaged as `STATIC_PROJECTED`
evidence. The result separately reports repair-scope coherence and raw global
Phase 6.3 state. Repair-action-derived deltas are traceable to exact actions;
an unexplained new root or any new conflict fails certification.

Repair dispositions are `REPAIR_CANDIDATE_READY_FOR_REVIEW`,
`PARTIAL_REPAIR_CANDIDATE`, `NO_SUPPORTED_AUTOMATIC_REPAIR`,
`REPAIR_BLOCKED_BY_CONFLICT`, and `REPAIR_GENERATION_FAILED`. Completeness is
reported independently. `runtime_correctness_certified` is always false.

## Python API and CLI

The public Python API is `chronos.generate_repair(...)`. It accepts a certified
predecessor directory, strict repair proposal, matching repository bundle,
isolated output directory, optional matching snapshot, and guarded overwrite.
It returns identities, certification, disposition, completeness, action/file
counts, projected results, artifact/patch paths, and the deterministic repair
semantic fingerprint.

The CLI is `chronos generate-repair --analysis ... --proposal ... --bundle ...
--output ...`. Repeated `--root` selects bounded roots, is sorted and
deduplicated, and must agree with strict proposal selection. Normal validation
errors return bounded JSON and exit code 2. The CLI never prints raw candidate
source or raw patch content.

## Scenario results

All six scenarios were generated twice. Each pair produced equal semantic
fingerprints and patch fingerprints.

| Scenario | Disposition | Completeness | Actions/files/hunks | Projected repair scope | Remaining findings | Semantic fingerprint |
| --- | --- | --- | ---: | --- | ---: | --- |
| Primary | `PARTIAL_REPAIR_CANDIDATE` | `PARTIALLY_ADDRESSED_SELECTED_ROOTS` | 2/2/2 | `COHERENT` | 5 | `sha256:149ce6d2797a3a505f5fa4f0154aff56318262b13af6b1ec1e31dd26d1034ec1` |
| Already coherent | `NO_SUPPORTED_AUTOMATIC_REPAIR` | `NO_SUPPORTED_REPAIR` | 0/0/0 | `COHERENT` | 9 | `sha256:9e27a719ee9e068f7af50582d9c433d812bfe02e2f0ac9de9ad7f7cb4500e131` |
| No material change | `NO_SUPPORTED_AUTOMATIC_REPAIR` | `NO_SUPPORTED_REPAIR` | 0/0/0 | `COHERENT` | 0 | `sha256:81969c9e8e110dd013564eecde9a1d396f7d77d26a4fa3a4bb2026c4bda18d91` |
| Conflict | `REPAIR_BLOCKED_BY_CONFLICT` | `NO_SUPPORTED_REPAIR` | 0/0/0 | `INCONSISTENT` | 5 | `sha256:51e1d34695789aebfff4a12ecbcdbcbed1699e0b94554a124a93657f3b9e924d` |
| Explicit deletion | `REPAIR_CANDIDATE_READY_FOR_REVIEW` | `FULLY_ADDRESSED_REPAIRABLE_SELECTED_ROOTS` | 1/1/1 | `UNRESOLVED` | 1 | `sha256:c2348236ccddd00259ec785e4e5222bbda463e0aff2f2c142a9157f56a1f109c` |
| Type alignment | `REPAIR_CANDIDATE_READY_FOR_REVIEW` | `FULLY_ADDRESSED_REPAIRABLE_SELECTED_ROOTS` | 1/1/1 | `UNRESOLVED` | 1 | `sha256:6d886251db59f521ba878011c07153127408254de509a5235c54c06abed9c934` |

In the primary case only the DAG `output_field` and quality `field` move from
`order_total` to `order_amount`. SQL `AVG(...)` is untouched and remains a
manual semantic question. The deletion case removes only the exact stale list
entry and preserves `order_status`. The type case changes only the bounded
contract declaration from `integer` to `numeric`; it adds no cast and makes no
runtime conversion claim.

Negative tests cover tampered predecessor artifacts, mismatched bundles and
revisions, unknown roots/groups, competing identities, dynamic Python/Jinja,
unsafe paths, symlinks, unsupported targets, secret-shaped content, malformed
and duplicate-key structured files, patch drift, protected-semantic changes,
unexplained projected roots/conflicts, artifact tampering, and overwrite
misuse. Correct no-repair outcomes are certified without manufacturing diffs.

## Artifact package

Every result contains exactly 27 semantic JSON artifacts plus `repairs/`:

1. `repair_generation_proposal.json`
2. `proposal_validation.json`
3. `predecessor_trust_validation.json`
4. `selected_root_causes.json`
5. `repairability_classification.json`
6. `repair_rule_evaluation.json`
7. `repair_plan.json`
8. `repair_actions.json`
9. `affected_file_inventory.json`
10. `original_file_fingerprints.json`
11. `candidate_file_fingerprints.json`
12. `patch_manifest.json`
13. `combined_patch.json`
14. `file_patch_records.json`
15. `static_patch_validation.json`
16. `protected_semantics_validation.json`
17. `projected_repository_state.json`
18. `projected_pr_analysis.json`
19. `projected_coherence_evaluation.json`
20. `projected_future_metadata_graph.json`
21. `projected_dependency_propagation.json`
22. `repair_comparison.json`
23. `remaining_findings.json`
24. `required_phase_7_validation.json`
25. `explanation_bundle.json`
26. `repair_certification.json`
27. `manifest.json`

Raw patch and candidate-file bytes stay under `repairs/` and are fingerprinted
from the semantic records rather than embedded in JSON.

## Verification and regression evidence

Focused suites passed:

- Phase 6.4 repair engine: 85/85;
- Phase 6.1: 44/44;
- Phase 6.2: 73/73;
- Phase 6.3: 75/75.

Full backend suites passed:

- unit: 1,050/1,050;
- certification: 240 passed, 1 intentional skip;
- API: 95/95;
- integration: 6 intentional environment-dependent skips.

Across the four backend test collections, **1,392 tests were executed: 1,385
passed, 7 were intentionally skipped, and 0 failed.** Frontend typecheck and
lint passed; all 186 tests across 9 files passed; and the Next.js production
build completed.

The 16 frozen root JSON artifacts are byte-diff clean. The Phase 4 physical
hash remains
`5dc730bae390908fa14f5ee5dc5d6a2b6a71382eecf664950bf60f76a74c94e8`
and its semantic fingerprint remains
`sha256:3e8444ec904e0ba1c55c5ae22d69edfa8e722310f51ab30fc783b8175a87ac4a`.
The pre-existing uncommitted `frontend/next-env.d.ts` development-path change
was preserved.

## Security and limits

The engine retains the Phase 6.3 200-file and 1 MiB per-source-file bounds,
limits predecessor artifacts to 5 MiB, and limits actions and patch hunks to
500. It rejects path traversal, drive-prefixed/absolute paths, symlinks,
non-regular Git objects, binary targets, VCS/generated/vendor targets, invalid
UTF-8, credentials/private keys, unrecognized overwrite targets, and output
outside the repository. Atomic staging is removed on failure.

## Limitations, warnings, and Phase 7 boundary

- Static parsing and projection do not prove runtime, data, orchestration,
  warehouse, dbt, or consumer behavior.
- Aggregation, filters, joins, expressions, CASE logic, thresholds, retention,
  metrics, and business intent remain manual without separately certified
  expected semantics.
- Conflicts and ambiguous future identities are retained, never guessed.
- Dynamic Python, arbitrary Jinja, generated tasks, and unsupported framework
  configuration are not automatically repaired.
- SQLGlot or structured serialization formatting is disclosed but remains a
  review concern.
- A ready candidate is not an approval, safe-to-merge claim, or execution
  certificate.

Phase 7 must use a disposable checkout, independently verify patch
application, execute only explicitly approved validations, compare runtime and
data semantics, obtain owner review, and create a separate execution
certificate. Phase 6.4 does not begin that work.

## Documentation

- Inventory: `PHASE_6_4_REPAIR_INVENTORY.md`
- Architecture: `PHASE_6_4_REPAIR_ARCHITECTURE.md`
- Developer guide: `PHASE_6_4_DEVELOPER_GUIDE.md`
- Final result: this document
