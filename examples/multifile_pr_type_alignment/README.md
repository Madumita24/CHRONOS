# Declaration-only type-alignment predecessor

The dbt schema explicitly changes `order_total` from `integer` to `numeric`,
while a bounded contract retains `integer`. Certified proposal metadata
authorizes declaration alignment only. Phase 6.4 must not introduce a SQL cast
or claim that runtime conversion is valid.
