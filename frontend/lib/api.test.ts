import { describe, expect, it, vi } from "vitest";

import {
  ExplorerContractError,
  GraphContractError,
  ReviewContractError,
  fetchCertifiedExplorer,
  fetchCertifiedGraph,
  fetchCertifiedReview,
} from "@/lib/api";
import { explorerFixture } from "@/test/explorer-fixture";
import { graphFixture } from "@/test/graph-fixture";
import { reviewFixture } from "@/test/review-fixture";

function response(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("fetchCertifiedReview", () => {
  it("loads and validates a certified review", async () => {
    const fetcher = vi.fn().mockResolvedValue(response(reviewFixture));
    await expect(
      fetchCertifiedReview("CHRONOS-DEMO-001", {
        fetcher,
        baseUrl: "http://api.test",
      }),
    ).resolves.toEqual(reviewFixture);
  });

  it("calls the read-only review endpoint", async () => {
    const fetcher = vi.fn().mockResolvedValue(response(reviewFixture));
    await fetchCertifiedReview("CHRONOS-DEMO-001", {
      fetcher,
      baseUrl: "http://api.test",
    });
    expect(fetcher).toHaveBeenCalledWith(
      "http://api.test/api/reviews/CHRONOS-DEMO-001",
      expect.objectContaining({ method: "GET", cache: "no-store" }),
    );
  });

  it("sends the JSON accept header", async () => {
    const fetcher = vi.fn().mockResolvedValue(response(reviewFixture));
    await fetchCertifiedReview("CHRONOS-DEMO-001", {
      fetcher,
      baseUrl: "http://api.test",
    });
    expect(fetcher.mock.calls[0][1].headers).toEqual({
      Accept: "application/json",
    });
  });

  it("encodes review identifiers", async () => {
    const fetcher = vi.fn().mockResolvedValue(response(reviewFixture));
    await fetchCertifiedReview("a/b", {
      fetcher,
      baseUrl: "http://api.test",
    });
    expect(fetcher.mock.calls[0][0]).toContain("a%2Fb");
  });

  it("surfaces stable API errors", async () => {
    const fetcher = vi.fn().mockResolvedValue(
      response(
        {
          detail: {
            code: "certification_integrity_error",
            message: "Integrity failed.",
          },
        },
        503,
      ),
    );
    await expect(
      fetchCertifiedReview("CHRONOS-DEMO-001", {
        fetcher,
        baseUrl: "http://api.test",
      }),
    ).rejects.toMatchObject({
      code: "certification_integrity_error",
      status: 503,
      message: "Integrity failed.",
    });
  });

  it("rejects an invalid successful contract", async () => {
    const fetcher = vi.fn().mockResolvedValue(response({ status: "ok" }));
    await expect(
      fetchCertifiedReview("CHRONOS-DEMO-001", {
        fetcher,
        baseUrl: "http://api.test",
      }),
    ).rejects.toBeInstanceOf(ReviewContractError);
  });
});

describe("fetchCertifiedGraph", () => {
  it("loads and validates the complete certified graph", async () => {
    const fetcher = vi.fn().mockResolvedValue(response(graphFixture));
    await expect(
      fetchCertifiedGraph("CHRONOS-DEMO-001", {
        fetcher,
        baseUrl: "http://api.test",
      }),
    ).resolves.toEqual(graphFixture);
  });

  it("calls the read-only graph endpoint without caching", async () => {
    const fetcher = vi.fn().mockResolvedValue(response(graphFixture));
    await fetchCertifiedGraph("CHRONOS-DEMO-001", {
      fetcher,
      baseUrl: "http://api.test",
    });
    expect(fetcher).toHaveBeenCalledWith(
      "http://api.test/api/reviews/CHRONOS-DEMO-001/graph",
      expect.objectContaining({ method: "GET", cache: "no-store" }),
    );
  });

  it("encodes graph review identifiers", async () => {
    const fetcher = vi.fn().mockResolvedValue(response(graphFixture));
    await fetchCertifiedGraph("a/b", {
      fetcher,
      baseUrl: "http://api.test",
    });
    expect(fetcher.mock.calls[0][0]).toContain("/api/reviews/a%2Fb/graph");
  });

  it("surfaces certification failures without fallback data", async () => {
    const fetcher = vi.fn().mockResolvedValue(
      response(
        {
          detail: {
            code: "certification_integrity_error",
            message: "Certified graph failed validation.",
          },
        },
        503,
      ),
    );
    await expect(
      fetchCertifiedGraph("CHRONOS-DEMO-001", {
        fetcher,
        baseUrl: "http://api.test",
      }),
    ).rejects.toMatchObject({
      code: "certification_integrity_error",
      status: 503,
    });
  });

  it("rejects a malformed successful response", async () => {
    const fetcher = vi.fn().mockResolvedValue(response({ mode: "future" }));
    await expect(
      fetchCertifiedGraph("CHRONOS-DEMO-001", {
        fetcher,
        baseUrl: "http://api.test",
      }),
    ).rejects.toBeInstanceOf(GraphContractError);
  });

  it("uses a stable graph API error for non-JSON failures", async () => {
    const fetcher = vi.fn().mockResolvedValue(
      new Response("gateway failed", { status: 502 }),
    );
    await expect(
      fetchCertifiedGraph("CHRONOS-DEMO-001", {
        fetcher,
        baseUrl: "http://api.test",
      }),
    ).rejects.toMatchObject({
      code: "graph_api_error",
      status: 502,
    });
  });
});

describe("fetchCertifiedExplorer", () => {
  it("loads and validates the complete certified explorer", async () => {
    const fixture = explorerFixture();
    const fetcher = vi.fn().mockResolvedValue(response(fixture));
    await expect(
      fetchCertifiedExplorer("CHRONOS-DEMO-001", {
        fetcher,
        baseUrl: "http://api.test",
      }),
    ).resolves.toEqual(fixture);
  });

  it("calls the read-only explorer endpoint without caching", async () => {
    const fetcher = vi.fn().mockResolvedValue(response(explorerFixture()));
    await fetchCertifiedExplorer("CHRONOS-DEMO-001", {
      fetcher,
      baseUrl: "http://api.test",
    });
    expect(fetcher).toHaveBeenCalledWith(
      "http://api.test/api/reviews/CHRONOS-DEMO-001/explorer",
      expect.objectContaining({ method: "GET", cache: "no-store" }),
    );
  });

  it("encodes explorer review identifiers", async () => {
    const fetcher = vi.fn().mockResolvedValue(response(explorerFixture()));
    await fetchCertifiedExplorer("a/b", {
      fetcher,
      baseUrl: "http://api.test",
    });
    expect(fetcher.mock.calls[0][0]).toContain(
      "/api/reviews/a%2Fb/explorer",
    );
  });

  it("surfaces explorer certification failures without fallback data", async () => {
    const fetcher = vi.fn().mockResolvedValue(
      response(
        {
          detail: {
            code: "certification_integrity_error",
            message: "Certified explorer failed validation.",
          },
        },
        503,
      ),
    );
    await expect(
      fetchCertifiedExplorer("CHRONOS-DEMO-001", {
        fetcher,
        baseUrl: "http://api.test",
      }),
    ).rejects.toMatchObject({
      code: "certification_integrity_error",
      status: 503,
    });
  });

  it("rejects a malformed successful explorer response", async () => {
    const fetcher = vi.fn().mockResolvedValue(response({ fields: [] }));
    await expect(
      fetchCertifiedExplorer("CHRONOS-DEMO-001", {
        fetcher,
        baseUrl: "http://api.test",
      }),
    ).rejects.toBeInstanceOf(ExplorerContractError);
  });

  it("uses a stable explorer API error for non-JSON failures", async () => {
    const fetcher = vi.fn().mockResolvedValue(
      new Response("gateway failed", { status: 502 }),
    );
    await expect(
      fetchCertifiedExplorer("CHRONOS-DEMO-001", {
        fetcher,
        baseUrl: "http://api.test",
      }),
    ).rejects.toMatchObject({
      code: "explorer_api_error",
      status: 502,
    });
  });
});
