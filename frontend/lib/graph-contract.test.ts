import { describe, expect, it } from "vitest";

import { certifiedGraphReviewSchema } from "@/lib/graph-contract";
import { graphFixture } from "@/test/graph-fixture";

function copyFixture(): Record<string, unknown> {
  return structuredClone(graphFixture) as unknown as Record<string, unknown>;
}

describe("certifiedGraphReviewSchema", () => {
  it("accepts the complete certified fixture", () => {
    expect(certifiedGraphReviewSchema.safeParse(graphFixture).success).toBe(true);
  });

  it("rejects unknown top-level properties", () => {
    expect(
      certifiedGraphReviewSchema.safeParse({
        ...graphFixture,
        frontendDerivedLineage: true,
      }).success,
    ).toBe(false);
  });

  it("requires a certified status", () => {
    const fixture = copyFixture();
    (fixture.certification as Record<string, unknown>).status = "uncertified";
    expect(certifiedGraphReviewSchema.safeParse(fixture).success).toBe(false);
  });

  it("requires all 26 current nodes", () => {
    const fixture = copyFixture();
    (fixture.currentGraph as { nodes: unknown[] }).nodes.pop();
    expect(certifiedGraphReviewSchema.safeParse(fixture).success).toBe(false);
  });

  it("requires all 27 current edges", () => {
    const fixture = copyFixture();
    (fixture.currentGraph as { edges: unknown[] }).edges.pop();
    expect(certifiedGraphReviewSchema.safeParse(fixture).success).toBe(false);
  });

  it("requires all 26 future nodes", () => {
    const fixture = copyFixture();
    (fixture.futureGraph as { nodes: unknown[] }).nodes.pop();
    expect(certifiedGraphReviewSchema.safeParse(fixture).success).toBe(false);
  });

  it("requires all 27 future edges", () => {
    const fixture = copyFixture();
    (fixture.futureGraph as { edges: unknown[] }).edges.pop();
    expect(certifiedGraphReviewSchema.safeParse(fixture).success).toBe(false);
  });

  it("rejects a dangling current edge", () => {
    const fixture = copyFixture();
    const edge = (fixture.currentGraph as { edges: Record<string, unknown>[] })
      .edges[0];
    edge.target = "missing-node";
    expect(certifiedGraphReviewSchema.safeParse(fixture).success).toBe(false);
  });

  it("rejects duplicate node IDs", () => {
    const fixture = copyFixture();
    const nodes = (fixture.futureGraph as {
      nodes: Record<string, unknown>[];
    }).nodes;
    nodes[1].id = nodes[0].id;
    expect(certifiedGraphReviewSchema.safeParse(fixture).success).toBe(false);
  });

  it("rejects duplicate edge IDs", () => {
    const fixture = copyFixture();
    const edges = (fixture.futureGraph as {
      edges: Record<string, unknown>[];
    }).edges;
    edges[1].id = edges[0].id;
    expect(certifiedGraphReviewSchema.safeParse(fixture).success).toBe(false);
  });

  it("requires the current order_total source", () => {
    const fixture = copyFixture();
    (fixture.sourceChange as { current: Record<string, unknown> }).current
      .fieldPath = "wrong";
    expect(certifiedGraphReviewSchema.safeParse(fixture).success).toBe(false);
  });

  it("requires the future order_amount source", () => {
    const fixture = copyFixture();
    (fixture.sourceChange as { future: Record<string, unknown> }).future
      .fieldPath = "wrong";
    expect(certifiedGraphReviewSchema.safeParse(fixture).success).toBe(false);
  });

  it("requires one renamed identity mapping", () => {
    const fixture = copyFixture();
    const mappings = fixture.identityMappings as Record<string, unknown>[];
    mappings[0].classification = "identity_preserved";
    expect(certifiedGraphReviewSchema.safeParse(fixture).success).toBe(false);
  });

  it("requires 25 preserved identity mappings", () => {
    const fixture = copyFixture();
    const mappings = fixture.identityMappings as Record<string, unknown>[];
    mappings[1].classification = "renamed";
    expect(certifiedGraphReviewSchema.safeParse(fixture).success).toBe(false);
  });

  it("requires the root relationship to remain unknown", () => {
    const fixture = copyFixture();
    const edges = (fixture.futureGraph as {
      edges: Record<string, unknown>[];
    }).edges;
    edges[0].compatibilityState = "incompatible";
    expect(certifiedGraphReviewSchema.safeParse(fixture).success).toBe(false);
  });

  it("requires exactly 26 conditional relationships", () => {
    const fixture = copyFixture();
    const edges = (fixture.futureGraph as {
      edges: Record<string, unknown>[];
    }).edges;
    edges[1].compatibilityState = "compatible";
    expect(certifiedGraphReviewSchema.safeParse(fixture).success).toBe(false);
  });

  it("requires 48 supporting paths", () => {
    const fixture = copyFixture();
    (fixture.supportingPaths as unknown[]).pop();
    expect(certifiedGraphReviewSchema.safeParse(fixture).success).toBe(false);
  });

  it("rejects duplicate supporting path IDs", () => {
    const fixture = copyFixture();
    const paths = fixture.supportingPaths as Record<string, unknown>[];
    paths[1].pathId = paths[0].pathId;
    expect(certifiedGraphReviewSchema.safeParse(fixture).success).toBe(false);
  });

  it("rejects dangling representative paths", () => {
    const fixture = copyFixture();
    const paths = fixture.representativePaths as Record<string, unknown>[];
    paths[0].supportingPathId = "missing-path";
    expect(certifiedGraphReviewSchema.safeParse(fixture).success).toBe(false);
  });

  it("rejects an inconsistent ordered path", () => {
    const fixture = copyFixture();
    const paths = fixture.supportingPaths as {
      futureNodeIds: string[];
    }[];
    paths[0].futureNodeIds.push("future-2");
    expect(certifiedGraphReviewSchema.safeParse(fixture).success).toBe(false);
  });

  it("rejects a path with a dangling graph reference", () => {
    const fixture = copyFixture();
    const paths = fixture.supportingPaths as {
      currentNodeIds: string[];
    }[];
    paths[0].currentNodeIds[0] = "missing-node";
    expect(certifiedGraphReviewSchema.safeParse(fixture).success).toBe(false);
  });

  it("requires the four explicit missing-evidence records", () => {
    const fixture = copyFixture();
    const root = fixture.rootUncertainty as { missingEvidence: unknown[] };
    root.missingEvidence.pop();
    expect(certifiedGraphReviewSchema.safeParse(fixture).success).toBe(false);
  });

  it("requires the certified summary values", () => {
    const fixture = copyFixture();
    (fixture.summary as Record<string, unknown>).confirmedFailures = 1;
    expect(certifiedGraphReviewSchema.safeParse(fixture).success).toBe(false);
  });
});
