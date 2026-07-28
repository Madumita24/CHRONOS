# CHRONOS Phase 3.5 — Evidence and Explanation Paths

## Final result

**PASS / VALID**

Phase 3.5 generated a deterministic, read-only explanation projection of the
existing Phase 3.1–3.4 artifacts. It did not make or modify a compatibility
decision.

- Artifact: `artifacts/explanation_bundle.json`
- Schema version: `1.0`
- Demonstration: `CHRONOS-DEMO-001`
- Validation state: `valid`
- Semantic fingerprint:
  `sha256:9fd969716566024c6227d9e9e8e87cabae02aa20cddd1a5148caaa7ca91ade11`
- Created at: `2026-07-28T04:00:00+00:00`
- Relationships explained: 27
- Paths explained: 48
- Downstream fields explained: 25
- Downstream datasets explained: 20
- Explicit uncertainty records: 1
- Explicit evidence chains: 1, containing all 9 authoritative inputs

## Executive explanation

CHRONOS verified that PostgreSQL `orders.order_total` currently feeds S3
`orders.order_total` through a Spark export mapping. The proposed change
replaces the PostgreSQL source field with `order_amount`. The current metadata
does not contain transform or query evidence showing that the mapping
references or adapts to the renamed field. CHRONOS therefore preserves this
boundary as `UNKNOWN`. All 48 downstream dependency paths pass through this
unresolved boundary, so their end-to-end compatibility remains `UNKNOWN` even
though 26 downstream relationships retain conditionally compatible local
structure.

This narrative is rendered from the typed source explanation, first-boundary
record, relationship conclusions, and path conclusions. It is not stored as an
independent compatibility decision.

## Source change

The source explanation contains only current, proposed, and counterfactual
source facts:

1. **Certified current fact:** PostgreSQL `orders.order_total` has native type
   `DOUBLE PRECISION`, normalized type `Number`, `nullable=true`, and
   `part_of_key=false`.
2. **Certified proposal:** `FIELD_RENAME` from `order_total` to `order_amount`.
3. **Counterfactual derivation:** PostgreSQL `orders.order_amount`, preserving
   dataset identity, native and normalized type, nullability, and key state.

The source explanation contains no downstream compatibility conclusion.

## First unresolved boundary

Relationship:
`future-lineage-68f7e0269dbea7279911b809`

- Certified current structure: PostgreSQL `orders.order_total` → S3
  `orders.order_total`
- Counterfactual structure: PostgreSQL `orders.order_amount` → S3
  `orders.order_total`
- Exposure: `SOURCE_REBASED_EDGE`
- Phase 3.4 compatibility: `UNKNOWN`
- Evidence strength: `INSUFFICIENT`
- Reason: `SOURCE_RENAME_SEMANTICS_UNKNOWN`
- Transform operations: absent
- Query evidence: absent
- Mapping-group provenance: Spark data-job input/output mapping
- Current lineage confidence: `0.5`

The `0.5` value is retained only as lineage provenance. It does not establish
candidate compatibility and is not transformed into an explanation score.

## Representative complete path

Path `dependency-path-e6449e300550f8fcdd5d19e5` has depth 7:

1. PostgreSQL `orders.order_amount`
2. S3 `orders.order_total`
3. Snowflake `orders.order_total`
4. dbt source `orders.order_total`
5. dbt analytics `order_details.order_total`
6. Snowflake analytics `order_details.order_total`
7. Tableau `TOTAL_REVENUE`
8. Tableau downstream `TOTAL_REVENUE`

The ordered edge states are:

1. `UNKNOWN`
2. `CONDITIONALLY_COMPATIBLE`
3. `CONDITIONALLY_COMPATIBLE`
4. `CONDITIONALLY_COMPATIBLE`
5. `CONDITIONALLY_COMPATIBLE`
6. `CONDITIONALLY_COMPATIBLE`
7. `CONDITIONALLY_COMPATIBLE`

The first uncertain edge is
`future-lineage-68f7e0269dbea7279911b809`; therefore the unchanged Phase 3.4
end-to-end path conclusion is `UNKNOWN`.

## Representative multipath field

Snowflake analytics `order_history.order_total` is represented by four
supporting paths:

- `dependency-path-2096cbc6535a63f48c10a792`
- `dependency-path-836e1e1ddbe267d59303ffc1`
- `dependency-path-e2342c757fb326786a1c67f3`
- `dependency-path-d2da9141e2433dd9332bd24a`

Its minimum depth is 4. All four paths share the same first unresolved boundary,
and their path conclusions do not differ. This is a topology and evaluation
statement only.

Across the complete result, 21 of the 25 downstream fields have more than one
supporting path. Every supporting path ID is retained in the machine-readable
field explanation.

## Relationship explanation summary

| Phase 3.4 conclusion | Count | Explanation meaning |
|---|---:|---|
| `UNKNOWN` | 1 | The source-rebased boundary lacks transform/query semantics. |
| `CONDITIONALLY_COMPATIBLE` | 26 | Local endpoints were not directly changed and certified current structure existed, but local structural continuity remains conditional on unresolved upstream availability. |

No relationship classified `CONDITIONALLY_COMPATIBLE` is described as simply
compatible or as proof of end-to-end compatibility.

## Path explanation summary

- Evaluated and explained: 48
- `UNKNOWN`: 48
- First uncertain edge: the source-rebased edge for all 48 canonical paths
- Preserved for every path: ordered fields, ordered relationship IDs, depth,
  edge-state sequence, reason codes, first uncertain/blocking edge, current
  provenance, and counterfactual provenance

## Field explanation summary

- Evaluated and explained: 25
- `UNKNOWN`: 25
- Multipath fields: 21
- Preserved for every field: machine identity, platform, dataset, minimum
  depth, exposure state, incoming relationships, all supporting paths,
  compatibility state, reason codes, uncertainty references, and provenance

## Dataset summary

- Downstream datasets explained: 20
- Dataset summaries with `UNKNOWN` rollup: 20

Each dataset record retains exposed-field identities and counts for compatible,
conditionally compatible, incompatible, and unknown fields. Every human
dataset explanation explicitly identifies itself as a technical compatibility
summary of exposed fields and not a business-impact or health verdict.

## Uncertainty inventory

One root uncertainty is recorded:
`uncertainty-source-rename-boundary`.

- Subject: `future-lineage-68f7e0269dbea7279911b809`
- Reason: `SOURCE_RENAME_SEMANTICS_UNKNOWN`
- Affected relationships: 27
- Affected paths: 48
- Affected downstream fields: 25
- Upstream uncertainty dependencies: none

It states what is unknown: whether the Spark export accepts the renamed input.
It states why: the captured metadata contains neither transform nor query
semantics for that boundary.

## Missing-evidence inventory

The uncertainty record identifies evidence classes that could resolve the
unknown:

- Spark transformation configuration
- Input-column reference query or code
- Explicit rename mapping
- Validated execution result

These are evidence requirements only. Phase 3.5 did not retrieve them and does
not provide repair or implementation advice.

## Provenance audit

The explicit evidence chain contains the nine authoritative inputs in order:

| Artifact | Semantic fingerprint |
|---|---|
| `current_metadata_snapshot.json` | `sha256:774185f19c6fea113ef7adfc5e14583e05e7e08a1fad0c59bd6c6fad755db72c` |
| `change_proposal.json` | `sha256:eeb4a726f9391cefe9e8f46a4bf822e9b4ad6d2cde61e350e3ee2fddb1db4369` |
| `change_proposal_validation.json` | `sha256:034bf7ec9e1650f37f3f395713bb4fe8a6c6d5f9e13509606dffddccfb43fa2c` |
| `change_semantic_contract.json` | `sha256:fc2982ac68c3f1292f8bd101896a5a7930d06ee7dc27f32233b330161651d5bc` |
| `phase_2_certification.json` | `sha256:8de57d9e01a699924a42ab612659608b43988675aa02225e3abf3c568a681148` |
| `counterfactual_source_state.json` | `sha256:1634909adb9d26ba55af9058823ef37c8dcf5bbc3d2e54d535638499ef58b87e` |
| `future_metadata_graph.json` | `sha256:a17fee73f5e3e29ff27223afe49b4438abd4d6dc2e966aa1e8aee4ae77eeb33c` |
| `dependency_propagation.json` | `sha256:ad19656e017da23afd3619b317d72b519fa320827aaeeff833ac9738cd997c78` |
| `compatibility_evaluation.json` | `sha256:7ce6d124d85cbdf6070dfdbde17235141f35fa9c672bb0ce960993407ccaaba4` |

All current-step evidence IDs resolve to Phase 1 evidence. All graph
provenance IDs resolve to the Phase 3.2 provenance registry. Every source,
relationship, path, field, dataset, and uncertainty explanation references the
explicit evidence chain.

The nine physical input files were SHA-256 hashed before and after loading and
after explanation generation. Every before/after pair is identical.

## Determinism audit

- Typed steps use fixed categories and deterministic step IDs.
- Human explanations use deterministic templates driven by typed records.
- JSON serialization sorts keys and uses a canonical compact representation.
- The semantic fingerprint includes input fingerprints, typed steps, reason
  codes, conclusions, evidence references, and uncertainty records.
- `created_at` and the fingerprint field itself are excluded from the semantic
  fingerprint.
- Builds at different timestamps produced identical semantic JSON and semantic
  fingerprints.
- A semantic narrative mutation changed the fingerprint.
- Export and load produced a semantically identical immutable bundle.

## Scope audit

Verified absent:

- New compatibility evaluation or compatibility upgrades/downgrades
- Impact analysis
- Risk score
- Severity
- Repair recommendation
- Business-impact conclusion
- External evidence retrieval
- DataHub access
- Network access
- Graph recomputation through the explanation query API
- Mutation of Phase 1–3.4 artifacts

The implementation is limited to immutable models, deterministic projection,
validation, serialization, local artifact generation, and read-only explanation
queries. Phase 3.6 was not started.

## Tests

Phase 3.5-specific suite:

- **52 passed**
- Covers the 35 required behaviors plus query completeness, evidence-chain
  coverage, provenance resolution, typed step ordering, multipath topology,
  model immutability, and fail-closed corruption cases.

Full repository regression suite:

- **612 passed**
- **7 skipped**
- **0 failed**

Certification subset:

- **72 passed**
- **1 skipped**
- **0 failed**

The skipped tests are existing environment-dependent cases; Phase 3.5
introduced no regression failure.
