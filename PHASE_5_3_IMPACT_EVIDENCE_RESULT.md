# CHRONOS Phase 5.3 Impact & Evidence Result

## Result

Phase 5.3 is implemented and verified for `CHRONOS-DEMO-001`.

The existing `/review` experience now combines:

- the Phase 5.1 certified review;
- the Phase 5.2 Current/Future/Diff field-lineage graph;
- a Phase 5.3 Impact & Evidence Explorer;
- one coordinated node, edge, or path selection state.

The implementation stops at explanation and inspection. It does not implement
repair planning, repair execution, proposal mutation, metadata writes, or
Phase 5.4 behavior.

## Certified endpoint

```text
GET /api/reviews/CHRONOS-DEMO-001/explorer
```

The endpoint is gated by the exact Phase 4 certification fingerprint:

```text
sha256:3e8444ec904e0ba1c55c5ae22d69edfa8e722310f51ab30fc783b8175a87ac4a
```

It loads the current snapshot, future graph, dependency propagation,
compatibility, explanations, technical impact, business context, severity,
and impact synthesis through their public loaders. Certified file identities,
semantic fingerprints, predecessor fingerprints, demonstration ID, and
proposal ID are checked before a response is returned.

Missing, corrupt, tampered, inconsistent, or contract-invalid data fails
closed. The API returns a stable error without local paths, tracebacks, raw
artifacts, secrets, or fallback metadata.

## Canonical result exposed

| Certified quantity | Value |
|---|---:|
| Downstream fields | 25 |
| Downstream datasets | 20 |
| Dependency paths | 48 |
| Structural relationships | 27 |
| Connected context assets | 66 |
| Context relationships | 211 |
| Field-to-context mappings | 257 |
| Root causes | 1 |
| Blocking questions | 1 |
| Required evidence classes | 4 |
| Confirmed downstream failures | 0 |

Relationship compatibility remains:

- `UNKNOWN`: 1;
- `CONDITIONALLY_COMPATIBLE`: 26;
- `COMPATIBLE`: 0;
- `INCOMPATIBLE`: 0.

Field severity if realized remains 3 high, 6 moderate, and 16 low. Dataset
severity if realized remains 3 high, 4 moderate, and 13 low.

The change-level interpretation remains:

- disposition: `HOLD_FOR_REVIEW`;
- decision certainty: `HIGH_CONFIDENCE`;
- technical certainty: `UNRESOLVED`;
- technical consequence: `UNRESOLVED_IMPACT`;
- severity if realized: `HIGH`;
- breadth: `WIDESPREAD`;
- contextual criticality: `ELEVATED_CONTEXT`;
- sensitivity: `PII`;
- explicit business criticality: absent.

## Root cause and required evidence

The explorer presents the one certified shared root cause:

```text
technical-impact-cause-source-rename-semantics
```

It shows the proposed PostgreSQL `order_amount` source field, the projected
first downstream S3 `order_total` dependency, `UNKNOWN` compatibility,
`INSUFFICIENT` evidence, 25 technically unresolved fields, and zero confirmed
failures.

The blocking question and four certified evidence requirements are exposed:

- Spark transformation configuration;
- input-column reference query or code;
- explicit rename mapping;
- validated execution result.

Required evidence is explicitly labelled unavailable and required. The
interface does not imply that CHRONOS has observed it.

## User experience

The explorer remains on `/review` and provides:

- a persistent root-cause banner and causal presentation chain;
- the blocking question and certified scope totals;
- searchable field, dataset, path, relationship, context, evidence, and
  decision views;
- a persistent detail pane, including dataset and context linkage detail;
- certified field/dataset severity distributions and field filters for
  platform, exposure, depth, severity, technical state, and path multiplicity;
- distinct observed, counterfactual, derived, missing, and decision evidence
  labels;
- explicit separation between decision certainty and technical certainty;
- explicit wording that unresolved technical impact is not confirmed failure;
- loading, transport-error, integrity-error, and search-empty states;
- responsive layouts for desktop, tablet, and narrow screens.

Selecting a field highlights its future graph node. Selecting a path
highlights its API-supplied nodes and edges. Selecting a relationship
highlights its future graph edge. Dataset and context selections open their
certified scope and linkage detail without inventing a graph object. Selecting
a current graph node opens the corresponding impact detail by exact machine
identity.

Search filters only records already present in the certified response. It
does not query DataHub or calculate new scope.

## No-reasoning boundary

The presentation service performs only certified loading, identity joins,
formatting, bounded reference selection, strict validation, and serialization.
It does not import or call graph builders, traversal, dependency propagation,
compatibility evaluation, technical impact analysis, business context
propagation, severity analysis, impact synthesis, or repair logic.

The browser performs display filtering, selection, layout, and highlighting.
It contains no DFS/BFS, lineage inference, compatibility propagation, impact
derivation, severity derivation, business criticality inference, or decision
logic.

## Verification

All release gates passed:

| Gate | Result |
|---|---:|
| Phase 5.3 backend/API tests | 38 passed |
| All presentation/API tests | 95 passed |
| Phase 5.3 frontend contract, API, and interaction tests | 62 passed |
| All frontend tests | 170 passed |
| Python unit tests | 773 passed |
| Certification tests | 240 passed, 1 skipped |
| TypeScript | passed |
| ESLint | passed |
| Next.js production build | passed |

The production build prerendered `/`, `/_not-found`, and `/review`
successfully.

## Main implementation files

- `src/chronos/presentation/explorer_models.py`
- `src/chronos/presentation/explorer_service.py`
- `src/chronos/presentation/api.py`
- `tests/api/test_explorer_api.py`
- `frontend/lib/explorer-contract.ts`
- `frontend/components/explorer/impact-evidence-explorer.tsx`
- `frontend/components/graph/graph-workspace.tsx`
- `frontend/app/explorer.css`
- `frontend/lib/explorer-contract.test.ts`
- `frontend/components/explorer/impact-evidence-explorer.test.tsx`

## Known constraints and risks

- The certified explorer response is approximately 0.9 MB for the frozen
  demonstration because all 257 mappings and 211 context relationships are
  intentionally inspectable. Pagination is not introduced in this phase.
- Review, graph, and explorer are separate read-only HTTP responses. Each is
  independently certification-gated, but the browser does not receive them in
  one atomic HTTP envelope.
- The experience is intentionally limited to the frozen
  `CHRONOS-DEMO-001` review.
- Context connectivity does not prove breakage, impact, importance, or
  business criticality.
- `HOLD_FOR_REVIEW` does not prove Spark execution failure.

## Phase boundary

Phase 5.3 is complete. Phase 5.4 has not started.
