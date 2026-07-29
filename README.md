# CHRONOS

Current completed phase: **Phase 5.1 — Frontend Foundation and Certified
Presentation Contract**.

CHRONOS now has a read-only engineering review surface for the frozen
`CHRONOS-DEMO-001` result. The browser consumes a strict presentation DTO from
a Python API that fails closed unless the Phase 4 certification and its
supporting artifacts pass their public deserializers and fingerprint checks.
No Phase 5.2 graph visualization, repair workflow, proposal entry, metadata
write, or browser-side decision logic is included.

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
`/api/reviews/CHRONOS-DEMO-001`, health at `/health`, and interactive API
documentation at `/api/docs`.

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

## Phase 5.1 documents

- [Architecture](PHASE_5_1_FRONTEND_ARCHITECTURE.md)
- [Verification result](PHASE_5_1_FRONTEND_FOUNDATION_RESULT.md)
- [Frontend operating notes](frontend/README.md)
- [Phase 4 certification](PHASE_4_CERTIFICATION_RESULT.md)
- [Authoritative certification artifact](artifacts/phase_4_certification.json)
