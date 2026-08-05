# Field type-change example

This proposal changes the real `order_total` source field from PostgreSQL
`DOUBLE PRECISION` / normalized `NUMBER` to `TEXT` / normalized `STRING`.
The field has supplied downstream lineage, making the compatibility question
meaningful. The snapshot does not certify consumer type expectations, so the
engine conservatively preserves uncertainty rather than claiming failure or
compatibility.

The resulting package is a generalized example certification, not the frozen
Phase 4 certification.
