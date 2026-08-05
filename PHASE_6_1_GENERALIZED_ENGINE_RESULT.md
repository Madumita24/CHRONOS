# CHRONOS Phase 6.1 Generalized Engine Result

## Final result

Phase 6.1 is complete. CHRONOS now analyzes `FIELD_RENAME`, `FIELD_DELETE`,
and `FIELD_TYPE_CHANGE` proposals through one deterministic backend pipeline.
It accepts an established DataHub-derived `CurrentMetadataSnapshot`, validates
one exact source field, derives the reachable graph and decision from supplied
evidence, certifies the run, and writes an isolated 14-file package.

No frontend workflow, SQL/dbt parsing, pull-request ingestion, repair logic,
LLM dependency, or DataHub write was added. Phase 6.2 was not started.

## Repository inspection and assumptions

The package, snapshot and proposal models, all Phase 2-4 builders and
certifiers, artifact serializers/loaders, test suites, CLI, and Phase 5
presentation boundary were inspected before production changes. The complete
pre-change findings are in `PHASE_6_1_HARDCODED_ASSUMPTION_INVENTORY.md`.

The legacy pipeline assumes one demonstration ID, one proposal ID,
`FIELD_RENAME`, the PostgreSQL `orders` dataset, `order_total`, `order_amount`,
canonical graph/context counts, and accepted predecessor fingerprints in many
production validators. The presentation layer additionally gates on the exact
Phase 4 fingerprint. Those assumptions remain only in the frozen path.

## Refactoring performed

A separate `src/chronos/structural_engine` package now contains:

- strict immutable proposals and safe JSON parsing;
- analysis identity and public result models;
- exact current-field resolution;
- rename, delete, and type-change operation adapters;
- one counterfactual/graph/propagation/impact pipeline;
- an explicit compatibility-rule registry;
- canonical serialization, semantic hashing, and deterministic IDs;
- operation-aware generalized certification;
- safe staged artifact export.

`src/chronos/cli.py` and `src/chronos/__main__.py` provide the CLI, while
`chronos.__init__` exposes `analyze_structural_change`. Existing lower-level
and presentation imports were not removed or redirected.

## Golden-fixture preservation

The root `artifacts/*.json` files were never regenerated. The 16 pre-change
physical SHA-256 hashes were compared again after implementation; all 16 are
byte-identical. The loaded and recomputed Phase 4 semantic fingerprint remains:

`sha256:3e8444ec904e0ba1c55c5ae22d69edfa8e722310f51ab30fc783b8175a87ac4a`

The generalized rename replay has its own clearly labeled analysis ID and
certification package. It does not claim to be the original Phase 4
certification.

## Proposal contracts and resolver

Every proposal requires proposal ID, analysis ID, operation, dataset URN,
current field path, and snapshot fingerprint. Snapshot ID and descriptive
metadata are optional. Unknown keys and invalid discriminators are rejected.

- Rename requires a new valid, distinct, non-colliding field path.
- Delete permits no replacement property.
- Type change requires distinct native/normalized types and supports optional
  non-negative precision, scale, and length proposal parameters. The current
  source schema model has no separate precision/scale/length fields, so those
  parameters remain proposal evidence rather than invented schema attributes.

The resolver validates DataHub dataset URN shape, exact snapshot identity,
unchanged dataset identity, field-path shape, one exact schema match, and
consistent schema field name/path identity. It assumes no platform, field
position, schema size, or canonical name.

## Operation and future-state semantics

Rename preserves count and non-name properties, uses a CHRONOS
counterfactual identity, clears an observed DataHub schema-field URN, and maps
`RENAMED`.

Delete removes exactly one active future source field, fabricates no
replacement, retains a removed current graph reference, marks outgoing
projected relationships unsatisfied, and maps `DELETED`.

Type change preserves field identity, count, order, nullability, key state,
description, and unrelated fields; it changes only type-related state, clears
the observed schema-field URN for the counterfactual version, and maps
`IDENTITY_PRESERVED_TYPE_CHANGED`.

The shared graph traversal selects only snapshot edges reachable from the
resolved origin. Downstream nodes remain available for analysis. Relationship
and path IDs are deterministic and contain no timestamp. Propagation counts,
direct/transitive/multipath exposure, datasets, and maximum depth are computed
from that graph.

## Compatibility, impact, context, and decision

The registry exposes rule identity, operation, required evidence, inputs,
result, reason, evidence strength, and explanation. Its verified example
outcomes are:

- rename with active lineage and no execution/adaptation evidence: `UNKNOWN`;
- delete with certified active field dependency and no future source:
  `INCOMPATIBLE`;
- cross-family type change without consumer expected types: `UNKNOWN`;
- a field with no supplied downstream dependency: no demonstrated downstream
  impact and `PROCEED`.

Safe widening is limited to four documented primitive native-type pairs
within one normalized family; all other unsupported evidence patterns default
to uncertainty. Field names are never compatibility evidence.

Technical findings reference one shared operation-specific root cause.
Connected snapshot context is propagated but never automatically labeled
broken, impacted, sensitive, or mission-critical. Severity uses per-run
technical consequence, certainty, breadth, and context. Disposition is chosen
by the existing deterministic decision vocabulary and rule evaluator rather
than by operation name.

Rename and type-change uncertainty produce distinct blocking questions and
required-evidence classes populated with the actual first supplied boundary.
Certified delete incompatibility produces a block without inventing a repair.

## Artifact packaging and certification

During verification, each generated package under
`artifacts/analyses/<analysis-id>` contained:

1. `proposal.json`
2. `proposal_validation.json`
3. `change_semantic_contract.json`
4. `counterfactual_source_state.json`
5. `future_metadata_graph.json`
6. `dependency_propagation.json`
7. `compatibility_evaluation.json`
8. `technical_impact_analysis.json`
9. `business_context_propagation.json`
10. `severity_criticality_analysis.json`
11. `impact_synthesis.json`
12. `explanation_bundle.json`
13. `analysis_certification.json`
14. `manifest.json`

Certification verifies the pre-certification package contract, common
identity, valid proposal entry, snapshot reference, operation-specific
counterfactual invariants, unrelated-property preservation, identity mapping,
graph/path integrity, one shared cause, propagation-to-impact traceability,
context distinction, rule traceability, and absence of absolute local paths.
The engine then validates the completed manifest names and fingerprints before
atomic export. Existing output fails closed unless explicit overwrite is used,
and output is restricted to the repository while the golden artifact root is
forbidden.

## Interfaces and examples

Python:

`from chronos import analyze_structural_change`

CLI:

`chronos analyze-structural-change --snapshot ... --proposal ... --output ...`

The public result exposes full identity, decision, certification status,
semantic fingerprint, manifest, key summary, output directory, artifact paths,
and loaded artifact documents. CLI failures return status 2 as concise JSON
without normal stack traces.

The three `examples/*/change.json` files use the certified snapshot. Delete
and type change select real `order_total` because repository inspection proved
it is the only source-schema field in this snapshot with supplied field-level
downstream lineage. No DataHub entity was fabricated.

## Determinism results

Each final example was run twice to different output directories after the
last engine change. Semantic fingerprints matched exactly:

- generalized golden rename:
  `sha256:3f825888b035868f685b55d7d7505a84b09d42b131194c8a7a705d9ba52d2f99`
  (`hold_for_review`);
- real-field delete:
  `sha256:5d41548509113343a62bf99005342bc6009d8522437f0b93a6dea4f083a95201`
  (`block_confirmed_incompatibility`);
- real-field type change:
  `sha256:a8255c14a5ca0b2f889721f68e85a7fe46733851a20351804ece4fea7068b4b0`
  (`hold_for_review`).

Configured creation timestamps and output directories do not affect semantic
fingerprints.

## Negative and generalization tests

The 44 Phase 6.1 tests pass. They cover all required invalid inputs:
nonexistent/mismatched/malformed datasets, nonexistent and ambiguous fields,
same-name and colliding rename, delete replacement, unchanged and unsupported
type, malformed proposal, invalid operation, snapshot mismatch, uncontrolled
overwrite, external output, predecessor tampering, and dangling endpoints.

They also prove different proposal/analysis IDs and fields work, all three
operations share the pipeline, counts derive from input data, decisions vary
with run inputs, causes/questions/evidence are operation-specific, packages are
isolated, semantic reruns are stable, CLI behavior fails closed, public result
content is complete, and the golden Phase 4 fingerprint is unchanged.

## Exact regression totals

- Backend unit: **817 run, 817 passed** (includes 44 Phase 6.1 tests).
- Backend certification: **241 run, 240 passed, 1 skipped** (existing
  environment-dependent skip).
- Backend API: **95 run, 95 passed**.
- Backend integration: **6 run, 0 failed, 6 skipped** because live integration
  services were not configured in this test run.
- Backend total: **1,159 run, 1,152 passed, 7 skipped, 0 failed**.
- Frontend Vitest: **9 files, 186 tests passed, 0 failed**.
- Frontend TypeScript typecheck: passed.
- Frontend ESLint: passed.
- Next.js production build: passed; `/`, `/_not-found`, and `/review` generated.

## Frontend and security audit

No Phase 5 frontend source, DTO, endpoint, or interaction was changed. The
existing `frontend/next-env.d.ts` generated working-tree change was present
before Phase 6.1, was restored after the build tool rewrote it, and is not a
Phase 6.1 deliverable.

Proposal parsing rejects arbitrary keys; output is contained and controlled;
artifacts contain no token, credential, or absolute local path; CLI normal
errors contain no stack trace; fingerprints exclude volatile location/time;
the engine performs no network request and no DataHub write. Verified generated
packages contained only snapshot-derived identities/evidence and proposal
counterfactuals; they are reproducible run outputs rather than source files.

## Known limitations, warnings, and follow-up questions

- A supplied snapshot is required; Phase 6.1 does not fetch a live arbitrary
  DataHub environment.
- Compatibility is limited to supplied metadata. Consumer type expectations,
  transform semantics, contract constraints, and execution results are often
  absent, so uncertainty is intentional.
- The widening registry is deliberately small and is not a universal database
  type system.
- The certified snapshot exposes downstream lineage for only one source-schema
  field, so other fields correctly produce a no-supplied-reach result.
- Six live integration tests were skipped due to unavailable configured live
  services; all deterministic and mocked integration boundaries passed in the
  unit/certification/API suites.
- A future approved phase can let the presentation layer discover validated
  manifests. Phase 6.1 keeps the UI on the immutable golden review.
- Future investigations should define certified consumer expected-type
  evidence, precision/scale semantics, broader type registries, live snapshot
  acquisition boundaries, and manifest discovery authorization. These are not
  implemented assumptions.
