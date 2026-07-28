"""Read-only queries over a materialized Phase 4.3 artifact."""

from __future__ import annotations

from chronos.snapshot import FieldMachineKey

from .models import (
    BreadthMetrics,
    ChangeLevelSeverityProfile,
    ContextAssetSignificanceAssessment,
    CriticalityEvidence,
    DatasetSeverityAssessment,
    FieldSeverityAssessment,
    MissingEvidence,
    SeverityCriticalityAnalysis,
)


def get_change_severity_profile(
    result: SeverityCriticalityAnalysis,
) -> ChangeLevelSeverityProfile:
    return result.change_level_profile


def get_field_assessment(
    result: SeverityCriticalityAnalysis,
    field_key: FieldMachineKey,
) -> FieldSeverityAssessment | None:
    return next(
        (
            item
            for item in result.field_assessments
            if item.field_key == field_key
        ),
        None,
    )


def get_dataset_assessment(
    result: SeverityCriticalityAnalysis,
    dataset_urn: str,
) -> DatasetSeverityAssessment | None:
    return next(
        (
            item
            for item in result.dataset_assessments
            if item.dataset_urn == dataset_urn
        ),
        None,
    )


def get_context_asset_assessment(
    result: SeverityCriticalityAnalysis,
    asset_id: str,
) -> ContextAssetSignificanceAssessment | None:
    return next(
        (
            item
            for item in result.context_asset_assessments
            if item.context_asset_id == asset_id
        ),
        None,
    )


def get_criticality_evidence(
    result: SeverityCriticalityAnalysis,
    subject_id: str,
) -> tuple[CriticalityEvidence, ...]:
    return tuple(
        item
        for item in result.criticality_evidence
        if item.subject_id == subject_id
    )


def get_breadth_evidence(
    result: SeverityCriticalityAnalysis,
    subject_id: str,
) -> tuple[BreadthMetrics, ...]:
    return tuple(
        item
        for item in result.breadth_metrics
        if item.subject_id == subject_id
    )


def get_missing_evidence(
    result: SeverityCriticalityAnalysis,
    subject_id: str,
) -> tuple[MissingEvidence, ...]:
    return tuple(
        item
        for item in result.missing_evidence
        if item.subject_id == subject_id
    )
