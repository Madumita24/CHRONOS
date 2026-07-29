import { describe, expect, it } from "vitest";

import { certifiedChangeReviewSchema } from "@/lib/review-contract";
import {
  mutableReviewFixture,
  reviewFixture,
} from "@/test/review-fixture";

function nested(
  root: Record<string, unknown>,
  key: string,
): Record<string, unknown> {
  return root[key] as Record<string, unknown>;
}

describe("certifiedChangeReviewSchema", () => {
  it("accepts the certified fixture", () => {
    expect(certifiedChangeReviewSchema.parse(reviewFixture)).toEqual(
      reviewFixture,
    );
  });

  it("rejects unknown root properties", () => {
    const value = { ...reviewFixture, invented: true };
    expect(certifiedChangeReviewSchema.safeParse(value).success).toBe(false);
  });

  it("rejects unknown nested properties", () => {
    const value = mutableReviewFixture();
    nested(value, "decision").invented = "no";
    expect(certifiedChangeReviewSchema.safeParse(value).success).toBe(false);
  });

  it("rejects a non-certified status", () => {
    const value = mutableReviewFixture();
    nested(value, "certification").status = "failed";
    expect(certifiedChangeReviewSchema.safeParse(value).success).toBe(false);
  });

  it("requires every certification check to pass", () => {
    const value = mutableReviewFixture();
    nested(value, "certification").checksPassed = 48;
    expect(certifiedChangeReviewSchema.safeParse(value).success).toBe(false);
  });

  it("rejects a malformed fingerprint", () => {
    const value = mutableReviewFixture();
    nested(value, "certification").fingerprint = "sha256:no";
    expect(certifiedChangeReviewSchema.safeParse(value).success).toBe(false);
  });

  it("rejects a timestamp without timezone", () => {
    const value = mutableReviewFixture();
    nested(value, "certification").certifiedAt = "2026-07-28T23:15:35";
    expect(certifiedChangeReviewSchema.safeParse(value).success).toBe(false);
  });

  it("does not accept a different demonstration", () => {
    const value = mutableReviewFixture();
    nested(value, "change").demonstrationId = "CHRONOS-DEMO-002";
    expect(certifiedChangeReviewSchema.safeParse(value).success).toBe(false);
  });

  it("does not accept another operation", () => {
    const value = mutableReviewFixture();
    nested(value, "change").operation = "field_delete";
    expect(certifiedChangeReviewSchema.safeParse(value).success).toBe(false);
  });

  it("requires hold-for-review disposition", () => {
    const value = mutableReviewFixture();
    nested(value, "decision").disposition = "proceed";
    expect(certifiedChangeReviewSchema.safeParse(value).success).toBe(false);
  });

  it("preserves unresolved technical certainty", () => {
    const value = mutableReviewFixture();
    nested(value, "decision").technicalCertainty = "confirmed";
    expect(certifiedChangeReviewSchema.safeParse(value).success).toBe(false);
  });

  it("rejects negative certified counts", () => {
    const value = mutableReviewFixture();
    nested(value, "technicalSummary").unresolvedFields = -1;
    expect(certifiedChangeReviewSchema.safeParse(value).success).toBe(false);
  });

  it("requires high severity if realized", () => {
    const value = mutableReviewFixture();
    nested(value, "severityProfile").severityIfRealized = "critical";
    expect(certifiedChangeReviewSchema.safeParse(value).success).toBe(false);
  });

  it("requires widespread breadth", () => {
    const value = mutableReviewFixture();
    nested(value, "severityProfile").breadth = "narrow";
    expect(certifiedChangeReviewSchema.safeParse(value).success).toBe(false);
  });

  it("requires valid DataHub dataset URNs", () => {
    const value = mutableReviewFixture();
    nested(value, "change").datasetUrn = "orders";
    expect(certifiedChangeReviewSchema.safeParse(value).success).toBe(false);
  });

  it("requires path hop counts to match relationships", () => {
    const value = mutableReviewFixture();
    const paths = value.representativePaths as Record<string, unknown>[];
    paths[0].hopCount = 3;
    expect(certifiedChangeReviewSchema.safeParse(value).success).toBe(false);
  });

  it("requires the current-state classification", () => {
    const value = mutableReviewFixture();
    nested(value, "currentState").classification = "counterfactual";
    expect(certifiedChangeReviewSchema.safeParse(value).success).toBe(false);
  });

  it("requires the counterfactual-state classification", () => {
    const value = mutableReviewFixture();
    nested(value, "counterfactualState").classification = "certified_current";
    expect(certifiedChangeReviewSchema.safeParse(value).success).toBe(false);
  });
});
