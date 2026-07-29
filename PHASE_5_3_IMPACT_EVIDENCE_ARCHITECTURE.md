# CHRONOS Phase 5.3 Impact & Evidence Architecture

## Purpose

Phase 5.3 extends the certified review and Phase 5.2 graph with one coordinated
Impact & Evidence Explorer. Its job is to answer why a selected field,
relationship, dataset, path, or context asset appears in the certified result.
It presents existing certified reasoning; it does not run that reasoning again.

The experience stays on `/review` and follows:

```text
Graph selection
  -> impact
  -> evidence
  -> connected context
  -> shared root cause
  -> certified HOLD FOR REVIEW explanation
```

## Certification boundary

`GET /api/reviews/CHRONOS-DEMO-001/explorer` uses the existing
`CertifiedArtifactLoader` and exact Phase 4 certification fingerprint:

```text
sha256:3e8444ec904e0ba1c55c5ae22d69edfa8e722310f51ab30fc783b8175a87ac4a
```

The service loads every contributor through its public deserializer and checks
its semantic fingerprint against the identity frozen in Phase 4. It also
validates predecessor fingerprints and cross-artifact IDs. Missing, corrupt,
tampered, or inconsistent inputs fail closed.

## Certified inputs

The explorer selects and joins presentation facts from:

- `current_metadata_snapshot.json`;
- `future_metadata_graph.json`;
- `dependency_propagation.json`;
- `compatibility_evaluation.json`;
- `explanation_bundle.json`;
- `technical_impact_analysis.json`;
- `business_context_propagation.json`;
- `severity_criticality_analysis.json`;
- `impact_synthesis.json`.

The explorer reuses the Phase 5.2 `CertifiedGraphReview` IDs so graph and
explorer records have one synchronization vocabulary.

## Presentation contract

`CertifiedImpactExplorer` contains:

- certification and canonical summary;
- the single root cause and its fixed presentation chain;
- the single blocking question;
- four required-evidence records;
- structured observed, counterfactual, missing, and decision evidence;
- 25 downstream field-impact records;
- 20 dataset-impact records;
- 66 connected context-asset records;
- 211 compact context-relationship references;
- 257 compact field-to-context mappings;
- 48 certified path details;
- 27 future relationship details;
- the certified decision explanation and certainty distinctions.

The DTO intentionally excludes raw artifacts, rule registries, credentials,
local paths, tracebacks, private configuration, and unbounded provenance.

## Impact model

Field and dataset records join by exact machine identity. Technical impact,
certainty, reason codes, depth, exposure, supporting paths, severity if
realized, criticality, breadth, sensitivity, root cause, context mappings, and
provenance are copied from their certified records.

`HIGH` is always labelled “severity if realized.” `PII` is sensitivity, not a
severity rule. `ELEVATED_CONTEXT` is contextual criticality; explicit business
criticality remains absent.

## Evidence model

Evidence records preserve:

- source class and source artifact;
- observed versus counterfactual versus missing versus decision
  classification;
- subject and supported claim;
- verification state;
- human-readable description;
- bounded machine references in expandable detail.

The evidence chain is selected from certified explanation steps and decision
evidence. Unresolved records never receive a verified check state.

## Context semantics

The contract preserves three different certified quantities:

- 66 unique connected context assets;
- 211 scoped context relationships;
- 257 field-to-context mappings.

Context assets are grouped for presentation into governance, operational, and
consumer sections while retaining their exact certified category and asset
type. “Connected” never implies broken, impacted, at risk, or mission critical.

## Selection synchronization

The graph workspace owns the single selection state for node, edge, and path.
Explorer tables and lists emit the same graph node, edge, or path IDs.
Selection from either surface updates the shared state and the graph highlight.
Dataset and context selections use additional variants of that same selection
state and open their certified detail. They do not highlight a graph object
because neither record corresponds to one field-lineage node or edge.

The frontend does not calculate reachability or path membership. Highlighting
uses API-supplied ordered node and edge IDs.

## Observed versus counterfactual evidence

Observed evidence describes current DataHub schema and lineage.
Counterfactual evidence describes CHRONOS future-graph derivations.
The root chain explicitly shows:

```text
observed order_total
  -> proposed order_amount
  -> projected order_amount to S3.order_total
  -> compatibility UNKNOWN
  -> evidence INSUFFICIENT
  -> 25 fields technically unresolved
  -> HIGH severity if realized / WIDESPREAD reach
  -> HOLD FOR REVIEW
```

These are supplied certified facts, not executable frontend rules.

## Certainty semantics

Decision certainty and technical certainty remain independent:

- decision certainty: `HIGH_CONFIDENCE`;
- technical certainty: `UNRESOLVED`.

The interface states that CHRONOS is highly confident review must be held
because compatibility is unresolved. It does not imply Spark will fail.

## No-reasoning boundary

Python presentation code may select, join, format, validate, and bound records.
React may search, filter, sort, select, and style supplied records. Neither
layer may rerun lineage traversal, compatibility evaluation, impact
propagation, severity, breadth, criticality, decision rules, or repair logic.

## Failure behavior

Explorer loading, transport failure, certification-integrity failure,
contract-invalid response, missing selection, and empty category are distinct
states. The Phase 5.2 graph remains usable when only the explorer endpoint
fails. No stale or fabricated explorer data is shown.

## Verification

Backend tests cover certification, canonical counts and semantics, cross-record
closure, deterministic serialization, tampering, security, and the
no-reasoning boundary. Frontend tests cover contract validation, all explorer
views, selection synchronization, evidence and certainty semantics, empty and
failure states, accessibility, and source audits. Full Phase 1-5.2 regression,
strict TypeScript, lint, and production build remain release gates.
