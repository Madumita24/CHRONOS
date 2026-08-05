import type {
  AnalysisDetail,
  AnalysisGraph,
  AnalysisIndex,
  EvidenceRecord,
  PatchPreview,
  ReleaseCertification,
} from "@/lib/phase6-contract";

const fingerprint = `sha256:${"a".repeat(64)}`;

export const certification: ReleaseCertification["certification"] = {
  state: "PHASE_6_CERTIFIED_WITH_NON_BLOCKING_LIMITATIONS",
  releaseId: "phase-6-rerun",
  certificationVersion: "6.5.0",
  packageFingerprint: fingerprint,
  releaseManifestFingerprint: fingerprint,
  topLevelCertificationFingerprint: fingerprint,
  limitations: ["Seven live DataHub integration tests were intentionally skipped."],
  runtimeVerified: false,
};

const common: Pick<
  AnalysisDetail,
  | "scenarioId"
  | "proposalId"
  | "operation"
  | "certification"
  | "manifestFingerprint"
  | "warnings"
  | "limitations"
  | "confirmedRuntimeFailures"
  | "executionValidity"
> = {
  scenarioId: "CHRONOS-DEMO-001",
  proposalId: "proposal-001",
  operation: "field_rename",
  certification,
  manifestFingerprint: fingerprint,
  warnings: [],
  limitations: [...certification.limitations],
  confirmedRuntimeFailures: 0,
  executionValidity: "UNVERIFIED",
};

type StructuralDetail = Extract<AnalysisDetail, { analysisType: "structural" }>;
type SemanticDetail = Extract<AnalysisDetail, { analysisType: "semantic" }>;
type PullRequestDetail = Extract<AnalysisDetail, { analysisType: "pull_request" }>;
type RepairDetail = Extract<AnalysisDetail, { analysisType: "repair" }>;

export const structuralDetail: StructuralDetail = {
  ...common,
  analysisId: "CHRONOS-DEMO-001-GENERALIZED-RENAME",
  analysisType: "structural",
  displayName: "Generalized field rename",
  decision: "hold_for_review",
  change: {
    datasetUrn: "urn:li:dataset:(urn:li:dataPlatform:snowflake,orders,PROD)",
    currentField: "order_total",
    proposedField: "order_amount",
    currentType: "NUMBER",
    proposedType: "NUMBER",
    identityMapping: "EXPLICIT_RENAME",
    compatibility: "UNKNOWN",
    downstreamFields: 4,
    downstreamDatasets: 2,
    rootCauses: ["root-1"],
    blockingQuestions: ["Does the consumer accept the renamed field?"],
    requiredEvidence: ["Consumer contract evidence"],
  },
};

export const semanticDetail: SemanticDetail = {
  ...common,
  analysisId: "CHRONOS-SEMANTIC-AGGREGATION-001",
  analysisType: "semantic",
  displayName: "Aggregation semantic change",
  decision: "hold_for_review",
  modelDatasetUrn: "urn:li:dataset:(urn:li:dataPlatform:dbt,orders_daily,PROD)",
  beforeFingerprint: fingerprint,
  afterFingerprint: fingerprint,
  semanticCompatibility: "SEMANTIC_COMPATIBILITY_UNKNOWN",
  structuralCompatibility: "STRUCTURALLY_COMPATIBLE",
  deltas: [{
    deltaId: "delta-1",
    deltaType: "AGGREGATION_CHANGE",
    before: "sum(order_total)",
    after: "avg(order_total)",
    affectedOutput: "daily_total",
    affectedModel: "orders_daily",
    scope: "FIELD-SPECIFIC",
    certainty: "CERTAIN",
    evidenceClass: "CODE-DERIVED",
    potentialConsequence: "The output meaning may change.",
    missingEvidence: ["Consumer expectation"],
  }],
  affectedOutputFields: ["daily_total"],
  rootCauses: ["root-semantic"],
  blockingQuestions: ["Is the new aggregation intended?"],
};

export const pullRequestDetail: PullRequestDetail = {
  ...common,
  analysisId: "CHRONOS-PR-CONFLICT-001",
  analysisType: "pull_request",
  displayName: "Conflicting pull request",
  decision: "block_confirmed_incompatibility",
  repository: "chronos/demo",
  baseIdentity: "base-commit",
  headIdentity: "head-commit",
  coherence: "INCONSISTENT",
  changedFiles: [{
    fileId: "file-1",
    path: "models/orders.sql",
    status: "modified",
    category: "sql",
    parser: "sqlglot",
    materialState: "MATERIAL",
    deltaCount: 1,
    warningCount: 0,
    resolvedEntityCount: 1,
    unresolvedReferenceCount: 1,
  }],
  logicalGroups: [{
    groupId: "group-1",
    currentIdentity: "order_total",
    proposedIdentities: ["order_amount", "order_value"],
    contributingFileIds: ["file-1"],
    structuralChangeIds: ["change-1"],
    semanticChangeIds: [],
    staleReferenceIds: ["stale-1"],
    coherence: "INCONSISTENT",
    conflictIds: ["conflict-1"],
    rootIds: ["root-1"],
    evidenceIds: ["evidence-1"],
  }],
  conflicts: [{
    conflictId: "conflict-1",
    currentEntity: "order_total",
    proposedIdentities: ["order_amount", "order_value"],
    supportingFileIds: ["file-1"],
    reason: "Two competing identities are proposed.",
    requiredEvidence: ["Owner selection"],
  }],
  rootCauses: ["root-1"],
};

export const repairDetail: RepairDetail = {
  ...common,
  analysisId: "CHRONOS-REPAIR-PRIMARY-001",
  analysisType: "repair",
  displayName: "Partial repair candidate",
  decision: "PARTIAL_REPAIR_CANDIDATE",
  predecessorAnalysisId: "CHRONOS-PR-PRIMARY-001",
  repairDisposition: "PARTIAL_REPAIR_CANDIDATE",
  repairCompleteness: "PARTIALLY_ADDRESSED_SELECTED_ROOTS",
  projectedStateLabel: "PROJECTED REPAIRED - STATIC ONLY - RUNTIME UNVERIFIED",
  repairability: [{
    rootId: "root-1",
    rootType: "STALE_REFERENCE",
    state: "AUTO_REPAIRABLE",
    reason: "The intended identity is unambiguous.",
    evidenceIds: ["evidence-1"],
    remainingUncertainty: ["Runtime behavior"],
    evidenceClass: "CODE-DERIVED",
  }],
  actions: [{
    actionId: "action-1",
    applicationOrder: 1,
    file: "models/orders.sql",
    exactTarget: "order_total",
    currentValue: "order_total",
    proposedValue: "order_amount",
    rule: "replace_stale_reference",
    rootId: "root-1",
    evidenceIds: ["evidence-1"],
    dependencies: [],
    protectedSemantics: ["aggregation"],
    remainingValidation: ["Execute Phase 7 tests"],
    evidenceClass: "STATIC PROJECTED",
  }],
  patches: [{
    patchId: "patch-001",
    file: "models/orders.sql",
    hunkCount: 1,
    fingerprint,
    actionIds: ["action-1"],
    protectedSemanticsState: "STATICALLY_PRESERVED",
    staticValidationState: "PASS",
  }],
  comparison: {
    originalCoherence: "PARTIALLY_COHERENT",
    projectedCoherence: "COHERENT",
    originalStaleReferences: 1,
    projectedStaleReferences: 0,
    targetedRoots: 1,
    projectedClosedRoots: 1,
    remainingRoots: 0,
    newRoots: 0,
    conflictsBefore: 0,
    conflictsAfter: 0,
    unresolvedSemanticQuestions: 1,
    executionValidity: "UNVERIFIED",
  },
  remainingFindings: ["Semantic intent is not runtime verified."],
  phase7Requirements: [
    "clean_patch_application",
    "dependency_installation",
    "sql_dbt_validation",
    "schema_contract_validation",
    "dag_checks",
    "repository_tests",
    "data_comparison",
    "downstream_consumer_checks",
    "owner_business_approval",
    "runtime_evidence_collection",
  ],
};

export const noRepairDetail: RepairDetail = {
  ...repairDetail,
  analysisId: "CHRONOS-REPAIR-COHERENT-001",
  displayName: "No supported automatic repair",
  decision: "NO_SUPPORTED_AUTOMATIC_REPAIR",
  repairDisposition: "NO_SUPPORTED_AUTOMATIC_REPAIR",
  repairCompleteness: "NO_SUPPORTED_REPAIR",
  repairability: [],
  actions: [],
  patches: [],
};

export const conflictRepairDetail: RepairDetail = {
  ...noRepairDetail,
  analysisId: "CHRONOS-REPAIR-CONFLICT-001",
  displayName: "Repair blocked by conflict",
  decision: "REPAIR_BLOCKED_BY_CONFLICT",
  repairDisposition: "REPAIR_BLOCKED_BY_CONFLICT",
  repairability: [{
    rootId: "root-conflict",
    rootType: "IDENTITY_CONFLICT",
    state: "BLOCKED_BY_CONFLICT",
    reason: "No winning identity is certified.",
    evidenceIds: ["evidence-conflict"],
    remainingUncertainty: ["Owner decision"],
    evidenceClass: "CODE-DERIVED",
  }],
};

function summary(detail: AnalysisDetail) {
  return {
    analysisId: detail.analysisId,
    analysisType: detail.analysisType,
    displayName: detail.displayName,
    scenarioId: detail.scenarioId,
    proposalId: detail.proposalId,
    certificationState: detail.certification.state,
    decision: detail.decision,
    operation: detail.operation,
    repositoryIdentity: detail.analysisType === "pull_request" ? detail.repository : null,
    baseIdentity: detail.analysisType === "pull_request" ? detail.baseIdentity : null,
    headIdentity: detail.analysisType === "pull_request" ? detail.headIdentity : null,
    coherence: detail.analysisType === "pull_request" ? detail.coherence : null,
    conflictCount: detail.analysisType === "pull_request" ? detail.conflicts.length : 0,
    rootCauseCount: detail.analysisType === "repair" ? detail.repairability.length : 1,
    affectedFileCount: detail.analysisType === "pull_request" ? detail.changedFiles.length : 0,
    affectedDatasetCount: 1,
    repairActionCount: detail.analysisType === "repair" ? detail.actions.length : 0,
    configuredAt: null,
    warnings: detail.warnings,
    limitations: detail.limitations,
    manifestFingerprint: detail.manifestFingerprint,
  } as const;
}

export const analysisIndex: AnalysisIndex = {
  certification,
  analyses: [structuralDetail, semanticDetail, pullRequestDetail, repairDetail].map(summary),
};

export const releaseCertification: ReleaseCertification = {
  certification,
  sourceCommit: "0123456789abcdef0123456789abcdef01234567",
  sourceTree: "89abcdef0123456789abcdef0123456789abcdef",
  testTotals: { executed: 1484, passed: 1477, skipped: 7, failed: 0 },
  skippedTestCount: 7,
  supportedCapabilities: ["certified_static_analysis"],
  unsupportedCapabilities: ["runtime_execution"],
  goldenPreservationState: "PASS",
};

export const analysisGraph: AnalysisGraph = {
  analysisId: structuralDetail.analysisId,
  mode: "PROPOSED",
  availableModes: ["CURRENT", "PROPOSED", "DIFF"],
  runtimeVerified: false,
  nodes: [
    { nodeId: "node-root-a", label: "Root A", nodeType: "root", state: "current", evidenceClass: "CODE-DERIVED" },
    { nodeId: "node-root-b", label: "Root B", nodeType: "root", state: "current", evidenceClass: "CODE-DERIVED" },
    { nodeId: "node-target", label: "Dashboard", nodeType: "dashboard", state: "proposed", evidenceClass: "COUNTERFACTUAL" },
  ],
  edges: [
    { edgeId: "edge-a", source: "node-root-a", target: "node-target", category: "COUNTERFACTUAL_EDGE", evidenceClass: "COUNTERFACTUAL", state: "proposed" },
    { edgeId: "edge-b", source: "node-root-b", target: "node-target", category: "CODE_DERIVED_PROPOSED_EDGE", evidenceClass: "CODE-DERIVED", state: "proposed" },
  ],
  representativePaths: [{
    pathId: "path-a",
    nodeIds: ["node-root-a", "node-target"],
    edgeIds: ["edge-a"],
    rootIds: ["root-a", "root-b"],
    contributingFileIds: ["models/orders.sql"],
    target: "Dashboard",
    evidenceClass: "COUNTERFACTUAL",
  }],
};

export const evidence: EvidenceRecord[] = [{
  evidenceId: "evidence-1",
  evidenceClass: "CODE-DERIVED",
  subject: "models/orders.sql",
  statement: "The static parser observed a stale field reference.",
  certainty: "CERTAIN",
}];

export const patchPreview: PatchPreview = {
  analysisId: repairDetail.analysisId,
  patchId: "patch-001",
  file: "models/orders.sql",
  fingerprint,
  lines: [
    { oldLine: null, newLine: null, kind: "header", text: "@@ -1 +1 @@" },
    { oldLine: 1, newLine: null, kind: "removal", text: "-select order_total" },
    { oldLine: null, newLine: 1, kind: "addition", text: "+select order_amount" },
  ],
  originalExcerpt: ["select order_total"],
  candidateExcerpt: ["select order_amount"],
  label: "CANDIDATE - NOT APPLIED",
  runtimeVerified: false,
};
