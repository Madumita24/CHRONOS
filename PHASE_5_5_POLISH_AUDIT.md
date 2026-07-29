# CHRONOS Phase 5.5 Polish Audit

## Scope and method

This audit was completed before Phase 5.5 implementation. It reviewed the
Phase 5.1-5.4 result reports, the current `/review` implementation, a clean
local API/frontend start, certified endpoint health, the full review workflow,
Current/Future/Diff graphs, root selection, impact, evidence, decision, loading
states, error-state tests, laptop layouts, and a narrow layout.

Findings are limited to presentation, interaction, accessibility, performance,
and release hardening. No certified analytical value or backend reasoning
requires change.

## Blocking

### B1 - Current and Diff summaries repeat Future uncertainty copy

The graph inspector summary says that one relationship is `UNKNOWN` and all 26
future relationships are conditionally compatible even when Current or Diff is
selected. Current must read as observed current state, and Diff must explain
removed, added, preserved, and projected records without applying Future
uncertainty styling to all current lineage.

Justified fix: make the inspector summary and call-to-action mode-aware using
the already selected presentation mode and API-supplied graph projections.

## Important

### I1 - The fitted Future graph makes the central boundary too small

At 1366x768 and 1280x720, fitting all 26 nodes keeps the topology visible but
makes node and edge labels too small for a judge or screen recording. The
`UNKNOWN` boundary exists and is focusable, but it is not a strong technical
moment until selected.

Justified fix: add a concise, human-readable root-boundary callout immediately
above the graph canvas and improve selected/path dimming and edge legibility.
Keep the complete deterministic topology and existing fit behavior.

### I2 - The overview contains too many parallel summaries

The overview repeats metrics in the hero, five metric cards, a seven-card
story, a six-step progress strip, supporting cards, and the root-cause banner.
This weakens the intended order: change, disposition, uncertainty, future,
reach, evidence gap, decision.

Justified fix: keep the hero, one concise review story, the memorable blocking
question, and supporting records; remove or consolidate redundant progress and
metric presentation. Keep connected context out of the first viewport.

### I3 - The change presentation does not explicitly say the dataset is unchanged

The rename itself is prominent, but the hero eyebrow says “Certified impact
assessment,” and the long identity line does not plainly explain that only a
PostgreSQL field changes.

Justified fix: label `FIELD RENAME`, show `PostgreSQL`, and state “Dataset
unchanged: orders” next to the change.

### I4 - Sticky navigation crowds section headings

Graph, Impact, Evidence, and Decision navigation lands with headings touching
or partially sitting under the sticky review controls at laptop height.

Justified fix: increase anchor offset and add section-focus spacing without
making the sticky header taller.

### I5 - Required-evidence markers resemble unchecked form controls

The four required evidence records use empty rounded squares. Although they are
not interactive, they can imply that a reviewer can complete a checklist.

Justified fix: use a non-form document/evidence icon and retain the explicit
`REQUIRED - NOT AVAILABLE` text.

### I6 - Internal identifiers are prominent in explorer and inspector views

Path IDs, relationship IDs, dataset URNs, context IDs, and several opaque
dataset keys appear directly in primary rows or detail headers.

Justified fix: lead with supplied human-readable field, dataset, and platform
labels. Move bounded identifiers into native disclosure sections labelled
“Certified provenance.”

### I7 - The decision story is accurate but too dense

The primary decision panel starts with a long certified narrative and an
internal rule ID. The certified reason cards exist, but the requested visual
story (`UNKNOWN + HIGH + WIDESPREAD + missing evidence -> HOLD FOR REVIEW`) is
not immediately scannable.

Justified fix: present the supplied inputs as a simple visual chain, shorten
the primary explanation without changing meaning, keep the full certified
narrative and rule ID in secondary provenance, and make `0 CONFIRMED FAILURES`
prominent.

### I8 - Terminology varies in case and specificity

Examples include “Hold for review,” “Unresolved fields,” “Context assets,” and
`Pii`. The required product language is `HOLD FOR REVIEW`, “Technically
unresolved fields,” “Connected context assets,” and `PII`.

Justified fix: normalize visible labels while preserving API enum values.

### I9 - Narrow navigation requires horizontal discovery

At 390px, the workflow navigation is usable but Decision is initially outside
the visible horizontal area. The hero title and review badge also compete for
space.

Justified fix: preserve horizontal keyboard scrolling, reduce narrow spacing,
and keep the active item visible. Do not redesign the desktop workflow.

## Polish

### P1 - Graph and explorer settle at different times

The graph response is smaller and commonly becomes ready before the explorer.
Existing skeletons honestly preserve layout and no fallback data appears.

Justified fix: align skeleton density and status wording; do not combine the
independently certification-gated requests or add artificial waiting.

### P2 - Graph reset language is ambiguous

The graph toolbar icon clears display filters and selection, while the workflow
also has “Reset review.”

Justified fix: expose a clear accessible name and tooltip for graph-only reset.

### P3 - Detail panels can prioritize reviewer facts better

Field, edge, and path detail is correct, but identity and bounded provenance
are mixed together. Field detail also omits an explicit root-cause row.

Justified fix: order supplied facts according to the Phase 5.5 specification
and place identifiers in disclosure content.

### P4 - Motion and focus feedback are minimal

Focus styles exist and selected states are visible, but section arrival and
record selection can be clearer.

Justified fix: add short opacity/border/background transitions that respect
`prefers-reduced-motion`; add no decorative animation.

## Verified strengths to preserve

- The first laptop viewport already shows the proposed rename, disposition,
  both certainty concepts, zero confirmed failures, 25 technically unresolved
  fields, and the root action.
- Future is the default graph mode.
- The graph topology and Dagre layout are deterministic.
- Paths use API-supplied ordered nodes and edges; no traversal occurs.
- Loading uses layout-shaped skeletons rather than a blocking spinner.
- Review certification failure fails closed.
- Graph and explorer transport failures are isolated.
- Required evidence, observed evidence, counterfactual evidence, missing
  evidence, and decision evidence are already distinct.
- The browser issues three read-only presentation requests and does not connect
  to DataHub.
- Selection, tabs, filters, and navigation do not refetch analytical data.
- Existing production code contains no analytical mock fallback.

## Implementation boundary

Phase 5.5 will address only the findings above. It will not change certified
counts, topology, compatibility, impact, severity, breadth, criticality,
disposition, root cause, blocking questions, or required evidence.
