# CHRONOS Phase 6 Frontend Integration Architecture

## Scope

This integration is a read-only presentation layer for the frozen Phase 6.1-
6.5 evidence. It does not rerun an analysis engine, inspect a repository at
request time, apply a patch, change DataHub, approve a proposal, or claim
runtime verification. The existing Phase 5 `/review` route and contracts stay
independent.

## Trust boundary

The trusted path is:

1. Phase 6.5's fixed 32-JSON release package establishes release identity,
   certification state, limitations, replay fingerprints, and test totals.
2. A fixed backend registry permits 17 public analysis IDs and two private
   predecessor packages used only to render repair context.
3. `Phase6PresentationService` loads only repository-owned relative package
   locations. It checks exact package closure, duplicate JSON keys, manifest
   membership, artifact fingerprints, Phase 6.5 replay fingerprints, repair
   patch fingerprints, supported schema versions, safe relative paths, and
   unsafe browser-bound values.
4. Immutable Pydantic DTOs reject extra fields and constrain certification,
   analysis, evidence, graph, repair, and compatibility vocabularies.
5. FastAPI exposes only bounded GET resources. Integrity failures become a
   generic 503 response; unknown IDs become a bounded 404 response.
6. The browser validates every response again with strict Zod schemas. A
   malformed or incomplete response fails closed instead of being rendered as
   certified evidence.

Raw certified JSON is never served directly. Client input can select a known
analysis ID, graph mode, or patch ID, but cannot select a filesystem path.

## Backend resources

| Resource | Purpose |
| --- | --- |
| `GET /api/phase6/release` | Release identity, certification, fingerprints, test totals, limitations, supported and unsupported capabilities, and golden-preservation state. |
| `GET /api/analyses` | Bounded selector summaries for the 17 public analyses. |
| `GET /api/analyses/{analysisId}` | Strict discriminated structural, semantic, pull-request, or repair detail. |
| `GET /api/analyses/{analysisId}/graph?mode=...` | Backend-supplied nodes, edges, representative paths, roots, files, and logical groups for an allowed state. |
| `GET /api/analyses/{analysisId}/evidence` | Typed evidence records for the selected certified analysis. |
| `GET /api/analyses/{analysisId}/repair` | Repairability, deterministic actions, patch summaries, projected comparison, and Phase 7 validation requirements. |
| `GET /api/analyses/{analysisId}/patches/{patchId}` | A lazy, bounded, unapplied candidate patch preview. |

Only `GET` is enabled by CORS. Patch previews carry the explicit label
`CANDIDATE - NOT APPLIED`; there is no apply, approve, merge, commit, push, or
download endpoint.

## Frontend routes and state

`/analyses` loads the release gate and the analysis index. It supports search
and filtering by analysis type, decision, coherence, and certification state.
Every row links internally with Next.js routing.

`/analyses/[analysisId]` renders a common certified context header and then a
type-specific surface:

- structural: current/proposed metadata changes and graph evidence;
- semantic: operation deltas, before/after fingerprints, and excerpts;
- pull request: changed files, logical groups, coherence, conflicts,
  traceability, evidence, decision, and graph;
- repair: repairability, deterministic plan, lazy patch previews, projected
  comparison, graph, and the exact Phase 7 validation checklist.

Release details use progressive disclosure. Graph, evidence, repair, and patch
requests have independent loading and error states. The selector and analysis
shell do not infer a decision from missing sections.

## Graph states

Non-repair analyses expose `CURRENT`, `PROPOSED`, and `DIFF`. Repair analyses
expose `CURRENT`, `PROPOSED`, and `PROJECTED_REPAIRED`, with projected repaired
as the default. The backend supplies the graph and representative paths for
each mode. The browser only lays out, filters, selects, and highlights those
records.

Edges keep their certified evidence category:

- `OBSERVED_DATAHUB_EDGE`;
- `CODE_DERIVED_PROPOSED_EDGE`;
- `COUNTERFACTUAL_EDGE`;
- `REMOVED_EDGE`;
- `UNRESOLVED_REFERENCE`.

The legend includes text, not color alone. Selecting a representative path
highlights its supplied nodes and edges and shows its roots, contributing
files, and logical groups. Multi-root targets use supplied memberships and are
not recomputed or double-counted in the browser. A textual graph summary is
available when the canvas is not useful.

## Responsive and accessibility behavior

Dense grids collapse into stacked cards on narrow screens. Patch bodies have a
contained horizontal scroll region, so they do not create document-level
overflow. Interactive controls use native buttons, links, labels, tabs, and
disclosures with visible focus. Loading and error messages use appropriate
status semantics. Motion is disabled for reduced-motion preferences.

## Security properties

- Exact allowlists prevent arbitrary package or path lookup.
- Safe-path and secret checks run before DTO construction.
- Pydantic and Zod both reject unknown fields and unsupported vocabularies.
- React renders excerpts as text; no raw-HTML injection API is used.
- Production browser source maps are not emitted.
- Error responses do not disclose repository roots or tracebacks.
- All rendered content is bounded; patch bodies are loaded only on request.

## Known limitation

The certified release has exactly one non-blocking limitation: seven live
DataHub-dependent tests were intentionally skipped in the offline certification
environment. The UI repeats this limitation verbatim and never upgrades it to
runtime verification.
