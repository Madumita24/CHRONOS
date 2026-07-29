import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ReviewPage } from "@/components/review-page";
import { reviewFixture } from "@/test/review-fixture";

function response(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("ReviewPage", () => {
  it("announces its loading state", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => undefined)));
    render(<ReviewPage reviewId="CHRONOS-DEMO-001" />);
    expect(screen.getByText("Loading certified review")).toBeInTheDocument();
    expect(screen.getByRole("main")).toHaveAttribute("aria-busy", "true");
  });

  it("renders the certified disposition", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(response(reviewFixture)),
    );
    render(<ReviewPage reviewId="CHRONOS-DEMO-001" />);
    expect(
      await screen.findByRole("heading", { name: "HOLD FOR REVIEW" }),
    ).toBeInTheDocument();
  });

  it("keeps decision and technical certainty separate", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(response(reviewFixture)),
    );
    render(<ReviewPage reviewId="CHRONOS-DEMO-001" />);
    expect(await screen.findByText("Decision certainty")).toBeInTheDocument();
    expect(screen.getAllByText("Technical certainty")).toHaveLength(2);
    expect(screen.getByText("HIGH CONFIDENCE")).toBeInTheDocument();
    expect(screen.getAllByText("UNRESOLVED").length).toBeGreaterThan(0);
  });

  it("renders the consolidated primary scope metrics", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(response(reviewFixture)),
    );
    render(<ReviewPage reviewId="CHRONOS-DEMO-001" />);
    await screen.findByText("Technically unresolved fields");
    expect(screen.getByText("Datasets")).toBeInTheDocument();
    expect(screen.getByText("Dependency paths")).toBeInTheDocument();
  });

  it("identifies the exact change without implying a dataset rename", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(response(reviewFixture)),
    );
    render(<ReviewPage reviewId="CHRONOS-DEMO-001" />);
    expect(await screen.findByText("Dataset unchanged: orders")).toBeVisible();
    expect(screen.getByText("order_total")).toBeVisible();
    expect(screen.getByText("order_amount")).toBeVisible();
  });

  it("states that no downstream failure is confirmed", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(response(reviewFixture)),
    );
    render(<ReviewPage reviewId="CHRONOS-DEMO-001" />);
    expect(
      await screen.findByText("No confirmed downstream failure"),
    ).toBeInTheDocument();
  });

  it("renders current and counterfactual fields", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(response(reviewFixture)),
    );
    render(<ReviewPage reviewId="CHRONOS-DEMO-001" />);
    expect((await screen.findAllByText("order_total")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("order_amount").length).toBeGreaterThan(0);
    expect(screen.getByText("Certified Current")).toBeInTheDocument();
    expect(screen.getAllByText("Counterfactual").length).toBeGreaterThan(0);
  });

  it("uses conditional severity wording", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(response(reviewFixture)),
    );
    render(<ReviewPage reviewId="CHRONOS-DEMO-001" />);
    expect(
      await screen.findByText("if the unresolved condition materializes"),
    ).toBeInTheDocument();
  });

  it("renders the blocking question", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(response(reviewFixture)),
    );
    render(<ReviewPage reviewId="CHRONOS-DEMO-001" />);
    expect(
      await screen.findByRole("heading", {
        name: /Does the Spark export mapping accept/,
      }),
    ).toBeInTheDocument();
  });

  it("renders required evidence", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(response(reviewFixture)),
    );
    render(<ReviewPage reviewId="CHRONOS-DEMO-001" />);
    expect(
      await screen.findByText("Explicit Rename Mapping"),
    ).toBeInTheDocument();
  });

  it("renders representative path without graph computation", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(response(reviewFixture)),
    );
    render(<ReviewPage reviewId="CHRONOS-DEMO-001" />);
    expect(
      await screen.findByRole("heading", {
        name: "Representative dependency paths",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("1 hops")).toBeInTheDocument();
  });

  it("renders certified context highlights", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(response(reviewFixture)),
    );
    render(<ReviewPage reviewId="CHRONOS-DEMO-001" />);
    expect(await screen.findByText("Popular Products")).toBeInTheDocument();
  });

  it("renders certification check provenance", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(response(reviewFixture)),
    );
    render(<ReviewPage reviewId="CHRONOS-DEMO-001" />);
    expect(await screen.findByText("49/49 checks passed")).toBeInTheDocument();
  });

  it("renders a transport error state", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new TypeError("Failed to fetch")),
    );
    render(<ReviewPage reviewId="CHRONOS-DEMO-001" />);
    expect(
      await screen.findByRole("heading", {
        name: "The review service is unavailable",
      }),
    ).toBeInTheDocument();
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("renders a distinct integrity error state", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        response(
          {
            detail: {
              code: "certification_integrity_error",
              message: "Integrity checks failed.",
            },
          },
          503,
        ),
      ),
    );
    render(<ReviewPage reviewId="CHRONOS-DEMO-001" />);
    expect(
      await screen.findByRole("heading", {
        name: "Certified review withheld",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "No fallback data is shown. Restore the certified artifacts and retry.",
      ),
    ).toBeInTheDocument();
  });

  it("treats invalid successful payloads as integrity errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(response({ status: "certified" })),
    );
    render(<ReviewPage reviewId="CHRONOS-DEMO-001" />);
    expect(
      await screen.findByText("Contract invalid"),
    ).toBeInTheDocument();
  });

  it("retries after an error", async () => {
    const fetcher = vi
      .fn()
      .mockRejectedValueOnce(new TypeError("Failed to fetch"))
      .mockResolvedValueOnce(response(reviewFixture));
    vi.stubGlobal("fetch", fetcher);
    render(<ReviewPage reviewId="CHRONOS-DEMO-001" />);
    fireEvent.click(await screen.findByRole("button", { name: /Retry/ }));
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));
    expect(
      await screen.findByRole("heading", { name: "HOLD FOR REVIEW" }),
    ).toBeInTheDocument();
  });

  it("exposes the primary navigation landmark", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(response(reviewFixture)),
    );
    render(<ReviewPage reviewId="CHRONOS-DEMO-001" />);
    await screen.findByText("Certified change review");
    expect(
      screen.getByRole("navigation", { name: "Primary navigation" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("main")).toBeInTheDocument();
  });
});
