import { z } from "zod";

const fingerprintSchema = z
  .string()
  .regex(/^sha256:[0-9a-f]{64}$/);

const fieldIdentitySchema = z
  .object({
    datasetUrn: z.string().startsWith("urn:li:dataset:("),
    fieldPath: z.string().min(1),
  })
  .strict();

const distributionSchema = z
  .object({
    critical: z.number().int().nonnegative(),
    high: z.number().int().nonnegative(),
    moderate: z.number().int().nonnegative(),
    low: z.number().int().nonnegative(),
    undetermined: z.number().int().nonnegative(),
  })
  .strict();

export const certifiedChangeReviewSchema = z
  .object({
    certification: z
      .object({
        status: z.literal("certified"),
        fingerprint: fingerprintSchema,
        certifiedAt: z.iso.datetime({ offset: true }),
        checksPassed: z.number().int().positive(),
        checkCount: z.number().int().positive(),
        scopeStatement: z.string().min(1),
      })
      .strict()
      .refine((value) => value.checksPassed === value.checkCount, {
        message: "Every certification check must pass",
      }),
    change: z
      .object({
        demonstrationId: z.literal("CHRONOS-DEMO-001"),
        proposalId: z.string().min(1),
        operation: z.literal("field_rename"),
        datasetUrn: z.string().startsWith("urn:li:dataset:("),
        displayIdentity: z.string().min(1),
        platform: z.string().min(1),
        environment: z.string().min(1),
        currentField: z.string().min(1),
        requestedField: z.string().min(1),
        description: z.string().nullable(),
        rationale: z.string().nullable(),
      })
      .strict(),
    decision: z
      .object({
        disposition: z.literal("hold_for_review"),
        dispositionLabel: z.string().min(1),
        decisionCertainty: z.string().min(1),
        technicalCertainty: z.literal("unresolved"),
        decisionRuleId: z.string().min(1),
        reasons: z.array(
          z
            .object({
              code: z.string().min(1),
              statement: z.string().min(1),
            })
            .strict(),
        ),
        narrative: z.string().min(1),
      })
      .strict(),
    technicalSummary: z
      .object({
        changeOrigins: z.number().int().nonnegative(),
        rootCauses: z.number().int().nonnegative(),
        relationshipImpacts: z.number().int().nonnegative(),
        dependencyPaths: z.number().int().nonnegative(),
        downstreamFields: z.number().int().nonnegative(),
        downstreamDatasets: z.number().int().nonnegative(),
        confirmedDownstreamFailures: z.number().int().nonnegative(),
        potentialRelationships: z.number().int().nonnegative(),
        unresolvedRelationships: z.number().int().nonnegative(),
        unresolvedPaths: z.number().int().nonnegative(),
        unresolvedFields: z.number().int().nonnegative(),
      })
      .strict(),
    scopeSummary: z
      .object({
        datasets: z.number().int().nonnegative(),
        downstreamFields: z.number().int().nonnegative(),
        connectedContextAssets: z.number().int().nonnegative(),
        contextRelationships: z.number().int().nonnegative(),
        fieldToContextMappings: z.number().int().nonnegative(),
        contextCategories: z.array(z.string().min(1)),
        unresolvedContextReferences: z.number().int().nonnegative(),
      })
      .strict(),
    severityProfile: z
      .object({
        technicalConsequence: z.string().min(1),
        technicalCertainty: z.literal("unresolved"),
        contextCriticality: z.string().min(1),
        breadth: z.literal("widespread"),
        sensitivity: z.string().min(1),
        severityIfRealized: z.literal("high"),
        fieldDistribution: distributionSchema,
        datasetDistribution: distributionSchema,
      })
      .strict(),
    rootCause: z
      .object({
        rootCauseId: z.string().min(1),
        rootRelationshipId: z.string().min(1),
        title: z.string().min(1),
        explanation: z.string().min(1),
      })
      .strict(),
    blockingQuestions: z.array(
      z
        .object({
          questionId: z.string().min(1),
          question: z.string().min(1),
          subject: z.string().min(1),
          reason: z.string().min(1),
          resolutionState: z.literal("unresolved"),
          affectedFields: z.number().int().nonnegative(),
          affectedDatasets: z.number().int().nonnegative(),
          affectedPaths: z.number().int().nonnegative(),
          requiredEvidenceIds: z.array(z.string().min(1)),
        })
        .strict(),
    ),
    requiredEvidence: z.array(
      z
        .object({
          evidenceId: z.string().min(1),
          evidenceClass: z.string().min(1),
          subject: z.string().min(1),
          reason: z.string().min(1),
          state: z.literal("required_for_decision_resolution"),
        })
        .strict(),
    ),
    representativePaths: z.array(
      z
        .object({
          pathId: z.string().min(1),
          kind: z.enum(["short", "deep", "multipath"]),
          technicalPathId: z.string().min(1),
          sourceField: fieldIdentitySchema,
          downstreamField: fieldIdentitySchema,
          downstreamDatasetUrn: z.string().startsWith("urn:li:dataset:("),
          contextAssetId: z.string().startsWith("urn:li:"),
          unresolvedBoundaryRelationshipId: z.string().min(1),
          relationshipIds: z.array(z.string().min(1)).min(1),
          hopCount: z.number().int().positive(),
          explanation: z.string().min(1),
        })
        .strict()
        .refine(
          (value) => value.hopCount === value.relationshipIds.length,
          { message: "Path hop count must match relationship count" },
        ),
    ),
    contextHighlights: z.array(
      z
        .object({
          highlightId: z.string().min(1),
          kind: z.string().min(1),
          subjectId: z.string().startsWith("urn:li:"),
          displayName: z.string().nullable(),
          selectionBasis: z.string().min(1),
          supportingDatasetUrns: z.array(
            z.string().startsWith("urn:li:dataset:("),
          ),
          supportingFieldCount: z.number().int().nonnegative(),
        })
        .strict(),
    ),
    currentState: z
      .object({
        classification: z.literal("certified_current"),
        datasetUrn: z.string().startsWith("urn:li:dataset:("),
        fieldPath: z.string().min(1),
        fieldName: z.string().min(1),
        nativeType: z.string().nullable(),
        normalizedType: z.string().min(1),
        schemaFieldCount: z.number().int().positive(),
      })
      .strict(),
    counterfactualState: z
      .object({
        classification: z.literal("counterfactual"),
        datasetUrn: z.string().startsWith("urn:li:dataset:("),
        fieldPath: z.string().min(1),
        fieldName: z.string().min(1),
        nativeType: z.string().nullable(),
        normalizedType: z.string().min(1),
        schemaFieldCount: z.number().int().positive(),
      })
      .strict(),
  })
  .strict();

export type CertifiedChangeReview = z.infer<
  typeof certifiedChangeReviewSchema
>;
