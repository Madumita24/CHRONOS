# Primary multi-file PR fixture

This authored, never-executed repository fixture maps to the real certified
dbt `order_details.order_total` identity. It was not retrieved from a live
production repository. SQL proposes `order_amount` and changes `SUM` to `AVG`;
dbt schema agrees and enables its contract, while the DAG and quality file
retain static `order_total` references. Expected repository coherence is
`INCONSISTENT`, with runtime consequences still unverified.
