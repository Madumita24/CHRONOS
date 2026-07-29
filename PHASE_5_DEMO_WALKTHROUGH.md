# CHRONOS Phase 5 Demo Walkthrough

## Purpose

This is a presentation script for the frozen `CHRONOS-DEMO-001` certified
result. It explains only values supplied by the Phase 4 presentation package.
It does not demonstrate proposal entry, repair, approval, metadata mutation,
or live analytical recomputation.

## 90-second walkthrough

### 0:00–0:15 — Establish the change

Open `http://localhost:3000/review`.

Say:

> This is a PostgreSQL field rename from `orders.order_total` to
> `orders.order_amount`. The dataset identity remains `orders`.

Point to:

- `FIELD RENAME`
- `Dataset unchanged: orders`
- `HOLD FOR REVIEW`

### 0:15–0:30 — Explain certainty correctly

Say:

> The decision certainty is high confidence, while technical certainty at the
> first Spark export boundary is unresolved. CHRONOS reports zero confirmed
> downstream failures and 25 technically unresolved fields.

Do not describe `UNRESOLVED` as `INCOMPATIBLE`.

### 0:30–0:50 — Show the graph moment

Select **View unresolved boundary**.

Say:

> Future is the default counterfactual projection. The root callout makes the
> precise boundary visible: `order_amount` reaches the first downstream field,
> but the relationship is `UNKNOWN` because evidence is insufficient.

Briefly select:

1. **Current** — observed lineage only; no future compatibility styling.
2. **Diff** — one source removed, one added, 25 downstream identities
   preserved, projected root still `UNKNOWN`.
3. **Future** — return to the default and inspect the root relationship.

### 0:50–1:05 — Show reach

Select **Impact**.

Say:

> The certified blast radius contains 25 downstream fields, 20 datasets, 48
> dependency paths, and connected governance, operational, and consumer
> context. These are supplied records, not browser-computed traversal.

Select one field only if time permits; human-readable identity leads and
internal IDs remain in certified provenance.

### 1:05–1:20 — Show the evidence gap

Select **Evidence**.

Read the blocking question:

> Does the Spark export mapping accept or adapt to PostgreSQL
> `orders.order_amount` after `order_total` is renamed?

Point to the four required, unavailable evidence classes:

- explicit rename mapping;
- impact-column reference query or code;
- Spark configuration;
- validated execution.

### 1:20–1:30 — Close on the decision

Select **Decision**.

Say:

> The certified decision inputs are `UNKNOWN + HIGH + WIDESPREAD + MISSING`.
> That yields `HOLD FOR REVIEW` with high decision confidence. It does not mean
> the change is a confirmed failure; the certified failure count remains zero.

## Three-minute extended walkthrough

Use the 90-second path, then add:

- the representative shortest, deepest, and multipath graph shortcuts;
- one field detail and one dataset detail;
- observed versus counterfactual versus missing evidence classification;
- the certified narrative disclosure;
- the explicit read-only next action.

## Questions and precise answers

**Did the browser calculate the impact?**

No. It validates and renders certified review, graph, and explorer contracts.

**Why is the disposition confident if compatibility is unresolved?**

Decision certainty describes confidence in the review disposition. Technical
certainty describes whether the source relationship is known. They are
different certified concepts.

**Is the change broken?**

No confirmed breakage is asserted. The certified count is zero. Severity is
conditional on the unresolved boundary materializing as incompatible.

**Can CHRONOS fix or approve it here?**

No. Phase 5 is read-only. Repair, approval, and metadata writes are absent.

**Does the frontend connect to DataHub?**

No. It calls the local CHRONOS presentation API, which serves certification-
gated artifacts produced by the backend pipeline.
