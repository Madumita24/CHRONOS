import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ReviewPage } from "@/components/review-page";
import { explorerFixture } from "@/test/explorer-fixture";
import { graphFixture } from "@/test/graph-fixture";
import { reviewFixture } from "@/test/review-fixture";

const certifiedExplorerFixture = explorerFixture();

function response(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function renderWorkflow(graphStatus = 200) {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/graph")) {
        return Promise.resolve(response(graphFixture, graphStatus));
      }
      if (url.endsWith("/explorer")) {
        return Promise.resolve(response(certifiedExplorerFixture));
      }
      return Promise.resolve(response(reviewFixture));
    }),
  );
  return render(<ReviewPage reviewId="CHRONOS-DEMO-001" />);
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  window.history.replaceState({}, "", "/review");
});

describe("certified change review workflow", () => {
  it("presents the five-stage workflow with persistent review context", async () => {
    renderWorkflow();
    await screen.findByText("Certified impact assessment");
    const navigation = screen.getByRole("navigation", { name: "Review sections" });
    for (const section of ["Overview", "Graph", "Impact", "Evidence", "Decision"]) {
      expect(within(navigation).getByRole("button", { name: section })).toBeVisible();
    }
    expect(screen.getByText("Phase 4 certified")).toBeVisible();
    expect(screen.getByText("Operation")).toBeVisible();
  });

  it("navigates to each workflow section without losing the certified result", async () => {
    renderWorkflow();
    const navigation = await screen.findByRole("navigation", {
      name: "Review sections",
    });
    const user = userEvent.setup();
    for (const section of ["Graph", "Impact", "Evidence", "Decision"]) {
      await user.click(within(navigation).getByRole("button", { name: section }));
      expect(window.location.search).toBe(`?section=${section.toLowerCase()}`);
      expect(
        within(navigation).getByRole("button", { name: section }),
      ).toHaveAttribute("aria-current", "location");
    }
    expect(
      screen.getByRole("heading", { name: "Hold for review", level: 1 }),
    ).toBeVisible();
  });

  it("focuses the certified UNKNOWN root boundary from the overview", async () => {
    renderWorkflow();
    await screen.findByText("Graph summary");
    const user = userEvent.setup();
    await user.click(
      screen.getAllByRole("button", { name: "View unresolved boundary" })[0],
    );
    expect(window.location.search).toBe("?section=graph");
    expect(await screen.findByText("Relationship evidence")).toBeVisible();
  });

  it("synchronizes a field selection with impact detail", async () => {
    renderWorkflow();
    const explorer = await screen.findByRole("region", { name: "Show me why" });
    const user = userEvent.setup();
    await user.click(
      await within(explorer).findByRole("button", {
        name: /field_0 dataset_0/i,
      }),
    );
    expect(await screen.findByText("Field impact")).toBeVisible();
  });

  it("synchronizes the root edge with relationship evidence", async () => {
    renderWorkflow();
    const user = userEvent.setup();
    await user.click(
      await screen.findByRole("button", {
        name: "Inspect unknown root boundary",
      }),
    );
    expect(await screen.findByText("Relationship evidence")).toBeVisible();
    expect(screen.getAllByText("Path participation").length).toBeGreaterThan(0);
  });

  it("opens certified path evidence from a supplied path selection", async () => {
    renderWorkflow();
    const explorer = await screen.findByRole("region", { name: "Show me why" });
    const user = userEvent.setup();
    await user.click(await within(explorer).findByRole("tab", { name: "Paths" }));
    await user.click(
      within(explorer).getByRole("button", { name: /dependency-path-0/i }),
    );
    expect(await screen.findByText("Path evidence")).toBeVisible();
  });

  it("supports dataset and context selections in the unified detail surface", async () => {
    renderWorkflow();
    const explorer = await screen.findByRole("region", { name: "Show me why" });
    const user = userEvent.setup();
    await user.click(
      await within(explorer).findByRole("tab", { name: "Datasets" }),
    );
    await user.click(
      within(explorer).getByRole("button", { name: /dataset_0/i }),
    );
    expect(await screen.findByText("Dataset impact")).toBeVisible();

    await user.click(within(explorer).getByRole("tab", { name: "Context" }));
    await user.click(
      within(explorer).getByRole("button", {
        name: new RegExp(
          certifiedExplorerFixture.contextAssets[0].displayName,
          "i",
        ),
      }),
    );
    expect(await screen.findByText("Context detail")).toBeVisible();
  });

  it("clears stale selection when graph mode changes", async () => {
    renderWorkflow();
    const explorer = await screen.findByRole("region", { name: "Show me why" });
    const user = userEvent.setup();
    await user.click(
      await within(explorer).findByRole("button", {
        name: /field_0 dataset_0/i,
      }),
    );
    await screen.findByText("Field impact");
    await user.click(screen.getByRole("button", { name: "Current" }));
    expect(await screen.findByText("Unresolved is not failed")).toBeVisible();
  });

  it("reset returns to the future overview and clears selection", async () => {
    renderWorkflow();
    const explorer = await screen.findByRole("region", { name: "Show me why" });
    const user = userEvent.setup();
    await user.click(
      await within(explorer).findByRole("button", {
        name: /field_0 dataset_0/i,
      }),
    );
    await screen.findByText("Field impact");
    await user.click(screen.getByRole("button", { name: "Reset review" }));
    expect(window.location.search).toBe("?section=overview");
    expect(screen.getByRole("button", { name: "Future" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(await screen.findByText("Unresolved is not failed")).toBeVisible();
  });

  it("fails a partial graph feature honestly while preserving other certified sections", async () => {
    renderWorkflow(503);
    expect(
      await screen.findByText("Certified graph unavailable"),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Hold for review", level: 1 }),
    ).toBeVisible();
    expect(await screen.findByRole("region", { name: "Show me why" })).toBeVisible();
  });

  it("contains no repair, approval, or mutation controls", async () => {
    renderWorkflow();
    await screen.findByText("Certified impact assessment");
    expect(screen.queryByRole("button", { name: /repair/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /approve/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /apply/i })).not.toBeInTheDocument();
  });

  it("handles an invalid section deep link non-destructively", async () => {
    window.history.replaceState({}, "", "/review?section=not-a-section");
    renderWorkflow();
    expect(
      await screen.findByText(
        "The requested review section is unavailable. Showing the certified overview.",
      ),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Hold for review", level: 1 }),
    ).toBeVisible();
  });

  it("keeps HOLD distinct from confirmed failure and shows certified evidence inputs", async () => {
    renderWorkflow();
    await screen.findByText("Known, unknown, and required");
    expect(screen.getAllByText("0").length).toBeGreaterThan(0);
    expect(screen.getByText("HIGH")).toBeVisible();
    expect(
      screen.getAllByText(/not a confirmed failure/i).length,
    ).toBeGreaterThan(0);
    for (const evidence of [
      "Spark configuration",
      "Input query or code",
      "Explicit rename mapping",
      "Validated execution",
    ]) {
      expect(screen.getAllByText(evidence).length).toBeGreaterThan(0);
    }
    expect(screen.getByText("Certified decision rule")).toBeVisible();
    expect(screen.getByText("Certified reason codes")).toBeVisible();
  });
});
