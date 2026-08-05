# CHRONOS Phase 6 Frontend Handoff

## Purpose

This contract defines how a future frontend integration may present Phase 6
results. Phase 6.5 does not implement or redesign the frontend.

## Trust boundary

The frontend must consume only a complete certified manifest and its validated
artifacts through a read-only presentation adapter. It must fail closed when
the package, identity, fingerprint, certification state, or supported schema is
invalid.

Raw repository files, SQL, YAML, DAG code, and patch application are not
frontend inputs. Static projected state must always be labeled as projected
and runtime-unverified.

## Permitted presentation

A future UI may display:

- analysis selector and certified analysis type;
- structural deltas;
- semantic deltas;
- changed files and parser status;
- repository coherence;
- conflicts and competing identities;
- Future Graph records supplied by the backend;
- root causes, paths, evidence, and uncertainty;
- PR disposition;
- Repair Plan and repairability classifications;
- candidate patch hunks and file previews;
- projected repair-scope coherence;
- remaining findings and required validation;
- certification state, limitations, and fingerprints.

All labels must preserve the vocabulary and dimension distinctions certified
in Phase 6.5.

## Prohibited frontend behavior

The frontend must not:

- parse SQL, dbt, YAML/JSON, Python, Git, or repositories;
- resolve DataHub entities;
- compute graph paths or lineage;
- derive structural or semantic compatibility;
- correlate cross-file changes;
- generate root causes, severity, or decisions;
- classify or generate repairs;
- apply a patch;
- execute project code;
- choose between conflicting identities;
- call `STATIC_PROJECTED` or `PROJECTED_POST_REPAIR` verified;
- claim runtime correctness, business approval, or merge safety;
- write to DataHub or source control.

## Suggested read model

The presentation adapter should validate `manifest.json` first, then expose a
bounded view derived from the capability matrix, PR/repair manifests, replayed
evidence, patch records, projected comparison, remaining findings, and release
certification. It should transmit no absolute local paths or credentials.

The existing Phase 5 `CHRONOS-DEMO-001` endpoints remain unchanged. Phase 6
integration should be additive and must not reinterpret the frozen Phase 4
certification as a generalized Phase 6 package.

## UX requirements

Every projected or uncertain record needs a visible evidence label. No-patch
and conflict-blocked outcomes are valid results and need explicit empty states.
The user must be able to see which roots were addressed, which remain, why a
repair was blocked, and what Phase 7 evidence is still required.

No approval, apply, execute, commit, or push control is authorized by this
handoff.
