# CHRONOS Phase 6.1 Developer Guide

## Inputs

Supply a snapshot serialized by the existing CHRONOS
`CurrentMetadataSnapshot` loader, one strict JSON proposal, and a new output
directory inside the repository. The engine analyzes only what the supplied
snapshot certifies; this is not a live arbitrary-DataHub query interface.

Install the repository package in its existing environment:

```powershell
.\.venv-datahub-310\Scripts\python.exe -m pip install -e .
```

## Python API

```python
from chronos import analyze_structural_change

result = analyze_structural_change(
    snapshot="artifacts/current_metadata_snapshot.json",
    proposal="examples/field_delete/change.json",
    output_dir="artifacts/analyses/example-delete",
)

print(result.identity.analysis_id)
print(result.certification_status)
print(result.disposition)
print(result.semantic_fingerprint)
print(result.manifest)
print(result.key_summary)
```

The function fails closed on invalid proposal or snapshot identity, ambiguous
target resolution, unsafe output, or failed certification.

## CLI

```powershell
chronos analyze-structural-change `
  --snapshot artifacts/current_metadata_snapshot.json `
  --proposal examples/field_delete/change.json `
  --output artifacts/analyses/example-delete
```

Without an installed console script, use:

```powershell
.\.venv-datahub-310\Scripts\python.exe -m chronos analyze-structural-change `
  --snapshot artifacts/current_metadata_snapshot.json `
  --proposal examples/field_delete/change.json `
  --output artifacts/analyses/example-delete
```

The CLI emits one concise JSON status object. A normal validation failure
returns status 2 without a stack trace. Existing output is rejected; use
`--overwrite` only for a known prior generalized package.

## Proposal shapes

Common fields are `proposal_id`, `analysis_id`, `operation`, `dataset_urn`,
`current_field_path`, `source_snapshot_fingerprint`, optional
`source_snapshot_id`, optional `description`, optional `created_at`, and a
string-to-string `proposal_metadata` object.

Rename adds:

```json
{"operation": "FIELD_RENAME", "proposed_field_path": "order_amount"}
```

Delete adds no operation-specific property:

```json
{"operation": "FIELD_DELETE"}
```

Type change adds:

```json
{
  "operation": "FIELD_TYPE_CHANGE",
  "proposed_native_type": "TEXT",
  "proposed_normalized_type": "STRING"
}
```

Complete runnable files and selection rationale are in `examples/field_rename`,
`examples/field_delete`, and `examples/field_type_change`.
