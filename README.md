# CHRONOS

Current completed presentation phase: **Phase 5.5 - Demo Polish & UX Hardening**.

Phase 6.1 adds a separate reusable backend structural-change engine for
`FIELD_RENAME`, `FIELD_DELETE`, and `FIELD_TYPE_CHANGE`. It consumes a frozen
DataHub-derived snapshot, creates an isolated certified analysis package, and
preserves the Phase 1-5 golden fixture and frontend behavior.

Phase 6.2 adds a separate deterministic semantic SQL/dbt change engine for one
logical model. It compares parser-normalized BEFORE/AFTER SQL, resolves exact
DataHub model and field identities from the supplied snapshot, detects
aggregation, filter, join, expression, and structural output deltas, and
certifies an isolated 18-artifact analysis package. It never executes SQL or
Jinja, queries or writes DataHub, generates repairs, or changes the frontend.

Phase 6.3 adds deterministic analysis for one coordinated multi-file
BASE-to-HEAD repository transition. It supports safe local Git ranges and
offline PR bundles, bounded SQL/dbt/YAML/JSON/Python-AST parsing, exact
cross-file correlation, coherence/conflict detection, a composite Future
Graph, multi-root propagation, and a certified 26-artifact PR decision. It
does not execute repository code or generate repairs.

Phase 6.4 adds deterministic, isolated repair-candidate generation from one
complete certified Phase 6.3 package and its exact repository bundle. It
classifies repairability, creates a typed Repair Plan, uses registered
parser-aware editors, emits review-only patches and previews, and reruns Phase
6.3 as a static projection. It never applies a patch, executes analyzed code,
certifies runtime correctness, modifies DataHub, commits, or pushes.

Phase 6.5 adds an independent release-certification gate over the complete
Phase 6 chain. It replays all final fixtures twice, validates cross-phase trust,
golden fingerprints, vocabulary and dimension separation, determinism,
portability, security, tamper handling, test evidence, and release readiness.
It adds no analysis feature, frontend, patch application, or runtime claim.

CHRONOS has a read-only engineering review surface for the frozen
`CHRONOS-DEMO-001` result. The review now includes a certified, interactive
Current/Future/Diff field-lineage graph and a coordinated Impact & Evidence
Explorer. The explorer exposes certified field, dataset, path, relationship,
context, evidence, root-cause, and decision records and synchronizes field,
path, and relationship selection with the graph. Its records come from a
Python presentation API that fails closed unless the Phase 4 certification
and supporting artifacts pass their public deserializers and fingerprint
checks. Phase 5.5 makes the proposed field rename, dataset identity,
uncertainty boundary, evidence gap, and `HOLD FOR REVIEW` decision legible in
a short demo without changing certified analytical values.

The browser does not traverse lineage or derive compatibility, impact,
severity, or disposition. It calls only the three read-only CHRONOS
presentation endpoints. Direct DataHub access, repair workflow, proposal
entry, approval controls, and metadata writes remain out of scope.

## Run locally

Install the Python package into the existing project environment:

```powershell
.\.venv-datahub-310\Scripts\python.exe -m pip install -e .
```

Start the certified presentation API:

```powershell
.\.venv-datahub-310\Scripts\python.exe -m chronos.presentation
```

The API is available at `http://127.0.0.1:8000`, with the review endpoint at
`/api/reviews/CHRONOS-DEMO-001`, graph endpoint at
`/api/reviews/CHRONOS-DEMO-001/graph`, explorer endpoint at
`/api/reviews/CHRONOS-DEMO-001/explorer`, health at `/health`, and interactive
API documentation at `/api/docs`.

In a second terminal, start the frontend:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000/review`.

Before a demo, confirm that `http://127.0.0.1:8000/health` reports `ready`,
open the review in a fresh browser tab, and follow [DEMO_CHECKLIST.md](DEMO_CHECKLIST.md).

## Demo story

The frozen scenario is a PostgreSQL field rename inside the unchanged
`orders` dataset:

`orders.order_total` → `orders.order_amount`

CHRONOS shows zero confirmed downstream failures, one technically unresolved
Spark export boundary, 25 technically unresolved downstream fields across 20
datasets and 48 certified paths, missing execution evidence, and a
high-confidence disposition of `HOLD FOR REVIEW`. This is a request for
evidence review, not a claim that the change has failed.

The judge-ready sequence is documented in
[PHASE_5_DEMO_WALKTHROUGH.md](PHASE_5_DEMO_WALKTHROUGH.md).

## Validate

```powershell
.\.venv-datahub-310\Scripts\python.exe -m unittest discover -s tests\api -v
.\.venv-datahub-310\Scripts\python.exe -m unittest discover -s tests\unit
.\.venv-datahub-310\Scripts\python.exe -m unittest discover -s tests\certification
.\.venv-datahub-310\Scripts\python.exe -m unittest discover -s tests\integration

cd frontend
npm run typecheck
npm run lint
npm test
npm run build
```

## Generalized structural analysis

See [the Phase 6.1 developer guide](PHASE_6_1_DEVELOPER_GUIDE.md) for the
Python and CLI entry points and the three strict JSON proposal examples. The
engine does not query or write DataHub, parse SQL/dbt, ingest pull requests,
or generate repairs.

Architecture and verification are recorded in
[PHASE_6_1_GENERALIZED_ENGINE_ARCHITECTURE.md](PHASE_6_1_GENERALIZED_ENGINE_ARCHITECTURE.md)
and `PHASE_6_1_GENERALIZED_ENGINE_RESULT.md`.

## Semantic SQL/dbt analysis

See [the Phase 6.2 developer guide](PHASE_6_2_DEVELOPER_GUIDE.md) for the
Python and CLI interfaces, strict proposal shape, safe dbt boundary, and four
runnable examples. The architecture and verified evidence boundary are in
[PHASE_6_2_SEMANTIC_CHANGE_ARCHITECTURE.md](PHASE_6_2_SEMANTIC_CHANGE_ARCHITECTURE.md),
with pre-change inspection in
[PHASE_6_2_SQL_SEMANTIC_INVENTORY.md](PHASE_6_2_SQL_SEMANTIC_INVENTORY.md).
Final verification, fingerprints, and exact regression totals are recorded in
[PHASE_6_2_SEMANTIC_CHANGE_RESULT.md](PHASE_6_2_SEMANTIC_CHANGE_RESULT.md).

## Multi-file pull-request analysis

See [the Phase 6.3 developer guide](PHASE_6_3_DEVELOPER_GUIDE.md) for local
Git and exported-bundle APIs, CLI usage, supported files/DAG patterns, and the
four examples. Design and evidence boundaries are documented in
[PHASE_6_3_MULTIFILE_PR_ARCHITECTURE.md](PHASE_6_3_MULTIFILE_PR_ARCHITECTURE.md),
with the inspection-first findings in
[PHASE_6_3_PR_INTAKE_INVENTORY.md](PHASE_6_3_PR_INTAKE_INVENTORY.md).
Final outcomes, fingerprints, security audit, and exact regression totals are
recorded in
[PHASE_6_3_MULTIFILE_PR_RESULT.md](PHASE_6_3_MULTIFILE_PR_RESULT.md).

## Deterministic repair candidate generation

See [the Phase 6.4 developer guide](PHASE_6_4_DEVELOPER_GUIDE.md) for the
strict proposal, Python and CLI entry points, review package, supported edit
boundary, and six deterministic examples. Design and trust boundaries are in
[PHASE_6_4_REPAIR_ARCHITECTURE.md](PHASE_6_4_REPAIR_ARCHITECTURE.md), with the
inspection-first findings in
[PHASE_6_4_REPAIR_INVENTORY.md](PHASE_6_4_REPAIR_INVENTORY.md). Final scenario
fingerprints, security checks, limitations, and exact regression totals are
recorded in [PHASE_6_4_REPAIR_RESULT.md](PHASE_6_4_REPAIR_RESULT.md).

## Complete Phase 6 certification

See [the Phase 6.5 developer guide](PHASE_6_5_DEVELOPER_GUIDE.md) for the
independent certification command, regression commands, package interpretation,
and rerun process. The trust and release-gate design is documented in
[PHASE_6_5_CERTIFICATION_ARCHITECTURE.md](PHASE_6_5_CERTIFICATION_ARCHITECTURE.md),
with inspection findings in
[PHASE_6_5_CERTIFICATION_INVENTORY.md](PHASE_6_5_CERTIFICATION_INVENTORY.md).
The final decision and evidence are in
[PHASE_6_5_CERTIFICATION_RESULT.md](PHASE_6_5_CERTIFICATION_RESULT.md) and the
machine package under `artifacts/certifications/phase-6/`.

Release scope and next-phase contracts are recorded in
[PHASE_6_RELEASE_NOTES.md](PHASE_6_RELEASE_NOTES.md),
[PHASE_6_FRONTEND_HANDOFF.md](PHASE_6_FRONTEND_HANDOFF.md), and
[PHASE_7_HANDOFF.md](PHASE_7_HANDOFF.md).

## Phase 5 documents

- [Phase 5.5 demo checklist](DEMO_CHECKLIST.md)
- [Phase 5 demo walkthrough](PHASE_5_DEMO_WALKTHROUGH.md)
- [Phase 5.5 polish audit](PHASE_5_5_POLISH_AUDIT.md)
- [Phase 5.5 polish architecture](PHASE_5_5_DEMO_POLISH_ARCHITECTURE.md)
- [Phase 5.5 verification result](PHASE_5_5_DEMO_POLISH_RESULT.md)
- [Phase 5.3 impact and evidence architecture](PHASE_5_3_IMPACT_EVIDENCE_ARCHITECTURE.md)
- [Phase 5.3 verification result](PHASE_5_3_IMPACT_EVIDENCE_RESULT.md)
- [Phase 5.4 change review architecture](PHASE_5_4_CHANGE_REVIEW_ARCHITECTURE.md)
- [Phase 5.4 verification result](PHASE_5_4_CHANGE_REVIEW_RESULT.md)
- [Phase 5.2 graph architecture](PHASE_5_2_GRAPH_ARCHITECTURE.md)
- [Phase 5.2 verification result](PHASE_5_2_FUTURE_GRAPH_UI_RESULT.md)
- [Architecture](PHASE_5_1_FRONTEND_ARCHITECTURE.md)
- [Verification result](PHASE_5_1_FRONTEND_FOUNDATION_RESULT.md)
- [Frontend operating notes](frontend/README.md)
- [Phase 4 certification](PHASE_4_CERTIFICATION_RESULT.md)
- [Authoritative certification artifact](artifacts/phase_4_certification.json)

## Troubleshooting

- **Frontend says the review service is unavailable:** start
  `python -m chronos.presentation` in the project virtual environment and
  verify `/health`.
- **Certified review is withheld:** do not bypass the message. Restore the
  Phase 4 certified artifacts and rerun certification; the UI intentionally
  has no fallback analytical data.
- **Graph or explorer alone is unavailable:** the corresponding feature is
  isolated. The certified overview remains usable while that read-only
  endpoint is diagnosed.
- **Port already in use:** identify the process already listening on port
  `8000` or `3000`; do not start duplicate demo servers.
- **Stale browser state:** use **Reset review** or reload `/review`. Display
  filters never alter the certified result.
