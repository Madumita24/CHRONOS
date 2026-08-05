import { describe, expect, it } from "vitest";

import {
  analysisDetailSchema,
  analysisGraphSchema,
  analysisIndexSchema,
  patchPreviewSchema,
  releaseCertificationSchema,
} from "@/lib/phase6-contract";
import {
  analysisGraph,
  analysisIndex,
  conflictRepairDetail,
  patchPreview,
  pullRequestDetail,
  releaseCertification,
  repairDetail,
  semanticDetail,
  structuralDetail,
} from "@/test/phase6-fixture";

describe("Phase 6 transport contracts", () => {
  it("accepts the exact release certification shape", () => {
    expect(releaseCertificationSchema.parse(releaseCertification)).toEqual(releaseCertification);
  });

  it("rejects inconsistent release test arithmetic", () => {
    expect(() => releaseCertificationSchema.parse({
      ...releaseCertification,
      testTotals: { ...releaseCertification.testTotals, executed: 1485 },
    })).toThrow();
  });

  it("rejects a nonzero failed-test count", () => {
    expect(() => releaseCertificationSchema.parse({
      ...releaseCertification,
      testTotals: { executed: 1485, passed: 1477, skipped: 7, failed: 1 },
    })).toThrow();
  });

  it("accepts the certified analysis index", () => {
    expect(analysisIndexSchema.parse(analysisIndex).analyses).toHaveLength(4);
  });

  it("rejects unknown fields in index summaries", () => {
    const summary = { ...analysisIndex.analyses[0], invented: true };
    expect(() => analysisIndexSchema.parse({ ...analysisIndex, analyses: [summary] })).toThrow();
  });

  it("discriminates the structural detail", () => {
    expect(analysisDetailSchema.parse(structuralDetail).analysisType).toBe("structural");
  });

  it("discriminates the semantic detail", () => {
    expect(analysisDetailSchema.parse(semanticDetail).analysisType).toBe("semantic");
  });

  it("discriminates the pull-request detail", () => {
    expect(analysisDetailSchema.parse(pullRequestDetail).analysisType).toBe("pull_request");
  });

  it("discriminates the repair detail", () => {
    expect(analysisDetailSchema.parse(repairDetail).analysisType).toBe("repair");
  });

  it("rejects an unsupported repair disposition", () => {
    expect(() => analysisDetailSchema.parse({ ...repairDetail, repairDisposition: "AUTO_APPLY" })).toThrow();
  });

  it("accepts the explicit conflict-blocked repair state", () => {
    const parsed = analysisDetailSchema.parse(conflictRepairDetail);
    expect(parsed.analysisType).toBe("repair");
    if (parsed.analysisType !== "repair") throw new Error("Expected repair detail");
    expect(parsed.repairDisposition).toBe("REPAIR_BLOCKED_BY_CONFLICT");
  });

  it("rejects an unsupported semantic compatibility state", () => {
    expect(() => analysisDetailSchema.parse({ ...semanticDetail, semanticCompatibility: "PROBABLY_SAFE" })).toThrow();
  });

  it("rejects unsafe changed-file paths", () => {
    const changedFiles = [{ ...pullRequestDetail.changedFiles[0], path: "../secret.env" }];
    expect(() => analysisDetailSchema.parse({ ...pullRequestDetail, changedFiles })).toThrow();
  });

  it("accepts graph closure supplied by the backend", () => {
    expect(analysisGraphSchema.parse(analysisGraph).representativePaths).toHaveLength(1);
  });

  it("rejects a graph edge with a dangling endpoint", () => {
    const edges = [{ ...analysisGraph.edges[0], target: "missing-node" }];
    expect(() => analysisGraphSchema.parse({ ...analysisGraph, edges })).toThrow();
  });

  it("rejects a representative path with a missing edge", () => {
    const representativePaths = [{ ...analysisGraph.representativePaths[0], edgeIds: ["missing-edge"] }];
    expect(() => analysisGraphSchema.parse({ ...analysisGraph, representativePaths })).toThrow();
  });

  it("accepts a bounded unapplied patch preview", () => {
    expect(patchPreviewSchema.parse(patchPreview).label).toBe("CANDIDATE - NOT APPLIED");
  });

  it("rejects an applied-patch label", () => {
    expect(() => patchPreviewSchema.parse({ ...patchPreview, label: "APPLIED" })).toThrow();
  });
});
