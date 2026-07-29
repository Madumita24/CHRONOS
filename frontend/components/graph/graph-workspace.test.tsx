import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { GraphWorkspace } from "@/components/graph/graph-workspace";
import { graphFixture } from "@/test/graph-fixture";

function response(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

async function renderGraph(body: unknown = graphFixture, status = 200) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(body, status)));
  const rendered = render(<GraphWorkspace reviewId="CHRONOS-DEMO-001" />);
  await screen.findByText("Graph summary");
  return rendered;
}

describe("GraphWorkspace", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads the certified graph endpoint", async () => {
    await renderGraph();
    expect(fetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/reviews/CHRONOS-DEMO-001/graph",
      expect.objectContaining({ method: "GET", cache: "no-store" }),
    );
  });

  it("renders the complete future graph by default", async () => {
    await renderGraph();
    expect(screen.getByText(/Future · 26 fields · 27 relationships/)).toBeVisible();
  });

  it("marks Future as the active mode", async () => {
    await renderGraph();
    expect(screen.getByRole("button", { name: "Future" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("shows order_amount as the active future source", async () => {
    await renderGraph();
    const canvas = screen.getByTestId("graph-mode-future");
    expect(within(canvas).getByText("order_amount")).toBeInTheDocument();
  });

  it("does not show order_total as an active future graph node", async () => {
    await renderGraph();
    const canvas = screen.getByTestId("graph-mode-future");
    expect(within(canvas).queryByText("order_total")).not.toBeInTheDocument();
  });

  it("switches to all 26 current fields and 27 relationships", async () => {
    await renderGraph();
    await userEvent.click(screen.getByRole("button", { name: "Current" }));
    expect(screen.getByText(/Current · 26 fields · 27 relationships/)).toBeVisible();
    expect(
      screen.getByText(/All 27 relationships are certified current lineage/),
    ).toBeVisible();
  });

  it("shows order_total as the current source", async () => {
    await renderGraph();
    await userEvent.click(screen.getByRole("button", { name: "Current" }));
    expect(
      within(screen.getByTestId("graph-mode-current")).getByText("order_total"),
    ).toBeInTheDocument();
  });

  it("switches to the explicit diff projection", async () => {
    await renderGraph();
    await userEvent.click(screen.getByRole("button", { name: "Diff" }));
    expect(screen.getByText(/Diff · 27 fields · 28 relationships/)).toBeVisible();
    expect(
      screen.getByText(/25 downstream identities are preserved/),
    ).toBeVisible();
  });

  it("shows removed and added source identities in Diff", async () => {
    await renderGraph();
    await userEvent.click(screen.getByRole("button", { name: "Diff" }));
    const canvas = screen.getByTestId("graph-mode-diff");
    expect(within(canvas).getByText("order_total")).toBeInTheDocument();
    expect(within(canvas).getByText("order_amount")).toBeInTheDocument();
  });

  it("does not mutate the future projection after mode changes", async () => {
    await renderGraph();
    await userEvent.click(screen.getByRole("button", { name: "Current" }));
    await userEvent.click(screen.getByRole("button", { name: "Diff" }));
    await userEvent.click(screen.getByRole("button", { name: "Future" }));
    expect(screen.getByText(/Future · 26 fields · 27 relationships/)).toBeVisible();
    expect(
      within(screen.getByTestId("graph-mode-future")).getByText("order_amount"),
    ).toBeInTheDocument();
  });

  it("exposes a visibly labelled UNKNOWN root relationship", async () => {
    await renderGraph();
    expect(screen.getByText("UNKNOWN")).toBeInTheDocument();
  });

  it("keeps UNKNOWN distinct from INCOMPATIBLE in the legend", async () => {
    await renderGraph();
    const legend = screen.getByLabelText("Graph legend");
    expect(within(legend).getByText("Unknown")).toBeVisible();
    expect(within(legend).getByText("Incompatible")).toBeVisible();
  });

  it("reports all 26 conditionally compatible relationships", async () => {
    await renderGraph();
    expect(
      screen.getByText(/The other 26 assessed future relationships are CONDITIONALLY COMPATIBLE/),
    ).toBeVisible();
  });

  it("renders the certified summary counts", async () => {
    await renderGraph();
    expect(screen.getByText("48")).toBeVisible();
    expect(screen.getByText("paths")).toBeVisible();
    expect(screen.getByText("5")).toBeVisible();
    expect(screen.getByText("max depth")).toBeVisible();
  });

  it("opens a field inspector from a node selection", async () => {
    const { container } = await renderGraph();
    await waitFor(() => {
      expect(container.querySelector('[data-id="future-0"]')).not.toBeNull();
    });
    const node = container.querySelector('[data-id="future-0"]');
    expect(node).not.toBeNull();
    fireEvent.click(node!);
    expect(screen.getByText("Field")).toBeVisible();
    expect(screen.getByText("Graph state")).toBeVisible();
  });

  it("opens a relationship inspector from an edge selection", async () => {
    await renderGraph();
    await userEvent.click(
      screen.getByRole("button", { name: "Inspect UNKNOWN root boundary" }),
    );
    expect(screen.getByText("Relationship")).toBeVisible();
    expect(screen.getByText("Path participation")).toBeVisible();
  });

  it("shows root current and future identities in the edge inspector", async () => {
    await renderGraph();
    await userEvent.click(
      screen.getByRole("button", { name: "Inspect UNKNOWN root boundary" }),
    );
    expect(screen.getByText(/Current: order_total → derived_total_1/)).toBeVisible();
    expect(screen.getByText(/Future: order_amount → derived_total_1/)).toBeVisible();
  });

  it("shows all four missing-evidence labels for the root edge", async () => {
    await renderGraph();
    await userEvent.click(
      screen.getByRole("button", { name: "Inspect UNKNOWN root boundary" }),
    );
    expect(screen.getByText("Explicit rename mapping")).toBeVisible();
    expect(screen.getByText("Transform semantics")).toBeVisible();
    expect(screen.getByText("Query evidence")).toBeVisible();
    expect(screen.getByText("Runtime validation")).toBeVisible();
  });

  it("selects the shortest representative certified path", async () => {
    await renderGraph();
    await userEvent.click(screen.getByRole("button", { name: "Shortest boundary" }));
    expect(screen.getByText("Certified path")).toBeVisible();
    expect(screen.getByRole("button", { name: "Shortest boundary" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("selects the deepest representative certified path", async () => {
    await renderGraph();
    await userEvent.click(screen.getByRole("button", { name: "Deepest path" }));
    expect(screen.getByText("Certified path")).toBeVisible();
    expect(screen.getByRole("button", { name: "Deepest path" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("selects the multipath representative field", async () => {
    await renderGraph();
    await userEvent.click(screen.getByRole("button", { name: "Multipath field" }));
    expect(screen.getByText("Certified path")).toBeVisible();
    expect(screen.getByRole("button", { name: "Multipath field" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("searches already supplied field and dataset labels", async () => {
    await renderGraph();
    await userEvent.type(
      screen.getByRole("searchbox", { name: "Search graph fields" }),
      "derived_total_25",
    );
    expect(screen.getByText(/Future · 1 fields · 0 relationships/)).toBeVisible();
  });

  it("filters the supplied nodes by platform", async () => {
    await renderGraph();
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Filter by platform" }),
      "postgres",
    );
    expect(screen.getByText(/Future · 1 fields · 0 relationships/)).toBeVisible();
  });

  it("filters supplied relationships by UNKNOWN", async () => {
    await renderGraph();
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Filter by compatibility" }),
      "unknown",
    );
    expect(screen.getByText(/Future · 2 fields · 1 relationships/)).toBeVisible();
  });

  it("filters supplied relationships by conditional compatibility", async () => {
    await renderGraph();
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Filter by compatibility" }),
      "conditionally_compatible",
    );
    expect(screen.getByText(/Future · 26 fields · 26 relationships/)).toBeVisible();
  });

  it("shows an empty display-filter state without changing the contract", async () => {
    await renderGraph();
    await userEvent.type(
      screen.getByRole("searchbox", { name: "Search graph fields" }),
      "does-not-exist",
    );
    expect(screen.getByText("No fields match these display filters")).toBeVisible();
    expect(
      screen.getByText("The certified graph is unchanged. Clear filters to restore it."),
    ).toBeVisible();
  });

  it("provides a dedicated fit-to-view control", async () => {
    await renderGraph();
    expect(screen.getByRole("button", { name: "Fit graph to view" })).toBeEnabled();
  });

  it("clears selection and all display filters", async () => {
    await renderGraph();
    await userEvent.type(
      screen.getByRole("searchbox", { name: "Search graph fields" }),
      "does-not-exist",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Clear selection and filters" }),
    );
    expect(screen.getByRole("searchbox", { name: "Search graph fields" })).toHaveValue(
      "",
    );
    expect(screen.getByText(/Future · 26 fields · 27 relationships/)).toBeVisible();
  });

  it("exposes accessible pressed states for all graph modes", async () => {
    await renderGraph();
    for (const label of ["Current", "Future", "Diff"]) {
      expect(screen.getByRole("button", { name: label })).toHaveAttribute(
        "aria-pressed",
      );
    }
  });

  it("rejects a malformed graph instead of showing fallback content", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({ invalid: true })));
    render(<GraphWorkspace reviewId="CHRONOS-DEMO-001" />);
    expect(
      await screen.findByText("Graph contract invalid"),
    ).toBeVisible();
    expect(screen.queryByText("Graph summary")).not.toBeInTheDocument();
  });

  it("closes the graph when the backend certification gate fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        response(
          {
            detail: {
              code: "certification_integrity_error",
              message: "Certification mismatch.",
            },
          },
          503,
        ),
      ),
    );
    render(<GraphWorkspace reviewId="CHRONOS-DEMO-001" />);
    expect(
      await screen.findByText("Certification integrity failure"),
    ).toBeVisible();
    expect(screen.getByText("Certification mismatch.")).toBeVisible();
  });

  it("retries a failed certified graph load", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(
        response(
          { detail: { code: "unavailable", message: "Not ready." } },
          503,
        ),
      )
      .mockResolvedValueOnce(response(graphFixture));
    vi.stubGlobal("fetch", fetcher);
    render(<GraphWorkspace reviewId="CHRONOS-DEMO-001" />);
    await userEvent.click(await screen.findByRole("button", { name: "Retry" }));
    expect(await screen.findByText("Graph summary")).toBeVisible();
    const graphCalls = fetcher.mock.calls.filter(([url]) =>
      String(url).endsWith("/graph"),
    );
    expect(graphCalls).toHaveLength(2);
  });

  it("contains no client-side DFS, BFS, or lineage inference implementation", () => {
    const source = readFileSync(
      resolve(process.cwd(), "components/graph/graph-workspace.tsx"),
      "utf8",
    );
    expect(source).not.toMatch(/\b(?:dfs|bfs)\b/i);
    expect(source).not.toContain("inferLineage");
    expect(source).not.toContain("computeCompatibility");
  });

  it("keeps the graph read-only without connection handles", async () => {
    const { container } = await renderGraph();
    const node = container.querySelector('[data-id="future-0"]');
    expect(node).not.toBeNull();
    fireEvent.click(node as Element);
    await waitFor(() => expect(screen.getByText("Field")).toBeVisible());
    expect(screen.queryByText(/create relationship/i)).not.toBeInTheDocument();
  });
});
