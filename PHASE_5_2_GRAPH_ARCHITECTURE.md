# CHRONOS Phase 5.2 Graph Architecture

## Scope

Phase 5.2 extends the Phase 5.1 certified presentation boundary with an
interactive current-versus-counterfactual field-lineage graph. It does not
retrieve metadata, traverse DataHub, recompute lineage, evaluate compatibility,
propagate impact, derive severity, derive disposition, or generate repairs.

## Existing foundation

Phase 5.1 remains the application shell and trust boundary:

- `chronos.presentation` loads certified artifacts through public
  deserializers;
- the Phase 4 certification fingerprint is fixed at
  `sha256:3e8444ec904e0ba1c55c5ae22d69edfa8e722310f51ab30fc783b8175a87ac4a`;
- FastAPI exposes browser-facing DTOs;
- Next.js, strict TypeScript, and Zod validate the browser contract;
- `/review` remains the review route.

Phase 5.2 adds a graph endpoint and graph workspace inside that route. It does
not replace the Phase 5.1 review content or its error states.

## Certified artifact sources

The graph presentation service may select and join records from:

- `current_metadata_snapshot.json`;
- `counterfactual_source_state.json`;
- `future_metadata_graph.json`;
- `dependency_propagation.json`;
- `compatibility_evaluation.json`;
- `technical_impact_analysis.json`;
- `impact_synthesis.json`.

Every artifact is loaded through its public Python deserializer and its semantic
fingerprint must match the input identity frozen in the Phase 4 certification.
The service also verifies the predecessor fingerprint chain between the
snapshot, future graph, propagation, compatibility, and synthesis records.

## Graph presentation contract

`GET /api/reviews/CHRONOS-DEMO-001/graph` returns
`CertifiedGraphReview`, containing:

- certification identity;
- source-change context;
- complete current, future, and diff projections;
- 26 current-to-future identity mappings;
- one root-uncertainty record;
- all 48 certified supporting paths;
- three certified representative-path shortcuts;
- concise legend tokens;
- frozen summary metrics.

The DTO exposes intentional node, edge, path, and provenance fields rather than
raw artifact payloads. Pydantic validation rejects duplicate IDs, dangling
endpoints, dangling path references, incorrect canonical counts, an invalid
source replacement, a non-unknown root boundary, or incompatible certified
totals.

## Projection semantics

### Current

The current projection contains the 26 observed snapshot field nodes and 27
observed lineage edges. Its source is PostgreSQL `orders.order_total`;
`orders.order_amount` is absent. Compatibility and future technical-impact
states are null because they do not describe the observed graph.

### Future

The future projection contains the 26 active Future Graph fields and 27
structural relationships. Its source is PostgreSQL `orders.order_amount`;
the former source identity is absent. The 25 downstream field identities are
preserved. Compatibility, exposure, technical-impact, path participation, and
provenance values are copied from certified Phase 3 and Phase 4 records.

### Diff

The diff projection is a presentation composition supplied by the API. It
contains the removed current source identity, the added future source identity,
the 25 identity-preserved downstream nodes, the removed current source edge,
and all 27 future relationships. Diff state is explicit in the DTO; the browser
does not compare field names or derive differences.

## Root uncertainty

The root relationship is the certified projected boundary:

```text
PostgreSQL orders.order_amount
  -> S3 orders.order_total
```

Its compatibility is `unknown`, evidence strength is `insufficient`, and reason
code is `source_rename_semantics_unknown`. The selected-edge inspector also
receives the paired current relationship and the four certified missing
evidence records. `Unknown` is never displayed as `incompatible`.

## Library and layout

The frontend uses `@xyflow/react` for pan, zoom, fit, selection, custom nodes,
custom edges, and keyboard support. It uses `@dagrejs/dagre` only for
deterministic left-to-right presentation layout. Dagre receives already-loaded
nodes and edges; it does not discover lineage, compatibility, impact, or paths.

The same projection and filters always produce the same positions. Nodes remain
shared in the DAG, including multipath nodes; the UI never duplicates a node
for each path.

## Interaction model

The graph workspace provides:

- Current, Future, and Diff mode controls;
- field, dataset, and platform search over loaded DTO nodes;
- minimal platform and compatibility filters;
- built-in zoom, fit, and pan controls;
- reset selection;
- node and edge selection;
- three representative-path shortcuts;
- path highlighting using API-supplied ordered node and edge IDs;
- a persistent inspector for summary, node, edge, or path details.

Selecting a node or edge exposes its certified `supportingPathIds`; choosing
one of those IDs highlights the matching already-loaded path DTO. No DFS, BFS,
shortest-path, blast-radius, compatibility propagation, or severity rule exists
in React.

## Visual semantics

Text labels accompany every color and line treatment:

| Presentation state | Meaning |
| --- | --- |
| Certified current | Observed snapshot identity |
| Counterfactual changed | Proposed source identity |
| Counterfactual unresolved | Future identity reached through unresolved evidence |
| Counterfactual inherited | Structurally retained future identity |
| Source changed | Change origin |
| Directly exposed | First downstream field |
| Transitively exposed | Reached beyond the direct boundary |
| Multipath exposed | Supported by more than one certified path |
| Unknown | Evidence cannot establish compatibility |
| Conditionally compatible | Local continuation depends on unresolved upstream evidence |
| Incompatible | Certified incompatibility; currently zero relationships |

## Accessibility and responsive behavior

React Flow nodes and edges remain keyboard-focusable and selectable. All graph
controls have visible labels, status meaning is textual, selection is repeated
in a semantic inspector, and focus indicators remain visible. Desktop is the
primary target; at narrower widths the inspector moves below the graph while
controls and search remain available.

## Failure behavior

The graph route has distinct transport, certification-integrity,
contract-invalid, empty-graph, and selected-path-missing states. It never
renders mock or stale production data. Phase 5.1 remains usable if the graph
endpoint is unavailable, while the graph itself is clearly marked unavailable.

## Run and verify

Start the certified presentation API from the repository root:

```powershell
.\.venv-datahub-310\Scripts\python.exe -m chronos.presentation
```

Start the frontend from a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000/review`. The graph contract is available at
`GET http://127.0.0.1:8000/api/reviews/CHRONOS-DEMO-001/graph`.

Run the Phase 5.2 and regression gates:

```powershell
.\.venv-datahub-310\Scripts\python.exe -m unittest discover -s tests\api -v
.\.venv-datahub-310\Scripts\python.exe -m unittest discover -s tests\unit
.\.venv-datahub-310\Scripts\python.exe -m unittest discover -s tests\certification
.\.venv-datahub-310\Scripts\python.exe -m unittest discover -s tests\integration

cd frontend
npm test
npm run typecheck
npm run lint
npm run build
```
