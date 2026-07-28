# CHRONOS Phase 3.3 — Dependency Propagation

## Result

**PASS — dependency-state propagation is complete for
`CHRONOS-DEMO-001`.**

This result answers which fields and structural relationships are downstream
of the changed source. It does not determine compatibility, breakage,
business impact, safety, risk, or repair.

Authoritative Future Graph fingerprint:

`sha256:a17fee73f5e3e29ff27223afe49b4438abd4d6dc2e966aa1e8aee4ae77eeb33c`

Dependency propagation fingerprint:

`sha256:ad19656e017da23afd3619b317d72b519fa320827aaeeff833ac9738cd997c78`

## Computed summary

| Metric | Computed value |
|---|---:|
| Changed source fields | 1 |
| Directly exposed fields | 1 |
| Single-path transitively exposed fields | 3 |
| Multipath-exposed fields | 21 |
| Unique downstream exposed fields | 25 |
| Unique downstream exposed datasets | 20 |
| Maximum shortest exposure depth | 5 |
| Exposed structural relationships | 27 |
| Processed structural relationships | 27 |
| Distinct supporting paths | 48 |

The values were calculated by traversal. The 25-field, 20-dataset, and
depth-5 values were used only as post-computation acceptance baselines.

## Depth-oriented view

Every relationship shown below retains:

`compatibility = NOT_EVALUATED`

### Depth 0

```text
PostgreSQL orders.order_amount
state: SOURCE_CHANGED
path count: 0 (traversal seed)
identity state: COUNTERFACTUAL_CHANGED
```

### Depth 1

```text
S3 orders.order_total
state: DIRECTLY_EXPOSED
shortest depth: 1
path count: 1
identity state: COUNTERFACTUAL_UNRESOLVED
```

The incoming edge is the single `SOURCE_REBASED_EDGE`:

```text
PostgreSQL orders.order_amount
  → S3 orders.order_total
```

Its Phase 3.2 structural state is `COUNTERFACTUAL_PROJECTED`; its
compatibility remains `NOT_EVALUATED`.

### Depth 2

```text
Snowflake source orders.order_total
state: TRANSITIVELY_EXPOSED
shortest depth: 2
path count: 1
identity state: COUNTERFACTUAL_UNRESOLVED
```

### Depth 3

```text
dbt source orders.order_total
state: TRANSITIVELY_EXPOSED
shortest depth: 3
path count: 1
identity state: COUNTERFACTUAL_UNRESOLVED
```

Another depth-3 node demonstrates multipath exposure:

```text
Snowflake analytics.order_details.order_total
state: MULTIPATH_EXPOSED
shortest depth: 3
path count: 2
identity state: COUNTERFACTUAL_UNRESOLVED
```

### Depth 4

```text
dbt analytics.order_details.order_total
state: TRANSITIVELY_EXPOSED
shortest depth: 4
path count: 1
identity state: COUNTERFACTUAL_UNRESOLVED
```

### Depth 5

```text
Looker explore order_details.order_total
state: MULTIPATH_EXPOSED
shortest depth: 5
path count: 2
identity state: COUNTERFACTUAL_UNRESOLVED
```

## Representative transitive path

```text
depth 0  PostgreSQL orders.order_amount
  ↓
depth 1  S3 orders.order_total
  ↓
depth 2  Snowflake source orders.order_total
  ↓
depth 3  dbt source orders.order_total
  ↓
depth 4  dbt analytics.order_details.order_total
```

This path establishes dependency exposure only.

## Multipath example

`Snowflake analytics.order_details.order_total` has:

- minimum depth: 3
- distinct supporting path count: 2
- propagation state: `MULTIPATH_EXPOSED`
- identity state: `COUNTERFACTUAL_UNRESOLVED`
- compatibility: `NOT_EVALUATED`

Supporting path IDs:

- `dependency-path-ba191a7dc2f8c3e014003ead`
- `dependency-path-b520d7be2f2e3ed26e3cdbb5`

Distinct path identity is based on the ordered field-node and relationship-ID
sequence. Duplicate representations of an identical path are deduplicated.

## Propagation semantics

Field exposure and Phase 3.2 identity state are separate dimensions:

| Dimension | Example value |
|---|---|
| Identity/counterfactual state | `COUNTERFACTUAL_UNRESOLVED` |
| Dependency exposure state | `MULTIPATH_EXPOSED` |
| Relationship compatibility | `NOT_EVALUATED` |

`MULTIPATH_EXPOSED` therefore means only that more than one distinct
source-rooted structural path reaches the field.

## Traversal boundary

Propagation follows only the 27 typed Future Graph field-lineage
relationships. It explicitly ignores:

- dashboard and BI context
- ownership
- tags
- glossary assignments
- domains
- Data Products
- documents
- pipeline context
- structured-property context

None of the 225 context relationships appears in a supporting dependency
path.

## Cycle and depth semantics

Minimum depth is computed with cycle-safe breadth-first traversal. Supporting
paths are deterministic distinct simple paths; a node already present in the
current path is not revisited.

The maximum **shortest** exposure depth is 5. Some alternate multipath routes
contain up to 7 edges. Those longer routes are retained as path evidence but
do not overwrite the field's minimum exposure depth.

## Preserved boundaries

- No downstream field was renamed.
- The active source remains `orders.order_amount`; historical
  `orders.order_total` remains provenance only.
- All 25 downstream identity states remain
  `COUNTERFACTUAL_UNRESOLVED`.
- All 27 relationship compatibility states remain `NOT_EVALUATED`.
- No impact, breakage, compatibility, risk, safety, or repair state exists.
- No DataHub request was made.
- Phase 3.4 was not started.
