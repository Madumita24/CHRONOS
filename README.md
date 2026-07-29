# CHRONOS

Current completed phase: **Phase 5.4 - Change Review Workflow**.

CHRONOS has a read-only engineering review surface for the frozen
`CHRONOS-DEMO-001` result. The review now includes a certified, interactive
Current/Future/Diff field-lineage graph and a coordinated Impact & Evidence
Explorer. The explorer exposes certified field, dataset, path, relationship,
context, evidence, root-cause, and decision records and synchronizes field,
path, and relationship selection with the graph. Its records come from a
Python presentation API that fails closed unless the Phase 4 certification
and supporting artifacts pass their public deserializers and fingerprint
checks. The browser does not traverse lineage or derive compatibility, impact,
severity, or disposition. Repair workflow, proposal entry, and metadata
writes remain out of scope.

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

## Phase 5 documents

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
