"""Certified artifact loading and deterministic presentation mapping."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, TypeVar

from chronos.counterfactual_source import (
    CounterfactualSourceState,
    load_source_state,
)
from chronos.impact_synthesis import ImpactSynthesis, load_impact_synthesis
from chronos.phase4_certification import (
    CertificationCheckStatus,
    Phase4CertificationResult,
    Phase4CertificationStatus,
    load_phase4_certification,
    validate_phase4_certification,
)
from chronos.proposal import ChangeProposal, load_proposal

from .errors import CertifiedReviewNotFound, PresentationIntegrityError
from .models import (
    BlockingQuestionDTO,
    CertificationDTO,
    CertifiedChangeReview,
    ChangeDTO,
    ContextHighlightDTO,
    DecisionDTO,
    DecisionReasonDTO,
    FieldIdentityDTO,
    RepresentativePathDTO,
    RequiredEvidenceDTO,
    RootCauseDTO,
    ScopeSummaryDTO,
    SeverityDistributionDTO,
    SeverityProfileDTO,
    SourceStateDTO,
    TechnicalSummaryDTO,
)


EXPECTED_PHASE4_CERTIFICATION_FINGERPRINT = (
    "sha256:3e8444ec904e0ba1c55c5ae22d69edfa"
    "8e722310f51ab30fc783b8175a87ac4a"
)
SUPPORTED_REVIEW_ID = "CHRONOS-DEMO-001"
_T = TypeVar("_T")


class CertifiedReviewService:
    """Load one certified review without adding decision semantics."""

    def __init__(
        self,
        artifact_dir: str | Path,
        *,
        expected_fingerprint: str = (
            EXPECTED_PHASE4_CERTIFICATION_FINGERPRINT
        ),
    ) -> None:
        self._artifact_dir = Path(artifact_dir)
        self._expected_fingerprint = expected_fingerprint

    def get_review(self, review_id: str) -> CertifiedChangeReview:
        if review_id != SUPPORTED_REVIEW_ID:
            raise CertifiedReviewNotFound(
                f"Certified review {review_id!r} was not found."
            )

        certification = self._load(
            "phase_4_certification.json",
            load_phase4_certification,
        )
        try:
            validate_phase4_certification(certification)
        except Exception as exc:
            raise PresentationIntegrityError(
                "Phase 4 certification validation failed."
            ) from exc
        if (
            certification.certification_status
            is not Phase4CertificationStatus.CERTIFIED
            or certification.semantic_fingerprint
            != self._expected_fingerprint
            or any(
                check.status is not CertificationCheckStatus.PASS
                for check in certification.certification_checks
            )
        ):
            raise PresentationIntegrityError(
                "Phase 4 certification gate rejected the artifact."
            )

        proposal = self._load("change_proposal.json", load_proposal)
        synthesis = self._load(
            "impact_synthesis.json", load_impact_synthesis
        )
        source_state = self._load(
            "counterfactual_source_state.json", load_source_state
        )
        identities = {
            item.artifact_name: item.semantic_fingerprint
            for item in certification.input_artifact_identities
        }
        for name, actual in (
            ("change_proposal.json", proposal.semantic_fingerprint),
            ("impact_synthesis.json", synthesis.semantic_fingerprint),
            (
                "counterfactual_source_state.json",
                source_state.semantic_fingerprint,
            ),
        ):
            if identities.get(name) != actual:
                raise PresentationIntegrityError(
                    f"Certified identity mismatch for {name}."
                )
        if not (
            proposal.demonstration_id
            == synthesis.demonstration_id
            == source_state.demonstration_id
            == certification.demonstration_id
            == review_id
            and proposal.proposal_id
            == synthesis.proposal_id
            == certification.proposal_id
        ):
            raise PresentationIntegrityError(
                "Certified artifact identities are inconsistent."
            )
        return _map_review(
            certification=certification,
            proposal=proposal,
            synthesis=synthesis,
            source_state=source_state,
        )

    def _load(self, name: str, loader: Callable[[Path], _T]) -> _T:
        try:
            return loader(self._artifact_dir / name)
        except Exception as exc:
            raise PresentationIntegrityError(
                f"Certified artifact {name} could not be loaded."
            ) from exc


def _map_review(
    *,
    certification: Phase4CertificationResult,
    proposal: ChangeProposal,
    synthesis: ImpactSynthesis,
    source_state: CounterfactualSourceState,
) -> CertifiedChangeReview:
    technical = certification.technical_baseline
    context = certification.context_baseline
    severity = certification.severity_baseline
    decision = certification.decision_baseline
    candidate = next(
        item
        for item in source_state.candidate_source_schema.fields
        if item.field_path == proposal.change.requested_after.field_path
    )
    reasons_by_code = {
        item.reason_code.value: item for item in synthesis.decision_reasons
    }
    return CertifiedChangeReview(
        certification=CertificationDTO(
            status=certification.certification_status.value,
            fingerprint=certification.semantic_fingerprint,
            certified_at=certification.certified_at,
            checks_passed=sum(
                item.status is CertificationCheckStatus.PASS
                for item in certification.certification_checks
            ),
            check_count=len(certification.certification_checks),
            scope_statement=certification.scope_statement,
        ),
        change=ChangeDTO(
            demonstration_id=proposal.demonstration_id,
            proposal_id=proposal.proposal_id,
            operation=proposal.change_type.value,
            dataset_urn=proposal.change.target.dataset_urn,
            display_identity=(
                proposal.change.target.display_identity
                or proposal.change.target.dataset_urn
            ),
            platform=proposal.change.target.platform or "unknown",
            environment=proposal.change.target.environment or "unknown",
            current_field=proposal.change.before.field_path,
            requested_field=proposal.change.requested_after.field_path,
            description=proposal.description,
            rationale=proposal.rationale,
        ),
        decision=DecisionDTO(
            disposition=decision.disposition,
            disposition_label=_label(decision.disposition),
            decision_certainty=decision.decision_certainty,
            technical_certainty=decision.technical_certainty,
            decision_rule_id=decision.decision_rule_id,
            reasons=tuple(
                DecisionReasonDTO(
                    code=code,
                    statement=reasons_by_code[code].statement,
                )
                for code in decision.decision_reason_codes
            ),
            narrative=synthesis.assessment.narrative,
        ),
        technical_summary=TechnicalSummaryDTO(
            change_origins=technical.change_origins,
            root_causes=technical.technical_root_causes,
            relationship_impacts=technical.relationship_impacts,
            dependency_paths=technical.path_impacts,
            downstream_fields=technical.downstream_fields,
            downstream_datasets=technical.downstream_datasets,
            confirmed_downstream_failures=(
                technical.confirmed_downstream_failures
            ),
            potential_relationships=technical.potential_relationships,
            unresolved_relationships=technical.unresolved_relationships,
            unresolved_paths=technical.unresolved_paths,
            unresolved_fields=technical.unresolved_fields,
        ),
        scope_summary=ScopeSummaryDTO(
            datasets=context.technical_scope_datasets,
            downstream_fields=technical.downstream_fields,
            connected_context_assets=context.unique_context_assets,
            context_relationships=context.scoped_context_relationships,
            field_to_context_mappings=context.field_to_context_mappings,
            context_categories=context.context_categories,
            unresolved_context_references=(
                context.unresolved_context_references
            ),
        ),
        severity_profile=SeverityProfileDTO(
            technical_consequence=severity.technical_consequence,
            technical_certainty=severity.technical_certainty,
            context_criticality=severity.context_criticality,
            breadth=severity.breadth,
            sensitivity=severity.sensitivity,
            severity_if_realized=severity.severity_if_realized,
            field_distribution=SeverityDistributionDTO(
                **severity.field_distribution.__dict__
            ),
            dataset_distribution=SeverityDistributionDTO(
                **severity.dataset_distribution.__dict__
            ),
        ),
        root_cause=RootCauseDTO(
            root_cause_id=technical.root_cause_id,
            root_relationship_id=technical.root_relationship_id,
            title="Unresolved source rename boundary",
            explanation=synthesis.source_change.human_explanation,
        ),
        blocking_questions=tuple(
            BlockingQuestionDTO(
                question_id=item.question_id,
                question=item.question,
                subject=item.subject,
                reason=item.reason,
                resolution_state=item.resolution_state.value,
                affected_fields=len(item.affected_field_keys),
                affected_datasets=len(item.affected_dataset_urns),
                affected_paths=len(item.affected_path_ids),
                required_evidence_ids=item.required_evidence_ids,
            )
            for item in synthesis.blocking_questions
        ),
        required_evidence=tuple(
            RequiredEvidenceDTO(
                evidence_id=item.required_evidence_id,
                evidence_class=item.evidence_class,
                subject=item.subject,
                reason=item.reason,
                state=item.state.value,
            )
            for item in synthesis.required_evidence
        ),
        representative_paths=tuple(
            RepresentativePathDTO(
                path_id=item.representative_path_id,
                kind=item.kind.value,
                technical_path_id=item.technical_path_id,
                source_field=FieldIdentityDTO(
                    dataset_urn=item.source_field.dataset_urn,
                    field_path=item.source_field.field_path,
                ),
                downstream_field=FieldIdentityDTO(
                    dataset_urn=item.downstream_field.dataset_urn,
                    field_path=item.downstream_field.field_path,
                ),
                downstream_dataset_urn=item.downstream_dataset_urn,
                context_asset_id=item.context_asset_id,
                unresolved_boundary_relationship_id=(
                    item.unresolved_boundary_relationship_id
                ),
                relationship_ids=item.ordered_relationship_ids,
                hop_count=len(item.ordered_relationship_ids),
                explanation=item.explanation,
            )
            for item in synthesis.representative_evidence_paths
        ),
        context_highlights=tuple(
            ContextHighlightDTO(
                highlight_id=item.highlight_id,
                kind=item.kind.value,
                subject_id=item.subject_id,
                display_name=item.display_name,
                selection_basis=item.selection_basis,
                supporting_dataset_urns=item.supporting_dataset_urns,
                supporting_field_count=len(item.supporting_field_keys),
            )
            for item in synthesis.context_highlights
        ),
        current_state=SourceStateDTO(
            classification="certified_current",
            dataset_urn=proposal.change.target.dataset_urn,
            field_path=proposal.change.before.field_path,
            field_name=proposal.change.before.field_name,
            native_type=proposal.change.before.native_type,
            normalized_type=proposal.change.before.normalized_type,
            schema_field_count=(
                source_state.current_source_schema_reference.field_count
            ),
        ),
        counterfactual_state=SourceStateDTO(
            classification=source_state.state_classification.value,
            dataset_urn=source_state.dataset_identity.dataset_urn,
            field_path=candidate.field_path,
            field_name=candidate.field_name,
            native_type=candidate.native_type,
            normalized_type=candidate.normalized_type,
            schema_field_count=len(
                source_state.candidate_source_schema.fields
            ),
        ),
    )


def _label(value: str) -> str:
    return value.replace("_", " ").strip().title()
