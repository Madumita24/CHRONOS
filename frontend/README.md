# CHRONOS Certified Review Frontend

This workspace is the Phase 5.1 read-only review client. It uses Next.js App
Router, React, strict TypeScript, and Zod. The browser does not read artifacts,
connect to DataHub, traverse lineage, or evaluate decision rules.

## Data boundary

The client calls:

```text
GET http://127.0.0.1:8000/api/reviews/CHRONOS-DEMO-001
```

`NEXT_PUBLIC_CHRONOS_API_BASE_URL` can override the local API origin. Copy the
shape in `.env.example` when a local override is needed. There is no production
mock or fallback payload.

Every successful response is parsed through the strict Zod schema in
`lib/review-contract.ts`. Unknown fields, a non-certified status, inconsistent
check counts, malformed identities, incorrect Phase 5.1 decision semantics, or
invalid path counts close the client integrity gate.

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

The review route renders one of four states:

- loading;
- valid certified review;
- presentation-service transport error;
- certification or response-contract integrity error.

Integrity failures never render stale or fabricated review data.

## Phase boundary

The cards under “Representative dependency paths” are certified textual
evidence summaries. They are not a graph visualization. Interactive lineage
rendering remains Phase 5.2 work.
