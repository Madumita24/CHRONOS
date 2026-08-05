"use client";

import { AlertCircle, ArrowRight, RefreshCw, Search } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { CertificationBanner } from "@/components/phase6/certification-banner";
import { Phase6Shell } from "@/components/phase6/phase6-shell";
import type { AnalysisIndex, ReleaseCertification } from "@/lib/phase6-contract";
import { fetchAnalysisIndex, fetchReleaseCertification } from "@/lib/phase6-api";

type State =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; index: AnalysisIndex; release: ReleaseCertification };

export function AnalysisIndexPage() {
  const [state, setState] = useState<State>({ kind: "loading" });
  const [attempt, setAttempt] = useState(0);
  const [search, setSearch] = useState("");
  const [type, setType] = useState("all");
  const [decision, setDecision] = useState("all");
  const [coherence, setCoherence] = useState("all");
  const [certification, setCertification] = useState("all");

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      fetchAnalysisIndex({ signal: controller.signal }),
      fetchReleaseCertification({ signal: controller.signal }),
    ]).then(([index, release]) => setState({ kind: "ready", index, release }))
      .catch((error: unknown) => {
        if (!controller.signal.aborted) setState({ kind: "error", message: error instanceof Error ? error.message : "Certified analysis index unavailable." });
      });
    return () => controller.abort();
  }, [attempt]);

  const analyses = useMemo(() => {
    if (state.kind !== "ready") return [];
    const term = search.trim().toLowerCase();
    return state.index.analyses.filter((item) =>
      (!term || `${item.displayName} ${item.scenarioId} ${item.operation}`.toLowerCase().includes(term)) &&
      (type === "all" || item.analysisType === type) &&
      (decision === "all" || item.decision === decision) &&
      (coherence === "all" || item.coherence === coherence) &&
      (certification === "all" || item.certificationState === certification),
    );
  }, [state, search, type, decision, coherence, certification]);

  return (
    <Phase6Shell>
      <main className="p6-page">
        <header className="p6-page-heading">
          <p className="p6-eyebrow">PHASE 6 · CERTIFIED STATIC EVIDENCE</p>
          <h1>Select a certified analysis</h1>
          <p>Inspect structural, semantic, multi-file PR, and candidate-repair evidence. No analysis or repository access occurs in this browser.</p>
        </header>
        {state.kind === "loading" && <IndexSkeleton />}
        {state.kind === "error" && <Failure title="CERTIFIED ANALYSIS UNAVAILABLE" message={state.message} onRetry={() => { setState({ kind: "loading" }); setAttempt((value) => value + 1); }} />}
        {state.kind === "ready" && state.index.certification.state === "PHASE_6_NOT_CERTIFIED" && <Failure title="CERTIFIED ANALYSIS UNAVAILABLE" message="The release certification gate rejected this package." />}
        {state.kind === "ready" && state.index.certification.state !== "PHASE_6_NOT_CERTIFIED" && (
          <>
            <CertificationBanner certification={state.index.certification} />
            <ReleasePanel release={state.release} />
            <section className="p6-selector" aria-labelledby="selector-title">
              <div className="p6-section-heading"><div><p className="p6-eyebrow">ANALYSIS CATALOG</p><h2 id="selector-title">Certified fixtures</h2></div><span>{analyses.length} shown</span></div>
              <div className="p6-filters" aria-label="Analysis filters">
                <label><Search size={15} aria-hidden="true" /><span className="sr-only">Search analyses</span><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search title or scenario" /></label>
                <FilterSelect label="type" value={type} onChange={setType} options={["all", "structural", "semantic", "pull_request", "repair"]} />
                <FilterSelect label="decision" value={decision} onChange={setDecision} options={["all", ...new Set(state.index.analyses.map((item) => item.decision))]} />
                <FilterSelect label="coherence" value={coherence} onChange={setCoherence} options={["all", "COHERENT", "PARTIALLY_COHERENT", "INCONSISTENT", "UNRESOLVED"]} />
                <FilterSelect label="certification" value={certification} onChange={setCertification} options={["all", "PHASE_6_CERTIFIED", "PHASE_6_CERTIFIED_WITH_NON_BLOCKING_LIMITATIONS"]} />
              </div>
              <div className="p6-analysis-grid">
                {analyses.map((item) => (
                  <Link className="p6-analysis-card" href={`/analyses/${encodeURIComponent(item.analysisId)}`} key={item.analysisId}>
                    <div><span className="p6-type">{label(item.analysisType)}</span><span className="p6-state">{item.certificationState === "PHASE_6_CERTIFIED" ? "CERTIFIED" : "CERTIFIED · LIMITED"}</span></div>
                    <h3>{item.displayName}</h3><p>{item.scenarioId}</p>
                    <dl><div><dt>Decision</dt><dd>{label(item.decision)}</dd></div><div><dt>Affected scope</dt><dd>{item.affectedFileCount} files · {item.affectedDatasetCount} datasets</dd></div><div><dt>Warnings</dt><dd>{item.warnings.length}</dd></div></dl>
                    <span className="p6-open">Open certified analysis <ArrowRight size={15} aria-hidden="true" /></span>
                  </Link>
                ))}
              </div>
              {analyses.length === 0 && <p className="p6-empty">No certified analyses match these filters.</p>}
            </section>
          </>
        )}
      </main>
    </Phase6Shell>
  );
}

function ReleasePanel({ release }: { release: ReleaseCertification }) {
  return <details className="p6-release"><summary>Phase 6 release certification</summary><div className="p6-release-grid"><Metric label="Tests" value={`${release.testTotals.passed}/${release.testTotals.executed} passed`} /><Metric label="Skipped" value={`${release.skippedTestCount} live DataHub`} /><Metric label="Golden preservation" value={release.goldenPreservationState} /><Metric label="Runtime" value="UNVERIFIED" /></div><dl className="p6-fingerprints"><div><dt>Release</dt><dd>{release.certification.releaseId} · v{release.certification.certificationVersion}</dd></div><div><dt>Package fingerprint</dt><dd>{release.certification.packageFingerprint}</dd></div><div><dt>Manifest fingerprint</dt><dd>{release.certification.releaseManifestFingerprint}</dd></div><div><dt>Certification fingerprint</dt><dd>{release.certification.topLevelCertificationFingerprint}</dd></div></dl><p>{release.supportedCapabilities.length} supported capabilities · {release.unsupportedCapabilities.length} unsupported/out-of-scope capabilities</p></details>;
}

function FilterSelect({ label: name, value, onChange, options }: { label: string; value: string; onChange: (value: string) => void; options: Iterable<string> }) {
  return <label><span className="sr-only">Filter by {name}</span><select aria-label={`Filter by ${name}`} value={value} onChange={(event) => onChange(event.target.value)}>{Array.from(options).map((option) => <option value={option} key={option}>{label(option)}</option>)}</select></label>;
}
function Metric({ label: name, value }: { label: string; value: string }) { return <div><span>{name}</span><strong>{value}</strong></div>; }
function IndexSkeleton() { return <div className="p6-skeleton" aria-busy="true" aria-label="Loading certified analysis index"><i /><i /><i /></div>; }
function Failure({ title, message, onRetry }: { title: string; message: string; onRetry?: () => void }) { return <section className="p6-failure" role="alert"><AlertCircle aria-hidden="true" /><div><h2>{title}</h2><p>{message}</p>{onRetry && <button onClick={onRetry}><RefreshCw size={14} aria-hidden="true" /> Retry</button>}</div></section>; }
function label(value: string) { return value.replaceAll("_", " ").toUpperCase(); }
