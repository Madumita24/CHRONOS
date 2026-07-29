import type { CertifiedChangeReview } from "@/lib/review-contract";

export const reviewFixture = {
  certification: {
    status: "certified",
    fingerprint:
      "sha256:3e8444ec904e0ba1c55c5ae22d69edfa8e722310f51ab30fc783b8175a87ac4a",
    certifiedAt: "2026-07-28T23:15:35.377927+00:00",
    checksPassed: 49,
    checkCount: 49,
    scopeStatement: "Certified read-only Phase 4 scope.",
  },
  change: {
    demonstrationId: "CHRONOS-DEMO-001",
    proposalId: "CHRONOS-DEMO-001-PROPOSAL-001",
    operation: "field_rename",
    datasetUrn:
      "urn:li:dataset:(urn:li:dataPlatform:postgres,b2fd91.order_entry_db.order_entry.orders,PROD)",
    displayIdentity:
      "PostgreSQL / order_entry_db / order_entry / orders / order_total",
    platform: "postgres",
    environment: "PROD",
    currentField: "order_total",
    requestedField: "order_amount",
    description: "Rename the canonical orders total field.",
    rationale: "Frozen CHRONOS demonstration proposal.",
  },
  decision: {
    disposition: "hold_for_review",
    dispositionLabel: "Hold For Review",
    decisionCertainty: "high_confidence",
    technicalCertainty: "unresolved",
    decisionRuleId: "decision-hold-unresolved-material-broad",
    reasons: [
      {
        code: "unresolved_source_compatibility",
        statement: "The first downstream Spark boundary remains unresolved.",
      },
    ],
    narrative:
      "CHRONOS recommends HOLD FOR REVIEW. The proposal has not been proven incompatible and no confirmed failure is asserted.",
  },
  technicalSummary: {
    changeOrigins: 1,
    rootCauses: 1,
    relationshipImpacts: 27,
    dependencyPaths: 48,
    downstreamFields: 25,
    downstreamDatasets: 20,
    confirmedDownstreamFailures: 0,
    potentialRelationships: 26,
    unresolvedRelationships: 1,
    unresolvedPaths: 48,
    unresolvedFields: 25,
  },
  scopeSummary: {
    datasets: 20,
    downstreamFields: 25,
    connectedContextAssets: 66,
    contextRelationships: 211,
    fieldToContextMappings: 257,
    contextCategories: ["bi", "pipeline", "ownership"],
    unresolvedContextReferences: 1,
  },
  severityProfile: {
    technicalConsequence: "unresolved_impact",
    technicalCertainty: "unresolved",
    contextCriticality: "elevated_context",
    breadth: "widespread",
    sensitivity: "pii",
    severityIfRealized: "high",
    fieldDistribution: {
      critical: 0,
      high: 3,
      moderate: 6,
      low: 16,
      undetermined: 0,
    },
    datasetDistribution: {
      critical: 0,
      high: 3,
      moderate: 4,
      low: 13,
      undetermined: 0,
    },
  },
  rootCause: {
    rootCauseId: "technical-impact-cause-source-rename-semantics",
    rootRelationshipId: "future-lineage-68f7e0269dbea7279911b809",
    title: "Unresolved source rename boundary",
    explanation:
      "The certified proposal changes the source identity from orders.order_total to orders.order_amount.",
  },
  blockingQuestions: [
    {
      questionId: "blocking-question-spark-export-rename-compatibility",
      question:
        "Does the Spark export mapping accept or adapt to PostgreSQL orders.order_amount after order_total is renamed?",
      subject: "future-lineage-68f7e0269dbea7279911b809",
      reason:
        "Captured metadata contains neither transform nor query semantics for that boundary.",
      resolutionState: "unresolved",
      affectedFields: 25,
      affectedDatasets: 20,
      affectedPaths: 48,
      requiredEvidenceIds: ["required-evidence-explicit-rename-mapping"],
    },
  ],
  requiredEvidence: [
    {
      evidenceId: "required-evidence-explicit-rename-mapping",
      evidenceClass: "explicit_rename_mapping",
      subject: "future-lineage-68f7e0269dbea7279911b809",
      reason: "Required to determine source boundary compatibility.",
      state: "required_for_decision_resolution",
    },
  ],
  representativePaths: [
    {
      pathId: "representative-path-short",
      kind: "short",
      technicalPathId: "dependency-path-short",
      sourceField: {
        datasetUrn:
          "urn:li:dataset:(urn:li:dataPlatform:postgres,b2fd91.order_entry_db.order_entry.orders,PROD)",
        fieldPath: "order_amount",
      },
      downstreamField: {
        datasetUrn:
          "urn:li:dataset:(urn:li:dataPlatform:s3,b2fd91.demo-data-bucket/order_entry/orders,PROD)",
        fieldPath: "order_total",
      },
      downstreamDatasetUrn:
        "urn:li:dataset:(urn:li:dataPlatform:s3,b2fd91.demo-data-bucket/order_entry/orders,PROD)",
      contextAssetId:
        "urn:li:dataFlow:(spark,b2fd91.export_table_orders_to_s3,b2fd91.default)",
      unresolvedBoundaryRelationshipId:
        "future-lineage-68f7e0269dbea7279911b809",
      relationshipIds: ["future-lineage-68f7e0269dbea7279911b809"],
      hopCount: 1,
      explanation: "Representative certified short path.",
    },
  ],
  contextHighlights: [
    {
      highlightId: "context-highlight-bi-consumer",
      kind: "bi_consumer",
      subjectId: "urn:li:chart:(looker,b2fd91.dashboard_elements.221)",
      displayName: "Popular Products",
      selectionBasis: "Certified representative selection.",
      supportingDatasetUrns: [
        "urn:li:dataset:(urn:li:dataPlatform:looker,b2fd91.order-entry.explore.order_details,PROD)",
      ],
      supportingFieldCount: 1,
    },
  ],
  currentState: {
    classification: "certified_current",
    datasetUrn:
      "urn:li:dataset:(urn:li:dataPlatform:postgres,b2fd91.order_entry_db.order_entry.orders,PROD)",
    fieldPath: "order_total",
    fieldName: "order_total",
    nativeType: "DOUBLE PRECISION",
    normalizedType: "Number",
    schemaFieldCount: 15,
  },
  counterfactualState: {
    classification: "counterfactual",
    datasetUrn:
      "urn:li:dataset:(urn:li:dataPlatform:postgres,b2fd91.order_entry_db.order_entry.orders,PROD)",
    fieldPath: "order_amount",
    fieldName: "order_amount",
    nativeType: "DOUBLE PRECISION",
    normalizedType: "Number",
    schemaFieldCount: 15,
  },
} satisfies CertifiedChangeReview;

export function mutableReviewFixture(): Record<string, unknown> {
  return structuredClone(reviewFixture) as unknown as Record<string, unknown>;
}
