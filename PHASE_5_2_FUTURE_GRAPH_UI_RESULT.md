# CHRONOS Phase 5.2 Future Graph UI Result

## Final result

Phase 5.2 is complete. The Phase 5.1 review has been extended with a read-only,
interactive field-lineage workspace for `CHRONOS-DEMO-001`. It presents the
complete certified current graph, counterfactual future graph, and explicit
diff projection without performing lineage traversal or technical reasoning in
the browser.

The implementation stops before Phase 5.3. It does not include repair advice,
repair generation, detailed context exploration, proposal entry, or metadata
writes.

## Architecture

The Phase 5.2 boundary is documented in
`PHASE_5_2_GRAPH_ARCHITECTURE.md`. FastAPI owns certified artifact loading,
cross-artifact validation, presentation joining, and the strict graph DTO.
Next.js owns only rendering, deterministic layout, display filtering,
selection, and supplied-path highlighting.

Phase 5.1 remains intact: the textual certified review continues to render even
when the graph endpoint is unavailable, while the graph fails closed in its own
clearly labelled region.

## Graph library

The frontend uses `@xyflow/react` 12.11.2 for nodes, edges, selection, pan,
zoom, fit-to-view, minimap, controls, and keyboard-focusable graph elements.
It uses `@dagrejs/dagre` 3.0.0 exclusively for deterministic left-to-right
layout.

## Graph presentation API

`GET /api/reviews/CHRONOS-DEMO-001/graph` returns the strict
`CertifiedGraphReview` contract:

- certification and source-change context;
- current, future, and diff projections;
- 26 current-to-future identity mappings;
- explicit root uncertainty;
- all 48 supplied supporting paths;
- three representative-path shortcuts;
- legend tokens and canonical summary metrics.

Pydantic rejects duplicate IDs, dangling endpoints, dangling path references,
invalid source replacement, invalid identity-mapping counts, an invalid root
boundary, and canonical-count mismatches. The endpoint returns stable `404`
and `503` responses and exposes no local paths, secrets, tracebacks, or raw
artifact dumps.

## Certification gate

The graph uses the Phase 4 certification fingerprint:

```text
sha256:3e8444ec904e0ba1c55c5ae22d69edfa8e722310f51ab30fc783b8175a87ac4a
```

Every contributing artifact is loaded through its public deserializer. Its
semantic fingerprint must match the identity frozen in the certification, and
the certified predecessor chain must remain consistent. Missing, corrupt,
tampered, or cross-reference-inconsistent inputs fail closed with
`certification_integrity_error`.

## Current graph

The current projection contains 26 observed field nodes and 27 observed
lineage relationships. PostgreSQL `orders.order_total` is the active source;
`orders.order_amount` is absent. Future compatibility and technical-impact
states are not applied to the observed graph.

## Future graph

The future projection contains 26 active field nodes and 27 structural
relationships. PostgreSQL `orders.order_amount` is the active source; the old
source identity is absent. All 25 downstream identities are preserved.

One projected root edge is `UNKNOWN`; 26 relationships are
`CONDITIONALLY_COMPATIBLE`. No confirmed downstream failure is asserted.

## Diff graph

The API supplies an explicit diff projection with 27 nodes and 28
relationships:

- removed `orders.order_total` source identity;
- added `orders.order_amount` source identity;
- 25 preserved downstream identities;
- removed current root relationship;
- projected future root relationship;
- all remaining future relationships.

The browser does not compare names or infer additions, removals, or preserved
identities.

## Node model

Every field node contains an opaque ID, machine key, field and parent-dataset
labels, platform, dataset URN, field path, graph state, explicit diff state,
exposure and compatibility presentation states, depth, path count, origin and
root-target flags, supplied supporting-path IDs, and bounded provenance
references.

## Edge model

Every relationship contains opaque and certified relationship IDs, endpoint
IDs and identities, current endpoint identities where relevant, relationship
and diff states, exposure, compatibility, technical impact, evidence strength,
reason and explanation, root-uncertainty flag, mapping groups, path
participation, supplied supporting-path IDs, transform/query evidence, and
bounded provenance.

## Layout

Dagre receives sorted, already-supplied nodes and edges and produces a stable
left-to-right layout. Nodes are not duplicated for each path; shared and
multipath nodes remain shared. The same projection and display filters produce
the same positions.

## Root uncertainty rendering

The projected PostgreSQL `order_amount` to S3 `order_total` boundary is a
thick dashed amber edge with an explicit `UNKNOWN` label. `INCOMPATIBLE` has a
separate red solid treatment and remains visible in the legend even though the
certified graph currently contains zero incompatible relationships.

The relationship inspector shows the paired current and future boundary,
reason, explanation, 48-path participation, and all four missing-evidence
records. It does not show repair advice.

## Multipath handling

The graph keeps one node per field identity. Certified path counts and
supporting-path IDs expose multipath participation without duplicating nodes or
running traversal in React. The certified summary reports 21 multipath fields.

## Path highlighting

All 48 supporting paths are carried by the API as ordered current, future, and
diff node and edge ID lists. Selecting a representative or supporting path
highlights those supplied IDs and dims unrelated elements. The frontend does
not calculate shortest, deepest, or multipath routes.

## Inspector

The persistent inspector presents one of four views:

- canonical graph summary;
- selected field details;
- selected relationship and uncertainty evidence;
- selected certified path details.

An explicit root-boundary shortcut provides reliable keyboard and pointer
access to the uncertainty record.

## Search and filtering

Search matches supplied field, dataset, URN, and platform labels. Platform and
compatibility controls filter already-loaded presentation records. An empty
display-filter result is distinct from a missing or invalid certified graph,
and it explicitly states that the underlying graph is unchanged.

## Accessibility

Current/Future/Diff controls expose `aria-pressed`; search and filters have
labels; zoom and fit controls have accessible names; nodes and edges remain
focusable; status meaning is repeated in text; selection is represented in a
semantic complementary inspector; keyboard focus remains visible. At narrow
widths, the inspector moves beneath the canvas and controls wrap.

## Security

The browser calls only the read-only presentation API. It never reads
repository artifacts or connects to DataHub. Production code contains no graph
fixture or fallback payload. DTOs bound provenance references and exclude
secrets, local filesystem paths, raw queries, tracebacks, and internal loader
state.

## No-reasoning audit

The frontend contains no DFS, BFS, lineage discovery, blast-radius
calculation, compatibility propagation, impact propagation, severity
derivation, disposition rule, or path classification. Dagre performs layout
only. Current/Future/Diff semantics, compatibility, uncertainty, and path
membership arrive explicitly in the API DTO.

## Verification

All gates passed on 2026-07-28:

| Gate | Result |
| --- | --- |
| Graph presentation API focused tests | 32 passed |
| All presentation API tests | 57 passed |
| Graph workspace interaction tests | 34 passed |
| Graph Zod contract tests | 23 passed |
| Graph API client tests | 6 passed |
| Complete frontend suite | 108 passed |
| Frontend TypeScript | passed with `strict: true` |
| Frontend lint | passed with no warnings |
| Next.js optimized production build | passed |
| Existing unit suite | 773 passed |
| Existing certification suite | 240 passed, 1 skipped |
| Existing integration suite | 6 skipped by their environment gates |
| Total Python | 1,070 passed, 7 skipped |

The total Python count is 1,077 executed tests including the seven
environment-gated skips. No Phase 1-4 or Phase 5.1 regression was observed.

## Rendered runtime verification

The built application and local API were inspected together in a real browser.
The Future view rendered 26 nodes and 27 edges with one explicit `UNKNOWN`
root label and no console errors. Current rendered 26 nodes and 27 edges with
only `order_total` active. Diff rendered 27 nodes and 28 edges with both
`order_total` and `order_amount`. The root inspector displayed all four
certified missing-evidence records.

## Known limitations

- At fit-to-view scale, the complete 26-node graph prioritizes overall
  topology; users must zoom for detailed node labels.
- Search and filters are presentation-only and do not request a reduced graph
  from the server.
- Detailed traversal of the 66 context assets is intentionally deferred to
  Phase 5.3.
- Only the frozen `CHRONOS-DEMO-001` review is supported.

## Warnings

- FastAPI currently emits the existing Starlette `TestClient` deprecation
  warning about the transition from `httpx` to `httpx2`; tests and runtime
  behavior are unaffected.
- The six live DataHub integration tests and one live reconstruction
  certification test remain skipped unless their explicit environment gates
  are enabled.

## Explicitly not implemented

- Phase 5.3 impact/context exploration;
- repair UI or repair recommendations;
- proposal entry or approval workflow;
- metadata writes;
- frontend reasoning or traversal;
- production mock or fallback graph data.
