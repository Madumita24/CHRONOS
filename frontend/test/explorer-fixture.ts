const datasetUrn = (index: number) =>
  `urn:li:dataset:(urn:li:dataPlatform:test,dataset_${index},PROD)`;
const fieldId = (index: number) => `future-field-${index}`;
const pathId = (index: number) => `dependency-path-${index}`;
const relationshipId = (index: number) => `future-lineage-${index}`;
const edgeId = (index: number) => `future-edge-${index}`;
const assetId = (index: number) => `urn:li:tag:context-${index}`;
const contextRelationshipId = (index: number) =>
  `context-relationship-${index}`;
const mappingId = (index: number) => `context-mapping-${index}`;

export function explorerFixture() {
  const relationships = Array.from({ length: 27 }, (_, index) => ({
    graphEdgeId: edgeId(index),
    relationshipId: relationshipId(index),
    upstream: {
      datasetUrn: datasetUrn(index % 20),
      fieldPath: `field_${index}`,
    },
    downstream: {
      datasetUrn: datasetUrn((index + 1) % 20),
      fieldPath: `field_${index + 1}`,
    },
    isRootUncertainty: index === 0,
    compatibilityState:
      index === 0 ? "unknown" : "conditionally_compatible",
    technicalImpactState:
      index === 0 ? "unresolved_impact" : "potential_impact",
    evidenceStrength: index === 0 ? "insufficient" : "derived",
    reasonCodes: ["certified_reason"],
    supportingPathIds: [pathId(index % 48)],
    pathParticipationCount: 1,
    humanExplanation: "Certified relationship explanation.",
    evidenceReferences: ["evidence-chain"],
    provenanceReferences: [`relationship-provenance-${index}`],
  }));
  const paths = Array.from({ length: 48 }, (_, index) => ({
    pathId: pathId(index),
    graphNodeIds: [fieldId(index % 25), fieldId((index + 1) % 25)],
    graphEdgeIds: [edgeId(index % 27)],
    orderedFields: [
      {
        datasetUrn: datasetUrn(index % 20),
        fieldPath: `field_${index % 25}`,
      },
      {
        datasetUrn: datasetUrn((index + 1) % 20),
        fieldPath: `field_${(index + 1) % 25}`,
      },
    ],
    relationshipIds: [relationshipId(index % 27)],
    targetFieldId: fieldId(index % 25),
    targetField: {
      datasetUrn: datasetUrn(index % 20),
      fieldPath: `field_${index % 25}`,
    },
    targetDatasetUrn: datasetUrn(index % 20),
    depth: 1,
    compatibilityState: "unknown",
    technicalImpactState: "unresolved_impact",
    severityIfRealized:
      index < 3 ? "high" : index < 9 ? "moderate" : "low",
    certainty: "unresolved",
    uncertainRelationshipIds: [relationshipId(0)],
    evidenceReferences: ["evidence-chain"],
    contextAssetIds: [assetId(index % 66)],
    humanExplanation: "Certified path explanation.",
    provenanceReferences: [`path-provenance-${index}`],
  }));
  const fields = Array.from({ length: 25 }, (_, index) => ({
    fieldId: fieldId(index),
    machineKey: `${datasetUrn(index % 20)}|field_${index}`,
    identity: {
      datasetUrn: datasetUrn(index % 20),
      fieldPath: `field_${index}`,
    },
    displayIdentity: `test / dataset_${index % 20} / field_${index}`,
    datasetUrn: datasetUrn(index % 20),
    datasetDisplayName: `dataset_${index % 20}`,
    platform: "test",
    shortestExposureDepth: 1,
    exposureClassification: "transitively_exposed",
    supportingPathIds: [pathId(index)],
    supportingPathCount: 1,
    compatibilityState: "unknown",
    technicalImpactState: "unresolved_impact",
    certainty: "unresolved",
    severityIfRealized:
      index < 3 ? "high" : index < 9 ? "moderate" : "low",
    criticality: "standard_context",
    breadth: "limited",
    sensitivity: "pii",
    reasonCodes: ["source_boundary_unresolved"],
    rootCauseId: "technical-impact-cause-source-rename-semantics",
    evidenceReferences: ["evidence-chain"],
    contextAssetIds: [assetId(index)],
    contextMappingIds: [mappingId(index)],
    humanExplanation: "Certified field explanation.",
    provenanceReferences: [`field-provenance-${index}`],
  }));
  const datasets = Array.from({ length: 20 }, (_, index) => ({
    datasetId: datasetUrn(index),
    datasetUrn: datasetUrn(index),
    displayName: `dataset_${index}`,
    platform: "test",
    exposedFieldCount: 1,
    fieldIds: [fieldId(index)],
    supportingPathIds: [pathId(index)],
    technicalImpactState: "unresolved_impact",
    technicalSummary: "One exposed field remains unresolved.",
    severityIfRealized:
      index < 3 ? "high" : index < 7 ? "moderate" : "low",
    certainty: "unresolved",
    criticality: "standard_context",
    breadth: "limited",
    sensitivity: "pii",
    rootCauseIds: ["technical-impact-cause-source-rename-semantics"],
    contextAssetIds: [assetId(index)],
    contextMappingIds: [mappingId(index)],
    reasonCodes: ["unresolved_technical_boundary"],
    provenanceReferences: [`dataset-provenance-${index}`],
  }));
  const contextAssets = Array.from({ length: 66 }, (_, index) => ({
    contextAssetId: assetId(index),
    group:
      index % 3 === 0
        ? "governance"
        : index % 3 === 1
          ? "operational"
          : "consumer",
    category: index % 3 === 0 ? "tag" : index % 3 === 1 ? "pipeline" : "bi",
    assetType: "tag",
    displayName: `Context ${index}`,
    resolutionState: "resolved",
    connectedDatasetUrns: [datasetUrn(index % 20)],
    connectedFieldIds: [fieldId(index % 25)],
    relationshipCount: 1,
    relationshipIds: [contextRelationshipId(index)],
    mappingIds: [mappingId(index % 257)],
    supportingPathIds: [pathId(index % 48)],
    attributes: [{ name: "source", values: ["certified"] }],
    provenanceReferences: [`context-provenance-${index}`],
  }));
  const contextRelationships = Array.from(
    { length: 211 },
    (_, index) => ({
      relationshipId: contextRelationshipId(index),
      relationshipCategory: "association",
      contextCategory: "tag",
      anchorDatasetUrn: datasetUrn(index % 20),
      anchorFieldId: fieldId(index % 25),
      contextAssetIds: [assetId(index % 66)],
      exposureType: "direct",
    }),
  );
  const contextMappings = Array.from({ length: 257 }, (_, index) => ({
    mappingId: mappingId(index),
    fieldId: fieldId(index % 25),
    datasetUrn: datasetUrn(index % 20),
    contextRelationshipId: contextRelationshipId(index % 211),
    contextAssetId: assetId(index % 66),
    contextCategory: "tag",
    exposureType: "direct",
    linkageState: "resolved",
    supportingPathIds: [pathId(index % 48)],
    provenanceReferences: [`mapping-provenance-${index}`],
  }));

  return {
    certification: {
      status: "certified",
      fingerprint:
        "sha256:3e8444ec904e0ba1c55c5ae22d69edfa8e722310f51ab30fc783b8175a87ac4a",
      certifiedAt: "2026-01-01T00:00:00+00:00",
      checksPassed: 49,
      checkCount: 49,
      scopeStatement: "Certified Phase 4 presentation scope.",
    },
    summary: {
      downstreamFields: 25,
      downstreamDatasets: 20,
      dependencyPaths: 48,
      structuralRelationships: 27,
      contextAssets: 66,
      contextRelationships: 211,
      fieldToContextMappings: 257,
      rootCauses: 1,
      blockingQuestions: 1,
      requiredEvidenceClasses: 4,
      confirmedFailures: 0,
      unresolvedFields: 25,
      compatibilityUnknown: 1,
      compatibilityConditional: 26,
      compatibilityCompatible: 0,
      compatibilityIncompatible: 0,
      fieldSeverityDistribution: {
        critical: 0,
        high: 3,
        moderate: 6,
        low: 16,
        undetermined: 0,
      },
      datasetSeverityDistribution: {
        critical: 0,
        high: 3,
        moderate: 4,
        low: 13,
        undetermined: 0,
      },
      technicalConsequence: "unresolved_impact",
      technicalCertainty: "unresolved",
      decisionCertainty: "high_confidence",
      severityIfRealized: "high",
      breadth: "widespread",
      criticality: "elevated_context",
      sensitivity: "pii",
      explicitBusinessCriticalityPresent: false,
    },
    rootCause: {
      causeId: "technical-impact-cause-source-rename-semantics",
      rootRelationshipId: relationshipId(0),
      proposedSource: {
        datasetUrn: datasetUrn(0),
        fieldPath: "order_amount",
      },
      firstDownstreamDependency: {
        datasetUrn: datasetUrn(1),
        fieldPath: "order_total",
      },
      compatibilityState: "unknown",
      evidenceState: "insufficient",
      technicalConsequence: "unresolved_impact",
      affectedFields: 25,
      affectedDatasets: 20,
      affectedPaths: 48,
      confirmedFailures: 0,
      humanExplanation: "One certified shared technical root cause.",
      steps: [
        {
          stepId: "source-step",
          stage: "field_rename",
          label: "Field rename",
          value: "order_total → order_amount",
          classification: "proposed",
        },
        {
          stepId: "decision-step",
          stage: "decision",
          label: "Certified disposition",
          value: "HOLD FOR REVIEW",
          classification: "decision",
        },
      ],
      provenanceReferences: ["root-provenance"],
    },
    blockingQuestion: {
      questionId: "blocking-question",
      question: "Does the Spark export accept the renamed input?",
      subject: relationshipId(0),
      reason: "Captured transform evidence is absent.",
      rootCauseId: "technical-impact-cause-source-rename-semantics",
      rootRelationshipId: relationshipId(0),
      resolutionState: "unresolved",
      affectedFields: 25,
      affectedDatasets: 20,
      affectedPaths: 48,
      requiredEvidenceIds: [
        "required-spark",
        "required-query",
        "required-rename",
        "required-execution",
      ],
    },
    requiredEvidence: [
      ["required-spark", "spark_transformation_configuration", "Spark configuration"],
      ["required-query", "input_column_reference_query_or_code", "Input query or code"],
      ["required-rename", "explicit_rename_mapping", "Explicit rename mapping"],
      ["required-execution", "validated_execution_result", "Validated execution"],
    ].map(([evidenceId, evidenceClass, label]) => ({
      evidenceId,
      evidenceClass,
      label,
      subject: relationshipId(0),
      reason: "Required to resolve the boundary.",
      state: "required_for_decision_resolution",
      availability: "not_available_required",
      sourceUncertaintyId: "uncertainty-source",
    })),
    evidenceChain: [
      {
        evidenceId: "evidence-chain",
        classification: "observed",
        category: "current_metadata",
        sourceArtifact: "current_metadata_snapshot.json",
        subject: datasetUrn(0),
        claimSupported: "Current field is observed.",
        verificationState: "verified",
        description: "Current source field observed.",
        provenanceReferences: ["snapshot-provenance"],
      },
    ],
    fields,
    datasets,
    contextAssets,
    contextRelationships,
    contextMappings,
    paths,
    relationships,
    decisionExplanation: {
      disposition: "hold_for_review",
      decisionRuleId: "decision-hold-unresolved-material-broad",
      decisionCertainty: "high_confidence",
      technicalCertainty: "unresolved",
      inputs: {
        technicalConsequence: "unresolved_impact",
        impactCertainty: "unresolved",
        severityIfRealized: "high",
        breadth: "widespread",
        criticality: "elevated_context",
      },
      reasons: [
        {
          reasonId: "decision-reason",
          reasonCode: "unresolved_source_compatibility",
          statement: "The source boundary remains unresolved.",
          evidenceIds: ["evidence-chain"],
        },
      ],
      narrative: "Hold until the required compatibility evidence is available.",
      whatWeKnow: ["The dependency cone is certified."],
      whatWeDoNotKnow: ["Whether execution succeeds."],
      confirmedFailureDistinction:
        "HOLD FOR REVIEW is not a confirmed failure. Zero downstream failures are confirmed.",
    },
  };
}
