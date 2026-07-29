import { z } from "zod";

import {
  certificationSchema,
  fieldIdentitySchema,
} from "@/lib/review-contract";

const graphStateSchema = z.enum([
  "certified_current",
  "counterfactual_changed",
  "counterfactual_inherited",
  "counterfactual_unresolved",
]);

const diffStateSchema = z.enum([
  "removed_current_identity",
  "added_counterfactual_identity",
  "identity_preserved",
  "removed_current_relationship",
  "projected_source_relationship",
]);

export const graphNodeSchema = z
  .object({
    id: z.string().min(1),
    machineKey: z.string().min(1),
    label: z.string().min(1),
    secondaryLabel: z.string().min(1),
    entityType: z.literal("field"),
    platform: z.string().min(1),
    datasetUrn: z.string().startsWith("urn:li:dataset:("),
    fieldPath: z.string().min(1),
    graphState: graphStateSchema,
    diffState: diffStateSchema.nullable(),
    exposureState: z.string().nullable(),
    compatibilityState: z
      .enum([
        "compatible",
        "incompatible",
        "conditionally_compatible",
        "unknown",
      ])
      .nullable(),
    technicalImpactState: z.string().nullable(),
    severityIfRealized: z.string().nullable(),
    certainty: z.string().nullable(),
    depth: z.number().int().nonnegative(),
    pathCount: z.number().int().nonnegative(),
    isChangeOrigin: z.boolean(),
    isRootBoundaryTarget: z.boolean(),
    supportingPathIds: z.array(z.string().min(1)),
    provenanceReferences: z.array(z.string().min(1)).max(12),
  })
  .strict();

export const graphEdgeSchema = z
  .object({
    id: z.string().min(1),
    relationshipId: z.string().min(1),
    source: z.string().min(1),
    target: z.string().min(1),
    upstream: fieldIdentitySchema,
    downstream: fieldIdentitySchema,
    currentUpstream: fieldIdentitySchema.nullable(),
    currentDownstream: fieldIdentitySchema.nullable(),
    relationshipType: z.string().min(1),
    graphState: z.string().min(1),
    diffState: diffStateSchema.nullable(),
    exposureState: z.string().nullable(),
    compatibilityState: z
      .enum([
        "compatible",
        "incompatible",
        "conditionally_compatible",
        "unknown",
      ])
      .nullable(),
    technicalImpactState: z.string().nullable(),
    evidenceStrength: z.string().nullable(),
    reasonCode: z.string().nullable(),
    explanation: z.string().nullable(),
    isRootUncertainty: z.boolean(),
    mappingGroupIds: z.array(z.string().min(1)),
    supportingPathIds: z.array(z.string().min(1)),
    pathParticipationCount: z.number().int().nonnegative(),
    transformOperations: z.array(z.string()),
    queryEvidence: z.array(z.string()),
    provenanceReferences: z.array(z.string().min(1)).max(12),
  })
  .strict();

export const graphProjectionSchema = z
  .object({
    mode: z.enum(["current", "future", "diff"]),
    nodes: z.array(graphNodeSchema),
    edges: z.array(graphEdgeSchema),
  })
  .strict()
  .superRefine((projection, context) => {
    const nodeIds = new Set(projection.nodes.map((node) => node.id));
    const edgeIds = new Set(projection.edges.map((edge) => edge.id));
    if (nodeIds.size !== projection.nodes.length) {
      context.addIssue({
        code: "custom",
        message: `${projection.mode} node IDs must be unique`,
      });
    }
    if (edgeIds.size !== projection.edges.length) {
      context.addIssue({
        code: "custom",
        message: `${projection.mode} edge IDs must be unique`,
      });
    }
    for (const edge of projection.edges) {
      if (!nodeIds.has(edge.source) || !nodeIds.has(edge.target)) {
        context.addIssue({
          code: "custom",
          message: `${projection.mode} edge endpoint is dangling`,
        });
      }
    }
  });

const graphPathSchema = z
  .object({
    pathId: z.string().min(1),
    futureGraphPathId: z.string().min(1),
    targetField: fieldIdentitySchema,
    depth: z.number().int().positive(),
    currentNodeIds: z.array(z.string().min(1)).min(2),
    currentEdgeIds: z.array(z.string().min(1)).min(1),
    futureNodeIds: z.array(z.string().min(1)).min(2),
    futureEdgeIds: z.array(z.string().min(1)).min(1),
    diffNodeIds: z.array(z.string().min(1)).min(2),
    diffEdgeIds: z.array(z.string().min(1)).min(1),
    compatibilityState: z.string().min(1),
    technicalImpactState: z.string().min(1),
    uncertainRelationshipIds: z.array(z.string().min(1)),
    provenanceReferences: z.array(z.string().min(1)).max(12),
  })
  .strict()
  .superRefine((path, context) => {
    for (const [nodes, edges, label] of [
      [path.currentNodeIds, path.currentEdgeIds, "current"],
      [path.futureNodeIds, path.futureEdgeIds, "future"],
      [path.diffNodeIds, path.diffEdgeIds, "diff"],
    ] as const) {
      if (nodes.length !== edges.length + 1) {
        context.addIssue({
          code: "custom",
          message: `${label} path ordering is inconsistent`,
        });
      }
    }
  });

const summarySchema = z
  .object({
    currentFieldNodes: z.literal(26),
    futureFieldNodes: z.literal(26),
    downstreamFields: z.literal(25),
    downstreamDatasets: z.literal(20),
    structuralRelationships: z.literal(27),
    supportingPaths: z.literal(48),
    rootUnknownBoundaries: z.literal(1),
    conditionalRelationships: z.literal(26),
    multipathFields: z.literal(21),
    confirmedFailures: z.literal(0),
    maximumDepth: z.literal(5),
  })
  .strict();

export const certifiedGraphReviewSchema = z
  .object({
    certification: certificationSchema,
    sourceChange: z
      .object({
        current: fieldIdentitySchema,
        future: fieldIdentitySchema,
        mappingClassification: z.literal("renamed"),
        disposition: z.literal("hold_for_review"),
        technicalCertainty: z.literal("unresolved"),
        severityIfRealized: z.literal("high"),
      })
      .strict(),
    currentGraph: graphProjectionSchema,
    futureGraph: graphProjectionSchema,
    diffGraph: graphProjectionSchema,
    identityMappings: z.array(
      z
        .object({
          mappingId: z.string().min(1),
          currentNodeId: z.string().min(1),
          futureNodeId: z.string().min(1),
          currentIdentity: fieldIdentitySchema,
          futureIdentity: fieldIdentitySchema,
          classification: z.enum(["renamed", "identity_preserved"]),
          provenanceReferences: z.array(z.string().min(1)),
        })
        .strict(),
    ),
    rootUncertainty: z
      .object({
        futureEdgeId: z.string().min(1),
        currentEdgeId: z.string().min(1),
        relationshipId: z.string().min(1),
        currentSource: fieldIdentitySchema,
        currentTarget: fieldIdentitySchema,
        futureSource: fieldIdentitySchema,
        futureTarget: fieldIdentitySchema,
        compatibilityState: z.literal("unknown"),
        evidenceStrength: z.literal("insufficient"),
        reasonCode: z.literal("source_rename_semantics_unknown"),
        explanation: z.string().min(1),
        missingEvidence: z
          .array(
            z
              .object({
                evidenceId: z.string().min(1),
                evidenceClass: z.string().min(1),
                label: z.string().min(1),
                reason: z.string().min(1),
              })
              .strict(),
          )
          .length(4),
        mappingGroupIds: z.array(z.string().min(1)),
        transformOperations: z.array(z.string()),
        queryEvidence: z.array(z.string()),
        pathParticipationCount: z.literal(48),
        provenanceReferences: z.array(z.string().min(1)).max(12),
      })
      .strict(),
    supportingPaths: z.array(graphPathSchema).length(48),
    representativePaths: z
      .array(
        z
          .object({
            shortcutId: z.string().min(1),
            label: z.string().min(1),
            kind: z.enum(["short", "deep", "multipath"]),
            supportingPathId: z.string().min(1),
            explanation: z.string().min(1),
          })
          .strict(),
      )
      .length(3),
    legend: z.array(
      z
        .object({
          key: z.string().min(1),
          label: z.string().min(1),
          description: z.string().min(1),
          tone: z.string().min(1),
        })
        .strict(),
    ),
    summary: summarySchema,
  })
  .strict()
  .superRefine((review, context) => {
    if (
      review.currentGraph.mode !== "current" ||
      review.futureGraph.mode !== "future" ||
      review.diffGraph.mode !== "diff"
    ) {
      context.addIssue({
        code: "custom",
        message: "Graph projection modes are inconsistent",
      });
    }
    if (
      review.currentGraph.nodes.length !== 26 ||
      review.currentGraph.edges.length !== 27 ||
      review.futureGraph.nodes.length !== 26 ||
      review.futureGraph.edges.length !== 27
    ) {
      context.addIssue({
        code: "custom",
        message: "Certified graph cardinalities are invalid",
      });
    }
    if (
      review.sourceChange.current.fieldPath !== "order_total" ||
      review.sourceChange.future.fieldPath !== "order_amount"
    ) {
      context.addIssue({
        code: "custom",
        message: "Source identity replacement is invalid",
      });
    }
    if (
      review.identityMappings.length !== 26 ||
      review.identityMappings.filter(
        (item) => item.classification === "renamed",
      ).length !== 1 ||
      review.identityMappings.filter(
        (item) => item.classification === "identity_preserved",
      ).length !== 25
    ) {
      context.addIssue({
        code: "custom",
        message: "Identity mapping cardinalities are invalid",
      });
    }
    const rootEdges = review.futureGraph.edges.filter(
      (edge) => edge.isRootUncertainty,
    );
    if (
      rootEdges.length !== 1 ||
      rootEdges[0]?.id !== review.rootUncertainty.futureEdgeId ||
      rootEdges[0]?.compatibilityState !== "unknown"
    ) {
      context.addIssue({
        code: "custom",
        message: "Root uncertainty relationship is invalid",
      });
    }
    if (
      review.futureGraph.edges.filter(
        (edge) =>
          edge.compatibilityState === "conditionally_compatible",
      ).length !== 26
    ) {
      context.addIssue({
        code: "custom",
        message: "Conditional relationship count is invalid",
      });
    }
    const pathIds = new Set(
      review.supportingPaths.map((path) => path.pathId),
    );
    if (pathIds.size !== 48) {
      context.addIssue({
        code: "custom",
        message: "Supporting path IDs must be unique",
      });
    }
    for (const shortcut of review.representativePaths) {
      if (!pathIds.has(shortcut.supportingPathId)) {
        context.addIssue({
          code: "custom",
          message: "Representative path reference is dangling",
        });
      }
    }
    for (const [
      projection,
      nodeKey,
      edgeKey,
    ] of [
      [review.currentGraph, "currentNodeIds", "currentEdgeIds"],
      [review.futureGraph, "futureNodeIds", "futureEdgeIds"],
      [review.diffGraph, "diffNodeIds", "diffEdgeIds"],
    ] as const) {
      const nodeIds = new Set(projection.nodes.map((node) => node.id));
      const edgeIds = new Set(projection.edges.map((edge) => edge.id));
      for (const path of review.supportingPaths) {
        if (
          path[nodeKey].some((id) => !nodeIds.has(id)) ||
          path[edgeKey].some((id) => !edgeIds.has(id))
        ) {
          context.addIssue({
            code: "custom",
            message: `Path reference dangles in ${projection.mode}`,
          });
        }
      }
    }
  });

export type CertifiedGraphReview = z.infer<
  typeof certifiedGraphReviewSchema
>;
export type GraphNodeRecord = z.infer<typeof graphNodeSchema>;
export type GraphEdgeRecord = z.infer<typeof graphEdgeSchema>;
export type GraphProjection = z.infer<typeof graphProjectionSchema>;
export type GraphPathRecord = z.infer<typeof graphPathSchema>;
