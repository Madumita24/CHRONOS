# CHRONOS Phase 6 Frontend Integration Developer Guide

## Prerequisites

- The repository root contains `certified_packages/phase6` and
  `artifacts/certifications/phase-6-rerun`.
- The Python environment can import the local `chronos` package.
- Node dependencies are installed in `frontend`.

The presentation API performs integrity validation on first access. Do not
edit retained packages, release artifacts, manifests, or fingerprints to make
the UI accept a payload.

## Run locally

From the repository root, start the read-only presentation API:

```powershell
.\.venv-datahub-310\Scripts\python.exe -m uvicorn `
  chronos.presentation.api:app --host 127.0.0.1 --port 8000
```

In a second terminal:

```powershell
Set-Location frontend
npm.cmd run dev
```

Open `http://localhost:3000/analyses`. The existing Phase 5 demo remains at
`http://localhost:3000/review`.

To use another API origin, set `NEXT_PUBLIC_CHRONOS_API_URL` before starting
Next.js. The default is `http://127.0.0.1:8000`.

## Validate

Focused backend presentation tests:

```powershell
.\.venv-datahub-310\Scripts\python.exe -m unittest `
  tests/api/test_phase6_presentation_api.py -v
```

All API tests:

```powershell
.\.venv-datahub-310\Scripts\python.exe -m unittest discover `
  -s tests/api -p "test_*.py"
```

Frontend validation:

```powershell
Set-Location frontend
npm.cmd run typecheck
npm.cmd run lint
npm.cmd test -- --run
npm.cmd run build
```

## Contract change workflow

1. Change the backend DTO and mapper without weakening the certified-package
   gates.
2. Add a focused backend integrity or mapping test.
3. Change the strict Zod contract and its fixture.
4. Add a component or contract test for success and failure behavior.
5. Run the focused and full checks above.
6. Verify `/review` remains unchanged.

Do not add request-time calls to the structural, semantic, pull-request, or
repair engines. A newly retained analysis requires an explicit backend
registry entry and matching Phase 6.5 replay evidence; a client-provided path
is never acceptable.

## Main files

- `src/chronos/presentation/phase6_models.py`: strict browser-facing DTOs.
- `src/chronos/presentation/phase6_service.py`: release and package integrity
  gates plus bounded mapping.
- `src/chronos/presentation/api.py`: read-only routes and bounded errors.
- `frontend/lib/phase6-contract.ts`: strict browser schemas.
- `frontend/lib/phase6-api.ts`: no-store fetch and contract validation.
- `frontend/components/phase6`: selector and analysis views.
- `frontend/app/analyses`: App Router entries.
- `frontend/app/phase6.css` and `phase6-path.css`: responsive and graph/patch
  presentation.

## Troubleshooting

- A 404 means the analysis or patch ID is not in the fixed registry/package.
- A 503 means certification or retained-package integrity validation failed.
  Inspect the server log locally; the response intentionally stays generic.
- A browser contract error means the API response did not match the strict Zod
  contract. Do not coerce or ignore the field.
- If a patch is wide on a phone, it should scroll inside its preview. A page-
  level horizontal scrollbar is a regression.
