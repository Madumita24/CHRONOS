# CHRONOS Phase 6.5 Developer Guide

## Environment setup

Use the existing Python 3.10 environment:

```powershell
.\.venv-datahub-310\Scripts\python.exe -m pip install -e .
```

In an offline environment where the declared build backend is already
installed, prevent build-isolation from attempting a package-index download:

```powershell
.\.venv-datahub-310\Scripts\python.exe -m pip install `
  --no-build-isolation -e .
```

Phase 6.5 adds no dependency. Verify the exact parser versions:

```powershell
.\.venv-datahub-310\Scripts\python.exe -c "import sqlglot,yaml; print(sqlglot.__version__, yaml.__version__)"
```

Expected output is SQLGlot `30.13.0` and PyYAML `6.0.3`. `pyproject.toml`
requires Python 3.10 or newer and declares the `chronos` console script.

## Certification command

The independent command is intentionally separate from the product CLI:

```powershell
.\.venv-datahub-310\Scripts\python.exe -m chronos.phase6_certification `
  --repository . `
  --test-summary .chronos-output\phase6-test-summary.json `
  --output artifacts\certifications\phase-6 `
  --overwrite
```

The test summary must contain the exact `unit`, `certification`, `api`, and
`integration` collections, each with non-negative `executed`, `passed`,
`skipped`, and `failed` integers. For each collection and in aggregate,
executed must equal passed plus skipped plus failed. A nonzero failure count
cannot certify.

Do not place the temporary test-summary input in the 32-artifact output
directory. Remove temporary replay/test outputs after the final audit.

## Focused checks

```powershell
.\.venv-datahub-310\Scripts\python.exe -m unittest `
  tests/certification/test_phase_6_certification.py
```

Focused predecessor checks remain:

```powershell
.\.venv-datahub-310\Scripts\python.exe -m unittest tests/unit/test_structural_engine.py
.\.venv-datahub-310\Scripts\python.exe -m unittest tests/unit/test_semantic_engine.py
.\.venv-datahub-310\Scripts\python.exe -m unittest tests/unit/test_pr_engine.py
.\.venv-datahub-310\Scripts\python.exe -m unittest tests/unit/test_repair_engine.py
```

## Complete backend regression

Run every collection separately so counts and skips remain attributable:

```powershell
.\.venv-datahub-310\Scripts\python.exe -m unittest discover -s tests\unit
.\.venv-datahub-310\Scripts\python.exe -m unittest discover -s tests\certification
.\.venv-datahub-310\Scripts\python.exe -m unittest discover -s tests\api
.\.venv-datahub-310\Scripts\python.exe -m unittest discover -s tests\integration
```

Do not report the discovered total as though skipped tests passed. Use:

```text
Across the four backend test collections, X tests were executed:
Y passed, Z were intentionally skipped, and 0 failed.
```

Then list executed/passed/skipped/failed for each collection.

## Frontend regression

Phase 6.5 adds no frontend feature. Verify the existing boundary:

```powershell
cd frontend
npm run typecheck
npm run lint
npm test
npm run build
```

Next.js may rewrite `frontend/next-env.d.ts` during a build. Preserve and
classify the pre-existing development-path modification; do not call it a
Phase 6.5 deliverable.

## Output package

The output is `artifacts/certifications/phase-6/` and contains exactly 32 JSON
artifacts. Start with:

1. `manifest.json` for closure and fingerprints;
2. `phase_6_certification.json` for the top-level decision;
3. `phase_6_release_manifest.json` for the release contract;
4. the four replay certification artifacts;
5. `end_to_end_primary_journey.json` for the primary trust journey;
6. security, tamper, failure, test, skip, and working-tree records.

The package contains no raw replay source, runtime result, secret, absolute
path, or applied patch.

## Interpreting state

`PHASE_6_CERTIFIED` means every in-scope gate passed with no release limitation.

`PHASE_6_CERTIFIED_WITH_NON_BLOCKING_LIMITATIONS` means every in-scope gate
passed but an explicitly recorded limitation remains. In the current offline
environment, live DataHub reconstruction/integration tests are skipped; static
and frozen evidence remains certified, while live service drift is not.

`PHASE_6_NOT_CERTIFIED` means at least one blocking gate failed. Do not average
failures into a score or bypass the failing artifact.

None of these states certifies runtime correctness or merge safety.

## Skipped-test handling

Set `CHRONOS_RUN_INTEGRATION=1` only when the official matching showcase
DataHub environment and CLI profile are available. The seven conditional tests
cover live reconstruction, readiness, entity resolution, schema, field
lineage, asset context, and snapshot round-trip.

If they remain skipped, preserve the explicit non-blocking limitation and do
not say that live DataHub was revalidated. If they run and fail, Phase 6 is not
certified until the mismatch is explained and corrected.

## Deterministic rerun

The certifier creates a repository-contained temporary workspace, runs 18
fixtures twice, compares semantic fingerprints and repair patch fingerprints,
scans all replay outputs, verifies frozen/fixture hashes, and deletes the
workspace. The final package is atomically staged.

`--overwrite` is accepted only when the destination already contains the exact
recognized 32-file certification package. It will not replace arbitrary data.

## Troubleshooting

### Package state is not certified

Open `phase_6_certification.json`, then inspect any artifact with `state: FAIL`.
Do not edit the manifest or certification output by hand; rerun the gate from
trusted inputs.

### Working-tree audit fails

Classify every path. Phase 6.5 deliverables and the known unrelated
`frontend/next-env.d.ts` change are allowed. Generated test output must be
removed. Any other change requires explanation or restoration before release.

### Manifest fingerprint mismatch

The package is tampered or partially regenerated. Remove the complete
certification directory or use recognized overwrite and rerun all replays.

### Parser version mismatch

Restore the pinned environment. Do not weaken the expected SQLGlot or PyYAML
versions to make a package pass.

### Live integration skips

This is expected without `CHRONOS_RUN_INTEGRATION=1`. Keep the limitation and
do not claim live verification.

## Phase 7 handoff

Phase 7 receives the certified Phase 6.4 package, its predecessor PR package,
repository/bundle identity, candidate and patch fingerprints, protected
semantics, remaining findings, required validations, environment policy, and
explicit execution authorization.

Phase 7 must independently apply the patch in a disposable checkout and run
authorized installation, compilation, schema/contract, DAG, test, data, and
consumer checks. Phase 6.5 performs none of those steps.
