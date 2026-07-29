"use client";

import {
  AlertTriangle,
  ArrowRight,
  BarChart3,
  Braces,
  ChevronRight,
  CircleHelp,
  Database,
  Eye,
  FileCode2,
  FileSearch,
  GitBranch,
  GitCompareArrows,
  ListChecks,
  RefreshCw,
  RotateCcw,
  ShieldAlert,
  ShieldCheck,
  Waypoints,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { ImpactEvidenceExplorer } from "@/components/explorer/impact-evidence-explorer";
import {
  GraphWorkspace,
  type GraphMode,
  type GraphSelection,
} from "@/components/graph/graph-workspace";
import { MetricCard } from "@/components/metric-card";
import { StatusBadge } from "@/components/status-badge";
import {
  ReviewApiError,
  ReviewContractError,
  fetchCertifiedReview,
} from "@/lib/api";
import {
  compactIdentifier,
  formatCertifiedAt,
  humanize,
} from "@/lib/format";
import type { CertifiedChangeReview } from "@/lib/review-contract";

type ReviewState =
  | { kind: "loading" }
  | { kind: "ready"; review: CertifiedChangeReview }
  | {
      kind: "error";
      message: string;
      category: "service" | "contract" | "integrity";
    };

export function ReviewPage({ reviewId }: { reviewId: string }) {
  const [state, setState] = useState<ReviewState>({ kind: "loading" });
  const [attempt, setAttempt] = useState(0);

  const retry = useCallback(() => {
    setState({ kind: "loading" });
    setAttempt((value) => value + 1);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    fetchCertifiedReview(reviewId, { signal: controller.signal })
      .then((review) => setState({ kind: "ready", review }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        const category =
          error instanceof ReviewContractError
            ? "contract"
            : error instanceof ReviewApiError &&
                error.code === "certification_integrity_error"
              ? "integrity"
              : "service";
        setState({
          kind: "error",
          category,
          message:
            error instanceof Error
              ? error.message
              : "The certified review could not be loaded.",
        });
      });
    return () => controller.abort();
  }, [attempt, reviewId]);

  return (
    <AppShell>
      {state.kind === "loading" && <ReviewLoading />}
      {state.kind === "error" && (
        <ReviewError
          category={state.category}
          message={state.message}
          onRetry={retry}
        />
      )}
      {state.kind === "ready" && (
        <ReviewContent review={state.review} reviewId={reviewId} />
      )}
    </AppShell>
  );
}

function ReviewLoading() {
  return (
    <main className="main loading-view" aria-busy="true">
      <span className="sr-only">Loading certified review</span>
      <div className="skeleton skeleton-kicker" />
      <div className="skeleton skeleton-title" />
      <div className="skeleton skeleton-hero" />
      <div className="metric-grid">
        {Array.from({ length: 4 }, (_, index) => (
          <div className="skeleton skeleton-metric" key={index} />
        ))}
      </div>
    </main>
  );
}

function ReviewError({
  category,
  message,
  onRetry,
}: {
  category: "service" | "contract" | "integrity";
  message: string;
  onRetry: () => void;
}) {
  const trustFailure = category !== "service";
  const Icon = trustFailure ? ShieldAlert : AlertTriangle;
  const label =
    category === "integrity"
      ? "Certification integrity failure"
      : category === "contract"
        ? "Contract invalid"
        : "Service unavailable";
  return (
    <main className="main centered-state">
      <section
        className={`error-panel ${trustFailure ? "integrity" : ""}`}
        aria-labelledby="error-title"
        role="alert"
      >
        <span className="error-icon" aria-hidden="true">
          <Icon size={26} />
        </span>
        <p className="eyebrow">{label}</p>
        <h1 id="error-title">
          {trustFailure
            ? "Certified review withheld"
            : "The review service is unavailable"}
        </h1>
        <p>{message}</p>
        <p className="error-guidance">
          {trustFailure
            ? "No fallback data is shown. Restore the certified artifacts and retry."
            : "The review, graph conclusions, and impact conclusions are unavailable. Confirm the local presentation API is running, then retry."}
        </p>
        <button className="button" type="button" onClick={onRetry}>
          <RefreshCw size={16} aria-hidden="true" />
          Retry certified load
        </button>
      </section>
    </main>
  );
}

function ReviewContent({
  review,
  reviewId,
}: {
  review: CertifiedChangeReview;
  reviewId: string;
}) {
  const question = review.blockingQuestions[0];
  const [selection, setSelection] = useState<GraphSelection>(null);
  const [graphMode, setGraphMode] = useState<GraphMode>("future");
  const [rootEdgeId, setRootEdgeId] = useState<string | null>(null);
  const [activeSection, setActiveSection] = useState<WorkflowSection>("overview");
  const [navigationNotice, setNavigationNotice] = useState<string | null>(null);
  const graphNarrative =
    graphMode === "current"
      ? {
          eyebrow: "Current state",
          title: "Inspect observed lineage",
          copy: "Current shows certified observed relationships only. Counterfactual compatibility styling is intentionally absent.",
        }
      : graphMode === "diff"
        ? {
            eyebrow: "Certified diff",
            title: "Compare the source identity change",
            copy: "Diff makes the removed current source, added future source, and preserved downstream identities explicit.",
          }
        : {
            eyebrow: "Future state",
            title: "Inspect where uncertainty begins",
            copy: "Future is the default view. Current and Diff remain available for comparison; the UNKNOWN root edge stays explicit.",
          };

  const navigateTo = useCallback((section: WorkflowSection) => {
    setActiveSection(section);
    setNavigationNotice(null);
    const target = document.getElementById(section);
    target?.scrollIntoView({ behavior: "smooth", block: "start" });
    const url = new URL(window.location.href);
    url.searchParams.set("section", section);
    url.hash = section;
    window.history.replaceState({}, "", url);
  }, []);

  useEffect(() => {
    const section = new URLSearchParams(window.location.search).get("section");
    if (!section) return;
    window.requestAnimationFrame(() => {
      if (!isWorkflowSection(section)) {
        setNavigationNotice(
          "The requested review section is unavailable. Showing the certified overview.",
        );
        return;
      }
      setActiveSection(section);
      document.getElementById(section)?.scrollIntoView({ block: "start" });
    });
  }, []);

  const selectReviewEntity = useCallback((next: GraphSelection) => {
    setSelection(next);
    if (
      next?.kind === "node" ||
      next?.kind === "edge" ||
      next?.kind === "path"
    ) {
      setGraphMode("future");
    }
  }, []);

  const focusRootBoundary = useCallback(() => {
    if (!rootEdgeId) {
      setNavigationNotice(
        "The certified graph is still loading. Try the boundary action again.",
      );
      return;
    }
    setGraphMode("future");
    setSelection({ kind: "edge", id: rootEdgeId });
    navigateTo("graph");
  }, [navigateTo, rootEdgeId]);

  const resetReview = useCallback(() => {
    setSelection(null);
    setGraphMode("future");
    navigateTo("overview");
  }, [navigateTo]);

  return (
    <main className="main">
      <div id="overview" className="workflow-anchor" />
      <div className="breadcrumb" aria-label="Breadcrumb">
        <span>Change reviews</span>
        <ChevronRight size={14} aria-hidden="true" />
        <span aria-current="page">{review.change.demonstrationId}</span>
      </div>

      <header className="review-context-header">
        <div className="review-context-change">
          <span>Certified change review</span>
          <strong>
            orders.{review.change.currentField}
            <ArrowRight size={14} aria-label="renamed to" />
            orders.{review.change.requestedField}
          </strong>
        </div>
        <div>
          <span>Operation</span>
          <strong>{humanize(review.change.operation)}</strong>
        </div>
        <div>
          <span>Disposition</span>
          <strong className="hold-text">HOLD FOR REVIEW</strong>
        </div>
        <div>
          <span>Technical certainty</span>
          <strong className="hold-text">
            {review.decision.technicalCertainty.toUpperCase()}
          </strong>
        </div>
        <StatusBadge tone="certified">
          <ShieldCheck size={14} aria-hidden="true" />
          Phase 4 certified
        </StatusBadge>
      </header>

      <WorkflowNavigation
        active={activeSection}
        onNavigate={navigateTo}
        onReset={resetReview}
      />

      {navigationNotice && (
        <p className="workflow-notice" role="status">
          {navigationNotice}
        </p>
      )}

      <section className="review-hero" aria-labelledby="review-title">
        <div className="review-hero-main">
          <p className="eyebrow">Field rename</p>
          <div className="review-change-title">
            <span>orders.{review.change.currentField}</span>
            <ArrowRight size={25} aria-label="renamed to" />
            <span>orders.{review.change.requestedField}</span>
          </div>
          <div className="review-change-meta" aria-label="Change identity">
            <span>{humanize(review.change.platform)}</span>
            <span>{humanize(review.change.operation)}</span>
            <span>Dataset unchanged: orders</span>
          </div>
          <div className="review-decision-title">
            <h1 id="review-title">HOLD FOR REVIEW</h1>
            <StatusBadge tone="hold">Review required</StatusBadge>
          </div>
          <p className="decision-narrative">
            CHRONOS cannot establish compatibility at the first Spark export
            boundary. The change is not a confirmed failure.
          </p>
          <div className="hero-fact-row">
            <span>
              <strong>
                {review.technicalSummary.confirmedDownstreamFailures}
              </strong>
              CONFIRMED FAILURES
            </span>
            <span>
              <strong>{review.technicalSummary.unresolvedFields}</strong>
              TECHNICALLY UNRESOLVED FIELDS
            </span>
          </div>
          <div className="workflow-actions">
            <button className="button" type="button" onClick={focusRootBoundary}>
              <Eye size={15} aria-hidden="true" />
              View unresolved boundary
            </button>
            <button
              className="button button-secondary"
              type="button"
              onClick={() => navigateTo("evidence")}
            >
              <FileSearch size={15} aria-hidden="true" />
              Review evidence gap
            </button>
          </div>
        </div>
        <div className="review-hero-side">
          <div>
            <span>Decision certainty</span>
            <strong>
              {humanize(review.decision.decisionCertainty).toUpperCase()}
            </strong>
            <small>Confidence in the review rule</small>
          </div>
          <div>
            <span>Technical certainty</span>
            <strong className="unresolved-text">
              {review.decision.technicalCertainty.toUpperCase()}
            </strong>
            <small>No confirmed downstream failure</small>
          </div>
          <div>
            <span>Severity if realized</span>
            <strong>{review.severityProfile.severityIfRealized.toUpperCase()}</strong>
            <small>if the unresolved condition materializes</small>
          </div>
        </div>
      </section>

      <section className="overview-section" aria-labelledby="scope-title">
        <SectionHeading
          eyebrow="Overview"
          title="The review in one screen"
          id="scope-title"
          supporting="Certified display facts from the Phase 4 presentation package."
        />
        <div className="overview-metric-grid">
          <MetricCard
            icon={Braces}
            label="Technically unresolved fields"
            value={review.technicalSummary.unresolvedFields}
            detail="Across the dependency cone"
          />
          <MetricCard
            icon={Database}
            label="Datasets"
            value={review.scopeSummary.datasets}
            detail="In certified technical scope"
          />
          <MetricCard
            icon={Waypoints}
            label="Dependency paths"
            value={review.technicalSummary.dependencyPaths}
            detail="Certified modeled paths"
          />
        </div>

        <div className="review-overview-grid">
          <article className="panel source-review-card">
            <p className="eyebrow">Current vs future</p>
            <div className="state-flow">
              <SourceState
                label="Current"
                field={review.currentState.fieldPath}
                classification={review.currentState.classification}
                type={review.currentState.nativeType}
              />
              <div className="state-arrow" aria-hidden="true">
                <ArrowRight size={18} />
                <span>Rename</span>
              </div>
              <SourceState
                label="Counterfactual"
                field={review.counterfactualState.fieldPath}
                classification={review.counterfactualState.classification}
                type={review.counterfactualState.nativeType}
              />
            </div>
          </article>
          <article className="panel overview-certainty-card">
            <p className="eyebrow">Certified interpretation</p>
            <div className="severity-grid">
              <LabelValue
                label="Severity if realized"
                value={review.severityProfile.severityIfRealized}
              />
              <LabelValue label="Breadth" value={review.severityProfile.breadth} />
              <LabelValue
                label="Criticality"
                value={review.severityProfile.contextCriticality}
              />
              <LabelValue
                label="Sensitivity"
                value={review.severityProfile.sensitivity}
              />
            </div>
            <small>No explicit business criticality is present.</small>
          </article>
        </div>

        <ReviewStory review={review} />

        {question && (
          <article className="overview-blocking-question">
            <CircleHelp size={21} aria-hidden="true" />
            <div>
              <p className="eyebrow">The question holding this review</p>
              <h2>{question.question}</h2>
              <p>{question.reason}</p>
              <div className="blocking-stats">
                <span>{question.affectedFields} fields</span>
                <span>{question.affectedDatasets} datasets</span>
                <span>{question.affectedPaths} paths</span>
                <span>{review.requiredEvidence.length} evidence classes</span>
              </div>
            </div>
            <button type="button" className="text-action" onClick={focusRootBoundary}>
              View root boundary
            </button>
          </article>
        )}

        <div className="overview-supporting-records">
          <article className="panel">
            <p className="eyebrow">Resolution requirements</p>
            <h2>Required evidence</h2>
            <div className="overview-evidence-list">
              {review.requiredEvidence.map((item) => (
                <span key={item.evidenceId}>
                  <FileCode2 size={13} aria-hidden="true" />
                  {humanize(item.evidenceClass)}
                </span>
              ))}
            </div>
          </article>
          <article className="panel">
            <p className="eyebrow">Certified evidence</p>
            <h2>Representative dependency paths</h2>
            {review.representativePaths.map((path) => (
              <div className="overview-path" key={path.pathId}>
                <strong>
                  {path.sourceField.fieldPath} →{" "}
                  {path.downstreamField.fieldPath}
                </strong>
                <span>{path.hopCount} hops</span>
              </div>
            ))}
          </article>
          <article className="panel">
            <p className="eyebrow">Connected context</p>
            <h2>Certified context highlights</h2>
            <div className="overview-context-list">
              {review.contextHighlights.map((item) => (
                <span key={item.highlightId}>
                  {item.displayName ??
                    compactIdentifier(item.subjectId, 18)}
                </span>
              ))}
            </div>
          </article>
        </div>
      </section>

      <div className="workflow-section-intro">
        <GitCompareArrows size={20} aria-hidden="true" />
        <div>
          <p className="eyebrow">{graphNarrative.eyebrow}</p>
          <h2>{graphNarrative.title}</h2>
          <p>{graphNarrative.copy}</p>
        </div>
      </div>

      <GraphWorkspace
        reviewId={reviewId}
        selection={selection}
        onSelectionChange={selectReviewEntity}
        mode={graphMode}
        onModeChange={setGraphMode}
        onRootBoundaryReady={setRootEdgeId}
      />

      <ImpactEvidenceExplorer
        reviewId={reviewId}
        selection={selection}
        selectedMachineKey={
          selection?.kind === "node" ? selection.machineKey ?? null : null
        }
        onSelect={(nextSelection) => {
          selectReviewEntity(nextSelection);
          setActiveSection("impact");
        }}
        onNavigate={navigateTo}
        onRootFocus={focusRootBoundary}
      />

      <footer className="certification-footer">
        <div>
          <ShieldCheck size={18} aria-hidden="true" />
          <span>
            <strong>
              {review.certification.checksPassed}/
              {review.certification.checkCount} checks passed
            </strong>
            <small>
              Certified {formatCertifiedAt(review.certification.certifiedAt)} UTC
            </small>
          </span>
        </div>
        <code title={review.certification.fingerprint}>
          {compactIdentifier(review.certification.fingerprint, 18)}
        </code>
      </footer>
    </main>
  );
}

type WorkflowSection =
  | "overview"
  | "graph"
  | "impact"
  | "evidence"
  | "decision";

const WORKFLOW_SECTIONS: readonly WorkflowSection[] = [
  "overview",
  "graph",
  "impact",
  "evidence",
  "decision",
];

function isWorkflowSection(value: string | null): value is WorkflowSection {
  return WORKFLOW_SECTIONS.includes(value as WorkflowSection);
}

function WorkflowNavigation({
  active,
  onNavigate,
  onReset,
}: {
  active: WorkflowSection;
  onNavigate: (section: WorkflowSection) => void;
  onReset: () => void;
}) {
  return (
    <nav className="review-section-nav" aria-label="Review sections">
      <div>
        {WORKFLOW_SECTIONS.map((section, index) => (
          <button
            key={section}
            type="button"
            aria-current={active === section ? "location" : undefined}
            onClick={() => onNavigate(section)}
          >
            <span aria-hidden="true">{index + 1}</span>
            {humanize(section)}
          </button>
        ))}
      </div>
      <button type="button" className="review-reset" onClick={onReset}>
        <RotateCcw size={13} aria-hidden="true" />
        Reset review
      </button>
    </nav>
  );
}

function ReviewStory({ review }: { review: CertifiedChangeReview }) {
  const story = [
    {
      key: "change",
      label: "Proposed change",
      value: `${review.change.currentField} → ${review.change.requestedField}`,
      icon: FileCode2,
    },
    {
      key: "future",
      label: "Counterfactual future",
      value: "Source identity changes tomorrow",
      icon: GitCompareArrows,
    },
    {
      key: "root",
      label: "Root uncertainty",
      value: `${review.technicalSummary.unresolvedRelationships} UNKNOWN boundary`,
      icon: GitBranch,
    },
    {
      key: "reach",
      label: "Downstream reach",
      value: `${review.technicalSummary.downstreamFields} fields · ${review.technicalSummary.downstreamDatasets} datasets · ${review.technicalSummary.dependencyPaths} paths`,
      icon: BarChart3,
    },
    {
      key: "evidence",
      label: "Evidence gap",
      value: `${review.requiredEvidence.length} required classes`,
      icon: ListChecks,
    },
    {
      key: "decision",
      label: "Decision",
      value: "HOLD FOR REVIEW",
      icon: ShieldAlert,
    },
  ];

  return (
    <div className="review-story" aria-label="Certified review story">
      {story.map((item) => {
        const Icon = item.icon;
        return (
          <article key={item.key}>
            <Icon size={15} aria-hidden="true" />
            <span>{item.label}</span>
            <strong>{item.value}</strong>
          </article>
        );
      })}
    </div>
  );
}

function SectionHeading({
  eyebrow,
  title,
  id,
  supporting,
}: {
  eyebrow: string;
  title: string;
  id: string;
  supporting?: string;
}) {
  return (
    <div className="section-heading">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h2 id={id}>{title}</h2>
      </div>
      {supporting && <p>{supporting}</p>}
    </div>
  );
}

function SourceState({
  label,
  field,
  classification,
  type,
}: {
  label: string;
  field: string;
  classification: string;
  type: string | null;
}) {
  return (
    <div className="source-state">
      <span>{label}</span>
      <strong>{field}</strong>
      <small>{type ?? "Type unavailable"}</small>
      <em>{humanize(classification)}</em>
    </div>
  );
}

function LabelValue({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{humanize(value)}</strong>
    </div>
  );
}
