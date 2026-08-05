# CHRONOS Phase 6.1 Hardcoded-Assumption Inventory

## Inspection gate

This inventory was created before Phase 6.1 production-code changes. The
repository was inspected across `src/chronos`, all backend and frontend tests,
the frozen `artifacts` package, public loaders, fingerprint utilities,
certifiers, presentation services, and the existing CLI.

The working tree already contained an unrelated generated change in
`frontend/next-env.d.ts` (`.next/types` to `.next/dev/types`). Phase 6.1 will
not modify, stage, or rely on that change.

## Frozen baseline

- Golden demonstration: `CHRONOS-DEMO-001`
- Golden proposal: `CHRONOS-DEMO-001-PROPOSAL-001`
- Dataset: PostgreSQL `orders`
- Operation: `order_total -> order_amount`
- Phase 4 semantic fingerprint:
  `sha256:3e8444ec904e0ba1c55c5ae22d69edfa8e722310f51ab30fc783b8175a87ac4a`
- The loaded certification fingerprint and independently recomputed
  fingerprint matched before implementation.
- Physical SHA-256 hashes for every file in `artifacts/` were captured during
  inspection for final byte-preservation comparison.

## Repository structure inspected

- `snapshot`: immutable DataHub-derived current-state models, validation,
  serialization, and assembly.
- `proposal` and `proposal_validation`: rename-only proposal model, factory,
  strict serializer, and current-snapshot validation.
- `change_semantics`: rename-only semantic contract.
- `counterfactual_source`: canonical rename materialization.
- `future_graph`: canonical graph projection and fixed-cardinality validation.
- `dependency_propagation`: canonical source-origin path and exposure logic.
- `compatibility_evaluation`: rename evidence rules and canonical rollups.
- `explanations`, `technical_impact`, `business_context`,
  `severity_criticality`, and `impact_synthesis`: Phase 3/4 result derivation.
- `phase2_certification`, `phase3_certification`, and
  `phase4_certification`: frozen demonstration certification.
- `presentation`: Phase 5 artifact gate and frozen review DTOs.
- `datahub.__main__`: readiness-only CLI; no general analysis command exists.
- `chronos.__init__`: no public structural-analysis entry point exists.

## One-scenario assumptions discovered

### Identity assumptions

`CHRONOS-DEMO-001` is enforced or emitted in proposal factories, snapshot
assembly/validation, Phase 3 and Phase 4 models/builders/certifiers, business
context, severity, impact synthesis, explanations, and presentation artifact
loading. Phase 4 certification also enforces the single proposal ID.

The Phase 5 presentation layer intentionally supports only
`CHRONOS-DEMO-001` and the frozen Phase 4 fingerprint. This is a golden-fixture
boundary and must remain unchanged in Phase 6.1.

### Operation assumptions

The legacy `ChangeType` contains only `FIELD_RENAME`. Proposal validation,
change semantics, counterfactual construction, graph building, propagation,
compatibility, impact, business context, severity, synthesis, and all three
certifiers reject any other operation.

### Field and dataset assumptions

Production modules containing explicit `order_total`, `order_amount`, or the
canonical PostgreSQL dataset URN include:

- `proposal.factory`;
- `counterfactual_source.models` and `.materializer`;
- `future_graph.models` and `.builder`;
- `dependency_propagation.builder`;
- `compatibility_evaluation.builder`;
- `explanations.builder`;
- `technical_impact.builder`;
- `business_context.builder`;
- `severity_criticality.builder`;
- `impact_synthesis.builder`;
- Phase 2, 3, and 4 certifiers;
- Phase 5 graph and explorer presentation mapping.

Several validators also assume the source is at a known canonical key rather
than resolving `(dataset_urn, field_path)` generically.

### Fixed-cardinality assumptions

The legacy pipeline validates golden counts in production models/builders and
certifiers, including 21 datasets, 26 active graph fields, 25 downstream
fields, 20 downstream datasets, 27 lineage relationships, 28 mapping groups,
48 paths, and fixed context/mapping totals. Phase 5 DTO models repeat these
counts to protect the frozen UI contract.

These values are legitimate golden certification expectations but cannot be
general-engine invariants.

### Fingerprint assumptions

- Phase 5 hardcodes the Phase 4 semantic fingerprint as its artifact gate.
- Phase 4 certification embeds predecessor semantic fingerprints, physical
  hashes, canonical root relationship identity, counts, and decision facts.
- The frozen JSON files live directly under `artifacts/`; legacy builders and
  tests assume those filenames.
- Timestamps are excluded by established semantic serializers, but the
  legacy pipeline has no per-analysis manifest or isolated output directory.

## Real snapshot observations for examples

The certified source schema contains 15 real PostgreSQL fields. The snapshot's
field-level lineage graph is rooted only at the real `order_total` source
field: 27 edges and 48 supplied paths reach 25 downstream fields in 20
downstream datasets. Therefore:

- the golden rename example remains `order_total -> order_amount`;
- delete and type-change examples may target the same real `order_total`
  field because it is the only source field in this certified snapshot with
  field-level downstream lineage;
- other source-schema fields can still validate and analyze generically, but
  this snapshot supplies no downstream path evidence for them;
- no example will invent a DataHub field, dataset, relationship, or path.

## Phase 6.1 separation decision

The frozen Phase 1-5 modules and root `artifacts/` package will remain the
golden certification implementation. Rewriting those canonical validators
would risk changing their public models, bytes, and fingerprint.

Phase 6.1 will add a reusable structural engine alongside the legacy modules.
It will:

- consume the existing public `CurrentMetadataSnapshot` model and loader;
- define a strict structural proposal union and generic analysis identity;
- resolve the target field from supplied snapshot data;
- use operation adapters for rename, delete, and type change;
- derive graph, paths, counts, compatibility, impact, context, severity, and
  decision from each input snapshot and proposal;
- write only to isolated `artifacts/analyses/<analysis-id>` directories;
- expose one Python API and one developer CLI;
- use separate analysis-level certification without weakening or replacing
  Phase 1-5 certification;
- preserve existing public imports and presentation DTO behavior.

## Final verification obligations

Phase 6.1 is blocked from completion unless final checks prove:

1. every original artifact is byte-identical;
2. the Phase 4 semantic fingerprint still reproduces exactly;
3. all legacy unit, certification, API, and frontend tests remain green;
4. generalized examples are isolated and deterministic;
5. no absolute path, secret, repair instruction, SQL/dbt analysis, PR intake,
   DataHub write, or client-side scenario workflow was introduced.
