# Explicit delete predecessor

The SQL output explicitly removes `order_total` while an unchanged bounded
quality list still references it. Certified proposal metadata states that the
field is intentionally deleted with no replacement. Phase 6.4 may remove only
that list value; it must not remove a SQL expression, DAG task, or unrelated
quality reference.
