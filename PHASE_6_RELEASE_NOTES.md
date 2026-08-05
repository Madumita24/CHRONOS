# CHRONOS Phase 6 Release Notes

## Release boundary

Phase 6 turns the certified CHRONOS metadata foundation into four reusable,
deterministic static analysis capabilities and one independent release gate.
It preserves the Phase 1-5 golden scenario and read-only frontend.

The release does not execute analyzed code, apply repair patches, write to
DataHub, infer business approval, or certify runtime correctness.

## Phase 6.1 - generalized schema-change analysis

Phase 6.1 analyzes `FIELD_RENAME`, `FIELD_DELETE`, and `FIELD_TYPE_CHANGE`
against a frozen DataHub-derived snapshot. One engine resolves the exact source
field, creates operation-specific counterfactual state, evaluates conservative
compatibility, propagates impact, and exports 14 certified artifacts.

Public API: `analyze_structural_change`.

CLI: `chronos analyze-structural-change`.

Examples: `examples/field_rename`, `examples/field_delete`, and
`examples/field_type_change`.

## Phase 6.2 - SQL/dbt semantic-change analysis

Phase 6.2 uses SQLGlot 30.13.0 to detect aggregation, filter, join, derived-
expression, and structural-output changes within one logical model. Bounded
static dbt references are supported without executing Jinja. Structural and
semantic changes remain separate. Output contains 18 certified artifacts.

Public API: `analyze_semantic_code_change`.

CLI: `chronos analyze-semantic-change`.

Examples cover aggregation, aggregation plus filter, filter, join, and derived
expression.

## Phase 6.3 - multi-file PR reasoning

Phase 6.3 accepts a bounded local Git range or exported bundle. It classifies
and parses supported SQL/dbt/YAML/JSON/Python-AST file forms, correlates exact
cross-file claims, distinguishes coherent/incomplete/conflicting/non-material
changes, constructs composite future state and graph evidence, propagates
multiple roots, and exports 26 certified artifacts.

Public APIs: `analyze_pull_request` and `analyze_pull_request_bundle`.

CLI: `chronos analyze-pr`.

Examples: primary incomplete migration, coherent migration, no-material PR,
and competing future identities.

## Phase 6.4 - candidate repair generation

Phase 6.4 revalidates a complete certified Phase 6.3 package and matching
bundle, classifies repairability, creates a typed Repair Plan, invokes explicit
parser-aware editors, produces isolated candidate previews and portable diffs,
protects untargeted semantics, and reruns unchanged Phase 6.3 statically.

Public API: `generate_repair`.

CLI: `chronos generate-repair`.

Output contains 27 semantic artifacts plus `repairs/`. Six examples cover a
partial primary repair, correct no-repair outcomes, conflict preservation,
strict deletion, and declaration-only type alignment.

No candidate is applied. Semantic changes such as `SUM` to `AVG` remain manual
without separately certified intent.

## Phase 6.5 - independent certification

Phase 6.5 replays all 18 final fixtures twice, validates the complete trust
chain, verifies package closure and fingerprints, audits vocabulary and
dimension separation, checks the frozen Phase 4 and Phase 5 boundary, scans
portability and security controls, exercises tamper handling, records actual
test evidence, and exports a 32-artifact release certification package.

Certification command:

```powershell
python -m chronos.phase6_certification --repository . `
  --test-summary <summary.json> `
  --output artifacts/certifications/phase-6
```

The current state is `PHASE_6_CERTIFIED_WITH_NON_BLOCKING_LIMITATIONS` because
seven live DataHub-dependent tests are skipped in the offline environment.

## Security boundaries

Phase 6 enforces strict proposals, safe contained paths, revision validation,
bounded Git/bundle intake, symlink/non-regular/binary/UTF-8 controls, file and
artifact resource limits, safe YAML and duplicate-key rejection, SQL/Python
AST boundaries, Jinja rejection, exact editor targeting, isolated patch
application checks, recognized overwrite, atomic staging, credential scans,
and bounded CLI errors.

No engine executes repository code or writes to DataHub.

## Known limitations

- Only documented static file and framework forms are supported.
- Dynamic Python, arbitrary Jinja/macros, generated tasks, and dynamic SQL are
  unresolved or unsupported.
- Repository coherence does not prove semantic or runtime compatibility.
- Automatic semantic-intent repair is unsupported.
- Competing identities are preserved, never selected automatically.
- Repair candidates require human review and Phase 7 execution evidence.
- The offline certification does not revalidate live DataHub service drift.

## Migration notes

Existing Phase 1-5 artifacts and presentation APIs are unchanged. Existing
Phase 6.1-6.4 API and CLI contracts remain unchanged. Consumers may adopt the
new release manifest and certification package without changing analysis
inputs.

Frontend integration must read certified manifests and presentation records;
it must not duplicate parsing, graph traversal, compatibility, decision, or
repair logic.

## Next steps

The next authorized integration phase may expose certified Phase 6 packages in
the frontend. Phase 7 may independently execute a selected, reviewed repair in
an authorized disposable environment. Neither step is part of this release.
