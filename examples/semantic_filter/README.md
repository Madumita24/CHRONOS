# Semantic filter example

This authored fixture targets the same real certified dbt model and real
`order_total` output. It adds a predicate over the real PostgreSQL
`order_status` source field. CHRONOS classifies the change as model-wide row-set
semantics and does not claim an exact row-count effect.
