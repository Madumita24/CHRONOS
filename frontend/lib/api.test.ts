import { describe, expect, it, vi } from "vitest";

import {
  ReviewContractError,
  fetchCertifiedReview,
} from "@/lib/api";
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
