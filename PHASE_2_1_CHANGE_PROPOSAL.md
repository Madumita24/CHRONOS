# CHRONOS Phase 2.1 — Change Proposal Domain Model

## Purpose

Phase 2.1 defines the immutable, typed representation of a requested metadata
change. It answers:

> What change is being proposed?

It does not answer whether the proposal matches current metadata, whether the
requested name already exists, what would be impacted, what a future graph
would contain, or how anything should be repaired.

`CurrentMetadataSnapshot` and `ChangeProposal` are independent objects:

```text
CurrentMetadataSnapshot + ChangeProposal != Modified CurrentMetadataSnapshot
```

The proposal references the certified snapshot fingerprint but never embeds or
mutates the snapshot.

## Supported operation

Phase 2.1 supports exactly:

```text
FIELD_RENAME
```

Unsupported operation values raise `UnsupportedChangeType`. Delete, type
change, add, Dataset rename, impact, propagation, and repair semantics are not
implemented.

## Domain structure

```text
ChangeProposal
├── proposal_id
├── demonstration_id
├── change_type
├── FieldRenameChange
│   ├── SchemaFieldTarget
│   ├── ClaimedFieldState
│   └── RequestedFieldState
├── ProposalSnapshotReference
├── ProposalProvenance
├── lifecycle_state
├── created_at
├── description / rationale
├── proposal_schema_version
└── semantic_fingerprint
```

All domain dataclasses are frozen. Future phases must create separate objects
rather than mutating a proposal in place.

## Proposal identity

Proposal identity is caller supplied and stable. It does not depend on display
text, random UUID generation, serialization time, or object memory address.

Canonical identity:

```text
CHRONOS-DEMO-001-PROPOSAL-001
```

## Target identity

The schema-field machine identity is:

```text
(parent Dataset URN, exact field path)
```

Canonical target:

```text
(
  urn:li:dataset:(urn:li:dataPlatform:postgres,b2fd91.order_entry_db.order_entry.orders,PROD),
  order_total
)
```

Platform, environment, and display identity are descriptive attributes. They
do not replace the machine key. Values are never trimmed, case-normalized, or
rewritten; invalid surrounding whitespace is rejected.

## Claimed before-state

The canonical proposal claims:

| Property | Value |
|---|---|
| Field path | `order_total` |
| Field name | `order_total` |
| Native type | `DOUBLE PRECISION` |
| Normalized type | `Number` |

This is a proposal precondition, not newly verified DataHub evidence. Phase
2.1 does not compare the claim with the certified snapshot.

## Requested after-state

The requested state is a separate immutable object:

| Property | Value |
|---|---|
| Field path | `order_amount` |
| Field name | `order_amount` |

No Dataset, platform, environment, type, nullability, key, lineage, or other
field change is implied or simulated.

## Snapshot reference

The proposal records:

- certified snapshot semantic fingerprint;
- observational snapshot ID;
- snapshot schema version.

The semantic fingerprint is the authoritative baseline reference because
semantically identical reconstructions can have different observational
snapshot IDs.

`create_canonical_proposal` uses the Phase 1.6 deserializer to load the
certified artifact and copy only this identity metadata. It does not inspect
the target field, query DataHub, or certify proposal validity.

## Provenance and evidence semantics

Canonical provenance is:

```text
source = canonical_demo
classification = proposed
```

`order_amount` is proposed information. It is never labeled `verified`,
`derived`, or `unknown` Phase 1 evidence. Proposal provenance is descriptive
and does not prove validity.

## Lifecycle

Phase 2.1 defines:

- `DRAFT`
- `STRUCTURALLY_VALID`

The canonical artifact is `STRUCTURALLY_VALID`. This means only that intrinsic
model rules pass. It does not mean approved, safe, deployable, non-impacting,
or valid against the current snapshot.

Only structurally valid proposals may be exported.

## Structural validation

Construction rejects:

- empty or whitespace-only proposal/demonstration IDs;
- unsupported proposal schema versions or operations;
- empty, whitespace-padded, or malformed target identities;
- empty or whitespace-padded before/after names and paths;
- missing or malformed snapshot fingerprints;
- target paths that differ from the claimed before path;
- identical before and requested-after paths;
- identical before and requested-after names;
- incomplete typed payloads;
- timestamps without an ISO-8601 timezone.

Phase 2.1 intentionally does not check:

- whether the target exists;
- whether the claimed type matches current metadata;
- whether `order_amount` already exists;
- whether the proposal baseline is stale;
- whether the rename is legal PostgreSQL DDL;
- lineage, impact, risk, severity, or repair.

Those current-snapshot comparison questions begin no earlier than Phase 2.2.

## Error model

Proposal failures are separate from DataHub retrieval failures:

- `InvalidChangeProposal`
- `UnsupportedChangeType`
- `InvalidChangeTarget`
- `InvalidFieldRename`
- `InvalidProposalSnapshotReference`
- `ProposalSerializationError`

Phase 2.1 performs no DataHub retrieval and does not reuse DataHub access
errors.

## Deterministic serialization

The proposal artifact uses canonical UTF-8 JSON:

- stable object-key ordering;
- enums serialized as stable string values;
- explicit typed nested objects;
- no runtime object IDs;
- no random value generation during serialization;
- no credentials.

Serialization preserves exact supplied identity values.

## Semantic fingerprint

The proposal fingerprint is:

```text
sha256:<digest of deterministic semantic JSON>
```

It is for reproducibility and change detection, not authentication.

Included semantics:

- proposal ID;
- demonstration ID;
- proposal schema version;
- change type;
- target machine identity and supplied descriptive target attributes;
- claimed before-state;
- requested after-state;
- certified snapshot reference;
- provenance;
- supplied description and rationale.

Excluded observational state:

- `created_at`;
- lifecycle state;
- the fingerprint field itself.

Therefore:

- different `created_at` values preserve the fingerprint;
- a different requested name changes it;
- a different target Dataset URN changes it;
- a different certified baseline fingerprint changes it.

## Canonical proposal

```text
Proposal: CHRONOS-DEMO-001-PROPOSAL-001
Operation: FIELD_RENAME
Target: PostgreSQL / order_entry_db / order_entry / orders / order_total
Requested change: order_total -> order_amount
Baseline: sha256:774185f19c6fea113ef7adfc5e14583e05e7e08a1fad0c59bd6c6fad755db72c
State: STRUCTURALLY_VALID
```

Proposal semantic fingerprint:

```text
sha256:eeb4a726f9391cefe9e8f46a4bf822e9b4ad6d2cde61e350e3ee2fddb1db4369
```

## Artifact independence

Canonical proposal:

```text
artifacts/change_proposal.json
```

Certified current state:

```text
artifacts/current_metadata_snapshot.json
```

Proposal creation, fingerprinting, serialization, export, and reload leave the
current-state artifact byte-for-byte unchanged.

## Phase boundary

Later phases may consume the proposal and current snapshot as separate
immutable inputs. They must not mutate either in place.

Phase 2.1 contains no DataHub client, network requirement, lineage traversal,
Future Graph, impact analysis, repair recommendation, approval, agent,
frontend, or DataHub write.
