# Primary coordinated repair

Generate the certified Phase 6.3 predecessor from
`examples/multifile_pr_primary`, then use `repair_proposal.json`. The expected
candidate changes only the exact stale DAG and quality field references. The
`AVG` aggregation remains unchanged and requires human semantic approval.

The repair package is isolated, unapplied, and not runtime verified.
