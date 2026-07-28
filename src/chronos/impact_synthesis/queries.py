"""Read-only queries over a materialized Phase 4.4 artifact."""

from __future__ import annotations

from .models import (
    BlockingQuestion,
    ChangeReviewAssessment,
    ContextHighlight,
    DecisionDisposition,
    DecisionReason,
    ImpactSynthesis,
    ImpactSynthesisSummary,
    RepresentativeEvidencePath,
    RequiredEvidence,
)


def get_change_assessment(
    result: ImpactSynthesis,
) -> ChangeReviewAssessment:
    return result.assessment


def get_disposition(result: ImpactSynthesis) -> DecisionDisposition:
    return result.decision_disposition


def get_blocking_questions(
    result: ImpactSynthesis,
) -> tuple[BlockingQuestion, ...]:
    return result.blocking_questions


def get_required_evidence(
    result: ImpactSynthesis,
) -> tuple[RequiredEvidence, ...]:
    return result.required_evidence


def get_decision_reasons(
    result: ImpactSynthesis,
) -> tuple[DecisionReason, ...]:
    return result.decision_reasons


def get_scope_summary(
    result: ImpactSynthesis,
) -> ImpactSynthesisSummary:
    return result.scope_summary


def get_representative_paths(
    result: ImpactSynthesis,
) -> tuple[RepresentativeEvidencePath, ...]:
    return result.representative_evidence_paths


def get_context_highlights(
    result: ImpactSynthesis,
) -> tuple[ContextHighlight, ...]:
    return result.context_highlights
