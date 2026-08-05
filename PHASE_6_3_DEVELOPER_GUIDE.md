# CHRONOS Phase 6.3 Developer Guide

## Install and boundary

Install the repository package in the existing environment:

```powershell
.\.venv-datahub-310\Scripts\python.exe -m pip install -e .
```

Phase 6.3 pins SQLGlot 30.13.0 and PyYAML 6.0.3. It reads Git objects or
offline bundle evidence. It never checks out or executes analyzed repository
content, SQL, dbt, Jinja, or DAG Python.

## Proposal format

```json
{
  "proposal_id": "PR-PROPOSAL-001",
  "analysis_id": "PR-ANALYSIS-001",
  "operation": "MULTI_FILE_PR_CHANGE",
  "source_snapshot_fingerprint": "sha256:...",
  "source_snapshot_id": "snapshot-...",
  "repository_identity": {
    "repository_name": "repository",
    "repository_namespace": "owner"
  },
  "base_revision": "base-ref-or-fixture-id",
  "head_revision": "head-ref-or-fixture-id",
  "intake_mode": "EXPORTED_PR_BUNDLE",
  "file_model_mappings": [
    {
      "path": "models/order_details.sql",
      "model_dataset_urn": "urn:li:dataset:(urn:li:dataPlatform:dbt,...,PROD)",
      "model_relation": "database.schema.order_details",
      "sql_dialect": "postgres"
    }
  ]
}
```

Optional fields are PR number, scenario ID, title, description, `created_at`,
string metadata, and `dbt_manifest_path` on a file mapping. Unknown properties,
arbitrary commands, duplicate mappings, mismatched snapshot/base/head, and
equal base/head identities fail closed.

## Python API

Bundle mode:

```python
from chronos import analyze_pull_request

result = analyze_pull_request(
    snapshot="artifacts/current_metadata_snapshot.json",
    proposal="examples/multifile_pr_primary/proposal.json",
    bundle="examples/multifile_pr_primary",
    output_dir="artifacts/analyses/multifile-pr-primary",
)
```

The convenience alias is:

```python
from chronos import analyze_pull_request_bundle

result = analyze_pull_request_bundle(
    snapshot="artifacts/current_metadata_snapshot.json",
    proposal="examples/multifile_pr_primary/proposal.json",
    bundle="examples/multifile_pr_primary",
    output_dir="artifacts/analyses/multifile-pr-primary",
)
```

Local Git mode:

```python
result = analyze_pull_request(
    snapshot="artifacts/current_metadata_snapshot.json",
    proposal="path/to/local-proposal.json",
    repository="path/to/exact/git/root",
    base_revision="base-ref",
    head_revision="head-ref",
    output_dir="artifacts/analyses/local-pr",
)
```

The immutable result exposes identity, public repository identity,
certification, decision, coherence, fingerprint, changed-file summary, logical
groups, roots, conflicts, key findings, Future Graph summary, manifest,
artifact paths, and all loaded artifacts.

## CLI

Offline bundle:

```powershell
.\.venv-datahub-310\Scripts\python.exe -m chronos analyze-pr `
  --snapshot artifacts/current_metadata_snapshot.json `
  --proposal examples/multifile_pr_primary/proposal.json `
  --bundle examples/multifile_pr_primary `
  --output artifacts/analyses/multifile-pr-primary
```

Local Git range:

```powershell
.\.venv-datahub-310\Scripts\python.exe -m chronos analyze-pr `
  --snapshot artifacts/current_metadata_snapshot.json `
  --proposal path/to/local-proposal.json `
  --repo path/to/exact/git/root `
  --base base-ref `
  --head head-ref `
  --output artifacts/analyses/local-pr
```

`--repo` and `--bundle` are mutually exclusive. Base/head overrides, when
supplied, must equal the proposal. Normal failure prints bounded JSON to
stderr and returns status 2 without ordinary stack traces or file content.
`--overwrite` can replace only a recognized prior PR package.

## Bundle format

```text
bundle-root/
  bundle.json
  base/<logical repository paths>
  head/<logical repository paths>
```

`bundle.json` contains schema version `1.0`, public repository identity,
base/head fixture IDs, and an array of exact records:

```json
{
  "status": "MODIFIED",
  "base_path": "models/order_details.sql",
  "head_path": "models/order_details.sql",
  "base_fingerprint": "sha256:...",
  "head_fingerprint": "sha256:..."
}
```

Use `null` path/fingerprint for the absent side of `ADDED` or `DELETED`.
Renames/copies have both logical paths. Fingerprints hash UTF-8 bytes after
line-ending normalization. Paths are relative POSIX paths. Symlinks, missing
content, traversal, hidden credentials, binary supported files, and files over
1 MiB are rejected or isolated according to the inventory policy.

## Supported files

- SQL and compiled dbt SQL;
- raw dbt SQL limited to static `ref()` and `source()` plus a mapped manifest;
- dbt `schema.yml`/`schema.yaml` with static models/columns/contracts/tests;
- explicit bounded `contract` YAML/JSON;
- pipeline and quality YAML/JSON with allowlisted static references;
- DAG Python parsed statically with `ast`;
- documentation-only and unsupported files retained without technical impact.

Arbitrary YAML/JSON does not become a contract or config. SQL model mappings
must provide exact DataHub model identity and dialect for certified resolution.

## Supported DAG patterns

```python
extract = Operator(
    task_id="extract",
    input_dataset="orders",
    output_field="order_amount",
)
publish = Operator(task_id="publish")
extract >> publish
extract.set_downstream(publish)
publish.set_upstream(extract)
```

Only literal strings and simple task names are interpreted. Loops,
comprehensions, f-strings, environment-variable values, function-returned
references/tasks, computed task IDs, and complex dependency expressions are
retained as unresolved. Imports are never followed.

## Examples

- `examples/multifile_pr_primary`: SQL/schema propose `order_amount`; DAG and
  quality retain `order_total`; expected `INCONSISTENT` and hold;
- `examples/multifile_pr_coherent`: all supported files use `order_amount`;
  expected `COHERENT`, but still hold because execution/semantic evidence is
  absent;
- `examples/multifile_pr_no_material`: formatting, comments, descriptions,
  YAML ordering, and documentation only; expected `no_material_change`;
- `examples/multifile_pr_conflict`: SQL and schema propose different future
  fields; expected explicit conflict and block.

All code/config files are authored, never-executed fixtures mapped to real
certified DataHub identities where applicable. They are not retrieved from a
live production repository.

## Interpreting states

Repository coherence answers whether supported static files agree.
Structural compatibility answers whether identity/type removal changes have
certified consumer adaptation. Semantic compatibility answers whether metric,
row-set, join, or expression meaning is approved/validated. Execution validity
answers whether the proposed repository has run successfully. These dimensions
must be read separately.

`INCONSISTENT` can be a precise stale reference without a confirmed runtime
failure. `COHERENT` does not mean approved. `PARTIALLY_COHERENT` preserves a
dynamic unknown. `UNRESOLVED` means correlation evidence is insufficient.

## Reading the 26-file package

Start with `manifest.json` for identity, counts, decision, graph summary, and
fingerprints. Then inspect:

- `changed_file_inventory.json` and `file_analysis_results.json` for coverage;
- the four `*_change_set.json` files for typed deltas;
- `entity_resolution.json` for observed/counterfactual/unresolved identities;
- `logical_change_groups.json` and `coherence_evaluation.json` for correlation,
  stale references, and conflicts;
- `composite_change_set.json` and the two counterfactual-state artifacts for
  the proposed repository/data estate;
- graph and propagation for root/file/path/target traceability;
- compatibility, impact, context, severity, and synthesis for the decision;
- explanation, certification, and manifest for audit closure.

No artifact contains raw analyzed file content or machine-specific repository
paths.

## Validation

```powershell
.\.venv-datahub-310\Scripts\python.exe -m unittest tests.unit.test_pr_engine -v
.\.venv-datahub-310\Scripts\python.exe -m unittest discover -s tests\unit
.\.venv-datahub-310\Scripts\python.exe -m unittest discover -s tests\certification
.\.venv-datahub-310\Scripts\python.exe -m unittest discover -s tests\api
.\.venv-datahub-310\Scripts\python.exe -m unittest discover -s tests\integration

cd frontend
npm run typecheck
npm run lint
npm test
npm run build
```

## Troubleshooting

- **Invalid Git revision:** provide one bounded revision resolving to a commit;
  do not pass a range or option.
- **Bundle fingerprint mismatch:** regenerate the exported manifest from the
  exact normalized base/head content; do not bypass validation.
- **Unsupported YAML/config:** use the documented dbt, contract, pipeline, or
  quality schema; unsupported files remain inventoried.
- **Dynamic DAG reference:** provide static evidence or treat the result as
  partial; CHRONOS will not execute it.
- **Ambiguous DataHub entity:** provide exact model mapping and resolve snapshot
  ambiguity; CHRONOS will not fabricate an identity.
- **Existing output:** choose a new directory or explicitly overwrite only a
  prior certified PR package.
- **Held coherent migration:** coherence is not execution or semantic approval;
  inspect root-specific required evidence.
