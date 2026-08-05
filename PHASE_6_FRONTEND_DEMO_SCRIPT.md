# CHRONOS Phase 6 Frontend Demo Script

## 60-90 second walkthrough

1. Open `/analyses`. Point out the certified-with-limitations banner and the
   exact offline limitation. Show the 17 retained analyses and filter to pull
   requests.
2. Open `CHRONOS-PR-PRIMARY-001`. Confirm the persistent analysis identity,
   repository context, `INCONSISTENT` coherence, and `hold_for_review`
   decision. State that these are certified artifact values, not browser
   inferences.
3. In changed files and logical groups, select a trace. Show the related files,
   roots, evidence, and findings. Open the graph, change between Current,
   Proposed, and Diff, and select one representative path. Note the textual
   fallback and multi-root membership details.
4. Return to the selector, filter to repairs, and open
   `CHRONOS-REPAIR-PRIMARY-001`. Show the deterministic two-action Repair Plan,
   repairability evidence classes, two certified patch summaries, affected
   roots, and protected/static safety indicators.
5. Expand one patch preview. Emphasize `CANDIDATE - NOT APPLIED`, bounded lazy
   loading, the certified fingerprint, and the lack of an apply control.
6. Show the projected comparison: `INCONSISTENT` to `COHERENT` and two stale
   references to zero. Then open the Projected Repaired graph. State that this
   is static projected evidence and execution remains `UNVERIFIED`.
7. Finish with the ten Phase 7 requirements and the release disclosure. State
   the boundary clearly: CHRONOS presents certified evidence; it does not
   execute, approve, merge, write to DataHub, or claim runtime correctness.
