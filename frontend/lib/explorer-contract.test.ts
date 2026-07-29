import { describe, expect, it } from "vitest";

import { certifiedImpactExplorerSchema } from "@/lib/explorer-contract";
import { explorerFixture } from "@/test/explorer-fixture";

const clone = () =>
  JSON.parse(
    JSON.stringify(explorerFixture()),
  ) as ReturnType<typeof explorerFixture>;

describe("certified impact explorer contract", () => {
  it("accepts the canonical fixture", () => {
    expect(certifiedImpactExplorerSchema.safeParse(explorerFixture()).success).toBe(true);
  });

  it("requires the exact certification fingerprint shape", () => {
    const fixture = clone();
    fixture.certification.fingerprint = "sha256:bad";
    expect(certifiedImpactExplorerSchema.safeParse(fixture).success).toBe(false);
  });

  it("requires certified status", () => {
    const fixture = clone();
    fixture.certification.status = "draft";
    expect(certifiedImpactExplorerSchema.safeParse(fixture).success).toBe(false);
  });

  it("requires exactly 25 field records", () => {
    const fixture = clone();
    fixture.fields.pop();
    expect(certifiedImpactExplorerSchema.safeParse(fixture).success).toBe(false);
  });

  it("requires exactly 20 dataset records", () => {
    const fixture = clone();
    fixture.datasets.pop();
    expect(certifiedImpactExplorerSchema.safeParse(fixture).success).toBe(false);
  });

  it("requires exactly 48 path records", () => {
    const fixture = clone();
    fixture.paths.pop();
    expect(certifiedImpactExplorerSchema.safeParse(fixture).success).toBe(false);
  });

  it("requires exactly 27 relationship records", () => {
    const fixture = clone();
    fixture.relationships.pop();
    expect(certifiedImpactExplorerSchema.safeParse(fixture).success).toBe(false);
  });

  it("requires exactly 66 context assets", () => {
    const fixture = clone();
    fixture.contextAssets.pop();
    expect(certifiedImpactExplorerSchema.safeParse(fixture).success).toBe(false);
  });

  it("requires exactly 211 context relationships", () => {
    const fixture = clone();
    fixture.contextRelationships.pop();
    expect(certifiedImpactExplorerSchema.safeParse(fixture).success).toBe(false);
  });

  it("requires exactly 257 context mappings", () => {
    const fixture = clone();
    fixture.contextMappings.pop();
    expect(certifiedImpactExplorerSchema.safeParse(fixture).success).toBe(false);
  });

  it("requires exactly four required evidence records", () => {
    const fixture = clone();
    fixture.requiredEvidence.pop();
    expect(certifiedImpactExplorerSchema.safeParse(fixture).success).toBe(false);
  });

  it("rejects an invented summary field", () => {
    const fixture = clone();
    (
      fixture.summary as typeof fixture.summary & {
        invented?: boolean;
      }
    ).invented = true;
    expect(certifiedImpactExplorerSchema.safeParse(fixture).success).toBe(false);
  });

  it("rejects an invented top-level field", () => {
    const fixture = clone();
    (fixture as typeof fixture & { invented?: boolean }).invented = true;
    expect(certifiedImpactExplorerSchema.safeParse(fixture).success).toBe(false);
  });

  it("requires zero confirmed failures", () => {
    const fixture = clone();
    fixture.summary.confirmedFailures = 1;
    expect(certifiedImpactExplorerSchema.safeParse(fixture).success).toBe(false);
  });

  it("requires unresolved technical certainty", () => {
    const fixture = clone();
    fixture.summary.technicalCertainty = "confirmed";
    expect(certifiedImpactExplorerSchema.safeParse(fixture).success).toBe(false);
  });

  it("requires high-confidence decision certainty", () => {
    const fixture = clone();
    fixture.summary.decisionCertainty = "low_confidence";
    expect(certifiedImpactExplorerSchema.safeParse(fixture).success).toBe(false);
  });

  it("requires absent explicit business criticality", () => {
    const fixture = clone();
    fixture.summary.explicitBusinessCriticalityPresent = true;
    expect(certifiedImpactExplorerSchema.safeParse(fixture).success).toBe(false);
  });

  it("requires the canonical shared root cause ID", () => {
    const fixture = clone();
    fixture.rootCause.causeId = "invented-cause";
    expect(certifiedImpactExplorerSchema.safeParse(fixture).success).toBe(false);
  });

  it("requires unknown root compatibility", () => {
    const fixture = clone();
    fixture.rootCause.compatibilityState = "incompatible";
    expect(certifiedImpactExplorerSchema.safeParse(fixture).success).toBe(false);
  });

  it("requires insufficient root evidence", () => {
    const fixture = clone();
    fixture.rootCause.evidenceState = "verified";
    expect(certifiedImpactExplorerSchema.safeParse(fixture).success).toBe(false);
  });

  it("requires unresolved blocking question state", () => {
    const fixture = clone();
    fixture.blockingQuestion.resolutionState = "resolved";
    expect(certifiedImpactExplorerSchema.safeParse(fixture).success).toBe(false);
  });

  it("requires the blocking question to reference the root relationship", () => {
    const fixture = clone();
    fixture.blockingQuestion.rootRelationshipId = "different-relationship";
    expect(certifiedImpactExplorerSchema.safeParse(fixture).success).toBe(false);
  });

  it("requires approved evidence classes", () => {
    const fixture = clone();
    fixture.requiredEvidence[0].evidenceClass = "invented_evidence";
    expect(certifiedImpactExplorerSchema.safeParse(fixture).success).toBe(false);
  });

  it("marks required evidence as unavailable", () => {
    const fixture = clone();
    fixture.requiredEvidence[0].availability = "available";
    expect(certifiedImpactExplorerSchema.safeParse(fixture).success).toBe(false);
  });

  it("requires unique field identifiers", () => {
    const fixture = clone();
    fixture.fields[1].fieldId = fixture.fields[0].fieldId;
    expect(certifiedImpactExplorerSchema.safeParse(fixture).success).toBe(false);
  });

  it("requires unique dataset identifiers", () => {
    const fixture = clone();
    fixture.datasets[1].datasetId = fixture.datasets[0].datasetId;
    expect(certifiedImpactExplorerSchema.safeParse(fixture).success).toBe(false);
  });

  it("requires unique path identifiers", () => {
    const fixture = clone();
    fixture.paths[1].pathId = fixture.paths[0].pathId;
    expect(certifiedImpactExplorerSchema.safeParse(fixture).success).toBe(false);
  });

  it("requires unique relationship identifiers", () => {
    const fixture = clone();
    fixture.relationships[1].relationshipId =
      fixture.relationships[0].relationshipId;
    expect(certifiedImpactExplorerSchema.safeParse(fixture).success).toBe(false);
  });

  it("requires unique context asset identifiers", () => {
    const fixture = clone();
    fixture.contextAssets[1].contextAssetId =
      fixture.contextAssets[0].contextAssetId;
    expect(certifiedImpactExplorerSchema.safeParse(fixture).success).toBe(false);
  });

  it("requires unique context relationship identifiers", () => {
    const fixture = clone();
    fixture.contextRelationships[1].relationshipId =
      fixture.contextRelationships[0].relationshipId;
    expect(certifiedImpactExplorerSchema.safeParse(fixture).success).toBe(false);
  });

  it("requires unique context mapping identifiers", () => {
    const fixture = clone();
    fixture.contextMappings[1].mappingId =
      fixture.contextMappings[0].mappingId;
    expect(certifiedImpactExplorerSchema.safeParse(fixture).success).toBe(false);
  });

  it("requires field provenance to stay bounded", () => {
    const fixture = clone();
    fixture.fields[0].provenanceReferences = Array.from(
      { length: 13 },
      (_, index) => `provenance-${index}`,
    );
    expect(certifiedImpactExplorerSchema.safeParse(fixture).success).toBe(false);
  });

  it("requires context assets to be grouped explicitly", () => {
    const fixture = clone();
    fixture.contextAssets[0].group = "business_critical";
    expect(certifiedImpactExplorerSchema.safeParse(fixture).success).toBe(false);
  });

  it("requires hold-for-review disposition", () => {
    const fixture = clone();
    fixture.decisionExplanation.disposition = "approve";
    expect(certifiedImpactExplorerSchema.safeParse(fixture).success).toBe(false);
  });

  it("requires the certified decision rule", () => {
    const fixture = clone();
    fixture.decisionExplanation.decisionRuleId = "invented-rule";
    expect(certifiedImpactExplorerSchema.safeParse(fixture).success).toBe(false);
  });
});
