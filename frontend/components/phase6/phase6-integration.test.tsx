import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AnalysisIndexPage } from "@/components/phase6/analysis-index-page";
import { AnalysisPage } from "@/components/phase6/analysis-page";
import {
  fetchAnalysis,
  fetchAnalysisEvidence,
  fetchAnalysisGraph,
  fetchAnalysisIndex,
  fetchPatchPreview,
  fetchReleaseCertification,
} from "@/lib/phase6-api";
import type { AnalysisDetail } from "@/lib/phase6-contract";
import {
  analysisGraph,
  analysisIndex,
  conflictRepairDetail,
  evidence,
  noRepairDetail,
  patchPreview,
  pullRequestDetail,
  releaseCertification,
  repairDetail,
  semanticDetail,
  structuralDetail,
} from "@/test/phase6-fixture";

vi.mock("@/lib/phase6-api", () => ({
  fetchAnalysis: vi.fn(),
  fetchAnalysisEvidence: vi.fn(),
  fetchAnalysisGraph: vi.fn(),
  fetchAnalysisIndex: vi.fn(),
  fetchPatchPreview: vi.fn(),
  fetchReleaseCertification: vi.fn(),
}));

beforeEach(() => {
  vi.mocked(fetchAnalysisIndex).mockResolvedValue(analysisIndex);
  vi.mocked(fetchReleaseCertification).mockResolvedValue(releaseCertification);
  vi.mocked(fetchAnalysis).mockResolvedValue(structuralDetail);
  vi.mocked(fetchAnalysisGraph).mockResolvedValue(analysisGraph);
  vi.mocked(fetchAnalysisEvidence).mockResolvedValue(evidence);
  vi.mocked(fetchPatchPreview).mockResolvedValue(patchPreview);
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

async function renderDetail(detail: AnalysisDetail = structuralDetail) {
  vi.mocked(fetchAnalysis).mockResolvedValue(detail);
  if (detail.analysisType === "repair") {
    vi.mocked(fetchAnalysisGraph).mockResolvedValue({
      ...analysisGraph,
      analysisId: detail.analysisId,
      mode: "PROJECTED_REPAIRED",
      availableModes: ["CURRENT", "PROPOSED", "PROJECTED_REPAIRED"],
    });
  }
  render(<AnalysisPage analysisId={detail.analysisId} />);
  await screen.findByRole("heading", { name: detail.displayName });
}

describe("Phase 6 certified analysis index", () => {
  it("announces the loading state", () => {
    vi.mocked(fetchAnalysisIndex).mockReturnValue(new Promise(() => undefined));
    render(<AnalysisIndexPage />);
    expect(screen.getByLabelText("Loading certified analysis index")).toHaveAttribute("aria-busy", "true");
  });

  it("renders all certified analysis types", async () => {
    render(<AnalysisIndexPage />);
    expect(await screen.findByText("Generalized field rename")).toBeVisible();
    expect(screen.getByText("Aggregation semantic change")).toBeVisible();
    expect(screen.getByText("Conflicting pull request")).toBeVisible();
    expect(screen.getByText("Partial repair candidate")).toBeVisible();
  });

  it("shows the exact non-blocking limitation", async () => {
    render(<AnalysisIndexPage />);
    expect(await screen.findByText("Live DataHub integration tests were not rerun in this offline certification environment. Static, deterministic, and frozen-fixture evidence passed.")).toBeVisible();
  });

  it("filters the catalog by analysis type", async () => {
    render(<AnalysisIndexPage />);
    await screen.findByText("Generalized field rename");
    fireEvent.change(screen.getByLabelText("Filter by type"), { target: { value: "repair" } });
    expect(screen.getByText("Partial repair candidate")).toBeVisible();
    expect(screen.queryByText("Generalized field rename")).not.toBeInTheDocument();
  });

  it("searches by title or scenario", async () => {
    render(<AnalysisIndexPage />);
    await screen.findByText("Generalized field rename");
    fireEvent.change(screen.getByPlaceholderText("Search title or scenario"), { target: { value: "Aggregation" } });
    expect(screen.getByText("Aggregation semantic change")).toBeVisible();
    expect(screen.queryByText("Conflicting pull request")).not.toBeInTheDocument();
  });

  it("fails closed when the index is unavailable", async () => {
    vi.mocked(fetchAnalysisIndex).mockRejectedValue(new Error("fingerprint mismatch"));
    render(<AnalysisIndexPage />);
    expect(await screen.findByRole("heading", { name: "CERTIFIED ANALYSIS UNAVAILABLE" })).toBeVisible();
    expect(screen.getByText("fingerprint mismatch")).toBeVisible();
  });

  it("fails closed for a not-certified gate", async () => {
    vi.mocked(fetchAnalysisIndex).mockResolvedValue({
      ...analysisIndex,
      certification: { ...analysisIndex.certification, state: "PHASE_6_NOT_CERTIFIED" },
    });
    render(<AnalysisIndexPage />);
    expect(await screen.findByText("The release certification gate rejected this package.")).toBeVisible();
    expect(screen.queryByText("Generalized field rename")).not.toBeInTheDocument();
  });

  it("exposes release totals without claiming runtime validation", async () => {
    render(<AnalysisIndexPage />);
    const release = await screen.findByText("Phase 6 release certification");
    fireEvent.click(release);
    expect(screen.getByText("1477/1484 passed")).toBeVisible();
    expect(screen.getByText("UNVERIFIED")).toBeVisible();
  });
});

describe("Phase 6 certified analysis detail", () => {
  it("renders structural current and proposed fields", async () => {
    await renderDetail(structuralDetail);
    expect(screen.getByText("order_total")).toBeVisible();
    expect(screen.getByText("order_amount")).toBeVisible();
    expect(screen.getByText("Consumer contract evidence")).toBeVisible();
  });

  it("renders semantic before and after meaning", async () => {
    await renderDetail(semanticDetail);
    expect(screen.getByText("sum(order_total)")).toBeVisible();
    expect(screen.getByText("avg(order_total)")).toBeVisible();
    expect(screen.getByText("The output meaning may change.")).toBeVisible();
  });

  it("renders PR changed files, groups, and explicit conflicts", async () => {
    await renderDetail(pullRequestDetail);
    expect(screen.getByText("models/orders.sql")).toBeVisible();
    expect(screen.getByText("No winner selected")).toBeVisible();
    expect(screen.getByText("Two competing identities are proposed.")).toBeVisible();
  });

  it("keeps certification, decision, coherence, and execution separate", async () => {
    await renderDetail(pullRequestDetail);
    expect(screen.getAllByText("INCONSISTENT").length).toBeGreaterThan(0);
    expect(screen.getAllByText("UNVERIFIED").length).toBeGreaterThan(0);
    expect(screen.getByText("CERTIFIED WITH NON-BLOCKING LIMITATIONS")).toBeVisible();
  });

  it("renders graph evidence supplied by the server", async () => {
    await renderDetail(structuralDetail);
    expect(await screen.findByText("3 nodes")).toBeVisible();
    expect(screen.getByText("2 relationships")).toBeVisible();
    expect(screen.getByText("COUNTERFACTUAL EDGE")).toBeVisible();
    expect(screen.getByRole("tab", { name: "CURRENT" })).toBeVisible();
    expect(screen.getByRole("tab", { name: "DIFF" })).toBeVisible();
  });

  it("activates graph modes from the keyboard", async () => {
    const user = userEvent.setup();
    await renderDetail(structuralDetail);
    const current = await screen.findByRole("tab", { name: "CURRENT" });
    current.focus();
    await user.keyboard("{Enter}");
    await waitFor(() => expect(fetchAnalysisGraph).toHaveBeenLastCalledWith(
      structuralDetail.analysisId,
      "CURRENT",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    ));
  });

  it("selects a representative multi-root path", async () => {
    await renderDetail(structuralDetail);
    const path = await screen.findByRole("button", { name: /path-a/ });
    fireEvent.click(path);
    expect(screen.getByText("root-a, root-b")).toBeVisible();
    expect(screen.getByLabelText("Selected path traceability")).toBeVisible();
  });

  it("renders evidence labels without promoting them to runtime truth", async () => {
    await renderDetail(structuralDetail);
    expect(await screen.findByText("The static parser observed a stale field reference.")).toBeVisible();
    expect(screen.getAllByText("CODE-DERIVED").length).toBeGreaterThan(0);
    expect(screen.getAllByText("UNVERIFIED").length).toBeGreaterThan(0);
  });

  it("isolates graph endpoint failure from the certified detail", async () => {
    vi.mocked(fetchAnalysisGraph).mockRejectedValue(new Error("graph package unavailable"));
    await renderDetail(structuralDetail);
    expect(await screen.findByText("graph package unavailable")).toBeVisible();
    expect(screen.getByText("order_total")).toBeVisible();
  });

  it("fails the entire detail closed when certification data is unavailable", async () => {
    vi.mocked(fetchAnalysis).mockRejectedValue(new Error("manifest mismatch"));
    render(<AnalysisPage analysisId="bad" />);
    expect(await screen.findByText("manifest mismatch")).toBeVisible();
    expect(screen.queryByText("Structural change")).not.toBeInTheDocument();
  });

  it("renders repairability, ordered actions, and projected comparison", async () => {
    await renderDetail(repairDetail);
    expect(screen.getByText("Repair Plan")).toBeVisible();
    expect(screen.getByText("AUTO REPAIRABLE")).toBeVisible();
    expect(screen.getByText("PARTIALLY_COHERENT → COHERENT")).toBeVisible();
    expect(screen.getByText("PHASE 7 REQUIRED")).toBeVisible();
    expect(await screen.findByText("PROJECTED REPAIRED · STATIC ONLY · RUNTIME UNVERIFIED")).toBeVisible();
    expect(screen.getByText("RUNTIME EVIDENCE COLLECTION")).toBeVisible();
  });

  it("loads a bounded candidate patch only on request", async () => {
    await renderDetail(repairDetail);
    expect(fetchPatchPreview).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Load bounded preview" }));
    expect(await screen.findByText(/CANDIDATE - NOT APPLIED/)).toBeVisible();
    expect(screen.getByRole("region", { name: "Patch for models/orders.sql" })).toBeVisible();
    expect(fetchPatchPreview).toHaveBeenCalledTimes(1);
  });

  it("renders the valid no-repair empty state", async () => {
    await renderDetail(noRepairDetail);
    expect(screen.getAllByText("NO SUPPORTED AUTOMATIC REPAIR").length).toBeGreaterThan(0);
    expect(screen.queryByText("Repair Plan")).not.toBeInTheDocument();
  });

  it("renders the conflict-blocked empty state without a winner", async () => {
    await renderDetail(conflictRepairDetail);
    expect(screen.getByText("No patch permitted until competing certified identities are resolved.")).toBeVisible();
    expect(screen.queryByRole("button", { name: /apply|approve/i })).not.toBeInTheDocument();
  });

  it("contains no apply, approve, merge, or execution controls", async () => {
    await renderDetail(repairDetail);
    expect(screen.queryByRole("button", { name: /apply|approve|merge|execute/i })).not.toBeInTheDocument();
  });

  it("aborts stale detail requests when the view unmounts", async () => {
    vi.mocked(fetchAnalysis).mockReturnValue(new Promise(() => undefined));
    const view = render(<AnalysisPage analysisId="pending" />);
    view.unmount();
    await waitFor(() => expect(fetchAnalysis).toHaveBeenCalledTimes(1));
    const options = vi.mocked(fetchAnalysis).mock.calls[0]?.[1];
    expect(options?.signal?.aborted).toBe(true);
  });
});
