"use client";

import {
  AlertTriangle,
  ArrowRight,
  Boxes,
  Braces,
  CheckCircle2,
  ChevronRight,
  CircleHelp,
  Database,
  FileCode2,
  GitBranch,
  Layers3,
  Network,
  RefreshCw,
  Route,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { GraphWorkspace } from "@/components/graph/graph-workspace";
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
  | { kind: "error"; message: string; integrity: boolean };

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
        const integrity =
          error instanceof ReviewContractError ||
          (error instanceof ReviewApiError &&
            error.code === "certification_integrity_error");
        setState({
          kind: "error",
          integrity,
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
          integrity={state.integrity}
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
  integrity,
  message,
  onRetry,
}: {
  integrity: boolean;
  message: string;
  onRetry: () => void;
}) {
  const Icon = integrity ? ShieldAlert : AlertTriangle;
  return (
    <main className="main centered-state">
      <section
        className={`error-panel ${integrity ? "integrity" : ""}`}
        aria-labelledby="error-title"
        role="alert"
      >
        <span className="error-icon" aria-hidden="true">
          <Icon size={26} />
        </span>
        <p className="eyebrow">
          {integrity ? "Certification gate closed" : "Connection interrupted"}
        </p>
        <h1 id="error-title">
          {integrity
            ? "Certified evidence cannot be displayed"
            : "The review service is unavailable"}
        </h1>
        <p>{message}</p>
        <p className="error-guidance">
          {integrity
            ? "No fallback data is shown. Restore the certified artifacts and retry."
            : "Confirm the local presentation API is running, then retry."}
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
  return (
    <main className="main">
      <div className="breadcrumb" aria-label="Breadcrumb">
        <span>Change reviews</span>
        <ChevronRight size={14} aria-hidden="true" />
        <span aria-current="page">{review.change.demonstrationId}</span>
      </div>

      <header className="page-heading">
        <div>
          <p className="eyebrow">Certified impact assessment</p>
          <h1>
            <span>{review.change.currentField}</span>
            <ArrowRight size={26} aria-label="renamed to" />
            <span>{review.change.requestedField}</span>
          </h1>
          <p className="dataset-identity">{review.change.displayIdentity}</p>
        </div>
        <div className="heading-meta">
          <StatusBadge tone="certified">
            <ShieldCheck size={14} aria-hidden="true" />
            {humanize(review.certification.status)}
          </StatusBadge>
          <span>{review.change.proposalId}</span>
        </div>
      </header>

      <section className="decision-hero" aria-labelledby="decision-title">
        <div className="decision-primary">
          <p className="eyebrow">Certified disposition</p>
          <div className="decision-title-row">
            <h2 id="decision-title">Hold for review</h2>
            <StatusBadge tone="hold">Review required</StatusBadge>
          </div>
          <p className="decision-narrative">{review.decision.narrative}</p>
          <div className="reason-row" aria-label="Decision reasons">
            {review.decision.reasons.map((reason) => (
              <span key={reason.code}>{humanize(reason.code)}</span>
            ))}
          </div>
        </div>
        <div className="certainty-panel">
          <div>
            <span>Decision certainty</span>
            <strong>{humanize(review.decision.decisionCertainty)}</strong>
            <small>Confidence in the review rule</small>
          </div>
          <div>
            <span>Technical certainty</span>
            <strong className="unresolved-text">
              {humanize(review.decision.technicalCertainty)}
            </strong>
            <small>No confirmed downstream failure</small>
          </div>
        </div>
      </section>

      <GraphWorkspace reviewId={reviewId} />

      <section aria-labelledby="scope-title">
        <SectionHeading
          eyebrow="Certified scope"
          title="What the evidence reaches"
          id="scope-title"
        />
        <div className="metric-grid">
          <MetricCard
            icon={CheckCircle2}
            label="Confirmed failures"
            value={review.technicalSummary.confirmedDownstreamFailures}
            detail="No breakage asserted"
          />
          <MetricCard
            icon={Braces}
            label="Unresolved fields"
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
            icon={Boxes}
            label="Context assets"
            value={review.scopeSummary.connectedContextAssets}
            detail="Connected business context"
          />
        </div>
      </section>

      <section className="two-column" aria-label="Source state comparison">
        <article className="panel state-panel">
          <SectionHeading
            eyebrow="Certified change"
            title="Source state comparison"
            id="state-title"
          />
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
          <dl className="detail-list">
            <div>
              <dt>Dataset</dt>
              <dd title={review.change.datasetUrn}>
                {compactIdentifier(review.change.datasetUrn, 24)}
              </dd>
            </div>
            <div>
              <dt>Schema fields</dt>
              <dd>{review.counterfactualState.schemaFieldCount}</dd>
            </div>
            <div>
              <dt>Environment</dt>
              <dd>{review.change.environment}</dd>
            </div>
          </dl>
        </article>

        <article className="panel severity-panel">
          <SectionHeading
            eyebrow="Conditional impact"
            title="Severity if realized"
            id="severity-title"
          />
          <div className="severity-callout">
            <StatusBadge tone="high">
              {humanize(review.severityProfile.severityIfRealized)}
            </StatusBadge>
            <span>if the unresolved condition materializes</span>
          </div>
          <div className="severity-grid">
            <LabelValue
              label="Breadth"
              value={review.severityProfile.breadth}
            />
            <LabelValue
              label="Context"
              value={review.severityProfile.contextCriticality}
            />
            <LabelValue
              label="Sensitivity"
              value={review.severityProfile.sensitivity}
            />
            <LabelValue
              label="Consequence"
              value={review.severityProfile.technicalConsequence}
            />
          </div>
        </article>
      </section>

      {question && (
        <section className="blocking-panel" aria-labelledby="blocking-title">
          <div className="blocking-icon" aria-hidden="true">
            <CircleHelp size={22} />
          </div>
          <div>
            <div className="section-kicker-row">
              <p className="eyebrow">Blocking question</p>
              <StatusBadge tone="unresolved">Unresolved</StatusBadge>
            </div>
            <h2 id="blocking-title">{question.question}</h2>
            <p>{question.reason}</p>
            <div className="blocking-stats">
              <span>{question.affectedFields} fields</span>
              <span>{question.affectedDatasets} datasets</span>
              <span>{question.affectedPaths} paths</span>
            </div>
          </div>
        </section>
      )}

      <section className="two-column evidence-layout">
        <article className="panel" aria-labelledby="evidence-title">
          <SectionHeading
            eyebrow="Resolution requirements"
            title="Required evidence"
            id="evidence-title"
          />
          <div className="evidence-list">
            {review.requiredEvidence.map((item, index) => (
              <div className="evidence-row" key={item.evidenceId}>
                <span>{String(index + 1).padStart(2, "0")}</span>
                <div>
                  <strong>{humanize(item.evidenceClass)}</strong>
                  <p>{item.reason}</p>
                </div>
                <FileCode2 size={17} aria-hidden="true" />
              </div>
            ))}
          </div>
        </article>

        <article className="panel" aria-labelledby="root-title">
          <SectionHeading
            eyebrow="Technical origin"
            title={review.rootCause.title}
            id="root-title"
          />
          <p className="panel-copy">{review.rootCause.explanation}</p>
          <dl className="code-details">
            <div>
              <dt>Root cause</dt>
              <dd>{review.rootCause.rootCauseId}</dd>
            </div>
            <div>
              <dt>Boundary</dt>
              <dd>{review.rootCause.rootRelationshipId}</dd>
            </div>
            <div>
              <dt>Unresolved paths</dt>
              <dd>{review.technicalSummary.unresolvedPaths}</dd>
            </div>
          </dl>
        </article>
      </section>

      <section aria-labelledby="paths-title">
        <SectionHeading
          eyebrow="Certified evidence"
          title="Representative dependency paths"
          id="paths-title"
          supporting="Selected by the certified impact synthesis; no graph is recomputed in the browser."
        />
        <div className="path-grid">
          {review.representativePaths.map((path) => (
            <article className="path-card" key={path.pathId}>
              <div className="path-card-head">
                <span className="path-icon" aria-hidden="true">
                  <Route size={17} />
                </span>
                <StatusBadge tone="neutral">
                  {humanize(path.kind)}
                </StatusBadge>
                <span>{path.hopCount} hops</span>
              </div>
              <div className="path-endpoints">
                <div>
                  <small>Source</small>
                  <strong>{path.sourceField.fieldPath}</strong>
                </div>
                <ArrowRight size={18} aria-hidden="true" />
                <div>
                  <small>Downstream</small>
                  <strong>{path.downstreamField.fieldPath}</strong>
                </div>
              </div>
              <p>{path.explanation}</p>
              <code title={path.contextAssetId}>
                {compactIdentifier(path.contextAssetId, 20)}
              </code>
            </article>
          ))}
        </div>
      </section>

      <section aria-labelledby="context-title">
        <SectionHeading
          eyebrow="Connected context"
          title="Certified context highlights"
          id="context-title"
          supporting={`${review.scopeSummary.connectedContextAssets} assets are connected in total. These highlights are the certified representative selection.`}
        />
        <div className="context-grid">
          {review.contextHighlights.map((item) => (
            <article className="context-card" key={item.highlightId}>
              <ContextIcon kind={item.kind} />
              <div>
                <span>{humanize(item.kind)}</span>
                <strong>
                  {item.displayName ??
                    compactIdentifier(item.subjectId, 18)}
                </strong>
                <small>
                  {item.supportingFieldCount} supporting field
                  {item.supportingFieldCount === 1 ? "" : "s"}
                </small>
              </div>
            </article>
          ))}
        </div>
      </section>

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

function ContextIcon({ kind }: { kind: string }) {
  const Icon =
    kind === "technical_dataset"
      ? Database
      : kind === "pipeline_context"
        ? GitBranch
        : kind === "bi_consumer"
          ? Layers3
          : kind === "data_product"
            ? Sparkles
            : kind === "associated_owner"
              ? ShieldCheck
              : Network;
  return (
    <span className="context-icon" aria-hidden="true">
      <Icon size={17} />
    </span>
  );
}
