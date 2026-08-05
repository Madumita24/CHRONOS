# CHRONOS Phase 6.2 Developer Guide

## Install and validate

The SQL parser is an exact project dependency:

```powershell
.\.venv-datahub-310\Scripts\python.exe -m pip install -e .
.\.venv-datahub-310\Scripts\python.exe -c "import sqlglot; print(sqlglot.__version__)"
```

The expected parser version is `30.13.0`. Phase 6.2 is read-only with respect
to DataHub and never executes supplied SQL or Jinja.

## Proposal contract

A complete proposal has this shape:

```json
{
  "proposal_id": "SEMANTIC-PROPOSAL-001",
  "analysis_id": "SEMANTIC-ANALYSIS-001",
  "operation": "SEMANTIC_CODE_CHANGE",
  "model_dataset_urn": "urn:li:dataset:(urn:li:dataPlatform:dbt,db.schema.model,PROD)",
  "model_relation": "db.schema.model",
  "sql_dialect": "postgres",
  "before_code_reference": "path/inside/repository/before.sql",
  "after_code_reference": "path/inside/repository/after.sql",
  "source_snapshot_fingerprint": "sha256:...",
  "source_snapshot_id": "snapshot-..."
}
```

Optional properties are `dbt_manifest_reference`, `scenario_id`,
`description`, `created_at`, and a string-to-string `proposal_metadata`
object. Unknown properties fail closed. Code and manifest paths must be
repository relative. The proposal dialect and all API/CLI overrides must
match exactly.

## Python API

```python
from chronos import analyze_semantic_code_change

result = analyze_semantic_code_change(
    snapshot="artifacts/current_metadata_snapshot.json",
    proposal="examples/semantic_aggregation/change.json",
    before_sql="examples/semantic_aggregation/before.sql",
    after_sql="examples/semantic_aggregation/after.sql",
    output_dir="artifacts/analyses/semantic-aggregation",
)

print(result.identity.analysis_id)
print(result.certification_status)
print(result.semantic_compatibility.value)
print(result.disposition)
print(result.semantic_fingerprint)
print(result.detected_deltas)
print(result.resolved_model)
print(result.affected_outputs)
print(result.manifest)
```

The result is immutable. `artifacts` contains the loaded 18-document package;
`artifact_paths` points to the exported copies. Invalid input, unresolved or
ambiguous identity, failed certification, unsafe paths, and uncontrolled
overwrite raise typed semantic-engine exceptions.

## CLI

```powershell
.\.venv-datahub-310\Scripts\python.exe -m chronos analyze-semantic-change `
  --snapshot artifacts/current_metadata_snapshot.json `
  --proposal examples/semantic_aggregation/change.json `
  --before examples/semantic_aggregation/before.sql `
  --after examples/semantic_aggregation/after.sql `
  --output artifacts/analyses/semantic-aggregation `
  --dialect postgres `
  --fixture
```

The `--fixture` flag documents intent and does not weaken validation.
`--overwrite` may replace only a recognized prior semantic package.
Successful output is one concise JSON object. Normal failure returns status 2
with bounded JSON and no ordinary stack trace.

## dbt input modes

Compiled dbt SQL needs no special handling because it is already SQL. For
bounded raw dbt, add `dbt_manifest_reference` to the proposal and pass the
same relative path with `--dbt-manifest` or `dbt_manifest=`.

Supported expressions are only:

```sql
{{ ref('orders') }}
{{ source('order_entry', 'orders') }}
```

The supplied manifest must resolve exactly one matching node/source and must
provide `relation_name` or complete database/schema/name identity. For
example:

```json
{
  "nodes": {
    "model.project.orders": {
      "resource_type": "model",
      "name": "orders",
      "relation_name": "order_entry_db.order_entry.orders"
    }
  },
  "sources": {}
}
```

CHRONOS substitutes that static identity and then parses SQL. It does not
invoke dbt or Jinja. Macros, loops, variables, dynamic arguments, Jinja blocks,
ambiguous matches, and missing manifests are unsupported; provide compiled
SQL instead.

## Examples

- `examples/semantic_aggregation`: `SUM` to `AVG`, plus a combined
  aggregation-and-filter proposal;
- `examples/semantic_filter`: model-wide filter addition;
- `examples/semantic_join`: `LEFT` to `INNER` using observed Snowflake
  relations;
- `examples/semantic_expression`: derived-expression literal change.

All four examples target real entities in the frozen snapshot. Their SQL is
authored fixture evidence, not claimed DataHub query text. Each README states
that boundary and each `expected-summary.json` records the expected outcome.

## Reading the package

Start with `manifest.json` for identity, parser version, delta counts,
decision, artifact list, and fingerprints. Use `semantic_diff.json` for exact
deltas, `entity_resolution.json` for observed/code-derived identity mapping,
and `compatibility_evaluation.json` for rule state and missing evidence.
`future_metadata_graph.json` contains only observed reachable edges;
`dependency_propagation.json` derives reach. `impact_synthesis.json` and
`explanation_bundle.json` connect delta, evidence, questions, severity, and
decision without proposing a repair.

## Tests

Focused semantic tests:

```powershell
.\.venv-datahub-310\Scripts\python.exe -m unittest tests.unit.test_semantic_engine -v
```

Full regression commands:

```powershell
.\.venv-datahub-310\Scripts\python.exe -m unittest discover -s tests\unit
.\.venv-datahub-310\Scripts\python.exe -m unittest discover -s tests\certification
.\.venv-datahub-310\Scripts\python.exe -m unittest discover -s tests\api -v
.\.venv-datahub-310\Scripts\python.exe -m unittest discover -s tests\integration

cd frontend
npm run typecheck
npm run lint
npm test
npm run build
```

The golden root artifacts must remain byte-identical and the Phase 4 semantic
fingerprint must remain
`sha256:3e8444ec904e0ba1c55c5ae22d69edfa8e722310f51ab30fc783b8175a87ac4a`.
