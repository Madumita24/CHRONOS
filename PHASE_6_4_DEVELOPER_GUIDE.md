# CHRONOS Phase 6.4 Developer Guide

## Install and safety boundary

Use the existing Python 3.10 environment and repository dependencies. Phase
6.4 adds no dependency and retains:

```text
sqlglot==30.13.0
PyYAML==6.0.3
```

Phase 6.4 creates review artifacts only. It does not apply them, execute the
analyzed project, write to DataHub, or certify runtime correctness.

Use a new output directory outside frozen and source trees, for example:

```text
.chronos-output/repairs/primary
```

The implementation rejects output under `artifacts/`, `src/`, `tests/`,
`examples/`, `frontend/`, and `.git`.

## Predecessor requirements

The primary input is one complete certified Phase 6.3 package plus its exact
exported repository bundle. Generate a predecessor with:

```powershell
chronos analyze-pr `
  --snapshot artifacts/current_metadata_snapshot.json `
  --proposal examples/multifile_pr_primary/proposal.json `
  --bundle examples/multifile_pr_primary `
  --output .chronos-output/analyses/multifile-pr-primary
```

The repair proposal must contain the semantic fingerprint of the predecessor
`manifest.json`, not its filesystem hash. Example proposals in `examples/`
already contain the deterministic fingerprints for their corresponding
fixtures.

The trust gate requires all 26 artifacts, reproduces certification, rechecks
all semantic fingerprints, and reparses matching HEAD bundle bytes. Copied
summaries and uncertified or tampered packages are invalid.

## Proposal format

```json
{
  "proposal_id": "CHRONOS-REPAIR-PRIMARY-PROPOSAL-001",
  "repair_analysis_id": "CHRONOS-REPAIR-PRIMARY-001",
  "operation": "GENERATE_REPAIR",
  "predecessor_analysis_id": "CHRONOS-PR-PRIMARY-001",
  "predecessor_manifest_fingerprint": "sha256:...",
  "repository_identity": {
    "repository_name": "chronos-multifile-primary",
    "repository_namespace": "Madumita24",
    "repository_fingerprint": "sha256:..."
  },
  "base_revision": "fixture-base-primary-v1",
  "head_revision": "fixture-head-primary-v1",
  "repair_mode": "ALL_SUPPORTED",
  "scenario_id": "CHRONOS-REPAIR-PRIMARY",
  "description": "Generate exact stale-reference candidates only."
}
```

Unknown properties are rejected. The proposal cannot contain commands, code,
prompts, or execution options.

Modes:

- `ALL_SUPPORTED`: classify every predecessor root;
- `SELECTED_ROOTS`: requires `target_root_cause_ids` only;
- `SELECTED_GROUPS`: requires `target_logical_change_group_ids` only.

Optional proposal metadata is a bounded string map. The conditional examples
use `approved_delete_field` and `approved_type_transition`; these values are
validated against certified predecessor evidence and do not authorize runtime
conversion.

## Python API

```python
from chronos import generate_repair

result = generate_repair(
    predecessor_analysis=".chronos-output/analyses/multifile-pr-primary",
    proposal="examples/repair_primary/repair_proposal.json",
    repository_bundle="examples/multifile_pr_primary",
    output_dir=".chronos-output/repairs/multifile-pr-primary",
)
```

Optional parameters:

- `snapshot`: defaults to `artifacts/current_metadata_snapshot.json` and must
  match the predecessor snapshot identity;
- `overwrite`: defaults to false and may replace only a recognized complete
  repair package.

The result exposes:

- repair and predecessor identities;
- certification status;
- disposition and completeness;
- repair actions and affected files;
- projected closed roots and remaining findings;
- projected repair-scope coherence;
- patch and artifact manifests;
- patch, candidate-preview, JSON artifact, and output paths;
- deterministic repair semantic fingerprint.

`certification_status == "certified"` means candidate generation and static
projection were certified. It does not mean the candidate runs correctly.

## CLI

```powershell
chronos generate-repair `
  --analysis .chronos-output/analyses/multifile-pr-primary `
  --proposal examples/repair_primary/repair_proposal.json `
  --bundle examples/multifile_pr_primary `
  --output .chronos-output/repairs/multifile-pr-primary
```

The CLI prints concise JSON containing counts, disposition, projected
coherence, fingerprint, and `runtime_verified: false`. It never prints raw
candidate source or unified diffs.

Normal validation failures return exit code 2 with bounded JSON on stderr and
no stack trace.

## Selected-root mode

Use a proposal already declaring `SELECTED_ROOTS`, or provide an explicit root
to an `ALL_SUPPORTED` proposal:

```powershell
chronos generate-repair `
  --analysis .chronos-output/analyses/multifile-pr-primary `
  --proposal examples/repair_primary/repair_proposal.json `
  --bundle examples/multifile_pr_primary `
  --root pr-root-2297cb428bdd70d7b419 `
  --output .chronos-output/repairs/selected-root
```

Repeated `--root` values are sorted and deduplicated. A CLI root list that
conflicts with a strict selected-root proposal is rejected. Unknown roots fail
closed.

## Supported repair categories

Supported when all rule evidence and exact target conditions are satisfied:

- stale static field references;
- stale static dataset/model references;
- dbt schema column-name alignment;
- bounded contract field alignment;
- quality target alignment;
- static DAG keyword alignment;
- pipeline config alignment;
- exact model-file/static dbt reference alignment;
- strict structured reference removal after an approved no-replacement delete;
- declaration-only type alignment after one approved transition;
- exact SQLGlot column, relation, or output-alias changes under protected AST
  invariants.

## Unsupported or manual categories

No automatic candidate is produced for:

- unapproved aggregation, filter, join, expression, CASE, threshold, retention,
  or metric changes;
- competing or ambiguous future identities;
- dynamic Python values, loops, environment values, or generated tasks;
- arbitrary Jinja or macros;
- unsupported files or unknown structured fields;
- unresolved required DataHub identities;
- uncertain deletion replacements;
- casts, precision, truncation, or type-conversion policy without explicit
  evidence;
- missing business/owner intent or missing runtime evidence.

These are valid manual, unsupported, conflict-blocked, or missing-evidence
results. They are not engine failures.

## Reading the Repair Plan

Open `repair_plan.json` first. The nested `plan` contains:

- selected root IDs;
- every repairability classification;
- typed actions;
- non-repairable and blocked roots;
- affected files;
- action dependencies and application order;
- expected coherence intent and compatibility limitations;
- required human decisions and Phase 7 validations;
- warnings that the candidate is unapplied and runtime unverified.

`FULLY_ADDRESSED_SELECTED_ROOTS` is used only when all selected roots are
repairable and addressed. The primary example is
`PARTIALLY_ADDRESSED_SELECTED_ROOTS` because semantic and contract roots remain
selected and unresolved.

## Reading repair actions

Each action in `repair_actions.json` provides:

- rule, root, group, file, and target-path IDs;
- exact current value and HEAD fingerprint;
- counterfactual value and identity-claim evidence;
- typed operation and structured/AST location;
- dependencies, confidence, preconditions, and checks;
- remaining evidence and human explanation;
- editor version, exact source/structured provenance, formatting disclosures,
  and protected-semantic fingerprints.

Vague instructions such as “fix the pipeline” are never emitted.

## Reading unified diffs

Review:

```text
repairs/patches/combined.patch
repairs/patches/files/<relative-path>.patch
repairs/patches/groups/<logical-group>.patch
```

Headers are portable `a/` and `b/` paths with no timestamps. Each file patch
record binds its action IDs, original and candidate fingerprints, patch
fingerprint, hunk count, and candidate path.

The package proves the diff regenerates deterministically and cleanly applies
to an isolated copy of the certified HEAD content. It does not apply the diff
to the source repository.

## Candidate previews

Candidate files are under:

```text
repairs/repaired_files/<repository-relative-path>
```

They are review copies only. Raw source and raw patch text remain outside the
27 semantic JSON artifacts.

## Projected versus verified

`projected_pr_analysis.json`, projected coherence, graph, and propagation are
produced by rerunning Phase 6.3 on an isolated repaired bundle. They are labeled
`STATIC_PROJECTED`.

The primary report distinguishes:

- repair-scope identity coherence: `COHERENT`;
- raw global Phase 6.3 state: `UNRESOLVED` because unrelated semantic/contract
  questions remain;
- stale references: 2 to 0;
- semantic approval: still missing;
- runtime correctness: not verified.

Never interpret projection as execution success, merge safety, or owner
approval.

## Primary example

Inputs:

- SQL: `AVG(o.order_total) AS order_amount`;
- dbt schema: `order_amount`;
- DAG: `output_field="order_total"`;
- quality: `field: order_total`.

Generated actions:

1. DAG static argument `order_total` to `order_amount`;
2. quality scalar `order_total` to `order_amount`.

The patch does not touch SQL or `AVG`. Result:

- two actions, two files, two hunks;
- stale references 2 to 0;
- projected repair-scope coherence `COHERENT`;
- unresolved semantic root retained;
- `PARTIAL_REPAIR_CANDIDATE`;
- runtime unverified.

Files: `examples/multifile_pr_primary` and `examples/repair_primary`.

## Coherent no-repair example

`examples/multifile_pr_coherent` already aligns static references. The matching
`examples/repair_coherent` proposal produces zero actions, zero hunks, and
`NO_SUPPORTED_AUTOMATIC_REPAIR`. Missing semantic/execution evidence does not
manufacture a patch.

## No-material example

`examples/multifile_pr_no_material` contains only non-material changes. The
repair package is certified with zero actions and hunks. Formatting and
documentation are not rewritten.

## Conflict example

`examples/multifile_pr_conflict` contains `order_amount` and `total_amount`
claims. `examples/repair_conflict` produces
`REPAIR_BLOCKED_BY_CONFLICT`, retains both alternatives, and generates no
patch.

## Delete example

`examples/multifile_pr_delete_repair` explicitly removes `order_total` and has
one list-valued quality reference. `examples/repair_delete` removes only the
exact `order_total` list line. `order_status`, SQL, and all other content remain.
Phase 7 must validate consumers and quality behavior.

## Type-alignment example

`examples/multifile_pr_type_alignment` explicitly changes the dbt declaration
from `integer` to `numeric`, while a bounded contract retains `integer`.
`examples/repair_type_alignment` updates only `contract.type`. It adds no cast
and does not certify conversion or precision behavior.

## Artifact package

The root contains exactly 27 semantic JSON artifacts:

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

Raw repair files under `repairs/` do not count as semantic JSON artifacts.

## Troubleshooting

### Predecessor manifest fingerprint mismatch

Regenerate the Phase 6.3 package and create a repair proposal bound to that
exact deterministic manifest. Do not edit the predecessor or copy its summary.

### Bundle or HEAD fingerprint mismatch

Use the exact BASE/HEAD exported bundle supplied to Phase 6.3. Regenerated,
formatted, or locally edited files are different evidence.

### No supported automatic repair

Inspect `repairability_classification.json`. The result may be correct because
references are already coherent, intent is semantic, the target is dynamic, or
evidence is missing.

### Blocked by conflict

Do not edit the repair proposal to pick a value. Supply a separately validated
authoritative resolution proposal in a later approved workflow.

### Output rejected

Choose a new repository-contained directory outside protected source, fixture,
frontend, test, VCS, and frozen-artifact trees. Use `--overwrite` only for a
recognized complete repair package.

### Candidate reformats SQL or structured content

Review action `formatting_changes`. SQLGlot serialization and structured
deletion fallback are disclosed. Protected semantic/structure fingerprints
must still match; otherwise generation fails.

## Phase 7 handoff

Phase 7 should consume the certified repair package in a disposable checkout,
verify patch application again, execute only explicitly approved project
validation, compare runtime/data semantics, gather owner approval, and produce
a separate execution certification. Phase 6.4 itself performs none of those
actions and does not begin Phase 7.
