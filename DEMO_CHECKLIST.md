# CHRONOS Demo Checklist

## Pre-demo health

- [ ] Work from the repository root on the expected revision.
- [ ] Confirm no secrets or local environment files are staged.
- [ ] Start the presentation API:
  `.\.venv-datahub-310\Scripts\python.exe -m chronos.presentation`
- [ ] Confirm `http://127.0.0.1:8000/health` reports `ready`.
- [ ] Start the frontend from `frontend` with `npm run dev`.
- [ ] Confirm `http://localhost:3000/review` loads without a console error.
- [ ] Confirm the hero says `orders.order_total → orders.order_amount`.
- [ ] Confirm the hero says `Dataset unchanged: orders`.
- [ ] Confirm `HOLD FOR REVIEW`, `0 CONFIRMED FAILURES`, and
  `25 TECHNICALLY UNRESOLVED FIELDS` are visible.
- [ ] Confirm Future is the active default graph mode.
- [ ] Confirm the root callout reads `UNKNOWN` and `evidence INSUFFICIENT`.
- [ ] Confirm Decision shows
  `UNKNOWN + HIGH + WIDESPREAD + MISSING → HOLD FOR REVIEW`.

## Presentation setup

- [ ] Use 100% browser zoom.
- [ ] Prefer a 1366×768 or larger viewport.
- [ ] Close unrelated tabs, notifications, terminals, and overlays.
- [ ] Reload `/review` immediately before presenting.
- [ ] Do not open internal provenance disclosures unless asked.
- [ ] Do not imply that `HOLD FOR REVIEW` means confirmed failure.

## 90-second path

- [ ] Overview: identify the field rename and unchanged dataset.
- [ ] State the disposition and separate decision certainty from technical
  certainty.
- [ ] Select **View unresolved boundary**.
- [ ] Graph: show Future and the explicit root boundary.
- [ ] Select **Current**, then **Diff**, then return to **Future**.
- [ ] Inspect the `UNKNOWN` root relationship.
- [ ] Impact: state 25 fields, 20 datasets, 48 paths, and connected context.
- [ ] Evidence: read the blocking question and four missing evidence classes.
- [ ] Decision: show the certified input chain and `0 CONFIRMED`.

## Recovery

- If the browser is in an unexpected state, select **Reset review**.
- If a display filter hides the graph, select **Clear selection and filters**.
- If the API is unavailable, stop the demo and restore `/health`; do not use
  cached or invented data.
- If certification integrity fails, treat it as a hard stop. The withheld
  state is the correct fail-closed behavior.

## Post-demo

- [ ] Stop only the API and frontend processes started for the demo.
- [ ] Confirm no temporary logs or local secrets are staged.
- [ ] Record questions without changing the certified scenario during the
  presentation.
