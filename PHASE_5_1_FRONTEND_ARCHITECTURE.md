# CHRONOS Phase 5.1 Frontend Architecture

## Status and scope

This document records the repository inspection and the architecture selected
for Phase 5.1 before implementation. It covers only the certified read-only
presentation boundary and the initial change-review application shell. Graph
visualization, repair workflows, proposal entry, write APIs, and new decision
logic are explicitly outside this phase.

## Existing repository

The repository currently has one Python package rooted at `src/chronos`, a
`unittest` suite under `tests`, immutable JSON artifacts under `artifacts`, and
phase reports at the repository root. It has no frontend, HTTP framework,
JavaScript package, or existing web-service convention.

The relevant certified public interfaces are:

- `chronos.phase4_certification.load_phase4_certification`
- `chronos.phase4_certification.validate_phase4_certification`
- `chronos.impact_synthesis.load_impact_synthesis`
- `chronos.impact_synthesis` read-only query functions
- `chronos.proposal.load_proposal`

The authoritative Phase 4 certification artifact is
`artifacts/phase_4_certification.json`. Its verified semantic fingerprint is
`sha256:3e8444ec904e0ba1c55c5ae22d69edfa8e722310f51ab30fc783b8175a87ac4a`.
It certifies the supporting `impact_synthesis.json` and
`change_proposal.json` semantic fingerprints.

## Selected architecture

### Python presentation boundary

A new `chronos.presentation` package provides:

- immutable presentation DTOs;
- a repository-root-independent artifact loader;
- a certification gate;
- a deterministic mapper that selects and formats already-certified facts;
- a small FastAPI application with one review endpoint and one health
  endpoint.

The mapper may select, join, label, and format certified records. It may not
evaluate compatibility, severity, breadth, criticality, or disposition. Those
values must be copied from the certified Phase 4 artifacts.

### Web client

A new `frontend` workspace uses Next.js App Router, React, strict TypeScript,
and Zod. The first route is `/review`, with `/` redirecting to it.

The browser calls the presentation endpoint and validates the entire response
with Zod before rendering it. It never reads repository artifacts, calls
DataHub, traverses a graph, or applies decision rules.

### Development topology

```text
Browser :3000
  -> GET http://127.0.0.1:8000/api/reviews/CHRONOS-DEMO-001
FastAPI presentation service :8000
  -> public Python deserializers
  -> Phase 4 certification gate
  -> certified artifact selection and formatting
  -> CertifiedChangeReview JSON
```

The API permits the local Next.js origins through a narrow CORS policy.
`CHRONOS_ARTIFACT_DIR` may override the artifact directory for tests or local
operation. No production mock or fallback data path exists.

## Certification gate

Every review load must:

1. Deserialize the Phase 4 certification through its public loader.
2. Require `certification_status == certified`.
3. Require the fixed Phase 5.1 certification fingerprint.
4. Require every certification check to pass.
5. Deserialize the proposal and impact-synthesis artifacts through their
   public loaders.
6. Match their semantic fingerprints to the identities recorded by the
   certification artifact.
7. Match demonstration and proposal identifiers across all loaded artifacts.

Any failure becomes a stable integrity error. Missing review IDs become
not-found responses. Unexpected failures are not returned with internal paths
or stack traces.

## Presentation contract

`CertifiedChangeReview` contains:

- `certification`
- `change`
- `decision`
- `technicalSummary`
- `scopeSummary`
- `severityProfile`
- `rootCause`
- `blockingQuestions`
- `requiredEvidence`
- `representativePaths`
- `contextHighlights`
- `currentState`
- `counterfactualState`

The API uses camelCase JSON keys as a browser-facing contract. Exact machine
identifiers remain available alongside display labels. The frontend schema is
strict, so additive API changes require an intentional contract update.

## Routes and states

- `GET /health` reports only service readiness and the expected certification
  fingerprint.
- `GET /api/reviews/CHRONOS-DEMO-001` returns the certified review.
- Unknown review IDs return `404`.
- Missing or invalid artifacts return `503` with a stable integrity error.

The `/review` page has four mutually exclusive states: loading, transport
error, certification/integrity error, and valid certified review.

## Visual foundation

The interface is an engineering review surface, not a generic dashboard. The
decision and unresolved technical certainty appear together at the top so
neither can be mistaken for the other. Certified scope metrics, the single
blocking question, required evidence, paths, and connected context then follow
in a consistent card and badge system.

The component system includes status badges, metric cards, section headers,
field identities, evidence rows, and integrity notices. Focus treatments,
semantic landmarks, keyboard navigation, contrast, and responsive layouts are
part of the initial foundation.

## Test boundary

Python tests cover the gate, mapper, status codes, error redaction,
determinism, and certified values. Frontend tests cover the strict schema,
formatters, loading/error/integrity/valid states, primary content, and
accessibility landmarks. The release gate also runs Python regression tests,
TypeScript checking, lint, frontend tests, and the Next.js production build.
