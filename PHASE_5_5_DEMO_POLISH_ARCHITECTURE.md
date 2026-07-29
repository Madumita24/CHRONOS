# CHRONOS Phase 5.5 Demo Polish Architecture

## Scope

Phase 5.5 is a presentation and reliability refinement of the existing Phase
5 review surface. It adds no analytical capability and changes no certified
value. The applicable trust boundary remains:

`Phase 4 certified artifacts → presentation API → strict frontend contracts → read-only UI`

## Presentation hierarchy

The review is organized as one continuous, five-stage narrative:

1. **Overview** — proposed field rename, unchanged dataset, disposition,
   decision certainty, technical certainty, zero confirmed failures, and
   certified scope.
2. **Graph** — Current, Future, and Diff projections with a mode-specific
   explanation and an explicit root-boundary callout.
3. **Impact** — supplied field, dataset, path, relationship, and context
   records.
4. **Evidence** — known facts, unresolved question, observed evidence,
   counterfactual evidence, decision evidence, and required unavailable
   evidence.
5. **Decision** — certified input chain, reason codes, failure distinction,
   and read-only next action.

The sticky review context preserves the change, operation, disposition,
technical certainty, certification, and navigation during long-form review.

## Information hierarchy changes

- The first viewport leads with `FIELD RENAME`, platform, unchanged dataset,
  `HOLD FOR REVIEW`, certainty concepts, zero confirmed failures, and
  technically unresolved field count.
- Duplicate progress and overview metrics were removed or consolidated.
- Current, Future, and Diff now have distinct outer narration, root callouts,
  summaries, and actions.
- Required evidence uses document/evidence icons rather than form-like empty
  checkboxes.
- Human-readable identities lead explorer rows and details. Bounded internal
  identifiers are available in native certified-provenance disclosures.
- The decision leads with the supplied input chain. The longer certified
  narrative and rule ID remain available on demand.

## State and request model

The page performs three independent, read-only requests:

- `GET /api/reviews/CHRONOS-DEMO-001`
- `GET /api/reviews/CHRONOS-DEMO-001/graph`
- `GET /api/reviews/CHRONOS-DEMO-001/explorer`

Graph modes, display filters, tab changes, selections, section navigation, and
reset behavior are local presentation state. They do not refetch analytical
data. Graph and explorer requests remain independent so one partial transport
failure does not hide an otherwise trusted section.

## Failure and integrity semantics

Failures are intentionally distinct:

- **Service unavailable** — transport or service failure; retry is offered.
- **Contract invalid** — a successful payload failed the strict public
  frontend schema; certified content is withheld.
- **Certification integrity failure** — the backend certification gate failed;
  certified content is withheld.

There is no analytical fallback. The main review fails closed on contract or
certification failure. Graph and explorer feature failures are isolated while
the certified overview remains inspectable.

## Graph presentation

Dagre placement and the supplied topology remain deterministic. Phase 5.5
does not add traversal. The mode banner presents facts already present in the
graph contract:

- Current: observed source and first relationship.
- Future: counterfactual source, `UNKNOWN` root, insufficient evidence, and
  first downstream field.
- Diff: removed current source, added future source, 25 preserved downstream
  identities, and projected `UNKNOWN` root.

Only Diff applies added/removed/preserved styling. Current never inherits
future uncertainty or diff styling.

## Accessibility and responsive behavior

- Semantic navigation, headings, tabs, buttons, disclosures, status text, and
  alerts remain available to assistive technology.
- Keyboard focus and activation are covered by the workflow test suite.
- Focus-visible styling is retained across interactive controls.
- Motion is short and disabled when `prefers-reduced-motion` is set.
- Anchor offsets account for sticky controls.
- Required viewports from 390×844 through 1920×1080 have no document-level
  horizontal overflow.
- Narrow navigation fits all five stages without hidden horizontal discovery.

## Performance and security boundary

- Loading states are layout-shaped skeletons.
- Independent responses settle without an artificial combined wait.
- No new background polling, WebSocket, analytics, or third-party request was
  added.
- The browser has no DataHub credentials or direct DataHub transport.
- Production code contains no synthetic analytical dataset and no client-side
  compatibility, impact, severity, lineage traversal, or decision engine.
- Repair, approval, mutation, and metadata-write controls remain absent.

## Explicit non-goals

- new reasoning;
- new contracts or backend DTOs;
- topology changes;
- live DataHub queries from the browser;
- proposal entry;
- automated repair;
- approval workflows;
- metadata writes;
- Phase 6 implementation.
