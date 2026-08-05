import { z } from "zod";

const id = z.string().min(1);
const ids = z.array(id);
const fingerprint = z.string().regex(/^sha256:[0-9a-f]{64}$/);
const gitObjectId = z.string().regex(/^[0-9a-f]{40}$/);
const safePath = z
  .string()
  .min(1)
  .refine(
    (value) =>
      !value.startsWith("/") &&
      !/^[A-Za-z]:[\\/]/.test(value) &&
      !value.split("/").includes(".."),
    "Unsafe relative path",
  );

export const certificationStateSchema = z.enum([
  "PHASE_6_CERTIFIED",
  "PHASE_6_CERTIFIED_WITH_NON_BLOCKING_LIMITATIONS",
  "PHASE_6_NOT_CERTIFIED",
]);
export const analysisTypeSchema = z.enum([
  "structural",
  "semantic",
  "pull_request",
  "repair",
]);
export const evidenceClassSchema = z.enum([
  "OBSERVED DATAHUB",
  "CODE-DERIVED",
  "COUNTERFACTUAL",
  "MISSING EVIDENCE",
  "STATIC PROJECTED",
  "DECISION EVIDENCE",
]);

export const phase6CertificationSchema = z
  .object({
    state: certificationStateSchema,
    releaseId: id,
    certificationVersion: z.literal("6.5.0"),
    packageFingerprint: fingerprint,
    releaseManifestFingerprint: fingerprint,
    topLevelCertificationFingerprint: fingerprint,
    limitations: ids,
    runtimeVerified: z.literal(false),
  })
  .strict();

export const releaseCertificationSchema = z
  .object({
    certification: phase6CertificationSchema,
    sourceCommit: gitObjectId,
    sourceTree: gitObjectId,
    testTotals: z
      .object({
        executed: z.number().int().nonnegative(),
        passed: z.number().int().nonnegative(),
        skipped: z.number().int().nonnegative(),
        failed: z.literal(0),
      })
      .strict()
      .refine(
        (value) =>
          value.executed === value.passed + value.skipped + value.failed,
        "Test arithmetic is invalid",
      ),
    skippedTestCount: z.literal(7),
    supportedCapabilities: ids,
    unsupportedCapabilities: ids,
    goldenPreservationState: z.literal("PASS"),
  })
  .strict();

export const analysisSummarySchema = z
  .object({
    analysisId: id,
    analysisType: analysisTypeSchema,
    displayName: id,
    scenarioId: id,
    proposalId: id,
    certificationState: certificationStateSchema,
    decision: id,
    operation: id,
    repositoryIdentity: id.nullable(),
    baseIdentity: id.nullable(),
    headIdentity: id.nullable(),
    coherence: id.nullable(),
    conflictCount: z.number().int().nonnegative(),
    rootCauseCount: z.number().int().nonnegative(),
    affectedFileCount: z.number().int().nonnegative(),
    affectedDatasetCount: z.number().int().nonnegative(),
    repairActionCount: z.number().int().nonnegative(),
    configuredAt: z.string().nullable(),
    warnings: ids,
    limitations: ids,
    manifestFingerprint: fingerprint,
  })
  .strict();

export const analysisIndexSchema = z
  .object({
    certification: phase6CertificationSchema,
    analyses: z.array(analysisSummarySchema),
  })
  .strict();

const baseAnalysis = {
  analysisId: id,
  displayName: id,
  scenarioId: id,
  proposalId: id,
  operation: id,
  decision: id,
  certification: phase6CertificationSchema,
  manifestFingerprint: fingerprint,
  warnings: ids,
  limitations: ids,
  confirmedRuntimeFailures: z.literal(0),
  executionValidity: z.literal("UNVERIFIED"),
};

const structuralAnalysisSchema = z
  .object({
    ...baseAnalysis,
    analysisType: z.literal("structural"),
    change: z
      .object({
        datasetUrn: z.string().startsWith("urn:li:dataset:("),
        currentField: id,
        proposedField: id.nullable(),
        currentType: z.string().nullable(),
        proposedType: z.string().nullable(),
        identityMapping: id,
        compatibility: z.enum(["COMPATIBLE", "INCOMPATIBLE", "UNKNOWN"]),
        downstreamFields: z.number().int().nonnegative(),
        downstreamDatasets: z.number().int().nonnegative(),
        rootCauses: ids,
        blockingQuestions: ids,
        requiredEvidence: ids,
      })
      .strict(),
  })
  .strict();

const semanticDeltaSchema = z
  .object({
    deltaId: id,
    deltaType: z.enum([
      "AGGREGATION_CHANGE",
      "FILTER_CHANGE",
      "JOIN_TYPE_CHANGE",
      "DERIVED_EXPRESSION_CHANGE",
      "OUTPUT_STRUCTURAL_CHANGE",
    ]),
    before: z.string(),
    after: z.string(),
    affectedOutput: z.string().nullable(),
    affectedModel: id,
    scope: z.enum(["FIELD-SPECIFIC", "MODEL-WIDE"]),
    certainty: id,
    evidenceClass: evidenceClassSchema,
    potentialConsequence: id,
    missingEvidence: ids,
  })
  .strict();

const semanticAnalysisSchema = z
  .object({
    ...baseAnalysis,
    analysisType: z.literal("semantic"),
    modelDatasetUrn: z.string().startsWith("urn:li:dataset:("),
    beforeFingerprint: fingerprint,
    afterFingerprint: fingerprint,
    semanticCompatibility: z.enum([
      "SEMANTICALLY_COMPATIBLE",
      "SEMANTICALLY_INCOMPATIBLE",
      "SEMANTIC_COMPATIBILITY_UNKNOWN",
    ]),
    structuralCompatibility: z.enum([
      "STRUCTURALLY_COMPATIBLE",
      "STRUCTURALLY_INCOMPATIBLE",
      "STRUCTURAL_COMPATIBILITY_UNKNOWN",
    ]),
    deltas: z.array(semanticDeltaSchema),
    affectedOutputFields: ids,
    rootCauses: ids,
    blockingQuestions: ids,
  })
  .strict();

const changedFileSchema = z
  .object({
    fileId: id,
    path: safePath,
    status: id,
    category: id,
    parser: id,
    materialState: id,
    deltaCount: z.number().int().nonnegative(),
    warningCount: z.number().int().nonnegative(),
    resolvedEntityCount: z.number().int().nonnegative(),
    unresolvedReferenceCount: z.number().int().nonnegative(),
  })
  .strict();

const logicalGroupSchema = z
  .object({
    groupId: id,
    currentIdentity: z.string().nullable(),
    proposedIdentities: ids,
    contributingFileIds: ids,
    structuralChangeIds: ids,
    semanticChangeIds: ids,
    staleReferenceIds: ids,
    coherence: id,
    conflictIds: ids,
    rootIds: ids,
    evidenceIds: ids,
  })
  .strict();

const conflictSchema = z
  .object({
    conflictId: id,
    currentEntity: id,
    proposedIdentities: ids,
    supportingFileIds: ids,
    reason: id,
    requiredEvidence: ids,
  })
  .strict();

const prAnalysisSchema = z
  .object({
    ...baseAnalysis,
    analysisType: z.literal("pull_request"),
    repository: id,
    baseIdentity: id,
    headIdentity: id,
    coherence: z.enum([
      "COHERENT",
      "PARTIALLY_COHERENT",
      "INCONSISTENT",
      "UNRESOLVED",
    ]),
    changedFiles: z.array(changedFileSchema),
    logicalGroups: z.array(logicalGroupSchema),
    conflicts: z.array(conflictSchema),
    rootCauses: ids,
  })
  .strict();

const repairabilitySchema = z
  .object({
    rootId: id,
    rootType: id,
    state: z.enum([
      "AUTO_REPAIRABLE",
      "CONDITIONALLY_REPAIRABLE",
      "MANUAL_DECISION_REQUIRED",
      "UNSUPPORTED",
      "BLOCKED_BY_CONFLICT",
      "BLOCKED_BY_MISSING_EVIDENCE",
    ]),
    reason: id,
    evidenceIds: ids,
    remainingUncertainty: ids,
    evidenceClass: z.literal("CODE-DERIVED"),
  })
  .strict();

const repairActionSchema = z
  .object({
    actionId: id,
    applicationOrder: z.number().int().positive(),
    file: safePath,
    exactTarget: id,
    currentValue: z.string(),
    proposedValue: z.string(),
    rule: id,
    rootId: id,
    evidenceIds: ids,
    dependencies: ids,
    protectedSemantics: ids,
    remainingValidation: ids,
    evidenceClass: z.literal("STATIC PROJECTED"),
  })
  .strict();

const patchSummarySchema = z
  .object({
    patchId: z.string().regex(/^patch-[0-9]{1,3}$/),
    file: safePath,
    hunkCount: z.number().int().nonnegative(),
    fingerprint,
    actionIds: ids,
    protectedSemanticsState: id,
    staticValidationState: id,
  })
  .strict();

const repairAnalysisSchema = z
  .object({
    ...baseAnalysis,
    analysisType: z.literal("repair"),
    predecessorAnalysisId: id,
    repairDisposition: z.enum([
      "PARTIAL_REPAIR_CANDIDATE",
      "NO_SUPPORTED_AUTOMATIC_REPAIR",
      "REPAIR_BLOCKED_BY_CONFLICT",
      "REPAIR_CANDIDATE_READY_FOR_REVIEW",
    ]),
    repairCompleteness: z.enum([
      "PARTIALLY_ADDRESSED_SELECTED_ROOTS",
      "FULLY_ADDRESSED_SELECTED_ROOTS",
      "NO_SUPPORTED_REPAIR",
    ]),
    projectedStateLabel: z.literal(
      "PROJECTED REPAIRED - STATIC ONLY - RUNTIME UNVERIFIED",
    ),
    repairability: z.array(repairabilitySchema),
    actions: z.array(repairActionSchema),
    patches: z.array(patchSummarySchema),
    comparison: z
      .object({
        originalCoherence: id,
        projectedCoherence: id,
        originalStaleReferences: z.number().int().nonnegative(),
        projectedStaleReferences: z.number().int().nonnegative(),
        targetedRoots: z.number().int().nonnegative(),
        projectedClosedRoots: z.number().int().nonnegative(),
        remainingRoots: z.number().int().nonnegative(),
        newRoots: z.number().int().nonnegative(),
        conflictsBefore: z.number().int().nonnegative(),
        conflictsAfter: z.number().int().nonnegative(),
        unresolvedSemanticQuestions: z.number().int().nonnegative(),
        executionValidity: z.literal("UNVERIFIED"),
      })
      .strict(),
    remainingFindings: ids,
    phase7Requirements: ids,
  })
  .strict();

export const analysisDetailSchema = z.discriminatedUnion("analysisType", [
  structuralAnalysisSchema,
  semanticAnalysisSchema,
  prAnalysisSchema,
  repairAnalysisSchema,
]);

const graphNodeSchema = z
  .object({
    nodeId: id,
    label: id,
    nodeType: id,
    state: id,
    evidenceClass: evidenceClassSchema,
  })
  .strict();
const graphEdgeSchema = z
  .object({
    edgeId: id,
    source: id,
    target: id,
    category: z.enum([
      "OBSERVED_DATAHUB_EDGE",
      "CODE_DERIVED_PROPOSED_EDGE",
      "COUNTERFACTUAL_EDGE",
      "REMOVED_EDGE",
      "UNRESOLVED_REFERENCE",
    ]),
    evidenceClass: evidenceClassSchema,
    state: id,
  })
  .strict();
export const analysisGraphSchema = z
  .object({
    analysisId: id,
    mode: z.enum(["CURRENT", "PROPOSED", "DIFF", "PROJECTED_REPAIRED"]),
    availableModes: z
      .array(z.enum(["CURRENT", "PROPOSED", "DIFF", "PROJECTED_REPAIRED"]))
      .min(1),
    runtimeVerified: z.literal(false),
    nodes: z.array(graphNodeSchema),
    edges: z.array(graphEdgeSchema),
    representativePaths: z.array(
      z
        .object({
          pathId: id,
          nodeIds: ids,
          edgeIds: ids,
          rootIds: ids,
          contributingFileIds: ids,
          target: id,
          evidenceClass: evidenceClassSchema,
        })
        .strict(),
    ),
  })
  .strict()
  .superRefine((graph, context) => {
    const nodes = new Set(graph.nodes.map((node) => node.nodeId));
    const edges = new Set(graph.edges.map((edge) => edge.edgeId));
    if (!graph.availableModes.includes(graph.mode) || new Set(graph.availableModes).size !== graph.availableModes.length) {
      context.addIssue({ code: "custom", message: "Invalid graph mode availability" });
    }
    for (const edge of graph.edges) {
      if (!nodes.has(edge.source) || !nodes.has(edge.target)) {
        context.addIssue({ code: "custom", message: "Dangling graph endpoint" });
      }
    }
    for (const path of graph.representativePaths) {
      if (
        path.nodeIds.some((node) => !nodes.has(node)) ||
        path.edgeIds.some((edge) => !edges.has(edge))
      ) {
        context.addIssue({ code: "custom", message: "Dangling graph path" });
      }
    }
  });

export const evidenceListSchema = z.array(
  z
    .object({
      evidenceId: id,
      evidenceClass: evidenceClassSchema,
      subject: id,
      statement: id,
      certainty: id,
    })
    .strict(),
);

export const patchPreviewSchema = z
  .object({
    analysisId: id,
    patchId: z.string().regex(/^patch-[0-9]{1,3}$/),
    file: safePath,
    fingerprint,
    lines: z.array(
      z
        .object({
          oldLine: z.number().int().positive().nullable(),
          newLine: z.number().int().positive().nullable(),
          kind: z.enum(["context", "addition", "removal", "header"]),
          text: z.string(),
        })
        .strict(),
    ),
    originalExcerpt: z.array(z.string()),
    candidateExcerpt: z.array(z.string()),
    label: z.literal("CANDIDATE - NOT APPLIED"),
    runtimeVerified: z.literal(false),
  })
  .strict();

export type AnalysisIndex = z.infer<typeof analysisIndexSchema>;
export type AnalysisSummary = z.infer<typeof analysisSummarySchema>;
export type AnalysisDetail = z.infer<typeof analysisDetailSchema>;
export type AnalysisGraph = z.infer<typeof analysisGraphSchema>;
export type GraphMode = AnalysisGraph["mode"];
export type EvidenceRecord = z.infer<typeof evidenceListSchema>[number];
export type PatchPreview = z.infer<typeof patchPreviewSchema>;
export type ReleaseCertification = z.infer<typeof releaseCertificationSchema>;
