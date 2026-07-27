# CHRONOS Phase 1.6 — Integration Verification Result

**Demonstration:** `CHRONOS-DEMO-001`

**Verification date:** 2026-07-26 America/Phoenix

**Scope:** Immutable current-state composition from authoritative Phase
1.1–1.5 outputs

## Final result

**Verified:** Phase 1.6 completed successfully against the existing local
DataHub Quickstart.

**Verified:** The exported `CurrentMetadataSnapshot` is current state only.
It contains no proposed `order_total` to `order_amount` mutation, Future
Graph, impact conclusion, severity, repair recommendation, agent, frontend,
or DataHub write.

## Prerequisites

| Prerequisite | Observed result |
|---|---|
| Phase 1.1 readiness | `ready`; `can_continue=true` |
| Phase 1.2 source dataset | `resolved` |
| Phase 1.2 source field | `resolved` |
| Phase 1.3 source schema | `retrieved`; 15 fields |
| Phase 1.4 lineage | `retrieved`; 25 / 20 / 5 baseline |
| Phase 1.5 context | `retrieved`; 21 scoped datasets |

The Phase 1.6 assembler consumed these public typed results. It did not own a
DataHub transport and did not rediscover missing metadata.

## Snapshot result

| Property | Observed value |
|---|---|
| Snapshot state | `validated` |
| Validation state | `valid` |
| Validation findings | `0` |
| Checked invariants | `29` |
| Snapshot schema version | `1.0` |
| Snapshot ID | `snapshot-4981780a1e7123349ef6` |
| Created at | `2026-07-27T02:25:48.659817+00:00` |
| Semantic fingerprint | `sha256:774185f19c6fea113ef7adfc5e14583e05e7e08a1fad0c59bd6c6fad755db72c` |
| Artifact | `artifacts/current_metadata_snapshot.json` |
| Artifact format | Deterministic UTF-8 JSON |
| Credentials present | No |

The snapshot ID includes the actual assembly timestamp and is therefore
observational. The semantic fingerprint excludes observation timestamps and
is stable across semantically unchanged assembly runs.

## Frozen baseline

| Metric | Observed | Expected | Result |
|---|---:|---:|---|
| Scoped datasets | 21 | 21 | Match |
| Source schema fields | 15 | 15 | Match |
| Lineage field nodes | 26 | 26 | Match |
| Unique downstream fields | 25 | 25 | Match |
| Unique downstream datasets | 20 | 20 | Match |
| Maximum field depth | 5 | 5 | Match |
| `order_total` native type | `DOUBLE PRECISION` | `DOUBLE PRECISION` | Match |
| `order_total` normalized type | `Number` | `Number` | Match |

The counts validate the supplied objects; they do not drive discovery or
repair.

## Observed lineage and context

| Metric | Observed |
|---|---:|
| Explicit lineage edges | 27 |
| Mapping groups | 28 |
| Captured lineage paths | 48 |
| Ownership assignments | 27 |
| Domain assignments | 6 |
| Tag assignments | 8 |
| Glossary assignments | 38 |
| Structured-property definitions | 5 |
| Structured-property assignments | 105 |
| Data-product memberships | 4 |
| Document relationships | 18 |
| Pipeline-context relationships | 4 |
| BI reachable-context entities | 15 |
| Dashboards in BI context | 3 |
| Unresolved stored references | 1 |

Pipeline-context relationship count is four because each of the two verified
Data Jobs is related to its two explicit endpoint field keys. It does not
alter lineage node or edge counts.

## Evidence

| Classification | Records |
|---|---:|
| Verified | 560 |
| Unknown | 1 |
| Derived | 0 |
| Total | 561 |

The unknown record preserves the unresolved Phase 1.5 tag-reference finding.
The stored assignment itself remains verified and unresolved; no replacement
tag was fabricated.

Every dataset, graph field, lineage edge, mapping group, structured-property
definition, and typed relationship references registered evidence. Validation
found no dangling evidence ID.

## Determinism

Two snapshots were assembled from the same authoritative Phase 1.1–1.5
objects with different `created_at` values.

| Check | Result |
|---|---|
| Snapshot IDs differ | Passed |
| Semantic JSON equal | Passed |
| Semantic fingerprints equal | Passed |
| Registry ordering stable | Passed |
| Relationship ordering stable | Passed |
| Evidence ordering stable | Passed |

## Round trip

The validated snapshot was serialized, written to JSON, reloaded, and checked.

| Check | Result |
|---|---|
| Stored fingerprint verified on load | Passed |
| Semantic equivalence | Passed |
| Same semantic fingerprint | Passed |
| Same graph and context counts | Passed |
| Same machine identities | Passed |
| Same evidence references | Passed |

## Automated verification

### Unit tests

Command:

```powershell
.\.venv-datahub-310\Scripts\python.exe -m unittest discover -s tests\unit -v
```

Result: **162 passed**.

This comprises the prior 124 Phase 1.1–1.5 tests and 38 Phase 1.6 tests.

### Live integration tests

Command:

```powershell
$env:CHRONOS_RUN_INTEGRATION = "1"
$env:CHRONOS_SNAPSHOT_ARTIFACT = "artifacts\current_metadata_snapshot.json"
.\.venv-datahub-310\Scripts\python.exe -m unittest discover -s tests\integration -v
```

Result: **6 passed**.

The sixth test assembles, validates, fingerprints, exports, reloads, and
compares the live `CurrentMetadataSnapshot`.

## Deviations

No frozen baseline deviation was observed.

The complete source schema is stored separately from the 26-node lineage-field
registry. This preserves all 15 canonical source fields without incorrectly
counting the other 14 source-schema fields as descendants in the Phase 1.4
graph.

## Read-only and scope guarantee

Phase 1.6 contains no:

- DataHub transport call in the assembler;
- Metadata Change Proposal or Metadata Change Event;
- GraphQL mutation or REST write;
- database dependency;
- proposed-change parsing;
- rename application;
- Future Graph;
- impact or severity reasoning;
- repair logic;
- agent or frontend.

Phase 1.6 stops at the validated current-state artifact. Phase 1.7 has not
begun.
