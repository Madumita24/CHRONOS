# Conflicting multi-file PR fixture

This authored, never-executed fixture maps SQL to a real DataHub model. SQL
proposes `order_amount`, dbt schema proposes `total_amount`, and the DAG keeps
`order_total`. CHRONOS must preserve both future claims, report an explicit
conflict, and never select one based on parser order.
