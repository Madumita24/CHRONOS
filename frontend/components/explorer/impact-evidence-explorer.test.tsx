import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ImpactEvidenceExplorer } from "@/components/explorer/impact-evidence-explorer";
import {
  ExplorerContractError,
  fetchCertifiedExplorer,
} from "@/lib/api";
import type { CertifiedImpactExplorer } from "@/lib/explorer-contract";
import { explorerFixture } from "@/test/explorer-fixture";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, fetchCertifiedExplorer: vi.fn() };
});

const fixture = explorerFixture() as unknown as CertifiedImpactExplorer;

function renderExplorer(onSelect = vi.fn()) {
  render(
    <ImpactEvidenceExplorer
      reviewId="CHRONOS-DEMO-001"
      selection={null}
      selectedMachineKey={null}
      onSelect={onSelect}
    />,
  );
  return onSelect;
}

describe("ImpactEvidenceExplorer", () => {
  beforeEach(() => {
    vi.mocked(fetchCertifiedExplorer).mockReset();
    vi.mocked(fetchCertifiedExplorer).mockResolvedValue(fixture);
  });

  it("loads the certified explorer for the current review", async () => {
    renderExplorer();
    expect(await screen.findByText("Show me why")).toBeInTheDocument();
    expect(fetchCertifiedExplorer).toHaveBeenCalledWith(
      "CHRONOS-DEMO-001",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });

  it("renders one shared root cause", async () => {
    renderExplorer();
    expect(
      await screen.findByText("One shared technical root cause"),
    ).toBeInTheDocument();
    expect(screen.getByText("UNKNOWN · evidence INSUFFICIENT")).toBeInTheDocument();
  });

  it("renders the blocking question", async () => {
    renderExplorer();
    expect(
      await screen.findAllByText(
        "Does the Spark export accept the renamed input?",
      ),
    ).toHaveLength(2);
    expect(screen.getAllByText("Spark configuration")).toHaveLength(2);
    expect(screen.getAllByText("Input query or code")).toHaveLength(2);
    expect(screen.getAllByText("Explicit rename mapping")).toHaveLength(2);
    expect(screen.getAllByText("Validated execution")).toHaveLength(2);
  });

  it("renders canonical explorer totals", async () => {
    renderExplorer();
    await screen.findByText("Show me why");
    expect(screen.getByText("25")).toBeInTheDocument();
    expect(screen.getByText("20")).toBeInTheDocument();
    expect(screen.getByText("48")).toBeInTheDocument();
    expect(screen.getByText("66")).toBeInTheDocument();
  });

  it("selecting a field requests graph node synchronization", async () => {
    const onSelect = renderExplorer();
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: /field_0/i }));
    expect(onSelect).toHaveBeenCalledWith({
      kind: "node",
      id: "future-field-0",
      machineKey: fixture.fields[0].machineKey,
    });
  });

  it("selecting a path requests graph path synchronization", async () => {
    const onSelect = renderExplorer();
    const user = userEvent.setup();
    await user.click(await screen.findByRole("tab", { name: "Paths" }));
    await user.click(
      screen.getByRole("button", { name: /field_0.*dataset_0/i }),
    );
    expect(onSelect).toHaveBeenCalledWith({
      kind: "path",
      id: "dependency-path-0",
    });
  });

  it("selecting a relationship requests graph edge synchronization", async () => {
    const onSelect = renderExplorer();
    const user = userEvent.setup();
    await user.click(
      await screen.findByRole("tab", { name: "Relationships" }),
    );
    await user.click(
      screen.getByRole("button", {
        name: /field_0.*field_1.*dataset_0.*dataset_1/i,
      }),
    );
    expect(onSelect).toHaveBeenCalledWith({
      kind: "edge",
      id: "future-edge-0",
    });
  });

  it("dataset selection opens its certified dataset detail", async () => {
    const onSelect = renderExplorer();
    const user = userEvent.setup();
    await user.click(await screen.findByRole("tab", { name: "Datasets" }));
    await user.click(screen.getByRole("button", { name: /dataset_0/i }));
    expect(onSelect).toHaveBeenCalledWith({
      kind: "dataset",
      id: fixture.datasets[0].datasetId,
    });
  });

  it("context selection opens its certified context detail", async () => {
    const onSelect = renderExplorer();
    const user = userEvent.setup();
    await user.click(await screen.findByRole("tab", { name: "Context" }));
    await user.click(screen.getByRole("button", { name: /Context 0/i }));
    expect(onSelect).toHaveBeenCalledWith({
      kind: "context",
      id: fixture.contextAssets[0].contextAssetId,
    });
  });

  it("renders certified field and dataset severity distributions", async () => {
    renderExplorer();
    expect(
      await screen.findByLabelText("Field severity if realized"),
    ).toHaveTextContent("High 3");
    const user = userEvent.setup();
    await user.click(screen.getByRole("tab", { name: "Datasets" }));
    expect(
      screen.getByLabelText("Dataset severity if realized"),
    ).toHaveTextContent("Moderate 4");
  });

  it("filters fields by certified severity without refetching", async () => {
    renderExplorer();
    const user = userEvent.setup();
    await user.selectOptions(
      await screen.findByLabelText("Filter fields by severity"),
      "high",
    );
    expect(screen.getAllByRole("button", { name: /field_/i })).toHaveLength(3);
    expect(fetchCertifiedExplorer).toHaveBeenCalledTimes(1);
  });

  it("groups context assets by governance, operational, and consumer", async () => {
    renderExplorer();
    const user = userEvent.setup();
    await user.click(await screen.findByRole("tab", { name: "Context" }));
    expect(screen.getByRole("heading", { name: "Governance" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Operational" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Consumer" })).toBeInTheDocument();
  });

  it("search filters already-loaded field records", async () => {
    renderExplorer();
    const user = userEvent.setup();
    const search = await screen.findByRole("searchbox");
    await user.type(search, "field_24");
    expect(screen.getByRole("button", { name: /field_24/i })).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /field_0\b/i }),
    ).not.toBeInTheDocument();
    expect(fetchCertifiedExplorer).toHaveBeenCalledTimes(1);
  });

  it("shows an empty state when search has no loaded matches", async () => {
    renderExplorer();
    const user = userEvent.setup();
    await user.type(await screen.findByRole("searchbox"), "no-such-field");
    expect(screen.getByText("No loaded records match")).toBeInTheDocument();
  });

  it("shows the evidence chain and its observed classification", async () => {
    renderExplorer();
    expect(
      await screen.findByText("Current source field observed."),
    ).toBeInTheDocument();
    expect(screen.getByText("Observed evidence")).toBeInTheDocument();
  });

  it("shows the certified decision explanation", async () => {
    renderExplorer();
    expect(
      await screen.findByRole("heading", { name: "HOLD FOR REVIEW" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("The source boundary remains unresolved."),
    ).toBeInTheDocument();
  });

  it("opens field impact detail from a graph selection", async () => {
    render(
      <ImpactEvidenceExplorer
        reviewId="CHRONOS-DEMO-001"
        selection={{ kind: "node", id: "current-field-0" }}
        selectedMachineKey={fixture.fields[0].machineKey}
        onSelect={vi.fn()}
      />,
    );
    expect(await screen.findByText("Field impact")).toBeInTheDocument();
    expect(screen.getByText("Certified field explanation.")).toBeInTheDocument();
  });

  it("shows dataset scope detail from the shared selection state", async () => {
    render(
      <ImpactEvidenceExplorer
        reviewId="CHRONOS-DEMO-001"
        selection={{ kind: "dataset", id: fixture.datasets[0].datasetId }}
        selectedMachineKey={null}
        onSelect={vi.fn()}
      />,
    );
    expect(await screen.findByText("Dataset impact")).toBeInTheDocument();
    expect(screen.getByText("Exposed fields")).toBeInTheDocument();
    expect(screen.getByText("Connected context")).toBeInTheDocument();
  });

  it("shows context linkage detail without assigning severity", async () => {
    render(
      <ImpactEvidenceExplorer
        reviewId="CHRONOS-DEMO-001"
        selection={{
          kind: "context",
          id: fixture.contextAssets[0].contextAssetId,
        }}
        selectedMachineKey={null}
        onSelect={vi.fn()}
      />,
    );
    expect(await screen.findByText("Context detail")).toBeInTheDocument();
    expect(screen.getByText("Relationship count")).toBeInTheDocument();
    expect(screen.getAllByText("Certified provenance").length).toBeGreaterThan(0);
    expect(
      within(screen.getByLabelText("Impact evidence detail")).queryByText(
        "Severity if realized",
      ),
    ).not.toBeInTheDocument();
  });

  it("renders a certification integrity failure without fallback data", async () => {
    vi.mocked(fetchCertifiedExplorer).mockRejectedValue(
      new ExplorerContractError(),
    );
    renderExplorer();
    expect(
      await screen.findByText("Explorer contract invalid"),
    ).toBeInTheDocument();
    expect(screen.queryByText("Context 0")).not.toBeInTheDocument();
  });

  it("supports retry after a load failure", async () => {
    vi.mocked(fetchCertifiedExplorer)
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce(fixture);
    renderExplorer();
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Retry" }));
    expect(await screen.findByText("Show me why")).toBeInTheDocument();
    await waitFor(() => expect(fetchCertifiedExplorer).toHaveBeenCalledTimes(2));
  });
});
