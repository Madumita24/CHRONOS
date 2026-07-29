import type {
  CertifiedGraphReview,
  GraphEdgeRecord,
  GraphNodeRecord,
} from "@/lib/graph-contract";

const SOURCE_DATASET =
  "urn:li:dataset:(urn:li:dataPlatform:postgres,demo.orders,PROD)";

function datasetUrn(index: number): string {
  return index === 0
    ? SOURCE_DATASET
    : `urn:li:dataset:(urn:li:dataPlatform:${platformFor(index)},demo.dataset_${index},PROD)`;
}

function platformFor(index: number): string {
  if (index === 0) return "postgres";
  if (index < 7) return "s3";
  if (index < 14) return "snowflake";
  if (index < 21) return "looker";
  return "bigquery";
}

function fieldPath(index: number): string {
  return index === 0 ? "order_total" : `derived_total_${index}`;
}

function identity(index: number, future = false) {
  return {
    datasetUrn: datasetUrn(index),
    fieldPath: index === 0 && future ? "order_amount" : fieldPath(index),
  };
}

function node(
  id: string,
  index: number,
  mode: "current" | "future" | "diff",
  overrides: Partial<GraphNodeRecord> = {},
): GraphNodeRecord {
  const future = mode !== "current";
  const field = index === 0 && future ? "order_amount" : fieldPath(index);
  return {
    id,
    machineKey: `${datasetUrn(index)}::${field}`,
    label: field,
    secondaryLabel: index === 0 ? "orders" : `dataset_${index}`,
    entityType: "field",
    platform: platformFor(index),
    datasetUrn: datasetUrn(index),
    fieldPath: field,
    graphState:
      mode === "current"
        ? "certified_current"
        : index === 0
          ? "counterfactual_changed"
          : "counterfactual_inherited",
    diffState:
      mode === "diff"
        ? index === 0
          ? "added_counterfactual_identity"
          : "identity_preserved"
        : null,
    exposureState: index === 0 ? "change_origin" : "downstream_exposed",
    compatibilityState:
      mode === "current"
        ? null
        : index === 0
          ? "unknown"
          : "conditionally_compatible",
    technicalImpactState: mode === "current" ? null : "unresolved",
    severityIfRealized: mode === "current" ? null : "high",
    certainty: mode === "current" ? null : "unresolved",
    depth: Math.min(index, 5),
    pathCount: index === 0 ? 48 : index < 22 ? 2 : 1,
    isChangeOrigin: index === 0,
    isRootBoundaryTarget: index === 1,
    supportingPathIds: Array.from(
      { length: index === 0 ? 48 : index < 22 ? 2 : 1 },
      (_, pathIndex) => `path-${pathIndex}`,
    ),
    provenanceReferences: ["phase4://certified"],
    ...overrides,
  };
}

function edge(
  id: string,
  source: string,
  target: string,
  upstreamIndex: number,
  downstreamIndex: number,
  mode: "current" | "future" | "diff",
  root: boolean,
  overrides: Partial<GraphEdgeRecord> = {},
): GraphEdgeRecord {
  const future = mode !== "current";
  return {
    id,
    relationshipId: `relationship-${upstreamIndex}-${downstreamIndex}`,
    source,
    target,
    upstream: identity(upstreamIndex, future),
    downstream: identity(downstreamIndex, future),
    currentUpstream: identity(upstreamIndex),
    currentDownstream: identity(downstreamIndex),
    relationshipType: "field_lineage",
    graphState: mode === "current" ? "certified_current" : "counterfactual",
    diffState:
      mode === "diff" && root ? "projected_source_relationship" : null,
    exposureState: mode === "current" ? null : "downstream_exposed",
    compatibilityState:
      mode === "current"
        ? null
        : root
          ? "unknown"
          : "conditionally_compatible",
    technicalImpactState: mode === "current" ? null : "unresolved",
    evidenceStrength: root && future ? "insufficient" : "structural",
    reasonCode:
      root && future ? "source_rename_semantics_unknown" : "inherited_lineage",
    explanation: root
      ? "The rename boundary lacks explicit transform or query evidence."
      : "Certified counterfactual relationship.",
    isRootUncertainty: root && future,
    mappingGroupIds: root ? ["mapping-root"] : [],
    supportingPathIds: Array.from(
      { length: root ? 48 : 2 },
      (_, pathIndex) => `path-${pathIndex}`,
    ),
    pathParticipationCount: root ? 48 : 2,
    transformOperations: [],
    queryEvidence: [],
    provenanceReferences: ["phase4://certified"],
    ...overrides,
  };
}

const currentNodes = Array.from({ length: 26 }, (_, index) =>
  node(`current-${index}`, index, "current"),
);
const futureNodes = Array.from({ length: 26 }, (_, index) =>
  node(`future-${index}`, index, "future"),
);

const pairs = [
  ...Array.from({ length: 25 }, (_, index) => [index, index + 1] as const),
  [0, 2] as const,
  [1, 3] as const,
];

const currentEdges = pairs.map(([upstream, downstream], index) =>
  edge(
    `current-edge-${index}`,
    `current-${upstream}`,
    `current-${downstream}`,
    upstream,
    downstream,
    "current",
    index === 0,
  ),
);
const futureEdges = pairs.map(([upstream, downstream], index) =>
  edge(
    `future-edge-${index}`,
    `future-${upstream}`,
    `future-${downstream}`,
    upstream,
    downstream,
    "future",
    index === 0,
  ),
);
const diffNodes = [
  node("diff-current-source", 0, "current", {
    diffState: "removed_current_identity",
  }),
  ...Array.from({ length: 26 }, (_, index) =>
    node(`diff-future-${index}`, index, "diff"),
  ),
];
const diffEdges = [
  edge(
    "diff-removed-root",
    "diff-current-source",
    "diff-future-1",
    0,
    1,
    "current",
    true,
    {
      diffState: "removed_current_relationship",
      isRootUncertainty: false,
    },
  ),
  ...pairs.map(([upstream, downstream], index) =>
    edge(
      `diff-edge-${index}`,
      `diff-future-${upstream}`,
      `diff-future-${downstream}`,
      upstream,
      downstream,
      "diff",
      index === 0,
    ),
  ),
];

export const graphFixture: CertifiedGraphReview = {
  certification: {
    status: "certified",
    fingerprint:
      "sha256:3e8444ec904e0ba1c55c5ae22d69edfa8e722310f51ab30fc783b8175a87ac4a",
    certifiedAt: "2026-07-28T23:15:35.377927+00:00",
    checksPassed: 49,
    checkCount: 49,
    scopeStatement: "Certified read-only Phase 4 scope.",
  },
  sourceChange: {
    current: identity(0),
    future: identity(0, true),
    mappingClassification: "renamed",
    disposition: "hold_for_review",
    technicalCertainty: "unresolved",
    severityIfRealized: "high",
  },
  currentGraph: {
    mode: "current",
    nodes: currentNodes,
    edges: currentEdges,
  },
  futureGraph: {
    mode: "future",
    nodes: futureNodes,
    edges: futureEdges,
  },
  diffGraph: {
    mode: "diff",
    nodes: diffNodes,
    edges: diffEdges,
  },
  identityMappings: Array.from({ length: 26 }, (_, index) => ({
    mappingId: `mapping-${index}`,
    currentNodeId: `current-${index}`,
    futureNodeId: `future-${index}`,
    currentIdentity: identity(index),
    futureIdentity: identity(index, index === 0),
    classification: index === 0 ? "renamed" : "identity_preserved",
    provenanceReferences: ["phase4://certified"],
  })),
  rootUncertainty: {
    futureEdgeId: "future-edge-0",
    currentEdgeId: "current-edge-0",
    relationshipId: "relationship-0-1",
    currentSource: identity(0),
    currentTarget: identity(1),
    futureSource: identity(0, true),
    futureTarget: identity(1, true),
    compatibilityState: "unknown",
    evidenceStrength: "insufficient",
    reasonCode: "source_rename_semantics_unknown",
    explanation: "The rename boundary lacks explicit semantic evidence.",
    missingEvidence: [
      {
        evidenceId: "evidence-1",
        evidenceClass: "explicit_rename_mapping",
        label: "Explicit rename mapping",
        reason: "Required to prove the boundary.",
      },
      {
        evidenceId: "evidence-2",
        evidenceClass: "transform_semantics",
        label: "Transform semantics",
        reason: "No transform operation was captured.",
      },
      {
        evidenceId: "evidence-3",
        evidenceClass: "query_evidence",
        label: "Query evidence",
        reason: "No query text was captured.",
      },
      {
        evidenceId: "evidence-4",
        evidenceClass: "runtime_validation",
        label: "Runtime validation",
        reason: "No runtime validation was captured.",
      },
    ],
    mappingGroupIds: ["mapping-root"],
    transformOperations: [],
    queryEvidence: [],
    pathParticipationCount: 48,
    provenanceReferences: ["phase4://certified"],
  },
  supportingPaths: Array.from({ length: 48 }, (_, index) => ({
    pathId: `path-${index}`,
    futureGraphPathId: `future-path-${index}`,
    targetField: identity((index % 25) + 1, true),
    depth: (index % 5) + 1,
    currentNodeIds: ["current-0", "current-1"],
    currentEdgeIds: ["current-edge-0"],
    futureNodeIds: ["future-0", "future-1"],
    futureEdgeIds: ["future-edge-0"],
    diffNodeIds: ["diff-future-0", "diff-future-1"],
    diffEdgeIds: ["diff-edge-0"],
    compatibilityState: "unknown",
    technicalImpactState: "unresolved",
    uncertainRelationshipIds: ["relationship-0-1"],
    provenanceReferences: ["phase4://certified"],
  })),
  representativePaths: [
    {
      shortcutId: "representative-short",
      label: "Shortest boundary",
      kind: "short",
      supportingPathId: "path-0",
      explanation: "One-hop root boundary.",
    },
    {
      shortcutId: "representative-deep",
      label: "Deepest path",
      kind: "deep",
      supportingPathId: "path-4",
      explanation: "Certified maximum-depth path.",
    },
    {
      shortcutId: "representative-multipath",
      label: "Multipath field",
      kind: "multipath",
      supportingPathId: "path-20",
      explanation: "Certified multipath example.",
    },
  ],
  legend: [
    {
      key: "unknown",
      label: "Unknown",
      description: "Evidence is insufficient.",
      tone: "unknown",
    },
    {
      key: "conditional",
      label: "Conditionally compatible",
      description: "Conditionally compatible relationship.",
      tone: "conditionally_compatible",
    },
    {
      key: "incompatible",
      label: "Incompatible",
      description: "Confirmed incompatible relationship.",
      tone: "incompatible",
    },
    {
      key: "added",
      label: "Added",
      description: "Counterfactual addition.",
      tone: "added",
    },
    {
      key: "removed",
      label: "Removed",
      description: "Current-state removal.",
      tone: "removed",
    },
  ],
  summary: {
    currentFieldNodes: 26,
    futureFieldNodes: 26,
    downstreamFields: 25,
    downstreamDatasets: 20,
    structuralRelationships: 27,
    supportingPaths: 48,
    rootUnknownBoundaries: 1,
    conditionalRelationships: 26,
    multipathFields: 21,
    confirmedFailures: 0,
    maximumDepth: 5,
  },
};
