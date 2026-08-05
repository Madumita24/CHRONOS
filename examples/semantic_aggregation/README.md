# Semantic aggregation example

This primary Phase 6.2 fixture maps to the real certified dbt `order_details`
Dataset and its observed `order_total` output. The SQL is authored test input;
it was not retrieved from DataHub or a live dbt repository. It changes
`SUM(o.order_total)` to `AVG(o.order_total)` while preserving output identity
and topology. Contract approval and execution evidence are intentionally
absent, so semantic compatibility remains unresolved.

`combined_after.sql` and `combined_change.json` add a model-wide status filter
to the same aggregation change, proving several deltas can coexist in one
logical model.
