"use client";

import { AlertCircle, ArrowLeft, ChevronRight, FileCode2, GitCompare, Network, RefreshCw, ShieldAlert, Wrench } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { CertificationBanner } from "@/components/phase6/certification-banner";
import { Phase6Shell } from "@/components/phase6/phase6-shell";
import type { AnalysisDetail, AnalysisGraph, EvidenceRecord, GraphMode, PatchPreview } from "@/lib/phase6-contract";
import { fetchAnalysis, fetchAnalysisEvidence, fetchAnalysisGraph, fetchPatchPreview } from "@/lib/phase6-api";

type DetailState = { kind: "loading" } | { kind: "error"; message: string } | { kind: "ready"; detail: AnalysisDetail };

export function AnalysisPage({ analysisId }: { analysisId: string }) {
  const [state, setState] = useState<DetailState>({ kind: "loading" });
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    fetchAnalysis(analysisId, { signal: controller.signal }).then((detail) => setState({ kind: "ready", detail })).catch((error: unknown) => {
      if (!controller.signal.aborted) setState({ kind: "error", message: error instanceof Error ? error.message : "Certified analysis unavailable." });
    });
    return () => controller.abort();
  }, [analysisId, attempt]);
  return <Phase6Shell><main className="p6-page p6-detail-page">
    <Link className="p6-back" href="/analyses"><ArrowLeft size={15} aria-hidden="true" /> All analyses</Link>
    {state.kind === "loading" && <DetailSkeleton />}
    {state.kind === "error" && <SectionFailure title="CERTIFIED ANALYSIS UNAVAILABLE" message={state.message} onRetry={() => { setState({ kind: "loading" }); setAttempt((value) => value + 1); }} />}
    {state.kind === "ready" && state.detail.certification.state === "PHASE_6_NOT_CERTIFIED" && <SectionFailure title="CERTIFIED ANALYSIS UNAVAILABLE" message="The package is not certified." />}
    {state.kind === "ready" && state.detail.certification.state !== "PHASE_6_NOT_CERTIFIED" && <AnalysisContent detail={state.detail} />}
  </main></Phase6Shell>;
}

function AnalysisContent({ detail }: { detail: AnalysisDetail }) {
  const repair = detail.analysisType === "repair";
  return <>
    <header className="p6-context-header"><div><span className="p6-type">{human(detail.analysisType)}</span><h1>{detail.displayName}</h1><p>{detail.analysisId} · {detail.scenarioId}</p></div><dl><div><dt>Proposal</dt><dd>{detail.proposalId}</dd></div><div><dt>{repair ? "Repair disposition" : "Decision"}</dt><dd>{human(repair ? detail.repairDisposition : detail.decision)}</dd></div><div><dt>Execution</dt><dd>UNVERIFIED</dd></div></dl></header>
    <CertificationBanner certification={detail.certification} />
    <nav className="p6-section-nav" aria-label="Analysis sections">{["overview", "changes", "graph", "evidence", "decision", ...(repair ? ["repair"] : []), "validation"].map((item) => <a href={`#${item}`} key={item}>{human(item)}</a>)}</nav>
    <section id="overview" className="p6-panel"><SectionHeading eyebrow="OVERVIEW" title="Certified analysis context" /><div className="p6-metric-grid"><Metric name="Analysis type" value={human(detail.analysisType)} /><Metric name="Operation" value={human(detail.operation)} /><Metric name="Confirmed runtime failures" value="0" /><Metric name="Manifest" value={shortFingerprint(detail.manifestFingerprint)} /></div><div className="p6-dimension-grid"><Dimension name="Certification state" value={human(detail.certification.state)} /><Dimension name="Decision" value={human(detail.decision)} /><Dimension name="Execution validity" value="UNVERIFIED" /><Dimension name="Runtime evidence" value="NOT COLLECTED" /></div></section>
    <section id="changes" className="p6-panel"><SectionHeading eyebrow="CHANGES" title={changeTitle(detail)} />{detail.analysisType === "structural" && <StructuralView detail={detail} />}{detail.analysisType === "semantic" && <SemanticView detail={detail} />}{detail.analysisType === "pull_request" && <PullRequestView detail={detail} />}{detail.analysisType === "repair" && <RepairOverview detail={detail} />}</section>
    <GraphPanel analysisId={detail.analysisId} />
    <EvidencePanel analysisId={detail.analysisId} />
    <section id="decision" className="p6-panel"><SectionHeading eyebrow="DECISION" title="Independent decision dimensions" /><div className="p6-dimension-grid"><Dimension name="PR decision" value={detail.analysisType === "repair" ? "See predecessor analysis" : human(detail.decision)} /><Dimension name="Repair disposition" value={detail.analysisType === "repair" ? human(detail.repairDisposition) : "NOT APPLICABLE"} /><Dimension name="Repository coherence" value={detail.analysisType === "pull_request" ? detail.coherence : detail.analysisType === "repair" ? detail.comparison.projectedCoherence : "SEPARATE DIMENSION"} /><Dimension name="Execution validity" value="UNVERIFIED" /></div><p className="p6-boundary">Static findings, unresolved compatibility, stale references, conflicts, and projected roots are not confirmed runtime failures.</p></section>
    {detail.analysisType === "repair" && <RepairReview detail={detail} />}
    <section id="validation" className="p6-panel p6-validation"><ShieldAlert aria-hidden="true" /><div><p className="p6-eyebrow">REMAINING VALIDATION</p><h2>{repair ? "PHASE 7 REQUIRED" : "Runtime evidence remains outside Phase 6"}</h2>{repair ? <><p>Phase 6 generated and statically projected this candidate. It has not been executed or verified.</p><ul>{detail.phase7Requirements.map((item) => <li key={item}>{human(item)}</li>)}</ul></> : <p>This certified package contains static analysis only. Runtime, data, consumer, and owner validation remain unverified.</p>}</div></section>
  </>;
}

function StructuralView({ detail }: { detail: Extract<AnalysisDetail, { analysisType: "structural" }> }) {
  const value = detail.change;
  return <><div className="p6-comparison"><StateCard title="CURRENT" primary={value.currentField} secondary={value.currentType ?? "Type unchanged or unavailable"} /><ChevronRight aria-hidden="true" /><StateCard title="PROPOSED" primary={value.proposedField ?? "Field removed or identity preserved"} secondary={value.proposedType ?? "Type unchanged or unavailable"} /></div><dl className="p6-record"><Row name="Dataset" value={value.datasetUrn} /><Row name="Identity mapping" value={value.identityMapping} /><Row name="Structural compatibility" value={value.compatibility} /><Row name="Downstream exposure" value={`${value.downstreamFields} fields · ${value.downstreamDatasets} datasets`} /></dl><QuestionList title="Blocking questions" values={value.blockingQuestions} /><QuestionList title="Required evidence" values={value.requiredEvidence} /></>;
}

function SemanticView({ detail }: { detail: Extract<AnalysisDetail, { analysisType: "semantic" }> }) {
  return <><dl className="p6-record"><Row name="Target model" value={detail.modelDatasetUrn} /><Row name="BEFORE fingerprint" value={detail.beforeFingerprint} /><Row name="AFTER fingerprint" value={detail.afterFingerprint} /><Row name="Semantic compatibility" value={detail.semanticCompatibility} /><Row name="Structural compatibility" value={detail.structuralCompatibility} /></dl><div className="p6-delta-grid">{detail.deltas.map((delta) => <article className="p6-delta" key={delta.deltaId}><div><span className="p6-type">{human(delta.deltaType)}</span><span className="p6-evidence">{delta.evidenceClass}</span></div><h3>{delta.affectedOutput ?? "Model-wide delta"}</h3><div className="p6-before-after"><div><small>BEFORE</small><code>{delta.before}</code></div><div><small>AFTER</small><code>{delta.after}</code></div></div><dl><Row name="Scope" value={delta.scope} /><Row name="Certainty" value={delta.certainty} /></dl><p><strong>Potential consequence:</strong> {delta.potentialConsequence}</p><p><strong>Missing evidence:</strong> {delta.missingEvidence.join(", ") || "None recorded"}</p></article>)}</div></>;
}

function PullRequestView({ detail }: { detail: Extract<AnalysisDetail, { analysisType: "pull_request" }> }) {
  const [selectedGroupId, setSelectedGroupId] = useState<string | null>(null);
  const selected = detail.logicalGroups.find((group) => group.groupId === selectedGroupId) ?? null;
  return <>
    <div className="p6-dimension-grid"><Dimension name="Repository" value={detail.repository} /><Dimension name="BASE" value={detail.baseIdentity} /><Dimension name="HEAD" value={detail.headIdentity} /><Dimension name="Coherence" value={detail.coherence} /></div>
    <h3>Changed files</h3>
    <div className="p6-file-grid">{detail.changedFiles.map((file) => <article className={selected?.contributingFileIds.includes(file.fileId) ? "p6-related" : undefined} key={file.fileId}><FileCode2 size={18} aria-hidden="true" /><div><strong>{file.path}</strong><span>{file.status} · {human(file.category)}</span><small>{file.parser}</small></div><dl><Row name="Material" value={human(file.materialState)} /><Row name="Deltas" value={String(file.deltaCount)} /><Row name="Warnings" value={String(file.warningCount)} /><Row name="Resolved entities" value={String(file.resolvedEntityCount)} /><Row name="Unresolved references" value={String(file.unresolvedReferenceCount)} /></dl></article>)}</div>
    <h3>Logical change groups</h3>
    <div className="p6-group-grid">{detail.logicalGroups.map((group) => <details className={selectedGroupId === group.groupId ? "p6-related" : undefined} key={group.groupId}><summary><span>{group.currentIdentity ?? "Unresolved identity group"}</span><b>{group.coherence}</b></summary><button className="p6-trace-group" aria-pressed={selectedGroupId === group.groupId} onClick={() => setSelectedGroupId(group.groupId)}>Trace this group</button><dl><Row name="Proposed" value={group.proposedIdentities.join(", ") || "None"} /><Row name="Contributing files" value={String(group.contributingFileIds.length)} /><Row name="Structural deltas" value={String(group.structuralChangeIds.length)} /><Row name="Semantic deltas" value={String(group.semanticChangeIds.length)} /><Row name="Stale references" value={String(group.staleReferenceIds.length)} /><Row name="Root causes" value={String(group.rootIds.length)} /></dl></details>)}</div>
    {selected && <aside className="p6-path-detail" aria-label="Selected logical group traceability"><strong>{selected.currentIdentity ?? "Unresolved identity group"}</strong><dl><Row name="Related files" value={selected.contributingFileIds.join(", ")} /><Row name="Related graph roots" value={selected.rootIds.join(", ")} /><Row name="Related evidence" value={selected.evidenceIds.join(", ")} /><Row name="Related findings" value={[...selected.structuralChangeIds, ...selected.semanticChangeIds, ...selected.staleReferenceIds].join(", ") || "None"} /></dl></aside>}
    {detail.conflicts.length > 0 && <><h3>Explicit conflicts</h3>{detail.conflicts.map((conflict) => <article className="p6-conflict" key={conflict.conflictId}><strong>No winner selected</strong><p>{conflict.reason}</p><Row name="Current" value={conflict.currentEntity} /><Row name="Competing proposals" value={conflict.proposedIdentities.join(" · ")} /><Row name="Supporting files" value={conflict.supportingFileIds.join(", ")} /><Row name="Required resolution" value={conflict.requiredEvidence.join(", ")} /></article>)}</>}
  </>;
}

function RepairOverview({ detail }: { detail: Extract<AnalysisDetail, { analysisType: "repair" }> }) {
  return <><div className="p6-dimension-grid"><Dimension name="Predecessor PR" value={detail.predecessorAnalysisId} /><Dimension name="Repair disposition" value={human(detail.repairDisposition)} /><Dimension name="Repair completeness" value={human(detail.repairCompleteness)} /><Dimension name="Projection" value="STATIC ONLY · RUNTIME UNVERIFIED" /></div><div className="p6-comparison"><StateCard title="ORIGINAL" primary={detail.comparison.originalCoherence} secondary={`${detail.comparison.originalStaleReferences} stale references`} /><ChevronRight aria-hidden="true" /><StateCard title="PROJECTED REPAIRED" primary={detail.comparison.projectedCoherence} secondary={`${detail.comparison.projectedStaleReferences} stale references · RUNTIME UNVERIFIED`} /></div></>;
}

function GraphPanel({ analysisId }: { analysisId: string }) {
  const [state, setState] = useState<{ kind: "loading" } | { kind: "error"; message: string } | { kind: "ready"; graph: AnalysisGraph }>({ kind: "loading" });
  const [mode, setMode] = useState<GraphMode | undefined>(undefined);
  const [selectedPathId, setSelectedPathId] = useState<string | null>(null);
  useEffect(() => { const controller = new AbortController(); fetchAnalysisGraph(analysisId, mode, { signal: controller.signal }).then((graph) => setState({ kind: "ready", graph })).catch((error: unknown) => { if (!controller.signal.aborted) setState({ kind: "error", message: error instanceof Error ? error.message : "Graph unavailable." }); }); return () => controller.abort(); }, [analysisId, mode]);
  if (state.kind !== "ready") return <section id="graph" className="p6-panel"><SectionHeading eyebrow="GRAPH" title="Composite certified graph" />{state.kind === "loading" ? <SectionSkeleton label="Loading graph" /> : <SectionFailure title="Graph unavailable" message={state.message} />}</section>;
  const selectedPath = state.graph.representativePaths.find((item) => item.pathId === selectedPathId) ?? null;
  return <section id="graph" className="p6-panel">
    <SectionHeading eyebrow="GRAPH" title="Composite certified graph" />
    <div className="p6-graph-tabs" role="tablist" aria-label="Graph state mode">
      {state.graph.availableModes.map((item) => <button role="tab" aria-selected={state.graph.mode === item} key={item} onClick={() => { setState({ kind: "loading" }); setSelectedPathId(null); setMode(item); }}>{human(item)}</button>)}
    </div>
    <div className="p6-graph-mode"><Network aria-hidden="true" /><strong>{human(state.graph.mode)}</strong><span>{state.graph.mode === "PROJECTED_REPAIRED" ? "PROJECTED REPAIRED · STATIC ONLY · RUNTIME UNVERIFIED" : "CERTIFIED STATIC GRAPH · RUNTIME UNVERIFIED"}</span></div>
    <div className="p6-legend" aria-label="Graph edge legend">{["OBSERVED_DATAHUB_EDGE", "CODE_DERIVED_PROPOSED_EDGE", "COUNTERFACTUAL_EDGE", "REMOVED_EDGE", "UNRESOLVED_REFERENCE"].map((item) => <span key={item} className={`edge-${item.toLowerCase()}`}><i aria-hidden="true" />{human(item)}</span>)}</div>
    <div className="p6-graph-summary" role="img" aria-label={`${state.graph.nodes.length} nodes, ${state.graph.edges.length} edges, and ${state.graph.representativePaths.length} representative paths`}><strong>{state.graph.nodes.length} nodes</strong><span>{state.graph.edges.length} relationships</span><span>{state.graph.representativePaths.length} representative paths shown</span></div>
    <div className="p6-path-buttons" aria-label="Representative multi-root paths">{state.graph.representativePaths.map((path) => <button key={path.pathId} aria-pressed={selectedPathId === path.pathId} onClick={() => setSelectedPathId(path.pathId)}>{shortFingerprint(path.pathId)}</button>)}</div>
    {selectedPath && <aside className="p6-path-detail" aria-label="Selected path traceability"><strong>{selectedPath.target}</strong><dl><Row name="All roots reaching target" value={selectedPath.rootIds.join(", ") || "No explicit root"} /><Row name="Contributing files" value={selectedPath.contributingFileIds.join(", ") || "None supplied"} /><Row name="Supporting nodes" value={String(selectedPath.nodeIds.length)} /><Row name="Evidence" value={selectedPath.evidenceClass} /></dl></aside>}
    <details><summary>Accessible graph records</summary><ul className="p6-bounded-list">{state.graph.nodes.slice(0, 24).map((node) => <li key={node.nodeId}><span className="p6-evidence">{node.evidenceClass}</span><strong>{node.label}</strong><small>{human(node.state)}</small></li>)}</ul></details>
  </section>;
}

function EvidencePanel({ analysisId }: { analysisId: string }) {
  const [state, setState] = useState<{ kind: "loading" } | { kind: "error"; message: string } | { kind: "ready"; evidence: EvidenceRecord[] }>({ kind: "loading" });
  useEffect(() => { const controller = new AbortController(); fetchAnalysisEvidence(analysisId, { signal: controller.signal }).then((evidence) => setState({ kind: "ready", evidence })).catch((error: unknown) => { if (!controller.signal.aborted) setState({ kind: "error", message: error instanceof Error ? error.message : "Evidence unavailable." }); }); return () => controller.abort(); }, [analysisId]);
  return <section id="evidence" className="p6-panel"><SectionHeading eyebrow="EVIDENCE" title="Certified evidence records" />{state.kind === "loading" && <SectionSkeleton label="Loading evidence" />}{state.kind === "error" && <SectionFailure title="Evidence unavailable" message={state.message} />}{state.kind === "ready" && state.evidence.length === 0 && <p className="p6-empty">No additional evidence records are required for this certified outcome.</p>}{state.kind === "ready" && <div className="p6-evidence-grid">{state.evidence.map((item) => <article key={item.evidenceId}><span className="p6-evidence">{item.evidenceClass}</span><h3>{human(item.subject)}</h3><p>{item.statement}</p><small>{human(item.certainty)}</small></article>)}</div>}</section>;
}

function RepairReview({ detail }: { detail: Extract<AnalysisDetail, { analysisType: "repair" }> }) {
  return <section id="repair" className="p6-panel">
    <SectionHeading eyebrow="REPAIR · REVIEW ONLY" title="Candidate repair package" />
    <h3>Repairability</h3>
    <div className="p6-repairability">{detail.repairability.map((item) => <article key={item.rootId}><span className="p6-state">{human(item.state)}</span><span className="p6-evidence">{item.evidenceClass}</span><h4>{human(item.rootType)}</h4><p>{item.reason}</p><small>{item.remainingUncertainty.map(human).join(" · ")}</small></article>)}</div>
    {detail.actions.length === 0 ? <ValidEmptyState disposition={detail.repairDisposition} /> : <>
      <h3>Repair Plan</h3>
      <ol className="p6-actions">{detail.actions.map((action) => <li value={action.applicationOrder} key={action.actionId}><div><strong>{action.file}</strong><span>{action.exactTarget}</span><span className="p6-evidence">{action.evidenceClass}</span></div><div className="p6-value-change"><code>{action.currentValue}</code><ChevronRight aria-hidden="true" /><code>{action.proposedValue}</code></div><dl><Row name="Rule" value={action.rule} /><Row name="Root cause" value={action.rootId} /><Row name="Evidence" value={action.evidenceIds.join(", ")} /><Row name="Dependencies" value={action.dependencies.join(", ") || "None"} /><Row name="Protected semantics" value={action.protectedSemantics.join(", ")} /><Row name="Remaining validation" value={action.remainingValidation.join(", ")} /></dl></li>)}</ol>
      <h3>Certified patch hunks</h3>
      <div className="p6-patches">{detail.patches.map((patch) => <PatchPanel analysisId={detail.analysisId} patch={patch} rootIds={detail.actions.filter((action) => patch.actionIds.includes(action.actionId)).map((action) => action.rootId)} key={patch.patchId} />)}</div>
    </>}
    <h3>Projected comparison</h3>
    <div className="p6-comparison-table"><Metric name="Coherence" value={`${detail.comparison.originalCoherence} → ${detail.comparison.projectedCoherence}`} /><Metric name="Stale references" value={`${detail.comparison.originalStaleReferences} → ${detail.comparison.projectedStaleReferences}`} /><Metric name="Roots projected closed" value={`${detail.comparison.projectedClosedRoots}/${detail.comparison.targetedRoots}`} /><Metric name="Roots remaining" value={String(detail.comparison.remainingRoots)} /><Metric name="New roots" value={String(detail.comparison.newRoots)} /><Metric name="Semantic questions" value={String(detail.comparison.unresolvedSemanticQuestions)} /><Metric name="Execution" value="UNVERIFIED" /></div>
    {detail.remainingFindings.length > 0 && <QuestionList title="Remaining findings" values={detail.remainingFindings} />}
  </section>;
}

function PatchPanel({ analysisId, patch, rootIds }: { analysisId: string; patch: Extract<AnalysisDetail, { analysisType: "repair" }>["patches"][number]; rootIds: string[] }) {
  const [state, setState] = useState<{ kind: "idle" } | { kind: "loading" } | { kind: "error"; message: string } | { kind: "ready"; patch: PatchPreview }>({ kind: "idle" });
  const load = () => { setState({ kind: "loading" }); fetchPatchPreview(analysisId, patch.patchId).then((preview) => setState({ kind: "ready", patch: preview })).catch((error: unknown) => setState({ kind: "error", message: error instanceof Error ? error.message : "Patch preview unavailable." })); };
  return <article className="p6-patch"><header><GitCompare aria-hidden="true" /><div><strong>{patch.file}</strong><small>{patch.patchId}</small></div>{state.kind === "idle" && <button onClick={load}>Load bounded preview</button>}</header><dl><Row name="Actions" value={patch.actionIds.join(", ")} /><Row name="Roots" value={rootIds.join(", ")} /><Row name="Protected semantics" value={patch.protectedSemanticsState} /><Row name="Static validation" value={patch.staticValidationState} /><Row name="Patch fingerprint" value={patch.fingerprint} /></dl>{state.kind === "loading" && <SectionSkeleton label="Loading patch preview" />}{state.kind === "error" && <SectionFailure title="Patch preview unavailable" message={state.message} onRetry={load} />}{state.kind === "ready" && <><div className="p6-candidate-label">{state.patch.label} · RUNTIME UNVERIFIED</div><div className="p6-diff" role="region" aria-label={`Patch for ${patch.file}`} tabIndex={0}>{state.patch.lines.map((line, index) => <div className={`diff-${line.kind}`} key={`${line.kind}-${index}`}><span>{line.oldLine ?? ""}</span><span>{line.newLine ?? ""}</span><b aria-label={line.kind}>{line.kind === "addition" ? "+" : line.kind === "removal" ? "−" : " "}</b><code>{line.text}</code></div>)}</div><details><summary>Original HEAD versus candidate</summary><div className="p6-preview"><pre aria-label="Original HEAD">{state.patch.originalExcerpt.join("\n")}</pre><pre aria-label="Candidate not applied">{state.patch.candidateExcerpt.join("\n")}</pre></div></details><small>{state.patch.fingerprint}</small></>}</article>;
}

function ValidEmptyState({ disposition }: { disposition: string }) { const blocked = disposition === "REPAIR_BLOCKED_BY_CONFLICT"; return <div className="p6-valid-empty"><Wrench aria-hidden="true" /><div><strong>{human(disposition)}</strong><p>{blocked ? "No patch permitted until competing certified identities are resolved." : "No supported automatic patch is needed or permitted for this certified state."}</p></div></div>; }
function SectionHeading({ eyebrow, title }: { eyebrow: string; title: string }) { return <header className="p6-section-heading"><div><p className="p6-eyebrow">{eyebrow}</p><h2>{title}</h2></div></header>; }
function StateCard({ title, primary, secondary }: { title: string; primary: string; secondary: string }) { return <article><span>{title}</span><strong>{primary}</strong><small>{secondary}</small></article>; }
function Dimension({ name, value }: { name: string; value: string }) { return <div><span>{name}</span><strong>{value}</strong></div>; }
function Metric({ name, value }: { name: string; value: string }) { return <div><span>{name}</span><strong>{value}</strong></div>; }
function Row({ name, value }: { name: string; value: string }) { return <div><dt>{name}</dt><dd>{value}</dd></div>; }
function QuestionList({ title, values }: { title: string; values: string[] }) { return <div className="p6-questions"><h3>{title}</h3><ul>{values.map((value) => <li key={value}>{value}</li>)}</ul></div>; }
function DetailSkeleton() { return <div className="p6-skeleton detail" aria-busy="true" aria-label="Loading certified analysis"><i /><i /><i /><i /></div>; }
function SectionSkeleton({ label }: { label: string }) { return <div className="p6-section-skeleton" aria-busy="true" aria-label={label}><i /><i /></div>; }
function SectionFailure({ title, message, onRetry }: { title: string; message: string; onRetry?: () => void }) { return <div className="p6-section-error" role="alert"><AlertCircle aria-hidden="true" /><div><strong>{title}</strong><p>{message}</p>{onRetry && <button onClick={onRetry}><RefreshCw size={14} aria-hidden="true" /> Retry</button>}</div></div>; }
function human(value: string) { return value.replaceAll("_", " ").replaceAll("-", " ").toUpperCase(); }
function shortFingerprint(value: string) { return `${value.slice(0, 15)}…${value.slice(-8)}`; }
function changeTitle(detail: AnalysisDetail) { return detail.analysisType === "structural" ? "Structural change" : detail.analysisType === "semantic" ? "Semantic deltas" : detail.analysisType === "pull_request" ? "Repository change set" : "Repair projection"; }
