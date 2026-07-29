# CHRONOS Certified Review Frontend

This workspace is the Phase 5.3 read-only review client. It uses Next.js App
Router, React, strict TypeScript, Zod, React Flow, and Dagre. The browser does
not read artifacts, connect to DataHub, traverse lineage, or evaluate decision
rules.

## Data boundary

The client calls:

```text
GET http://127.0.0.1:8000/api/reviews/CHRONOS-DEMO-001
GET http://127.0.0.1:8000/api/reviews/CHRONOS-DEMO-001/graph
GET http://127.0.0.1:8000/api/reviews/CHRONOS-DEMO-001/explorer
```

`NEXT_PUBLIC_CHRONOS_API_BASE_URL` can override the local API origin. Copy the
shape in `.env.example` when a local override is needed. There is no production
mock or fallback payload.

Every successful response is parsed through strict Zod schemas in
`lib/review-contract.ts`, `lib/graph-contract.ts`, and
`lib/explorer-contract.ts`. Unknown fields, a non-certified status,
inconsistent check counts, malformed identities, incorrect cardinalities,
duplicate identifiers, dangling graph endpoints, or invalid certified
semantics close the relevant client integrity gate.

## Routes

- `/` redirects to `/review`.
- `/review` loads `CHRONOS-DEMO-001`.

## Commands

```powershell
npm install
npm run dev
npm run typecheck
npm run lint
npm test
npm run build
```

The development page is `http://localhost:3000/review`. The Python
presentation service must be running separately on port `8000`.

## States

The review route, graph workspace, and explorer render:

- loading;
- valid certified review;
- presentation-service transport error;
- certification or response-contract integrity error.
- a complete certified Current, Future, or Diff graph;
- distinct graph transport, integrity, and display-filter-empty states.
- the one certified shared root cause and blocking question;
- searchable field, dataset, path, relationship, context, evidence, and
  decision views;
- coordinated graph and explorer selection;
- distinct explorer loading, transport, integrity, and search-empty states.

Integrity failures never render stale or fabricated review data.

## Phase boundary

Graph modes, path highlighting, explorer search, filters, selection, and
layout operate only on API-supplied presentation records. No browser-side
DFS/BFS, lineage discovery, compatibility propagation, severity derivation,
decision logic, or repair UI is present. Phase 5.4 repair work has not begun.
