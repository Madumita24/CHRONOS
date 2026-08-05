# CHRONOS Phase 6.1 Generalized Engine Architecture

## Problem and boundary

The Phase 1-5 implementation is intentionally a certification pipeline for
one fixture: `CHRONOS-DEMO-001`, a PostgreSQL field rename from `order_total`
to `order_amount`. Its models and certifiers contain canonical identities,
counts, and fingerprints. Phase 6.1 adds a reusable deterministic structural
analysis engine without weakening or rewriting that boundary.

The legacy modules and root `artifacts/*.json` remain the golden fixture. The
new `chronos.structural_engine` package consumes the established immutable
`CurrentMetadataSnapshot` through its public loader and writes only isolated
analysis packages. The Phase 5 presentation API remains golden-only.

## Shared pipeline

`analyze_structural_change` owns one pipeline:

1. strictly parse a discriminated proposal;
2. verify snapshot fingerprint and optional snapshot ID;
3. resolve exactly one `(dataset_urn, field_path)` in the source schema;
4. select an operation adapter and validate operation semantics;
5. build counterfactual schema and identity mapping;
6. project the reachable future graph and deterministic paths;
7. derive dependency exposure from that graph;
8. evaluate an explicit compatibility-rule registry;
9. derive technical impact, connected business context, severity, and a
   decision through the existing decision vocabulary and rule evaluator;
10. create explanations, certification, fingerprints, and a manifest;
11. atomically export the package to a repository-contained directory.

There is no pipeline copy per operation. Adapter behavior is limited to
proposal validation, projected source fields, projected field identity, and
root state.

## Proposal union and identity

The immutable union is:

- `FieldRenameProposal`: requires `proposed_field_path`;
- `FieldDeleteProposal`: permits no replacement property;
- `FieldTypeChangeProposal`: requires proposed native and normalized types,
  with optional precision, scale, and length.

Every variant requires proposal ID, analysis ID, operation, dataset URN,
current field path, and source snapshot fingerprint. Unknown JSON properties,
coercion, malformed paths, invalid discriminators, and inconsistent snapshot
identity fail closed. Analysis identity also records snapshot ID, engine
version, optional scenario ID, and configured creation time.

## Counterfactual and identity semantics

Rename preserves field count and all non-name properties, removes the old
active path, creates one counterfactual path, clears the DataHub schema-field
URN, and classifies the mapping as `RENAMED`.

Delete reduces field count by one, creates no replacement, retains the
current identity only as a removed graph node, marks projected outgoing
dependencies unsatisfied, and classifies the mapping as `DELETED`.

Type change preserves field identity and count, updates native and normalized
types, preserves unrelated properties, clears the observed DataHub
schema-field URN for the counterfactual version, and classifies the mapping as
`IDENTITY_PRESERVED_TYPE_CHANGED`.

The input snapshot is immutable in every case.

## Future graph and propagation

The graph builder starts at the resolved current field and traverses supplied
`SnapshotLineageEdge` records. It does not assume platform, schema position,
dataset size, names, counts, or a canonical root. Nodes distinguish inherited,
renamed, removed, and type-changed states. Relationships retain current edge,
mapping-group, source-entity, transform, and evidence references.

Path IDs hash the snapshot/proposal-derived relationship identity and path
content; timestamps and output directories are excluded. Certification
rejects unknown endpoints, unknown relationships, duplicate identities, and
path cardinality mismatches. Propagation derives direct, transitive, and
multipath exposure, downstream fields and datasets, paths, relationship count,
and maximum depth from the projected graph.

## Compatibility registry

`compatibility_registry.py` declares rule records with rule ID, operation,
required evidence, inputs, result, reason, evidence strength, and explanation.
Rules are deliberately small and conservative:

- no supplied active downstream dependency: `COMPATIBLE` for the demonstrated
  downstream question;
- rename with active lineage but no explicit adaptation/execution evidence:
  `UNKNOWN` / `INSUFFICIENT` /
  `SOURCE_RENAME_SEMANTICS_UNKNOWN`;
- delete with certified current field lineage and certified future absence:
  `INCOMPATIBLE` /
  `SOURCE_FIELD_REMOVED_WITH_ACTIVE_DEPENDENCY`;
- documented primitive widening within one normalized family:
  `CONDITIONALLY_COMPATIBLE`;
- any other type change without certified consumer expectations: `UNKNOWN`.

Identity preservation is never treated as compatibility. Descendants share
one operation-specific source cause rather than fabricated per-node causes.

## Impact, context, severity, and decision

Compatibility and observed reach map into the existing
`TechnicalConsequence`, `EvidenceCertainty`, `ExposureBreadth`,
`ContextCriticality`, and `SeverityIfRealized` vocabularies. Final disposition
uses the existing deterministic `evaluate_decision` rules. Thus the same
operation can proceed on a field with no supplied downstream reach, hold when
material evidence is unresolved, or block when an active dependency is
certifiably removed.

Business context is selected from snapshot relationships connected to the
affected graph. Relationship presence remains context only; it is not called
broken, impacted, critical, or sensitive without explicit evidence.

## Artifacts and certification

Each run writes 14 files: proposal, validation, semantic contract, the nine
analysis-stage artifacts, analysis certification, and manifest. Semantic
hashes exclude configured creation time and output location. The manifest has
names and fingerprints but no absolute local path. Export uses a staged
directory and atomic rename; existing output is rejected unless overwrite is
explicit, and overwrite is permitted only for a directory containing known
analysis artifact names. Output must remain inside the repository, and the
root golden artifact directory cannot be targeted.

Certification verifies identity, proposal/snapshot entry checks,
operation-specific source invariants, unrelated-property preservation, graph
and path integrity, rule traceability, portable content, and artifact
fingerprints. It does not require golden counts.

## Interfaces

Python exposes `from chronos import analyze_structural_change`. The CLI entry
is `chronos analyze-structural-change` (or `python -m chronos`). Both accept a
DataHub-derived snapshot JSON, strict proposal JSON, and isolated output
directory. The API returns identity, decision, certification state, semantic
fingerprint, manifest, key summary, and artifact references.

A future presentation scenario selector can list validated generalized
manifests and request an analysis by ID. Phase 6.1 deliberately does not add
that selector or alter the frozen Phase 5 DTOs.

## Migration strategy and non-goals

The new engine lives beside the legacy pipeline because extracting hardcoded
certification assertions from Phase 1-5 would risk the certified bytes and
public UI behavior. Reusable work uses `structural_engine`; golden review uses
the legacy modules until a separately approved migration exists.

Phase 6.1 contains no SQL/dbt parsing, semantic expression analysis, GitHub PR
intake, multi-file changes, repair generation or verification, DataHub
write-back, field additions, dataset changes, LLM dependency, or new frontend
workflow.
