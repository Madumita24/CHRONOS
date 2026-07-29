"use client";

import {
  AlertTriangle,
  Boxes,
  CircleHelp,
  Database,
  FileSearch,
  GitBranch,
  Link2,
  RefreshCw,
  Route,
  Search,
  ShieldAlert,
  Sparkles,
} from "lucide-react";
import { useEffect, useState } from "react";

import type { GraphSelection } from "@/components/graph/graph-workspace";
import {
  ExplorerContractError,
  ReviewApiError,
  fetchCertifiedExplorer,
} from "@/lib/api";
import type {
  CertifiedImpactExplorer,
  ContextAsset,
  DatasetImpact,
  ExplorerPath,
  ExplorerRelationship,
  FieldImpact,
} from "@/lib/explorer-contract";
import { humanize } from "@/lib/format";

type ExplorerState =
  | { kind: "loading" }
  | { kind: "ready"; explorer: CertifiedImpactExplorer }
  | { kind: "error"; message: string; integrity: boolean };
type ExplorerTab =
  | "fields"
  | "datasets"
  | "paths"
  | "relationships"
  | "context"
  | "evidence"
  | "decision";

export function ImpactEvidenceExplorer({
  reviewId,
  selection,
  selectedMachineKey,
  onSelect,
}: {
  reviewId: string;
  selection: GraphSelection;
  selectedMachineKey: string | null;
  onSelect: (selection: Exclude<GraphSelection, null>) => void;
}) {
  const [state, setState] = useState<ExplorerState>({ kind: "loading" });
  const [attempt, setAttempt] = useState(0);
  const [tab, setTab] = useState<ExplorerTab>("fields");
  const [search, setSearch] = useState("");
  const [fieldPlatform, setFieldPlatform] = useState("all");
  const [fieldExposure, setFieldExposure] = useState("all");
  const [fieldSeverity, setFieldSeverity] = useState("all");
  const [fieldState, setFieldState] = useState("all");
  const [fieldDepth, setFieldDepth] = useState("all");
  const [fieldPaths, setFieldPaths] = useState("all");

  useEffect(() => {
    const controller = new AbortController();
    fetchCertifiedExplorer(reviewId, { signal: controller.signal })
      .then((explorer) => setState({ kind: "ready", explorer }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setState({
          kind: "error",
          integrity:
            error instanceof ExplorerContractError ||
            (error instanceof ReviewApiError &&
              error.code === "certification_integrity_error"),
          message:
            error instanceof Error
              ? error.message
              : "The certified explorer could not be loaded.",
        });
      });
    return () => controller.abort();
  }, [attempt, reviewId]);

  if (state.kind === "loading") {
    return (
      <section className="explorer-section" aria-labelledby="explorer-title">
        <ExplorerHeading />
        <div className="explorer-loading" aria-busy="true">
          <span className="sr-only">Loading certified impact evidence</span>
          <div className="skeleton explorer-root-skeleton" />
          <div className="skeleton explorer-table-skeleton" />
        </div>
      </section>
    );
  }

  if (state.kind === "error") {
    const Icon = state.integrity ? ShieldAlert : AlertTriangle;
    return (
      <section className="explorer-section" aria-labelledby="explorer-title">
        <ExplorerHeading />
        <div className="explorer-error" role="alert">
          <Icon size={22} aria-hidden="true" />
          <div>
            <strong>
              {state.integrity
                ? "Certified explorer integrity check failed"
                : "Certified explorer unavailable"}
            </strong>
            <p>{state.message}</p>
          </div>
          <button
            type="button"
            className="button button-small"
            onClick={() => {
              setState({ kind: "loading" });
              setAttempt((value) => value + 1);
            }}
          >
            <RefreshCw size={14} aria-hidden="true" />
            Retry
          </button>
        </div>
      </section>
    );
  }

  const explorer = state.explorer;
  const selectedField =
    selection?.kind === "node"
      ? explorer.fields.find(
          (item) =>
            item.fieldId === selection.id ||
            item.machineKey === selectedMachineKey,
        ) ?? null
      : null;
  const selectedPath =
    selection?.kind === "path"
      ? explorer.paths.find((item) => item.pathId === selection.id) ?? null
      : null;
  const selectedRelationship =
    selection?.kind === "edge"
      ? explorer.relationships.find(
          (item) => item.graphEdgeId === selection.id,
        ) ?? null
      : null;
  const selectedDataset =
    selection?.kind === "dataset"
      ? explorer.datasets.find((item) => item.datasetId === selection.id) ??
        null
      : null;
  const selectedContext =
    selection?.kind === "context"
      ? explorer.contextAssets.find(
          (item) => item.contextAssetId === selection.id,
        ) ?? null
      : null;

  return (
    <section className="explorer-section" aria-labelledby="explorer-title">
      <ExplorerHeading />
      <RootCauseBanner explorer={explorer} />
      <div className="explorer-metrics" aria-label="Certified explorer totals">
        <ExplorerMetric label="Fields" value={explorer.summary.downstreamFields} />
        <ExplorerMetric
          label="Datasets"
          value={explorer.summary.downstreamDatasets}
        />
        <ExplorerMetric label="Paths" value={explorer.summary.dependencyPaths} />
        <ExplorerMetric
          label="Context assets"
          value={explorer.summary.contextAssets}
        />
        <ExplorerMetric
          label="Confirmed failures"
          value={explorer.summary.confirmedFailures}
          quiet
        />
      </div>
      <div className="explorer-shell">
        <div className="explorer-toolbar">
          <div className="explorer-tabs" role="tablist" aria-label="Explorer view">
            {(
              [
                "fields",
                "datasets",
                "paths",
                "relationships",
                "context",
                "evidence",
                "decision",
              ] as const
            ).map((item) => (
              <button
                key={item}
                type="button"
                role="tab"
                aria-selected={tab === item}
                onClick={() => setTab(item)}
              >
                {humanize(item)}
              </button>
            ))}
          </div>
          <label className="explorer-search">
            <Search size={15} aria-hidden="true" />
            <span className="sr-only">Search loaded explorer records</span>
            <input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder={`Search ${humanize(tab).toLocaleLowerCase()}`}
            />
          </label>
        </div>
        {tab === "fields" && (
          <div className="explorer-filters" aria-label="Field impact filters">
            <ExplorerSelect
              label="Platform"
              value={fieldPlatform}
              values={[...new Set(explorer.fields.map((item) => item.platform))]}
              onChange={setFieldPlatform}
            />
            <ExplorerSelect
              label="Exposure"
              value={fieldExposure}
              values={[
                ...new Set(
                  explorer.fields.map((item) => item.exposureClassification),
                ),
              ]}
              onChange={setFieldExposure}
            />
            <ExplorerSelect
              label="Severity"
              value={fieldSeverity}
              values={["high", "moderate", "low"]}
              onChange={setFieldSeverity}
            />
            <ExplorerSelect
              label="Technical state"
              value={fieldState}
              values={[
                ...new Set(
                  explorer.fields.map((item) => item.technicalImpactState),
                ),
              ]}
              onChange={setFieldState}
            />
            <ExplorerSelect
              label="Depth"
              value={fieldDepth}
              values={[
                ...new Set(
                  explorer.fields.map((item) =>
                    String(item.shortestExposureDepth),
                  ),
                ),
              ]}
              onChange={setFieldDepth}
            />
            <ExplorerSelect
              label="Paths"
              value={fieldPaths}
              values={["single", "multiple"]}
              onChange={setFieldPaths}
            />
          </div>
        )}
        {(tab === "fields" || tab === "datasets") && (
          <SeverityDistribution
            label={`${humanize(tab.slice(0, -1))} severity if realized`}
            distribution={
              tab === "fields"
                ? explorer.summary.fieldSeverityDistribution
                : explorer.summary.datasetSeverityDistribution
            }
          />
        )}
        <div className="explorer-body">
          <ExplorerList
            explorer={explorer}
            tab={tab}
            search={search}
            selection={selection}
            onSelect={onSelect}
            fieldFilters={{
              platform: fieldPlatform,
              exposure: fieldExposure,
              severity: fieldSeverity,
              state: fieldState,
              depth: fieldDepth,
              paths: fieldPaths,
            }}
          />
          <ExplorerDetail
            explorer={explorer}
            field={selectedField}
            path={selectedPath}
            relationship={selectedRelationship}
            dataset={selectedDataset}
            contextAsset={selectedContext}
          />
        </div>
      </div>
    </section>
  );
}

function ExplorerSelect({
  label,
  value,
  values,
  onChange,
}: {
  label: string;
  value: string;
  values: string[];
  onChange: (value: string) => void;
}) {
  return (
    <label>
      <span>{label}</span>
      <select
        aria-label={`Filter fields by ${label.toLocaleLowerCase()}`}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="all">All</option>
        {values.sort().map((item) => (
          <option key={item} value={item}>
            {humanize(item)}
          </option>
        ))}
      </select>
    </label>
  );
}

function SeverityDistribution({
  label,
  distribution,
}: {
  label: string;
  distribution: {
    critical: number;
    high: number;
    moderate: number;
    low: number;
    undetermined: number;
  };
}) {
  return (
    <div className="severity-distribution" aria-label={label}>
      <strong>{label}</strong>
      {Object.entries(distribution).map(([key, value]) => (
        <span key={key}>
          {humanize(key)} <b>{value}</b>
        </span>
      ))}
    </div>
  );
}

function ExplorerHeading() {
  return (
    <div className="section-heading explorer-heading">
      <div>
        <p className="eyebrow">Impact &amp; evidence explorer</p>
        <h2 id="explorer-title">Show me why</h2>
      </div>
      <p>
        Inspect certified impact, context, and evidence records. Selecting a
        field, path, or relationship coordinates with the future graph above.
      </p>
    </div>
  );
}

function RootCauseBanner({
  explorer,
}: {
  explorer: CertifiedImpactExplorer;
}) {
  const root = explorer.rootCause;
  return (
    <article className="root-cause-banner">
      <div className="root-cause-mark" aria-hidden="true">
        <GitBranch size={21} />
      </div>
      <div className="root-cause-copy">
        <div className="root-cause-title">
          <div>
            <p className="eyebrow">One shared technical root cause</p>
            <h3>
              {root.proposedSource.fieldPath}
              <span aria-hidden="true"> → </span>
              {root.firstDownstreamDependency.fieldPath}
            </h3>
          </div>
          <span className="explorer-state unresolved">
            Unknown · evidence insufficient
          </span>
        </div>
        <p>{root.humanExplanation}</p>
        <div className="root-cause-flow" aria-label="Certified causal chain">
          {root.steps.map((step) => (
            <div key={step.stepId} data-classification={step.classification}>
              <span>{step.label}</span>
              <strong>{step.value}</strong>
            </div>
          ))}
        </div>
        <div className="blocking-question-inline">
          <CircleHelp size={18} aria-hidden="true" />
          <div>
            <span>Blocking question</span>
            <strong>{explorer.blockingQuestion.question}</strong>
          </div>
        </div>
        <div className="required-evidence-inline" aria-label="Required evidence">
          {explorer.requiredEvidence.map((item) => (
            <span key={item.evidenceId}>
              <FileSearch size={13} aria-hidden="true" />
              {item.label}
            </span>
          ))}
        </div>
      </div>
    </article>
  );
}

function ExplorerMetric({
  label,
  value,
  quiet = false,
}: {
  label: string;
  value: number;
  quiet?: boolean;
}) {
  return (
    <div className={quiet ? "quiet" : ""}>
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  );
}

function ExplorerList({
  explorer,
  tab,
  search,
  selection,
  onSelect,
  fieldFilters,
}: {
  explorer: CertifiedImpactExplorer;
  tab: ExplorerTab;
  search: string;
  selection: GraphSelection;
  onSelect: (selection: Exclude<GraphSelection, null>) => void;
  fieldFilters: {
    platform: string;
    exposure: string;
    severity: string;
    state: string;
    depth: string;
    paths: string;
  };
}) {
  const query = search.trim().toLocaleLowerCase();
  const includes = (...values: string[]) =>
    !query || values.some((value) => value.toLocaleLowerCase().includes(query));

  if (tab === "fields") {
    const records = explorer.fields.filter((item) =>
      includes(
        item.displayIdentity,
        item.platform,
        item.severityIfRealized,
        item.technicalImpactState,
      ) &&
      (fieldFilters.platform === "all" ||
        item.platform === fieldFilters.platform) &&
      (fieldFilters.exposure === "all" ||
        item.exposureClassification === fieldFilters.exposure) &&
      (fieldFilters.severity === "all" ||
        item.severityIfRealized === fieldFilters.severity) &&
      (fieldFilters.state === "all" ||
        item.technicalImpactState === fieldFilters.state) &&
      (fieldFilters.depth === "all" ||
        String(item.shortestExposureDepth) === fieldFilters.depth) &&
      (fieldFilters.paths === "all" ||
        (fieldFilters.paths === "single"
          ? item.supportingPathCount === 1
          : item.supportingPathCount > 1)),
    );
    return (
      <RecordList
        label="Downstream field impacts"
        empty={records.length === 0}
        icon={FileSearch}
      >
        {records.map((item) => (
          <FieldRow
            key={item.fieldId}
            item={item}
            selected={selection?.kind === "node" && selection.id === item.fieldId}
            onClick={() => onSelect({ kind: "node", id: item.fieldId })}
          />
        ))}
      </RecordList>
    );
  }
  if (tab === "datasets") {
    const records = explorer.datasets.filter((item) =>
      includes(
        item.displayName,
        item.platform,
        item.severityIfRealized,
        item.technicalImpactState,
      ),
    );
    return (
      <RecordList
        label="Downstream dataset impacts"
        empty={records.length === 0}
        icon={Database}
      >
        {records.map((item) => (
          <DatasetRow
            key={item.datasetId}
            item={item}
            selected={
              selection?.kind === "dataset" &&
              selection.id === item.datasetId
            }
            onClick={() => onSelect({ kind: "dataset", id: item.datasetId })}
          />
        ))}
      </RecordList>
    );
  }
  if (tab === "paths") {
    const records = explorer.paths.filter((item) =>
      includes(
        item.pathId,
        item.targetField.fieldPath,
        item.targetDatasetUrn,
        item.severityIfRealized,
      ),
    );
    return (
      <RecordList
        label="Certified dependency paths"
        empty={records.length === 0}
        icon={Route}
      >
        {records.map((item) => (
          <PathRow
            key={item.pathId}
            item={item}
            selected={selection?.kind === "path" && selection.id === item.pathId}
            onClick={() => onSelect({ kind: "path", id: item.pathId })}
          />
        ))}
      </RecordList>
    );
  }
  if (tab === "relationships") {
    const records = explorer.relationships.filter((item) =>
      includes(
        item.relationshipId,
        item.upstream.fieldPath,
        item.downstream.fieldPath,
        item.compatibilityState,
      ),
    );
    return (
      <RecordList
        label="Certified structural relationships"
        empty={records.length === 0}
        icon={Link2}
      >
        {records.map((item) => (
          <RelationshipRow
            key={item.relationshipId}
            item={item}
            selected={
              selection?.kind === "edge" &&
              selection.id === item.graphEdgeId
            }
            onClick={() =>
              onSelect({ kind: "edge", id: item.graphEdgeId })
            }
          />
        ))}
      </RecordList>
    );
  }
  if (tab === "context") {
    const records = explorer.contextAssets.filter((item) =>
      includes(item.displayName, item.group, item.category, item.assetType),
    );
    return (
      <RecordList
        label="Certified context assets"
        empty={records.length === 0}
        icon={Boxes}
      >
        {(["governance", "operational", "consumer"] as const).map((group) => {
          const grouped = records.filter((item) => item.group === group);
          if (grouped.length === 0) return null;
          return (
            <div className="context-group" key={group}>
              <h3>{humanize(group)}</h3>
              {grouped.map((item) => (
                <ContextRow
                  key={item.contextAssetId}
                  item={item}
                  selected={
                    selection?.kind === "context" &&
                    selection.id === item.contextAssetId
                  }
                  onClick={() =>
                    onSelect({
                      kind: "context",
                      id: item.contextAssetId,
                    })
                  }
                />
              ))}
            </div>
          );
        })}
      </RecordList>
    );
  }
  if (tab === "evidence") {
    const records = explorer.evidenceChain.filter((item) =>
      includes(
        item.description,
        item.category,
        item.classification,
        item.sourceArtifact,
      ),
    );
    return (
      <RecordList
        label="Certified evidence chain"
        empty={records.length === 0}
        icon={Sparkles}
      >
        {records.map((item) => (
          <div className="explorer-record evidence-record" key={item.evidenceId}>
            <span className={`evidence-class ${item.classification}`}>
              {humanize(item.classification)}
            </span>
            <strong>{item.description}</strong>
            <small>
              {humanize(item.verificationState)} · {item.sourceArtifact}
            </small>
          </div>
        ))}
      </RecordList>
    );
  }

  const decision = explorer.decisionExplanation;
  const reasons = decision.reasons.filter((item) =>
    includes(item.statement, item.reasonCode),
  );
  return (
    <RecordList
      label="Certified decision explanation"
      empty={reasons.length === 0}
      icon={ShieldAlert}
    >
      <div className="decision-record">
        <span className="explorer-state hold">Hold for review</span>
        <p>{decision.narrative}</p>
        {reasons.map((reason) => (
          <div className="explorer-record" key={reason.reasonId}>
            <strong>{humanize(reason.reasonCode)}</strong>
            <small>{reason.statement}</small>
          </div>
        ))}
      </div>
    </RecordList>
  );
}

function RecordList({
  label,
  empty,
  icon: Icon,
  children,
}: {
  label: string;
  empty: boolean;
  icon: typeof FileSearch;
  children: React.ReactNode;
}) {
  return (
    <div className="explorer-list" aria-label={label}>
      {empty ? (
        <div className="explorer-empty">
          <Search size={22} aria-hidden="true" />
          <strong>No loaded records match</strong>
          <p>Change or clear the explorer search.</p>
        </div>
      ) : (
        <>
          <div className="explorer-list-label">
            <Icon size={15} aria-hidden="true" />
            <span>{label}</span>
          </div>
          {children}
        </>
      )}
    </div>
  );
}

function FieldRow({
  item,
  selected,
  onClick,
}: {
  item: FieldImpact;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      className="explorer-record selectable"
      aria-pressed={selected}
      onClick={onClick}
    >
      <span className={`severity-dot ${item.severityIfRealized}`} />
      <span>
        <strong>{item.identity.fieldPath}</strong>
        <small>{item.datasetDisplayName}</small>
      </span>
      <span className="record-meta">
        <em>{humanize(item.severityIfRealized)}</em>
        <small>depth {item.shortestExposureDepth}</small>
      </span>
    </button>
  );
}

function DatasetRow({
  item,
  selected,
  onClick,
}: {
  item: DatasetImpact;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      className="explorer-record selectable"
      aria-pressed={selected}
      onClick={onClick}
    >
      <Database size={16} aria-hidden="true" />
      <span>
        <strong>{item.displayName}</strong>
        <small>{item.platform}</small>
      </span>
      <span className="record-meta">
        <em>{humanize(item.severityIfRealized)}</em>
        <small>{item.exposedFieldCount} field(s)</small>
      </span>
    </button>
  );
}

function PathRow({
  item,
  selected,
  onClick,
}: {
  item: ExplorerPath;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      className="explorer-record selectable"
      aria-pressed={selected}
      onClick={onClick}
    >
      <Route size={16} aria-hidden="true" />
      <span>
        <strong>{item.targetField.fieldPath}</strong>
        <small>{item.pathId}</small>
      </span>
      <span className="record-meta">
        <em>{item.depth} hops</em>
        <small>{humanize(item.compatibilityState)}</small>
      </span>
    </button>
  );
}

function RelationshipRow({
  item,
  selected,
  onClick,
}: {
  item: ExplorerRelationship;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      className="explorer-record selectable"
      aria-pressed={selected}
      onClick={onClick}
    >
      <Link2 size={16} aria-hidden="true" />
      <span>
        <strong>
          {item.upstream.fieldPath} → {item.downstream.fieldPath}
        </strong>
        <small>{item.relationshipId}</small>
      </span>
      <span className="record-meta">
        <em>{humanize(item.compatibilityState)}</em>
        <small>{item.pathParticipationCount} path(s)</small>
      </span>
    </button>
  );
}

function ContextRow({
  item,
  selected,
  onClick,
}: {
  item: ContextAsset;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      className="explorer-record selectable"
      onClick={onClick}
      aria-pressed={selected}
    >
      <Boxes size={16} aria-hidden="true" />
      <span>
        <strong>{item.displayName}</strong>
        <small>
          {humanize(item.group)} · {humanize(item.category)}
        </small>
      </span>
      <span className="record-meta">
        <em>{item.connectedFieldIds.length} fields</em>
        <small>{item.relationshipCount} links</small>
      </span>
    </button>
  );
}

function ExplorerDetail({
  explorer,
  field,
  path,
  relationship,
  dataset,
  contextAsset,
}: {
  explorer: CertifiedImpactExplorer;
  field: FieldImpact | null;
  path: ExplorerPath | null;
  relationship: ExplorerRelationship | null;
  dataset: DatasetImpact | null;
  contextAsset: ContextAsset | null;
}) {
  const selected = field ?? path ?? relationship ?? dataset ?? contextAsset;
  return (
    <aside className="explorer-detail" aria-label="Impact evidence detail">
      <p className="eyebrow">
        {field
          ? "Field impact"
          : path
            ? "Path evidence"
          : relationship
              ? "Relationship evidence"
              : dataset
                ? "Dataset impact"
                : contextAsset
                  ? "Context detail"
              : "Certified interpretation"}
      </p>
      {!selected && (
        <>
          <h3>Unresolved is not failed</h3>
          <p>
            {explorer.decisionExplanation.confirmedFailureDistinction}
          </p>
          <DetailRow
            label="Technical state"
            value={explorer.summary.technicalConsequence}
          />
          <DetailRow
            label="Severity if realized"
            value={explorer.summary.severityIfRealized}
          />
          <DetailRow label="Breadth" value={explorer.summary.breadth} />
          <DetailRow
            label="Business criticality"
            value="Not explicitly present"
          />
        </>
      )}
      {field && (
        <>
          <h3>{field.identity.fieldPath}</h3>
          <code>{field.datasetUrn}</code>
          <p>{field.humanExplanation}</p>
          <DetailRow label="Platform" value={field.platform} />
          <DetailRow label="Exposure" value={field.exposureClassification} />
          <DetailRow
            label="Technical state"
            value={field.technicalImpactState}
          />
          <DetailRow label="Severity if realized" value={field.severityIfRealized} />
          <DetailRow label="Certainty" value={field.certainty} />
          <DetailRow label="Breadth" value={field.breadth} />
          <DetailRow label="Criticality" value={field.criticality} />
          <DetailRow label="Sensitivity" value={field.sensitivity} />
          <DetailRow
            label="Supporting paths"
            value={String(field.supportingPathCount)}
          />
        </>
      )}
      {path && (
        <>
          <h3>{path.targetField.fieldPath}</h3>
          <code>{path.pathId}</code>
          <p>{path.humanExplanation}</p>
          <div className="detail-chain">
            <span>{path.orderedFields[0].fieldPath}</span>
            <b>root unresolved edge</b>
            <span>{path.targetField.fieldPath}</span>
          </div>
          <DetailRow label="Depth" value={String(path.depth)} />
          <DetailRow label="Compatibility" value={path.compatibilityState} />
          <DetailRow
            label="Uncertain relationships"
            value={String(path.uncertainRelationshipIds.length)}
          />
          <DetailRow
            label="Ordered relationships"
            value={String(path.relationshipIds.length)}
          />
          <DetailRow
            label="Context assets"
            value={String(path.contextAssetIds.length)}
          />
        </>
      )}
      {relationship && (
        <>
          <h3>
            {relationship.upstream.fieldPath} →{" "}
            {relationship.downstream.fieldPath}
          </h3>
          <code>{relationship.relationshipId}</code>
          <p>{relationship.humanExplanation}</p>
          <DetailRow
            label="Compatibility"
            value={relationship.compatibilityState}
          />
          <DetailRow
            label="Technical impact"
            value={relationship.technicalImpactState}
          />
          <DetailRow
            label="Evidence strength"
            value={relationship.evidenceStrength}
          />
          <DetailRow
            label="Path participation"
            value={String(relationship.pathParticipationCount)}
          />
        </>
      )}
      {dataset && (
        <>
          <h3>{dataset.displayName}</h3>
          <code>{dataset.datasetUrn}</code>
          <p>{dataset.technicalSummary}</p>
          <DetailRow
            label="Exposed fields"
            value={String(dataset.exposedFieldCount)}
          />
          <DetailRow
            label="Supporting paths"
            value={String(dataset.supportingPathIds.length)}
          />
          <DetailRow
            label="Connected context"
            value={String(dataset.contextAssetIds.length)}
          />
          <DetailRow
            label="Technical state"
            value={dataset.technicalImpactState}
          />
          <DetailRow
            label="Severity if realized"
            value={dataset.severityIfRealized}
          />
          <DetailRow label="Certainty" value={dataset.certainty} />
        </>
      )}
      {contextAsset && (
        <>
          <h3>{contextAsset.displayName}</h3>
          <code>{contextAsset.contextAssetId}</code>
          <p>
            Certified {humanize(contextAsset.group)} context. Connectivity is
            not a severity or failure claim.
          </p>
          <DetailRow label="Category" value={contextAsset.category} />
          <DetailRow
            label="Connected datasets"
            value={String(contextAsset.connectedDatasetUrns.length)}
          />
          <DetailRow
            label="Connected fields"
            value={String(contextAsset.connectedFieldIds.length)}
          />
          <DetailRow
            label="Relationship count"
            value={String(contextAsset.relationshipCount)}
          />
          <DetailRow
            label="Mapping references"
            value={String(contextAsset.mappingIds.length)}
          />
          <DetailRow
            label="Certified provenance"
            value={String(contextAsset.provenanceReferences.length)}
          />
        </>
      )}
    </aside>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="explorer-detail-row">
      <span>{label}</span>
      <strong>{humanize(value)}</strong>
    </div>
  );
}
