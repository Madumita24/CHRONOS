# Conflict-blocked scenario

The predecessor contains competing `order_amount` and `total_amount` claims.
Phase 6.4 must preserve both alternatives, produce no patch, and return
`REPAIR_BLOCKED_BY_CONFLICT` until separate authoritative resolution evidence
exists.
