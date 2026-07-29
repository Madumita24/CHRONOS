"use client";

import {
  Background,
  Controls,
  MarkerType,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  type EdgeMouseHandler,
  type NodeMouseHandler,
  type ReactFlowInstance,
} from "@xyflow/react";
import {
  AlertTriangle,
  GitCompareArrows,
  Maximize2,
  Network,
  RefreshCw,
  Search,
  ShieldAlert,
  Waypoints,
  X,
} from "lucide-react";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";

import {
  GraphLineageEdge,
  type LineageFlowEdge,
} from "@/components/graph/graph-edge";
import {
  GraphFieldNode,
  type FieldFlowNode,
} from "@/components/graph/graph-node";
import {
  GraphContractError,
  ReviewApiError,
  fetchCertifiedGraph,
} from "@/lib/api";
import { humanize } from "@/lib/format";
import {
  type CertifiedGraphReview,
  type GraphEdgeRecord,
  type GraphNodeRecord,
  type GraphPathRecord,
  type GraphProjection,
} from "@/lib/graph-contract";
import { layoutGraph } from "@/lib/graph-layout";

export type GraphMode = "current" | "future" | "diff";
export type GraphSelection =
  | { kind: "node"; id: string; machineKey?: string }
  | { kind: "edge"; id: string }
  | { kind: "path"; id: string }
  | { kind: "dataset"; id: string }
  | { kind: "context"; id: string }
  | null;
type GraphState =
  | { kind: "loading" }
  | { kind: "ready"; graph: CertifiedGraphReview }
  | { kind: "error"; message: string; integrity: boolean };

const nodeTypes = { field: GraphFieldNode };
const edgeTypes = { lineage: GraphLineageEdge };

export function GraphWorkspace({
  reviewId,
  selection,
  onSelectionChange,
  mode,
  onModeChange,
  onRootBoundaryReady,
}: {
  reviewId: string;
  selection?: GraphSelection;
  onSelectionChange?: (selection: GraphSelection) => void;
  mode?: GraphMode;
  onModeChange?: (mode: GraphMode) => void;
  onRootBoundaryReady?: (edgeId: string) => void;
}) {
  return (
    <ReactFlowProvider>
      <CertifiedGraphWorkspace
        reviewId={reviewId}
        controlledSelection={selection}
        onSelectionChange={onSelectionChange}
        controlledMode={mode}
        onModeChange={onModeChange}
        onRootBoundaryReady={onRootBoundaryReady}
      />
    </ReactFlowProvider>
  );
}

function CertifiedGraphWorkspace({
  reviewId,
  controlledSelection,
  onSelectionChange,
  controlledMode,
  onModeChange,
  onRootBoundaryReady,
}: {
  reviewId: string;
  controlledSelection?: GraphSelection;
  onSelectionChange?: (selection: GraphSelection) => void;
  controlledMode?: GraphMode;
  onModeChange?: (mode: GraphMode) => void;
  onRootBoundaryReady?: (edgeId: string) => void;
}) {
  const [state, setState] = useState<GraphState>({ kind: "loading" });
  const [attempt, setAttempt] = useState(0);
  const [internalMode, setInternalMode] = useState<GraphMode>("future");
  const [internalSelection, setInternalSelection] =
    useState<GraphSelection>(null);
  const [search, setSearch] = useState("");
  const [platform, setPlatform] = useState("all");
  const [compatibility, setCompatibility] = useState("all");
  const flowRef = useRef<
    ReactFlowInstance<FieldFlowNode, LineageFlowEdge> | null
  >(null);
  const mode = controlledMode ?? internalMode;
  const selection =
    controlledSelection === undefined
      ? internalSelection
      : controlledSelection;
  const setMode = (nextMode: GraphMode) => {
    if (onModeChange) onModeChange(nextMode);
    else setInternalMode(nextMode);
  };
  const setSelection = (nextSelection: GraphSelection) => {
    if (onSelectionChange) onSelectionChange(nextSelection);
    else setInternalSelection(nextSelection);
  };

  useEffect(() => {
    const controller = new AbortController();
    fetchCertifiedGraph(reviewId, { signal: controller.signal })
      .then((graph) => setState({ kind: "ready", graph }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        setState({
          kind: "error",
          integrity:
            error instanceof GraphContractError ||
            (error instanceof ReviewApiError &&
              error.code === "certification_integrity_error"),
          message:
            error instanceof Error
              ? error.message
              : "The certified graph could not be loaded.",
        });
      });
    return () => controller.abort();
  }, [attempt, reviewId]);

  useEffect(() => {
    if (state.kind !== "ready" || !onRootBoundaryReady) return;
    const root = state.graph.futureGraph.edges.find(
      (edge) => edge.isRootUncertainty,
    );
    if (root) onRootBoundaryReady(root.id);
  }, [onRootBoundaryReady, state]);

  const retry = useCallback(() => {
    setState({ kind: "loading" });
    setAttempt((value) => value + 1);
  }, []);

  if (state.kind === "loading") {
    return (
      <section className="graph-section" aria-labelledby="graph-title">
        <GraphSectionHeading />
        <div className="graph-loading" aria-busy="true">
          <span className="sr-only">Loading certified lineage graph</span>
          <div className="skeleton graph-toolbar-skeleton" />
          <div className="skeleton graph-canvas-skeleton" />
        </div>
      </section>
    );
  }

  if (state.kind === "error") {
    const Icon = state.integrity ? ShieldAlert : AlertTriangle;
    return (
      <section className="graph-section" aria-labelledby="graph-title">
        <GraphSectionHeading />
        <div
          className={`graph-error ${state.integrity ? "integrity" : ""}`}
          role="alert"
        >
          <Icon size={24} aria-hidden="true" />
          <div>
            <strong>
              {state.integrity
                ? "Certified graph integrity check failed"
                : "Certified graph unavailable"}
            </strong>
            <p>{state.message}</p>
          </div>
          <button className="button button-small" type="button" onClick={retry}>
            <RefreshCw size={14} aria-hidden="true" />
            Retry
          </button>
        </div>
      </section>
    );
  }

  const graph = state.graph;
  const projection = projectionForMode(graph, mode);
  const selectedPath =
    selection?.kind === "path"
      ? graph.supportingPaths.find((path) => path.pathId === selection.id) ??
        null
      : null;
  const highlightedNodeIds = new Set(
    selectedPath ? pathNodeIds(selectedPath, mode) : [],
  );
  const highlightedEdgeIds = new Set(
    selectedPath ? pathEdgeIds(selectedPath, mode) : [],
  );
  const normalizedSearch = search.trim().toLocaleLowerCase();
  const platformOptions = [
    ...new Set(projection.nodes.map((node) => node.platform)),
  ].sort();

  const nodePasses = (node: GraphNodeRecord) =>
    (platform === "all" || node.platform === platform) &&
    (!normalizedSearch ||
      [
        node.fieldPath,
        node.label,
        node.secondaryLabel,
        node.datasetUrn,
        node.platform,
      ].some((value) => value.toLocaleLowerCase().includes(normalizedSearch)));

  const baseNodes = projection.nodes.filter(nodePasses);
  const baseNodeIds = new Set(baseNodes.map((node) => node.id));
  const filteredEdges = projection.edges.filter(
    (edge) =>
      baseNodeIds.has(edge.source) &&
      baseNodeIds.has(edge.target) &&
      (compatibility === "all" ||
        edge.compatibilityState === compatibility),
  );
  const visibleNodeIds =
    compatibility === "all"
      ? baseNodeIds
      : new Set(filteredEdges.flatMap((edge) => [edge.source, edge.target]));
  const visibleNodes = baseNodes.filter((node) => visibleNodeIds.has(node.id));
  const hasPathHighlight = selectedPath !== null;
  const flowEdges: LineageFlowEdge[] = filteredEdges.map((edge) => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    type: "lineage",
    ariaLabel: edgeAriaLabel(edge),
    markerEnd: { type: MarkerType.ArrowClosed, width: 15, height: 15 },
    data: {
      ...edge,
      highlighted:
        highlightedEdgeIds.has(edge.id) ||
        (selection?.kind === "edge" && selection.id === edge.id),
      dimmed: hasPathHighlight && !highlightedEdgeIds.has(edge.id),
    },
  }));
  const rawNodes: FieldFlowNode[] = visibleNodes.map((node) => ({
    id: node.id,
    type: "field",
    position: { x: 0, y: 0 },
    ariaLabel: `${node.fieldPath}, ${node.platform}, depth ${node.depth}`,
    data: {
      ...node,
      highlighted:
        highlightedNodeIds.has(node.id) ||
        (selection?.kind === "node" && selection.id === node.id),
      dimmed: hasPathHighlight && !highlightedNodeIds.has(node.id),
    },
  }));
  const flowNodes = layoutGraph(rawNodes, flowEdges);

  const selectNode: NodeMouseHandler<FieldFlowNode> = (_event, node) =>
    setSelection({
      kind: "node",
      id: node.id,
      machineKey: node.data.machineKey,
    });
  const selectEdge: EdgeMouseHandler<LineageFlowEdge> = (_event, edge) =>
    setSelection({ kind: "edge", id: edge.id });

  return (
      <section
        id="graph"
        className="graph-section workflow-anchor"
        aria-labelledby="graph-title"
      >
      <GraphSectionHeading />
      <div className="graph-shell">
        <GraphToolbar
          mode={mode}
          setMode={(nextMode) => {
            setMode(nextMode);
            setSelection(null);
          }}
          search={search}
          setSearch={setSearch}
          platform={platform}
          setPlatform={setPlatform}
          platforms={platformOptions}
          compatibility={compatibility}
          setCompatibility={setCompatibility}
          onFit={() => flowRef.current?.fitView({ padding: 0.16 })}
          onClear={() => {
            setSelection(null);
            setSearch("");
            setPlatform("all");
            setCompatibility("all");
          }}
        />
        <div className="graph-body">
          <div className="graph-canvas" data-testid={`graph-mode-${mode}`}>
            {flowNodes.length === 0 ? (
              <div className="graph-empty">
                <Search size={24} aria-hidden="true" />
                <strong>No fields match these display filters</strong>
                <p>The certified graph is unchanged. Clear filters to restore it.</p>
              </div>
            ) : (
              <ReactFlow<FieldFlowNode, LineageFlowEdge>
                nodes={flowNodes}
                edges={flowEdges}
                nodeTypes={nodeTypes}
                edgeTypes={edgeTypes}
                onNodeClick={selectNode}
                onEdgeClick={selectEdge}
                onPaneClick={() => setSelection(null)}
                onInit={(instance) => {
                  flowRef.current = instance;
                }}
                fitView
                fitViewOptions={{ padding: 0.16 }}
                minZoom={0.18}
                maxZoom={1.7}
                nodesDraggable={false}
                nodesConnectable={false}
                elementsSelectable
                nodesFocusable
                edgesFocusable
                proOptions={{ hideAttribution: true }}
              >
                <Background gap={22} size={1} color="#dce4ea" />
                <MiniMap
                  pannable
                  zoomable
                  nodeStrokeWidth={2}
                  ariaLabel="Certified graph minimap"
                />
                <Controls
                  showInteractive={false}
                  aria-label="Graph zoom and fit controls"
                />
              </ReactFlow>
            )}
          </div>
          <GraphInspector
            graph={graph}
            projection={projection}
            selection={selection}
            mode={mode}
            onSelectPath={(id) => setSelection({ kind: "path", id })}
            onSelectEdge={(id) => setSelection({ kind: "edge", id })}
            onClear={() => setSelection(null)}
          />
        </div>
        <GraphFooter
          graph={graph}
          mode={mode}
          visibleNodes={flowNodes.length}
          visibleEdges={flowEdges.length}
          onSelectPath={(id) => setSelection({ kind: "path", id })}
          selectedPathId={selectedPath?.pathId ?? null}
        />
      </div>
      </section>
  );
}

function GraphSectionHeading() {
  return (
    <div className="section-heading graph-heading">
      <div>
        <p className="eyebrow">Certified field lineage</p>
        <h2 id="graph-title">Current state and counterfactual future</h2>
      </div>
      <p>
        A read-only projection of certified Phase 4 artifacts. No lineage or
        compatibility is recomputed in this browser.
      </p>
    </div>
  );
}

function GraphToolbar({
  mode,
  setMode,
  search,
  setSearch,
  platform,
  setPlatform,
  platforms,
  compatibility,
  setCompatibility,
  onFit,
  onClear,
}: {
  mode: GraphMode;
  setMode: (mode: GraphMode) => void;
  search: string;
  setSearch: (value: string) => void;
  platform: string;
  setPlatform: (value: string) => void;
  platforms: string[];
  compatibility: string;
  setCompatibility: (value: string) => void;
  onFit: () => void;
  onClear: () => void;
}) {
  return (
    <div className="graph-toolbar" aria-label="Graph display controls">
      <div className="graph-mode-switcher" aria-label="Graph view mode">
        {(["current", "future", "diff"] as const).map((item) => (
          <button
            key={item}
            type="button"
            aria-pressed={mode === item}
            onClick={() => setMode(item)}
          >
            {item === "diff" && (
              <GitCompareArrows size={14} aria-hidden="true" />
            )}
            {humanize(item)}
          </button>
        ))}
      </div>
      <label className="graph-search">
        <span className="sr-only">Search graph fields</span>
        <Search size={15} aria-hidden="true" />
        <input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search fields or datasets"
          type="search"
        />
      </label>
      <label className="graph-select">
        <span>Platform</span>
        <select
          aria-label="Filter by platform"
          value={platform}
          onChange={(event) => setPlatform(event.target.value)}
        >
          <option value="all">All</option>
          {platforms.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
      </label>
      <label className="graph-select">
        <span>Compatibility</span>
        <select
          aria-label="Filter by compatibility"
          value={compatibility}
          onChange={(event) => setCompatibility(event.target.value)}
        >
          <option value="all">All</option>
          <option value="unknown">Unknown</option>
          <option value="conditionally_compatible">Conditional</option>
          <option value="incompatible">Incompatible</option>
          <option value="compatible">Compatible</option>
        </select>
      </label>
      <button
        className="graph-icon-button"
        type="button"
        title="Fit graph to view"
        aria-label="Fit graph to view"
        onClick={onFit}
      >
        <Maximize2 size={16} />
      </button>
      <button
        className="graph-icon-button"
        type="button"
        title="Clear selection and filters"
        aria-label="Clear selection and filters"
        onClick={onClear}
      >
        <X size={16} />
      </button>
    </div>
  );
}

function GraphInspector({
  graph,
  projection,
  selection,
  mode,
  onSelectPath,
  onSelectEdge,
  onClear,
}: {
  graph: CertifiedGraphReview;
  projection: GraphProjection;
  selection: GraphSelection;
  mode: GraphMode;
  onSelectPath: (id: string) => void;
  onSelectEdge: (id: string) => void;
  onClear: () => void;
}) {
  const node =
    selection?.kind === "node"
      ? projection.nodes.find((item) => item.id === selection.id) ?? null
      : null;
  const edge =
    selection?.kind === "edge"
      ? projection.edges.find((item) => item.id === selection.id) ?? null
      : null;
  const path =
    selection?.kind === "path"
      ? graph.supportingPaths.find((item) => item.pathId === selection.id) ??
        null
      : null;

  return (
    <aside className="graph-inspector" aria-label="Graph selection inspector">
      <div className="inspector-title">
        <div>
          <span className="eyebrow">Inspector</span>
          <strong>
            {node
              ? "Field"
              : edge
                ? "Relationship"
                : path
                  ? "Certified path"
                  : "Graph summary"}
          </strong>
        </div>
        {selection && (
          <button type="button" onClick={onClear} aria-label="Close inspector">
            <X size={15} />
          </button>
        )}
      </div>
      {node && <NodeDetails node={node} onSelectPath={onSelectPath} />}
      {edge && (
        <EdgeDetails
          edge={edge}
          graph={graph}
          onSelectPath={onSelectPath}
        />
      )}
      {path && <PathDetails path={path} mode={mode} />}
      {!node && !edge && !path && (
        <GraphSummary graph={graph} onSelectEdge={onSelectEdge} />
      )}
    </aside>
  );
}

function NodeDetails({
  node,
  onSelectPath,
}: {
  node: GraphNodeRecord;
  onSelectPath: (id: string) => void;
}) {
  return (
    <div className="inspector-content">
      <InspectorIdentity
        platform={node.platform}
        field={node.fieldPath}
        dataset={node.secondaryLabel}
      />
      <InspectorRow label="Graph state" value={humanize(node.graphState)} />
      <InspectorRow label="Depth" value={String(node.depth)} />
      <InspectorRow label="Supporting paths" value={String(node.pathCount)} />
      {node.compatibilityState && (
        <InspectorRow
          label="Compatibility"
          value={humanize(node.compatibilityState)}
          tone={node.compatibilityState}
        />
      )}
      {node.supportingPathIds.length > 0 && (
        <PathButtons
          ids={node.supportingPathIds}
          onSelectPath={onSelectPath}
        />
      )}
    </div>
  );
}

function EdgeDetails({
  edge,
  graph,
  onSelectPath,
}: {
  edge: GraphEdgeRecord;
  graph: CertifiedGraphReview;
  onSelectPath: (id: string) => void;
}) {
  const root = edge.isRootUncertainty ? graph.rootUncertainty : null;
  return (
    <div className="inspector-content">
      <div className="relationship-pair">
        <InspectorIdentity
          platform="Upstream field"
          field={edge.upstream.fieldPath}
          dataset={edge.upstream.datasetUrn}
        />
        <span aria-hidden="true">→</span>
        <InspectorIdentity
          platform="Downstream field"
          field={edge.downstream.fieldPath}
          dataset={edge.downstream.datasetUrn}
        />
      </div>
      <InspectorRow
        label="Compatibility"
        value={humanize(edge.compatibilityState ?? "not assessed")}
        tone={edge.compatibilityState ?? undefined}
      />
      <InspectorRow
        label="Technical impact"
        value={humanize(edge.technicalImpactState ?? "not assessed")}
      />
      <InspectorRow
        label="Path participation"
        value={String(edge.pathParticipationCount)}
      />
      {edge.explanation && <p className="inspector-explanation">{edge.explanation}</p>}
      {root && (
        <div className="root-evidence">
          <strong>Unresolved rename boundary</strong>
          <p>
            Current: {root.currentSource.fieldPath} →{" "}
            {root.currentTarget.fieldPath}
          </p>
          <p>
            Future: {root.futureSource.fieldPath} →{" "}
            {root.futureTarget.fieldPath}
          </p>
          <span>Missing evidence</span>
          <ul>
            {root.missingEvidence.map((item) => (
              <li key={item.evidenceId}>{item.label}</li>
            ))}
          </ul>
        </div>
      )}
      {edge.supportingPathIds.length > 0 && (
        <PathButtons
          ids={edge.supportingPathIds}
          onSelectPath={onSelectPath}
        />
      )}
    </div>
  );
}

function PathDetails({
  path,
  mode,
}: {
  path: GraphPathRecord;
  mode: GraphMode;
}) {
  return (
    <div className="inspector-content">
      <div className="path-heading">
        <Waypoints size={18} aria-hidden="true" />
        <div>
          <strong>{path.targetField.fieldPath}</strong>
          <span>{path.targetField.datasetUrn}</span>
        </div>
      </div>
      <InspectorRow label="Depth" value={String(path.depth)} />
      <InspectorRow
        label="Visible nodes"
        value={String(pathNodeIds(path, mode).length)}
      />
      <InspectorRow
        label="Compatibility"
        value={humanize(path.compatibilityState)}
        tone={path.compatibilityState}
      />
      <InspectorRow
        label="Technical impact"
        value={humanize(path.technicalImpactState)}
      />
      <p className="inspector-note">
        Highlighting follows the certified ordered node and relationship IDs
        supplied for this path.
      </p>
    </div>
  );
}

function GraphSummary({
  graph,
  onSelectEdge,
}: {
  graph: CertifiedGraphReview;
  onSelectEdge: (id: string) => void;
}) {
  return (
    <div className="inspector-content">
      <div className="graph-summary-origin">
        <Network size={19} aria-hidden="true" />
        <div>
          <strong>
            {graph.sourceChange.current.fieldPath} →{" "}
            {graph.sourceChange.future.fieldPath}
          </strong>
          <span>Certified source replacement</span>
        </div>
      </div>
      <div className="summary-number-grid">
        <div>
          <strong>{graph.summary.futureFieldNodes}</strong>
          <span>fields</span>
        </div>
        <div>
          <strong>{graph.summary.structuralRelationships}</strong>
          <span>relationships</span>
        </div>
        <div>
          <strong>{graph.summary.supportingPaths}</strong>
          <span>paths</span>
        </div>
        <div>
          <strong>{graph.summary.maximumDepth}</strong>
          <span>max depth</span>
        </div>
      </div>
      <div className="root-summary">
        <AlertTriangle size={17} aria-hidden="true" />
        <p>
          One root relationship is <strong>UNKNOWN</strong>. All 26 assessed
          future relationships are conditionally compatible.
        </p>
      </div>
      <button
        className="inspect-root-button"
        type="button"
        onClick={() => onSelectEdge(graph.rootUncertainty.futureEdgeId)}
      >
        Inspect unknown root boundary
      </button>
      <p className="inspector-note">
        Select a field, relationship, or representative path to inspect
        certified details.
      </p>
    </div>
  );
}

function GraphFooter({
  graph,
  mode,
  visibleNodes,
  visibleEdges,
  onSelectPath,
  selectedPathId,
}: {
  graph: CertifiedGraphReview;
  mode: GraphMode;
  visibleNodes: number;
  visibleEdges: number;
  onSelectPath: (id: string) => void;
  selectedPathId: string | null;
}) {
  return (
    <div className="graph-footer">
      <div className="graph-counts" aria-live="polite">
        <Network size={15} aria-hidden="true" />
        <span>
          {humanize(mode)} · {visibleNodes} fields · {visibleEdges} relationships
        </span>
      </div>
      <div className="path-shortcuts" aria-label="Representative paths">
        <span>Representative paths</span>
        {graph.representativePaths.map((shortcut) => (
          <button
            key={shortcut.shortcutId}
            type="button"
            aria-pressed={selectedPathId === shortcut.supportingPathId}
            title={shortcut.explanation}
            onClick={() => onSelectPath(shortcut.supportingPathId)}
          >
            {shortcut.label}
          </button>
        ))}
      </div>
      <div className="graph-legend" aria-label="Graph legend">
        {graph.legend.map((item) => (
          <span key={item.key} title={item.description}>
            <i className={`legend-swatch ${item.tone}`} aria-hidden="true" />
            {item.label}
          </span>
        ))}
      </div>
    </div>
  );
}

function InspectorIdentity({
  platform,
  field,
  dataset,
}: {
  platform: string;
  field: string;
  dataset: string;
}) {
  return (
    <div className="inspector-identity">
      <span>{platform}</span>
      <strong>{field}</strong>
      <small title={dataset}>{compactDataset(dataset)}</small>
    </div>
  );
}

function InspectorRow({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: string;
}) {
  return (
    <div className="inspector-row">
      <span>{label}</span>
      <strong className={tone ? `tone-${tone}` : undefined}>{value}</strong>
    </div>
  );
}

function PathButtons({
  ids,
  onSelectPath,
}: {
  ids: string[];
  onSelectPath: (id: string) => void;
}) {
  return (
    <div className="supporting-paths">
      <span>Certified supporting paths</span>
      <div>
        {ids.slice(0, 6).map((id, index) => (
          <button key={id} type="button" onClick={() => onSelectPath(id)}>
            Path {index + 1}
          </button>
        ))}
      </div>
      {ids.length > 6 && <small>+{ids.length - 6} additional paths</small>}
    </div>
  );
}

function projectionForMode(
  graph: CertifiedGraphReview,
  mode: GraphMode,
): GraphProjection {
  if (mode === "current") return graph.currentGraph;
  if (mode === "diff") return graph.diffGraph;
  return graph.futureGraph;
}

function pathNodeIds(path: GraphPathRecord, mode: GraphMode): string[] {
  if (mode === "current") return path.currentNodeIds;
  if (mode === "diff") return path.diffNodeIds;
  return path.futureNodeIds;
}

function pathEdgeIds(path: GraphPathRecord, mode: GraphMode): string[] {
  if (mode === "current") return path.currentEdgeIds;
  if (mode === "diff") return path.diffEdgeIds;
  return path.futureEdgeIds;
}

function edgeAriaLabel(edge: GraphEdgeRecord): string {
  const compatibility = edge.compatibilityState
    ? humanize(edge.compatibilityState)
    : "structural lineage";
  return `${edge.upstream.fieldPath} to ${edge.downstream.fieldPath}, ${compatibility}`;
}

function compactDataset(value: string): string {
  if (!value.startsWith("urn:li:dataset:(")) return value;
  const parts = value.slice("urn:li:dataset:(".length, -1).split(",");
  return parts[1] ?? value;
}
