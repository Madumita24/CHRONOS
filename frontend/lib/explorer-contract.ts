import { z } from "zod";

import {
  certificationSchema,
  fieldIdentitySchema,
  severityDistributionSchema,
} from "@/lib/review-contract";

const id = z.string().min(1);
const ids = z.array(id);

export const explorerSummarySchema = z
  .object({
    downstreamFields: z.literal(25),
    downstreamDatasets: z.literal(20),
    dependencyPaths: z.literal(48),
    structuralRelationships: z.literal(27),
    contextAssets: z.literal(66),
    contextRelationships: z.literal(211),
    fieldToContextMappings: z.literal(257),
    rootCauses: z.literal(1),
    blockingQuestions: z.literal(1),
    requiredEvidenceClasses: z.literal(4),
    confirmedFailures: z.literal(0),
    unresolvedFields: z.literal(25),
    compatibilityUnknown: z.literal(1),
    compatibilityConditional: z.literal(26),
    compatibilityCompatible: z.literal(0),
    compatibilityIncompatible: z.literal(0),
    fieldSeverityDistribution: severityDistributionSchema,
    datasetSeverityDistribution: severityDistributionSchema,
    technicalConsequence: z.literal("unresolved_impact"),
    technicalCertainty: z.literal("unresolved"),
    decisionCertainty: z.literal("high_confidence"),
    severityIfRealized: z.literal("high"),
    breadth: z.literal("widespread"),
    criticality: z.literal("elevated_context"),
    sensitivity: z.literal("pii"),
    explicitBusinessCriticalityPresent: z.literal(false),
  })
  .strict();

const rootCauseStepSchema = z
  .object({
    stepId: id,
    stage: id,
    label: id,
    value: id,
    classification: z.enum([
      "observed",
      "proposed",
      "counterfactual",
      "unresolved",
      "conditional",
      "decision",
    ]),
  })
  .strict();

export const explorerRootCauseSchema = z
  .object({
    causeId: z.literal("technical-impact-cause-source-rename-semantics"),
    rootRelationshipId: id,
    proposedSource: fieldIdentitySchema,
    firstDownstreamDependency: fieldIdentitySchema,
    compatibilityState: z.literal("unknown"),
    evidenceState: z.literal("insufficient"),
    technicalConsequence: z.literal("unresolved_impact"),
    affectedFields: z.literal(25),
    affectedDatasets: z.literal(20),
    affectedPaths: z.literal(48),
    confirmedFailures: z.literal(0),
    humanExplanation: id,
    steps: z.array(rootCauseStepSchema).min(1),
    provenanceReferences: ids.max(12),
  })
  .strict();

const blockingQuestionSchema = z
  .object({
    questionId: id,
    question: id,
    subject: id,
    reason: id,
    rootCauseId: z.literal(
      "technical-impact-cause-source-rename-semantics",
    ),
    rootRelationshipId: id,
    resolutionState: z.literal("unresolved"),
    affectedFields: z.literal(25),
    affectedDatasets: z.literal(20),
    affectedPaths: z.literal(48),
    requiredEvidenceIds: ids.length(4),
  })
  .strict();

export const explorerRequiredEvidenceSchema = z
  .object({
    evidenceId: id,
    evidenceClass: z.enum([
      "spark_transformation_configuration",
      "input_column_reference_query_or_code",
      "explicit_rename_mapping",
      "validated_execution_result",
    ]),
    label: id,
    subject: id,
    reason: id,
    state: id,
    availability: z.literal("not_available_required"),
    sourceUncertaintyId: id,
  })
  .strict();

export const explorerEvidenceRecordSchema = z
  .object({
    evidenceId: id,
    classification: z.enum([
      "observed",
      "counterfactual",
      "derived",
      "missing",
      "decision",
    ]),
    category: id,
    sourceArtifact: id,
    subject: id,
    claimSupported: id,
    verificationState: z.enum([
      "verified",
      "certified_derivation",
      "insufficient",
      "required",
      "certified_decision",
    ]),
    description: id,
    provenanceReferences: ids.max(12),
  })
  .strict();

export const fieldImpactSchema = z
  .object({
    fieldId: id,
    machineKey: id,
    identity: fieldIdentitySchema,
    displayIdentity: id,
    datasetUrn: id,
    datasetDisplayName: id,
    platform: id,
    shortestExposureDepth: z.number().int().positive(),
    exposureClassification: id,
    supportingPathIds: ids.min(1),
    supportingPathCount: z.number().int().positive(),
    compatibilityState: id,
    technicalImpactState: id,
    certainty: id,
    severityIfRealized: id,
    criticality: id,
    breadth: id,
    sensitivity: id,
    reasonCodes: ids,
    rootCauseId: id,
    evidenceReferences: ids,
    contextAssetIds: ids,
    contextMappingIds: ids,
    humanExplanation: id,
    provenanceReferences: ids.max(12),
  })
  .strict();

export const datasetImpactSchema = z
  .object({
    datasetId: id,
    datasetUrn: id,
    displayName: id,
    platform: id,
    exposedFieldCount: z.number().int().positive(),
    fieldIds: ids.min(1),
    supportingPathIds: ids.min(1),
    technicalImpactState: id,
    technicalSummary: id,
    severityIfRealized: id,
    certainty: id,
    criticality: id,
    breadth: id,
    sensitivity: id,
    rootCauseIds: ids.min(1),
    contextAssetIds: ids,
    contextMappingIds: ids,
    reasonCodes: ids,
    provenanceReferences: ids.max(12),
  })
  .strict();

const contextAttributeSchema = z
  .object({ name: id, values: z.array(z.string()) })
  .strict();

export const contextAssetSchema = z
  .object({
    contextAssetId: id,
    group: z.enum(["governance", "operational", "consumer"]),
    category: id,
    assetType: id,
    displayName: id,
    resolutionState: id,
    connectedDatasetUrns: ids,
    connectedFieldIds: ids,
    relationshipCount: z.number().int().positive(),
    relationshipIds: ids,
    mappingIds: ids,
    supportingPathIds: ids,
    attributes: z.array(contextAttributeSchema),
    provenanceReferences: ids.max(12),
  })
  .strict();

export const contextRelationshipSchema = z
  .object({
    relationshipId: id,
    relationshipCategory: id,
    contextCategory: id,
    anchorDatasetUrn: id,
    anchorFieldId: id.nullable(),
    contextAssetIds: ids,
    exposureType: id,
  })
  .strict();

export const contextMappingSchema = z
  .object({
    mappingId: id,
    fieldId: id,
    datasetUrn: id,
    contextRelationshipId: id,
    contextAssetId: id,
    contextCategory: id,
    exposureType: id,
    linkageState: id,
    supportingPathIds: ids,
    provenanceReferences: ids.max(12),
  })
  .strict();

export const explorerPathSchema = z
  .object({
    pathId: id,
    graphNodeIds: ids.min(2),
    graphEdgeIds: ids.min(1),
    orderedFields: z.array(fieldIdentitySchema).min(2),
    relationshipIds: ids.min(1),
    targetFieldId: id,
    targetField: fieldIdentitySchema,
    targetDatasetUrn: id,
    depth: z.number().int().positive(),
    compatibilityState: id,
    technicalImpactState: id,
    severityIfRealized: id,
    certainty: id,
    uncertainRelationshipIds: ids,
    evidenceReferences: ids,
    contextAssetIds: ids,
    humanExplanation: id,
    provenanceReferences: ids.max(12),
  })
  .strict();

export const explorerRelationshipSchema = z
  .object({
    graphEdgeId: id,
    relationshipId: id,
    upstream: fieldIdentitySchema,
    downstream: fieldIdentitySchema,
    isRootUncertainty: z.boolean(),
    compatibilityState: id,
    technicalImpactState: id,
    evidenceStrength: id,
    reasonCodes: ids,
    supportingPathIds: ids.min(1),
    pathParticipationCount: z.number().int().positive(),
    humanExplanation: id,
    evidenceReferences: ids,
    provenanceReferences: ids.max(12),
  })
  .strict();

const decisionReasonDetailSchema = z
  .object({
    reasonId: id,
    reasonCode: id,
    statement: id,
    evidenceIds: ids,
  })
  .strict();

const decisionExplanationSchema = z
  .object({
    disposition: z.literal("hold_for_review"),
    decisionRuleId: z.literal(
      "decision-hold-unresolved-material-broad",
    ),
    decisionCertainty: z.literal("high_confidence"),
    technicalCertainty: z.literal("unresolved"),
    inputs: z
      .object({
        technicalConsequence: id,
        impactCertainty: id,
        severityIfRealized: id,
        breadth: id,
        criticality: id,
      })
      .strict(),
    reasons: z.array(decisionReasonDetailSchema).min(1),
    narrative: id,
    whatWeKnow: ids,
    whatWeDoNotKnow: ids,
    confirmedFailureDistinction: id,
  })
  .strict();

export const certifiedImpactExplorerSchema = z
  .object({
    certification: certificationSchema,
    summary: explorerSummarySchema,
    rootCause: explorerRootCauseSchema,
    blockingQuestion: blockingQuestionSchema,
    requiredEvidence: z.array(explorerRequiredEvidenceSchema).length(4),
    evidenceChain: z.array(explorerEvidenceRecordSchema).min(1),
    fields: z.array(fieldImpactSchema).length(25),
    datasets: z.array(datasetImpactSchema).length(20),
    contextAssets: z.array(contextAssetSchema).length(66),
    contextRelationships: z
      .array(contextRelationshipSchema)
      .length(211),
    contextMappings: z.array(contextMappingSchema).length(257),
    paths: z.array(explorerPathSchema).length(48),
    relationships: z.array(explorerRelationshipSchema).length(27),
    decisionExplanation: decisionExplanationSchema,
  })
  .strict()
  .superRefine((explorer, context) => {
    const uniqueness = [
      [explorer.fields, "fieldId"],
      [explorer.datasets, "datasetId"],
      [explorer.contextAssets, "contextAssetId"],
      [explorer.contextRelationships, "relationshipId"],
      [explorer.contextMappings, "mappingId"],
      [explorer.paths, "pathId"],
      [explorer.relationships, "relationshipId"],
    ] as const;
    for (const [records, key] of uniqueness) {
      const values = records.map(
        (record) =>
          (record as unknown as Record<string, string>)[key],
      );
      if (new Set(values).size !== values.length) {
        context.addIssue({
          code: "custom",
          message: `Explorer ${key} values must be unique`,
        });
      }
    }
    const root = explorer.rootCause;
    if (
      explorer.blockingQuestion.rootRelationshipId !==
        root.rootRelationshipId ||
      explorer.blockingQuestion.rootCauseId !== root.causeId
    ) {
      context.addIssue({
        code: "custom",
        message: "Blocking question must reference the certified root cause",
      });
    }
  });

export type CertifiedImpactExplorer = z.infer<
  typeof certifiedImpactExplorerSchema
>;
export type FieldImpact = z.infer<typeof fieldImpactSchema>;
export type DatasetImpact = z.infer<typeof datasetImpactSchema>;
export type ContextAsset = z.infer<typeof contextAssetSchema>;
export type ExplorerPath = z.infer<typeof explorerPathSchema>;
export type ExplorerRelationship = z.infer<
  typeof explorerRelationshipSchema
>;
