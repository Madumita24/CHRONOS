# CHRONOS Phase 3.1 - Counterfactual Source-State Verification

**Verification date:** 2026-07-28 UTC

**Demonstration:** `CHRONOS-DEMO-001`

**Artifact:** `artifacts/counterfactual_source_state.json`

## Final result

**PASS**

The certified `FIELD_RENAME` was materialized exactly once in a new immutable
counterfactual PostgreSQL source schema. The certified current snapshot and
all Phase 2 artifacts remain unchanged.

Phase 3.1 materializes no downstream, lineage, governance, pipeline, or BI
state.

## Entry prerequisites

| Prerequisite | Observed | Result |
|---|---|---|
| Phase 1 snapshot | Embedded validation `valid` | PASS |
| Phase 2 package | `CERTIFIED`; 34 checks passed; 0 findings; 0 warnings | PASS |
| Proposal validation | `VALID` | PASS |
| Semantic contract | Reproduced and internally consistent | PASS |
| Demonstration | `CHRONOS-DEMO-001` everywhere | PASS |
| Operation | `FIELD_RENAME` everywhere | PASS |
| Dataset identity | Exact canonical PostgreSQL orders URN | PASS |
| Current field | `order_total` | PASS |
| Candidate field | `order_amount` | PASS |

Phase 3.1 independently recomputed the Phase 2 certification from the four
Phase 2 inputs and compared it semantically with the certification artifact.

## Input artifact fingerprints

| Input | Semantic fingerprint |
|---|---|
| Current snapshot | `sha256:774185f19c6fea113ef7adfc5e14583e05e7e08a1fad0c59bd6c6fad755db72c` |
| Proposal | `sha256:eeb4a726f9391cefe9e8f46a4bf822e9b4ad6d2cde61e350e3ee2fddb1db4369` |
| Proposal validation | `sha256:034bf7ec9e1650f37f3f395713bb4fe8a6c6d5f9e13509606dffddccfb43fa2c` |
| Semantic contract | `sha256:fc2982ac68c3f1292f8bd101896a5a7930d06ee7dc27f32233b330161651d5bc` |
| Phase 2 certification | `sha256:8de57d9e01a699924a42ab612659608b43988675aa02225e3abf3c568a681148` |

All stored semantic fingerprints reproduced before materialization.

## Current source-schema summary

| Property | Certified current value |
|---|---|
| Classification | `CERTIFIED_CURRENT` |
| Dataset URN | `urn:li:dataset:(urn:li:dataPlatform:postgres,b2fd91.order_entry_db.order_entry.orders,PROD)` |
| Platform | `postgres` |
| Environment | `PROD` |
| Qualified identity | `order_entry_db.order_entry.orders` |
| Logical identity | `orders` |
| Schema identity | `order_entry_db.order_entry.orders` |
| Field count | 15 |
| Target field | `order_total` |
| Target position | 5 |

## Candidate source-schema summary

| Property | Counterfactual value |
|---|---|
| Classification | `COUNTERFACTUAL` |
| Dataset URN | Unchanged canonical URN |
| Platform | `postgres` |
| Environment | `PROD` |
| Qualified identity | `order_entry_db.order_entry.orders` |
| Logical identity | `orders` |
| Schema identity | `order_entry_db.order_entry.orders` |
| Field count | 15 |
| Candidate target | `order_amount` |
| Candidate position | 5 |

The candidate schema is a replacement representation. It is not an additional
field appended to current metadata.

## Current and candidate target comparison

| Property | Certified current | Counterfactual candidate | Result |
|---|---|---|---|
| Dataset URN | Canonical PostgreSQL orders | Same | PRESERVED |
| Field path | `order_total` | `order_amount` | RENAMED |
| Field name | `order_total` | `order_amount` | RENAMED |
| Position | 5 | 5 | PRESERVED |
| Native type | `DOUBLE PRECISION` | `DOUBLE PRECISION` | PRESERVED |
| Normalized type | `Number` | `Number` | PRESERVED |
| Nullable | `true` | `true` | PRESERVED |
| Part of key | `false` | `false` | PRESERVED |
| DataHub type | `NumberTypeClass` | `NumberTypeClass` | PRESERVED |
| Description | `null` | `null` | PRESERVED |
| Partitioning key | `null` | `null` | PRESERVED |
| Recursive | `false` | `false` | PRESERVED |
| Schema-field URN | `null` | `null` | NOT FABRICATED |

## Field mapping summary

The artifact contains 15 ordered current-to-candidate mappings:

- 1 `RENAMED` mapping:
  `(canonical Dataset URN, order_total)` to
  `(canonical Dataset URN, order_amount)`;
- 14 `UNCHANGED` mappings whose machine identities are identical.

No mapping is applied outside the source schema.

## Preserved-property audit

For every field, Phase 3.1 derives metadata directly from the certified source
schema.

The 14 non-target fields preserve:

- original position and ordering;
- field path and field name;
- native and normalized type;
- DataHub type classification;
- description;
- nullability and key state;
- partitioning state;
- JSON path and label;
- recursion state;
- existing schema-field URN value;
- references to certified current evidence.

No property is reconstructed from an assumption.

## Cardinality and ordering audit

| Check | Expected | Observed | Result |
|---|---:|---:|---|
| Current field count | 15 | 15 | PASS |
| Candidate field count | 15 | 15 | PASS |
| Candidate `order_total` occurrences | 0 | 0 | PASS |
| Candidate `order_amount` occurrences | 1 | 1 | PASS |
| Candidate target position | 5 | 5 | PASS |
| Unchanged field paths | 14 | 14 | PASS |
| Unique field paths | 15 | 15 | PASS |
| Unique field positions | 15 | 15 | PASS |
| Preserved ordering | Positions 0-14 | Positions 0-14 | PASS |
| Added fields | 0 | 0 | PASS |
| Deleted fields | 0 | 0 | PASS |

## Identity audit

- The Dataset URN is copied exactly from certified current evidence.
- No new Dataset URN is created.
- The Dataset platform, environment, qualified name, logical name, schema
  name, and source platform are preserved.
- `order_amount` is classified `COUNTERFACTUAL`.
- Its current-source reference points to certified `order_total`.
- No schema-field URN is fabricated.

## Evidence-separation audit

| Object | Classification | Meaning |
|---|---|---|
| Snapshot source schema | `CERTIFIED_CURRENT` | DataHub-derived current evidence |
| Current field references | `CERTIFIED_CURRENT` | Source identities in the snapshot |
| Candidate Dataset | `COUNTERFACTUAL` | Derived candidate representation |
| Candidate schema | `COUNTERFACTUAL` | Derived source-only schema |
| Candidate fields | `COUNTERFACTUAL` | Derived fields, not live observations |

The artifact never labels `order_amount` verified, observed in DataHub,
existing current metadata, or live metadata.

## Lineage non-transformation audit

| Measure | Observed |
|---|---:|
| Downstream fields materialized | 0 |
| Lineage nodes transformed | 0 |
| Lineage edges transformed | 0 |
| Mapping groups transformed | 0 |
| Captured paths transformed | 0 |

The candidate source state exposes no lineage collection.

## Governance non-transformation audit

No owner, domain, tag, glossary, structured-property, Data Product, Document,
Chart, Dashboard, Data Job, Data Flow, or BI relationship is included or
transformed.

Governance records transformed: 0.

## Immutability and input-hash audit

All Phase 3.1 domain objects use frozen dataclasses and immutable tuples.

| Input artifact | SHA-256 before | SHA-256 after | Result |
|---|---|---|---|
| `current_metadata_snapshot.json` | `0F2DF1E0F842D95296078F6E533B197B8A35A34683F31FB1C6CEBE0CC3D2362E` | Same | UNCHANGED |
| `change_proposal.json` | `AD3840820C1A6DB6D588FAFAB73F23763862105DF6DB44EFE6D1E22B0ECC6BEE` | Same | UNCHANGED |
| `change_proposal_validation.json` | `9B06DF69BBCD4A889F24ECF3F749FCAB9EC17CDBBEFF50E97038803B387A7DB4` | Same | UNCHANGED |
| `change_semantic_contract.json` | `986139696A57B5A30A6772A0004799EBB213C4085C8DA82D0E53C3996F79BEE6` | Same | UNCHANGED |
| `phase_2_certification.json` | `F08A56932898707A22E727A607D5BF0280A86C19EADA3DCA8D8F0B1BE1EF12F2` | Same | UNCHANGED |

Mutation attempts against the current snapshot fail because the snapshot is
immutable. Candidate mutations outside the semantic contract fail validation.

## Determinism audit

| Property | Result |
|---|---|
| Repeated identical materialization | Semantically identical |
| Timestamp-only difference | Fingerprint unchanged |
| Candidate field semantic difference | Fingerprint changed |
| Dataset semantic difference | Fingerprint changed |
| Snapshot fingerprint difference | Fingerprint changed |
| Semantic-contract fingerprint difference | Fingerprint changed |
| Phase 2 certification fingerprint difference | Fingerprint changed |
| Deterministic JSON round trip | PASS |

Counterfactual source-state semantic fingerprint:

`sha256:1634909adb9d26ba55af9058823ef37c8dcf5bbc3d2e54d535638499ef58b87e`

Artifact file SHA-256:

`BA2E86A261F5C9BC66731543A9A3BCBB6AC2C60A10F34D57764F5577868DCE80`

The volatile `created_at` value is excluded from semantic identity.

## Test results

| Suite | Result |
|---|---|
| Phase 3.1 counterfactual source-state tests | 53 passed |
| Complete unit regression suite | 328 passed |
| Offline Phase 1 certification suite | 38 passed |
| Phase 2.4 certification suite | 34 passed |

The Phase 2.1, 2.2, and 2.3 tests are included in the complete unit suite.

## Runtime and scope audit

- No live DataHub request was made.
- No DataHub client or transport was instantiated.
- No Future Graph was built.
- No downstream rename was propagated.
- No lineage was transformed.
- No governance, pipeline, or BI metadata was transformed.
- No compatibility or impact conclusion was produced.
- No repair logic was introduced.
- No certified artifact was overwritten.

## Warnings

None.

## Final result

**PASS**

Phase 3.1 is complete. Phase 3.2 has not begun.
