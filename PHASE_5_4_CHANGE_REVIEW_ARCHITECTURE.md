# CHRONOS Phase 5.4 Change Review Architecture

## Purpose

Phase 5.4 composes the certified Phase 5.1 review, Phase 5.2 graph, and Phase
5.3 impact/evidence explorer into one reviewer-oriented workflow at `/review`.
It adds navigation, visual hierarchy, coordinated selection, and review
guidance. It does not add analytical reasoning.

## Review workflow

The page follows five anchored stages:

1. **Overview** — change, certification, disposition, certainty, scope, and the
   blocking question.
2. **Graph** — certified Current, Future, and Diff projections with the root
   UNKNOWN boundary directly focusable.
3. **Impact** — certified field, dataset, path, relationship, and context
   records.
4. **Evidence** — observed facts, counterfactual derivations, missing evidence,
   and decision evidence.
5. **Decision** — the certified disposition, rule, reasons, certainty
   distinction, and read-only reviewer next action.

The experience is a single page, not a wizard and not a set of disconnected
feature pages.

## Page structure

The existing application top bar remains the product shell. Inside the review
page:

- a compact sticky review-context header preserves the change, operation,
  certification, disposition, and technical certainty;
- lightweight in-page navigation links to each workflow stage;
- the overview hero leads with the proposed rename and `HOLD FOR REVIEW`;
- a concise review story connects change, future state, root uncertainty,
  reach, evidence gap, and decision;
- the existing graph and explorer remain the primary interactive surfaces;
- dedicated evidence and decision sections complete the review narrative.

## Selection synchronization

`ReviewContent` owns one `ReviewSelection` union:

```text
node | edge | path | dataset | context | null
```

The graph and explorer receive that same value and one change callback.
Selecting an entity replaces the prior selection, preventing contradictory
panels. Reset returns to the review summary. Graph mode/filter state remains
local because it is display state, not review-entity selection.

The root-boundary action selects the API-supplied future edge whose certified
record is marked `isRootUncertainty` and scrolls to the graph. It does not
search lineage or infer a boundary.

## Section and navigation model

Navigation uses semantic anchors (`overview`, `graph`, `impact`, `evidence`,
and `decision`). The current section is presentation state. Safe
`?section=<name>` state is supported for refreshable section links; entity DTOs
and sensitive data are never placed in the URL.

Contextual actions may move the reviewer to the graph, supporting paths,
connected context, evidence, root cause, or decision. These actions only
navigate among already-loaded certified records.

## Certified data boundary

The workflow continues to use the existing read-only endpoints:

```text
GET /api/reviews/CHRONOS-DEMO-001
GET /api/reviews/CHRONOS-DEMO-001/graph
GET /api/reviews/CHRONOS-DEMO-001/explorer
```

Every analytical value displayed by the workflow is supplied by these strict
contracts. React may format, group, filter, search, sort, select, and navigate.
It may not derive compatibility, impact, severity, breadth, criticality,
disposition, root cause, or the blocking question.

## Error isolation

- Review certification or contract failure closes the entire trusted review
  surface.
- A graph transport failure leaves the certified overview available and
  identifies only the graph feature as unavailable.
- An explorer transport failure leaves the overview and graph available and
  identifies impact/evidence detail as unavailable.
- Graph or explorer certification-integrity failure is labelled as an
  integrity failure and never replaced with fallback analytical data.
- Meaningful zeroes and absences remain visible facts.

## Terminology

The workflow consistently uses:

- `HOLD FOR REVIEW`;
- decision certainty;
- technical certainty;
- severity if realized;
- technically unresolved fields;
- connected context assets;
- unknown compatibility;
- conditionally compatible;
- observed;
- counterfactual;
- required evidence.

`HOLD FOR REVIEW` is explicitly distinguished from a failed change. `PII`
remains sensitivity, and `ELEVATED_CONTEXT` remains contextual criticality.

## Read-only boundary

Phase 5.4 contains no approve, reject, override, sign-off, submit, arbitrary
proposal input, repair advice, repair generation, patch generation, metadata
mutation, or DataHub write. The reviewer next action is limited to obtaining
the four certified evidence classes needed to resolve the blocking question.

## Accessibility

The workflow uses landmark regions, ordered headings, labelled navigation,
keyboard-accessible buttons and tabs, visible focus, textual selected-state
details, explicit status wording, and layouts that do not rely on color.
Narrow layouts stack inspectors and preserve navigation and decision content.

## Test strategy

Workflow tests cover the header, hero, navigation, overview facts, root focus,
shared selection, field/edge/path/dataset/context flows, reset, cross-links,
evidence grouping, required evidence, decision rule and reasons, failure
isolation, terminology, absence of mutation/repair controls, and accessibility
basics. Existing Phase 5.1–5.3 frontend tests and all Python API, unit,
certification, and integration gates remain mandatory.
