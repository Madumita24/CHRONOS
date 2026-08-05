# CHRONOS Phase 6 Frontend Integration Inventory

## Inspection boundary

This inventory was completed before Phase 6 frontend production changes. It
covers the existing Phase 5 browser and presentation service, the certified
Phase 6.1-6.5 contracts, retained artifacts, test boundaries, responsive
behavior, accessibility, and the additive integration required by the Phase 6
frontend handoff.

The inspected repository is on `main` at Phase 6.5 release state
`PHASE_6_CERTIFIED_WITH_NON_BLOCKING_LIMITATIONS`. The release limitation is
the seven offline-skipped live DataHub tests. Runtime correctness, business
approval, and merge safety are scope exclusions, not inferred limitations.

## Existing Phase 5 architecture

- Next.js App Router serves the frozen demonstration at `/review`; `/` redirects
  to that route.
- `ReviewPage` owns the trusted-review loading gate and shared selection state.
- `GraphWorkspace` renders backend-supplied Current, Future, and Diff nodes,
  edges, and ordered representative paths with React Flow and Dagre layout.
- `ImpactEvidenceExplorer` presents backend-supplied fields, datasets, paths,
  relationships, context, evidence, and decision records.
- One shared selection union coordinates graph and explorer node, edge, path,
  dataset, and context selection. Filtering and layout are presentation-only.
- Graph and explorer failures are isolated after the main review has passed its
  certification gate. Review contract or certification failure closes the
  trusted review surface.
- Loading uses layout-shaped skeletons. Empty, transport, integrity, and
  contract-error states are differentiated.
- FastAPI exposes read-only GET endpoints under `/api/reviews/{review_id}`.
- Strict immutable Pydantic DTOs use camelCase aliases and reject extra fields.
- Strict Zod schemas reject extra browser payload fields, dangling graph edges,
  invalid graph modes, invalid cardinalities, and altered golden semantics.

## Reusable components and patterns

- `AppShell`: product header and primary navigation; must be extended without
  changing the `/review` destination or golden review behavior.
- `StatusBadge` and `MetricCard`: compact state and count presentation.
- Graph nodes, edges, layout helpers, toolbar, inspector, legend, keyboard
  controls, and graph fallback summaries can be adapted for Phase 6 DTOs.
- Review workflow anchors, sticky context, skeletons, section-level error
  states, provenance disclosures, and evidence labels are reusable patterns.
- `fetchCertifiedReview`, `fetchCertifiedGraph`, and
  `fetchCertifiedExplorer` establish the no-store GET, bounded API-error, and
  runtime-Zod-validation pattern.
- `PresentationModel`, `CertifiedArtifactLoader`, and the presentation error
  mapping establish strict DTO and fail-closed service conventions.

## Golden-only assumptions that must remain isolated

- `/review` is hard-coded to `CHRONOS-DEMO-001` and the exact frozen Phase 4
  certification fingerprint.
- The current review contract permits only `field_rename`, `hold_for_review`,
  one specific source identity replacement, and golden Phase 4 vocabulary.
- Graph contracts enforce exactly 26 current/future nodes, 27 edges, 48 paths,
  one root uncertainty, and the `order_total` to `order_amount` mapping.
- Explorer contracts enforce exact golden counts: 25 fields, 20 datasets, 66
  context assets, 211 relationships, and 257 mappings.
- Existing graph states describe the Phase 5 counterfactual graph and cannot be
  widened in place to represent PR or repair projections.
- Existing API paths and DTOs load the frozen root `artifacts/` package. Phase 6
  must use separate services, models, endpoints, contracts, and routes.

## Certified Phase 6 inputs inspected

- Phase 6.1 packages contain 14 JSON artifacts and certify rename, delete, and
  type-change scenarios.
- Phase 6.2 packages contain 18 JSON artifacts and certify aggregation,
  aggregation-plus-filter, filter, join, and derived-expression scenarios.
- Phase 6.3 packages contain 26 JSON artifacts and certify primary, coherent,
  no-material, and conflict multi-file scenarios.
- Phase 6.4 packages contain 27 top-level JSON artifacts plus bounded patch and
  candidate-preview files, and certify primary, coherent, no-material,
  conflict, deletion, and type-alignment outcomes.
- Phase 6.5 contains exactly 32 JSON artifacts. Its replay certification files
  freeze every retained scenario's semantic fingerprint and patch
  fingerprints. Its manifest closes and fingerprints the release package.
- The repository currently retains Phase 6.5 replay summaries but no detailed,
  durable Phase 6.1-6.4 analysis packages. Request-time engine replay would
  violate the presentation trust boundary.

## Required retained fixture packages

Detailed packages for the certified scenarios must be generated once from the
existing certified fixture inputs, then retained under one repository-owned,
fixed analysis root. Generation is a release/build activity, never an API
request. Every retained package must match the corresponding Phase 6.5 replay
semantic fingerprint; repair packages must also match every certified patch
fingerprint.

The backend must discover packages through a fixed registry of analysis IDs and
relative directories. Client input must never select a filesystem path. The
registry is the only approved package discovery surface.

## Required backend contracts

- A release DTO containing release identity, version, certification state,
  fingerprints, test totals, skip count, limitations, capabilities, and golden
  preservation state.
- A bounded analysis-summary DTO for the selector.
- A strict discriminated detail union for structural, semantic, PR, and repair
  analyses.
- Separate bounded graph, evidence, repair, and patch-preview DTOs so section
  failures remain isolated.
- Relative safe paths only. No absolute paths, parent traversal, repository
  roots, credentials, raw tracebacks, or unbounded content.
- Known certification, compatibility, coherence, repair-disposition,
  repairability, evidence, graph-edge, and projection vocabularies only.
- Graph validators must reject duplicate IDs and dangling endpoints or paths.
- Patch validators must enforce certified IDs, relative paths, fingerprints,
  bounded hunks, escaped text, and manifest membership.

## Required certification trust gates

1. Load only the approved Phase 6.5 package directory.
2. Validate exact 32-file closure, strict JSON, release identity, version,
   manifest artifact list, and semantic fingerprints through the Phase 6.5
   public loader.
3. Reject `PHASE_6_NOT_CERTIFIED` and unknown states. Preserve the current
   certified-with-limitations state and limitation text.
4. For each approved analysis, validate exact package closure and every
   package-manifest artifact fingerprint.
5. Compare the package semantic fingerprint with the matching Phase 6.5 replay
   record. For repairs, compare every patch fingerprint too.
6. Validate schema and engine versions before mapping DTOs.
7. Scan all browser-bound values for unsafe paths, credentials, and unsupported
   vocabulary.
8. Map only certified artifact values; never rerun analysis or derive a new
   decision, compatibility, coherence, severity, or graph traversal.

## Required UI components

- `/analyses`: certified analysis selector with type, scenario, decision,
  coherence, certification, and warning filters.
- `/analyses/[analysisId]`: shared analysis shell with persistent identity,
  certification, decision/disposition, and repository context.
- Certification banner and compact release-certification disclosure.
- Structural state comparison and backend-supplied graph view.
- Semantic delta cards with before/after fingerprints and bounded excerpts.
- PR changed-file inventory, logical groups, coherence, conflict, traceability,
  graph, evidence, and decision sections.
- Repairability list, deterministic Repair Plan, bounded patch hunks, bounded
  original/candidate preview, projected comparison, valid no-repair states,
  and Phase 7 requirements.
- Section-level skeleton, unavailable, integrity, contract, and empty states.

## Graph compatibility

The reusable visual language is compatible, but the golden `CertifiedGraphReview`
contract is not. Phase 6 needs a separate graph DTO supporting
`OBSERVED_DATAHUB_EDGE`, `CODE_DERIVED_PROPOSED_EDGE`, `COUNTERFACTUAL_EDGE`,
`REMOVED_EDGE`, and `UNRESOLVED_REFERENCE`; Current, Proposed, and Diff modes;
and Current, Proposed, and Projected Repaired modes for repair analyses.

The backend must supply nodes, edges, ordered representative paths, root-to-
target memberships, contributing files, and logical groups. The browser may
filter, select, highlight, and lay out supplied records, but must not discover
paths, infer reachability, or double-count multi-root targets.

## Responsive constraints

- Preserve no document-level horizontal overflow at 1920x1080, 1440x900,
  1366x768, 1280x720, 768x900, and 390x844.
- Context, certification, and decision remain readable without relying on a
  wide table.
- Dense file, action, and finding tables convert to stacked cards on narrow
  screens.
- Patch and code excerpts use their own bounded horizontal scroll region.
- Graph canvas height and inspector stacking remain usable at laptop and phone
  widths.
- Long lists and patch bodies start bounded and disclose additional records on
  demand; all paths are not rendered simultaneously.

## Accessibility requirements

- Keyboard-accessible selector, tabs, graph controls, disclosures, list rows,
  and patch navigation with visible focus.
- Semantic landmarks and ordered headings; accessible tab and disclosure
  relationships; live loading/error announcements where appropriate.
- Text labels accompany every color or line-style distinction.
- Graphs include a textual node/edge/path fallback summary.
- Patch additions and removals use symbols and screen-reader labels in addition
  to color.
- Motion is decorative-only and disabled under `prefers-reduced-motion`.
- State badges expose their complete label to assistive technology.

## Frontend non-goals

No Phase 6 browser or presentation endpoint may parse repository source,
inspect Git, resolve DataHub identities, calculate graph traversal, derive
analysis semantics, generate or apply repairs, execute code, edit or download
candidate files into a repository, approve, merge, commit, push, write to
DataHub, or claim runtime verification. Phase 7 is not part of this work.

## Existing unrelated working-tree state

`frontend/next-env.d.ts` has a pre-existing generated-path difference. It is
not part of this integration and must not be overwritten or staged implicitly.
