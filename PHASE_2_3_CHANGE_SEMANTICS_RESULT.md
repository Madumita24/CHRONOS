# CHRONOS Phase 2.3 - Change Semantics Result

**Contract date:** 2026-07-27 UTC

**Demonstration:** `CHRONOS-DEMO-001`

**Contract artifact:** `artifacts/change_semantic_contract.json`

## Decision

The canonical validated `FIELD_RENAME` now has an immutable semantic contract.
The contract defines the exact source-field identity transition, properties
changed by the proposal, properties unchanged by the proposal, consequences
that remain unevaluated, certified preconditions, and permissions for a later
counterfactual application phase.

The contract is declarative. It does not materialize a transformed schema or
graph.

## Certified inputs

| Phase | Input | Status |
|---|---|---|
| Phase 1 | `artifacts/current_metadata_snapshot.json` | `CERTIFIED`; embedded validation `valid` |
| Phase 2.1 | `artifacts/change_proposal.json` | `COMPLETE`; `structurally_valid` |
| Phase 2.2 | `artifacts/change_proposal_validation.json` | `COMPLETE`; validation state `valid` |

All inputs were loaded through their existing public deserializers. Contract
construction fails closed unless all three inputs agree.

## Contract identity

| Property | Observed value |
|---|---|
| Contract schema version | `1.0` |
| Proposal ID | `CHRONOS-DEMO-001-PROPOSAL-001` |
| Proposal fingerprint | `sha256:eeb4a726f9391cefe9e8f46a4bf822e9b4ad6d2cde61e350e3ee2fddb1db4369` |
| Validation fingerprint | `sha256:034bf7ec9e1650f37f3f395713bb4fe8a6c6d5f9e13509606dffddccfb43fa2c` |
| Baseline snapshot fingerprint | `sha256:774185f19c6fea113ef7adfc5e14583e05e7e08a1fad0c59bd6c6fad755db72c` |
| Contract creation timestamp | `2026-07-27T05:25:40.414254+00:00` |
| Contract semantic fingerprint | `sha256:fc2982ac68c3f1292f8bd101896a5a7930d06ee7dc27f32233b330161651d5bc` |
| Contract artifact SHA-256 | `986139696A57B5A30A6772A0004799EBB213C4085C8DA82D0E53C3996F79BEE6` |

The creation timestamp is volatile and excluded from the semantic
fingerprint.

## Identity transition

The Dataset identity remains unchanged:

`urn:li:dataset:(urn:li:dataPlatform:postgres,b2fd91.order_entry_db.order_entry.orders,PROD)`

| Identity | Dataset URN | Field path | Classification |
|---|---|---|---|
| Current target | Unchanged canonical URN | `order_total` | `certified_current` |
| Candidate target | Unchanged canonical URN | `order_amount` | `counterfactual_candidate` |

The machine keys differ only by field path. The candidate identity has
`schema_field_urn = null`; no DataHub-supplied identity was fabricated.

## Changed properties

The changed set contains exactly two properties:

| Category | Property | Before | Candidate after |
|---|---|---|---|
| `CHANGED` | `field_path` | `order_total` | `order_amount` |
| `CHANGED` | `field_name` | `order_total` | `order_amount` |

No unrelated property is included in the changed set.

## Unchanged by proposal

These are counterfactual application invariants. They mean the proposal
requests no change to the property.

| Category | Property | Certified value |
|---|---|---|
| `UNCHANGED_BY_PROPOSAL` | Target Dataset URN | Canonical PostgreSQL orders URN |
| `UNCHANGED_BY_PROPOSAL` | Platform | `postgres` |
| `UNCHANGED_BY_PROPOSAL` | Environment | `PROD` |
| `UNCHANGED_BY_PROPOSAL` | Native type | `DOUBLE PRECISION` |
| `UNCHANGED_BY_PROPOSAL` | Normalized type | `Number` |
| `UNCHANGED_BY_PROPOSAL` | Nullable | `true` |
| `UNCHANGED_BY_PROPOSAL` | Part of key | `false` |
| `UNCHANGED_BY_PROPOSAL` | Other source fields | All 14 non-target fields |

The 14 preserved field paths are:

1. `order_id`
2. `order_date`
3. `order_mode`
4. `customer_id`
5. `order_status`
6. `sales_rep_id`
7. `promotion_id`
8. `warehouse_id`
9. `delivery_type`
10. `cost_of_delivery`
11. `wait_till_complete_yn`
12. `billing_address_id`
13. `delivery_address_id`
14. `payment_method_code`

## Unknown consequences

Every item below is typed `UNKNOWN` and `NOT_EVALUATED`:

- whether downstream field names change;
- whether downstream mappings adapt;
- whether Spark jobs remain valid;
- whether dbt models remain valid;
- whether Snowflake transformations remain valid;
- whether Looker assets remain valid;
- whether Power BI assets remain valid;
- whether Tableau assets remain valid;
- whether charts or dashboards break;
- whether governance should propagate;
- whether Data Products require updates;
- whether documentation requires updates;
- whether repair is possible.

None is classified unchanged, broken, safe, or risky.

## Frozen preconditions

All eight contract-construction preconditions are `SATISFIED`:

| Precondition | Observed |
|---|---|
| Baseline snapshot fingerprint matches | Exact match |
| Proposal fingerprint matches validation | Exact match |
| Phase 2.2 validation state | `valid` |
| Target Dataset exists | Exactly 1 |
| Target field exists | Exactly 1 |
| Before-state matches | `true` |
| Requested field collision count | `0` |
| Proposal type | `field_rename` |

A missing, stale, invalid, or inconsistent input raises a typed
`SemanticContractPreconditionError`; no partial contract is produced.

## Source-schema contract

| Rule | Contract value |
|---|---|
| Current source-field count | 15 |
| Candidate source-field count | 15 |
| Current target identity | `order_total` |
| Candidate replacement identity | `order_amount` |
| Other source fields | 14 unchanged paths |
| Transformed schema materialized | `false` |

This is a cardinality and identity rule only. Phase 2.3 does not construct the
candidate schema.

## Application and evidence rules

Required:

- create a new counterfactual representation;
- preserve all unchanged-by-proposal source properties;
- preserve the certified current snapshot;
- preserve current-evidence provenance.

Allowed:

- rename only the target source field path and field name in that new
  representation.

Forbidden:

- mutate `CurrentMetadataSnapshot`;
- change unrelated source fields;
- change the Dataset identity;
- change source types;
- delete certified current evidence;
- automatically rename downstream fields;
- infer downstream compatibility;
- reinterpret current evidence as counterfactual evidence;
- write to DataHub.

The source rename therefore does not propagate automatically through field
lineage. Current lineage remains evidence of the certified current graph.

## Human-readable contract

```text
Operation: FIELD_RENAME
Target: PostgreSQL orders.order_total
Changed: field path/name order_total -> order_amount
Unchanged by proposal: dataset identity, platform, environment, type,
nullability, key status, and the other 14 source fields
Unknown consequences: NOT_EVALUATED
Future application: must create a new counterfactual representation
Current snapshot mutation: FORBIDDEN
Automatic downstream rename: FORBIDDEN
```

## Immutability and determinism

- Contract and all nested records are frozen dataclasses.
- Collections are immutable tuples.
- Snapshot, proposal, and validation objects remain byte-for-byte equivalent
  before and after contract construction.
- Input artifact hashes remain unchanged.
- Repeated serialization is byte-deterministic.
- Round-trip loading preserves the complete contract.
- Changing the proposal, validation, or baseline fingerprint changes the
  contract fingerprint.
- Changing only the creation timestamp does not change the contract
  fingerprint.

Input artifact hashes after contract generation:

| Artifact | SHA-256 | Result |
|---|---|---|
| `current_metadata_snapshot.json` | `0F2DF1E0F842D95296078F6E533B197B8A35A34683F31FB1C6CEBE0CC3D2362E` | UNCHANGED |
| `change_proposal.json` | `AD3840820C1A6DB6D588FAFAB73F23763862105DF6DB44EFE6D1E22B0ECC6BEE` | UNCHANGED |
| `change_proposal_validation.json` | `9B06DF69BBCD4A889F24ECF3F749FCAB9EC17CDBBEFF50E97038803B387A7DB4` | UNCHANGED |

## Test results

| Suite | Result |
|---|---|
| Phase 2.3 semantic-contract unit tests | 42 passed |
| Phase 2.2 proposal-validation regression tests | 36 passed |
| Phase 2.1 proposal regression tests | 35 passed |
| Complete unit regression suite | 275 passed |
| Offline Phase 1 certification suite | 38 passed |

## Scope controls confirmed

- No DataHub request was made.
- No DataHub client or transport was instantiated.
- No Future Graph was created.
- No impact analysis was performed.
- No downstream rename was propagated.
- No transformed source schema was materialized.
- No repair logic was introduced.
- No DataHub write path was introduced.

Phase 2.3 stops here. Phase 2.4 has not begun.
