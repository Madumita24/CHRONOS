# Semantic join example

This authored fixture uses real certified Snowflake `orders` and
`order_history` Dataset identities and maps the output to the real dbt
`order_details.order_total` field. It changes `LEFT JOIN` to `INNER JOIN`.
Possible row preservation and cardinality consequences remain unresolved;
CHRONOS does not invent execution outcomes.
