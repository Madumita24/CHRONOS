from __future__ import annotations

import hashlib
import json
import socket
import tempfile
import unittest
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from chronos.business_context import load_business_context
from chronos.explanations import load_explanation_bundle
from chronos.impact_synthesis import (
    DEFAULT_DECISION_RULES,
    DecisionCertainty,
    DecisionDisposition,
    DecisionReasonCode,
    DecisionRuleInputs,
    ImpactSynthesisEntryError,
    ImpactSynthesisSerializationError,
    ImpactSynthesisValidationError,
    RequiredEvidenceState,
    evaluate_decision,
    export_impact_synthesis,
    get_blocking_questions,
    get_change_assessment,
    get_context_highlights,
    get_decision_reasons,
    get_disposition,
    get_representative_paths,
    get_required_evidence,
    get_scope_summary,
    impact_synthesis_from_json,
    impact_synthesis_semantic_fingerprint,
    load_impact_synthesis,
    synthesize_impact,
    synthesize_impact_from_artifacts,
    validate_impact_synthesis,
)
from chronos.phase3_certification import load_phase3_certification
from chronos.severity_criticality import (
    ContextCriticality,
    EvidenceCertainty,
    ExposureBreadth,
    SeverityIfRealized,
    TechnicalConsequence,
    load_severity_analysis,
)
from chronos.snapshot import contains_secret
from chronos.technical_impact import load_technical_impact


ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "artifacts"
NAMES = (
    "current_metadata_snapshot.json",
    "change_proposal.json",
    "change_proposal_validation.json",
    "change_semantic_contract.json",
    "phase_2_certification.json",
    "counterfactual_source_state.json",
    "future_metadata_graph.json",
    "dependency_propagation.json",
    "compatibility_evaluation.json",
    "explanation_bundle.json",
    "phase_3_certification.json",
    "technical_impact_analysis.json",
    "business_context_propagation.json",
    "severity_criticality_analysis.json",
)
PATHS = tuple(ARTIFACTS / name for name in NAMES)
CAUSE = "technical-impact-cause-source-rename-semantics"


def fixed_clock(hour: int):
    return lambda: datetime(2026, 7, 28, hour, tzinfo=timezone.utc)


class ImpactSynthesisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.before_hashes = {
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in PATHS
        }
        cls.phase3 = load_phase3_certification(PATHS[10])
        cls.technical = load_technical_impact(PATHS[11])
        cls.context = load_business_context(PATHS[12])
        cls.severity = load_severity_analysis(PATHS[13])
        cls.explanations = load_explanation_bundle(PATHS[9])
        cls.result = cls.build(18)

    @classmethod
    def build(cls, hour: int):
        return synthesize_impact_from_artifacts(
            *PATHS, clock=fixed_clock(hour)
        )

    def derive(
        self,
        *,
        phase3=None,
        technical=None,
        context=None,
        severity=None,
        explanations=None,
    ):
        return synthesize_impact(
            phase3 or self.phase3,
            technical or self.technical,
            context or self.context,
            severity or self.severity,
            explanations or self.explanations,
            input_artifact_hashes=self.result.input_artifact_hashes,
            clock=fixed_clock(19),
        )

    def validate(self, value) -> None:
        validate_impact_synthesis(
            value,
            self.phase3,
            self.technical,
            self.context,
            self.severity,
            self.explanations,
        )

    def test_01_canonical_synthesis_succeeds(self) -> None:
        self.validate(self.result)
        self.assertEqual(
            self.result.decision_disposition,
            DecisionDisposition.HOLD_FOR_REVIEW,
        )

    def test_02_phase3_certification_required(self) -> None:
        fingerprints = replace(
            self.phase3.phase_3_semantic_fingerprints,
            explanation_bundle="sha256:" + "0" * 64,
        )
        invalid = replace(
            self.phase3,
            phase_3_semantic_fingerprints=fingerprints,
        )
        with self.assertRaises(ImpactSynthesisEntryError):
            self.derive(phase3=invalid)

    def test_03_phase41_required(self) -> None:
        invalid = replace(
            self.technical, proposal_id="different-proposal"
        )
        with self.assertRaises(ImpactSynthesisEntryError):
            self.derive(technical=invalid)

    def test_04_phase42_required(self) -> None:
        invalid = replace(
            self.context,
            technical_impact_fingerprint="sha256:" + "0" * 64,
        )
        with self.assertRaises(ImpactSynthesisEntryError):
            self.derive(context=invalid)

    def test_05_phase43_required(self) -> None:
        invalid = replace(
            self.severity,
            business_context_fingerprint="sha256:" + "0" * 64,
        )
        with self.assertRaises(ImpactSynthesisEntryError):
            self.derive(severity=invalid)

    def test_06_exactly_one_decision_exists(self) -> None:
        self.assertIsNotNone(self.result.assessment)
        self.assertFalse(hasattr(self.result, "assessments"))

    def test_07_rule_registry_is_serialized(self) -> None:
        self.assertEqual(
            self.result.decision_rule_registry,
            DEFAULT_DECISION_RULES,
        )
        self.assertEqual(len(self.result.decision_rule_registry), 4)

    def test_08_canonical_rule_is_deterministic(self) -> None:
        first = evaluate_decision(self.result.change_severity_profile)
        second = evaluate_decision(self.result.change_severity_profile)
        self.assertEqual(first, second)
        self.assertEqual(
            first.rule_id,
            "decision-hold-unresolved-material-broad",
        )

    def test_09_disposition_derives_from_evidence(self) -> None:
        selected = evaluate_decision(
            self.result.assessment.selected_rule_inputs
        )
        self.assertEqual(
            selected.disposition, self.result.decision_disposition
        )

    def test_10_decision_certainty_is_distinct(self) -> None:
        self.assertEqual(
            self.result.decision_certainty,
            DecisionCertainty.HIGH_CONFIDENCE,
        )
        self.assertEqual(
            self.result.change_severity_profile.impact_certainty,
            EvidenceCertainty.UNRESOLVED,
        )

    def test_11_zero_confirmed_breakages_preserved(self) -> None:
        self.assertEqual(
            self.result.scope_summary.confirmed_downstream_failures, 0
        )

    def test_12_technical_scope_preserved(self) -> None:
        scope = self.result.scope_summary
        self.assertEqual(scope.unresolved_downstream_fields, 25)
        self.assertEqual(scope.downstream_datasets, 20)
        self.assertEqual(scope.unresolved_paths, 48)
        self.assertEqual(len(scope.downstream_field_keys), 25)
        self.assertEqual(len(scope.downstream_dataset_urns), 20)

    def test_13_context_is_connected_scope_not_impact(self) -> None:
        scope = self.result.scope_summary
        self.assertEqual(scope.context_assets, 66)
        self.assertEqual(scope.context_relationships, 211)
        self.assertEqual(scope.field_to_context_mappings, 257)
        self.assertIn(
            "connected to the unresolved technical cone",
            self.result.assessment.narrative,
        )
        self.assertNotIn(
            "66 impacted assets", self.result.assessment.narrative
        )

    def test_14_root_cause_remains_consolidated(self) -> None:
        self.assertEqual(self.result.root_causes, (CAUSE,))

    def test_15_one_canonical_blocking_question(self) -> None:
        questions = self.result.blocking_questions
        self.assertEqual(len(questions), 1)
        self.assertIn("Spark export mapping", questions[0].question)
        self.assertEqual(questions[0].root_cause_id, CAUSE)

    def test_16_required_evidence_is_preserved(self) -> None:
        classes = {
            item.evidence_class for item in self.result.required_evidence
        }
        self.assertEqual(
            classes,
            {
                "spark_transformation_configuration",
                "input_column_reference_query_or_code",
                "explicit_rename_mapping",
                "validated_execution_result",
            },
        )
        self.assertTrue(
            all(
                item.state
                is RequiredEvidenceState.REQUIRED_FOR_DECISION_RESOLUTION
                for item in self.result.required_evidence
            )
        )

    def test_17_no_repair_or_workflow_semantics(self) -> None:
        value = self.result.to_json().lower()
        for term in (
            "sql patch",
            "spark patch",
            "migration plan",
            "repair proposal",
            "remediation order",
            "notification priority",
        ):
            self.assertNotIn(term, value)

    def test_18_no_numeric_score_or_probability(self) -> None:
        value = self.result.to_json().lower()
        self.assertNotIn("risk_score", value)
        self.assertNotIn("failure_probability", value)
        self.assertNotIn("confidence_percentage", value)

    def test_19_widespread_alone_cannot_block(self) -> None:
        result = evaluate_decision(
            DecisionRuleInputs(
                TechnicalConsequence.NO_DEMONSTRATED_IMPACT,
                EvidenceCertainty.ESTABLISHED,
                SeverityIfRealized.UNDETERMINED,
                ExposureBreadth.WIDESPREAD,
                ContextCriticality.ELEVATED_CONTEXT,
                False,
            )
        )
        self.assertEqual(result.disposition, DecisionDisposition.PROCEED)

    def test_20_high_alone_is_not_confirmed_failure(self) -> None:
        inputs = self.result.change_severity_profile
        self.assertEqual(
            inputs.severity_if_realized, SeverityIfRealized.HIGH
        )
        self.assertEqual(
            inputs.technical_consequence,
            TechnicalConsequence.UNRESOLVED_IMPACT,
        )

    def test_21_unresolved_material_consequence_holds(self) -> None:
        result = evaluate_decision(self.result.change_severity_profile)
        self.assertEqual(
            result.disposition, DecisionDisposition.HOLD_FOR_REVIEW
        )

    def test_22_synthetic_no_impact_proceeds(self) -> None:
        inputs = DecisionRuleInputs(
            TechnicalConsequence.NO_DEMONSTRATED_IMPACT,
            EvidenceCertainty.ESTABLISHED,
            SeverityIfRealized.UNDETERMINED,
            ExposureBreadth.LOCAL,
            ContextCriticality.STANDARD_CONTEXT,
            False,
        )
        self.assertEqual(
            evaluate_decision(inputs).disposition,
            DecisionDisposition.PROCEED,
        )

    def test_23_synthetic_conditional_case(self) -> None:
        inputs = DecisionRuleInputs(
            TechnicalConsequence.POTENTIAL_IMPACT,
            EvidenceCertainty.CONDITIONAL,
            SeverityIfRealized.MODERATE,
            ExposureBreadth.BROAD,
            ContextCriticality.STANDARD_CONTEXT,
            True,
        )
        self.assertEqual(
            evaluate_decision(inputs).disposition,
            DecisionDisposition.PROCEED_WITH_CONDITIONS,
        )

    def test_24_synthetic_confirmed_incompatibility(self) -> None:
        inputs = DecisionRuleInputs(
            TechnicalConsequence.CONFIRMED_IMPACT,
            EvidenceCertainty.ESTABLISHED,
            SeverityIfRealized.HIGH,
            ExposureBreadth.LIMITED,
            ContextCriticality.STANDARD_CONTEXT,
            False,
        )
        self.assertEqual(
            evaluate_decision(inputs).disposition,
            DecisionDisposition.BLOCK_CONFIRMED_INCOMPATIBILITY,
        )

    def test_25_selected_inputs_and_reasons_serialized(self) -> None:
        raw = self.result.to_dict()
        self.assertIn("selected_rule_inputs", raw["assessment"])
        self.assertEqual(
            raw["decision_reason_codes"],
            [item.value for item in self.result.decision_reason_codes],
        )

    def test_26_reason_codes_resolve_to_typed_evidence(self) -> None:
        evidence_ids = {
            item.evidence_id for item in self.result.decision_evidence
        }
        self.assertTrue(
            all(
                reason.evidence_ids
                and set(reason.evidence_ids) <= evidence_ids
                for reason in self.result.decision_reasons
            )
        )

    def test_27_representative_paths_resolve(self) -> None:
        path_ids = {
            item.path_id for item in self.technical.path_impacts
        }
        mapping_ids = {
            item.mapping_id
            for item in self.context.technical_to_context_mappings
        }
        self.assertEqual(len(self.result.representative_evidence_paths), 3)
        for item in self.result.representative_evidence_paths:
            self.assertIn(item.technical_path_id, path_ids)
            self.assertIn(item.context_mapping_id, mapping_ids)

    def test_28_context_highlights_are_deterministic(self) -> None:
        other = self.build(20)
        self.assertEqual(
            self.result.context_highlights, other.context_highlights
        )
        self.assertTrue(self.result.context_highlights)
        self.assertNotIn(
            "highest risk",
            json.dumps(
                [item.selection_basis for item in self.result.context_highlights]
            ).lower(),
        )

    def test_29_provenance_closes(self) -> None:
        sources = {
            item.source_artifact for item in self.result.decision_evidence
        }
        self.assertEqual(
            sources,
            {
                "phase_3_certification.json",
                "technical_impact_analysis.json",
                "business_context_propagation.json",
                "severity_criticality_analysis.json",
                "explanation_bundle.json",
            },
        )

    def test_30_deterministic_serialization_and_ordering(self) -> None:
        other = self.build(21)
        self.assertEqual(self.result.semantic_json(), other.semantic_json())
        self.assertEqual(
            self.result.semantic_fingerprint, other.semantic_fingerprint
        )
        self.assertEqual(
            tuple(item.rule_id for item in self.result.decision_rule_registry),
            tuple(
                item.rule_id
                for item in sorted(
                    self.result.decision_rule_registry,
                    key=lambda item: item.precedence,
                )
            ),
        )

    def test_31_timestamp_is_not_semantic(self) -> None:
        other = self.build(22)
        self.assertNotEqual(self.result.created_at, other.created_at)
        self.assertEqual(
            self.result.semantic_fingerprint, other.semantic_fingerprint
        )

    def test_32_semantic_mutation_changes_fingerprint(self) -> None:
        altered = replace(
            self.result.scope_summary, context_assets=65
        )
        altered_assessment = replace(
            self.result.assessment, scope_summary=altered
        )
        changed = replace(
            self.result,
            scope_summary=altered,
            assessment=altered_assessment,
        )
        self.assertNotEqual(
            self.result.semantic_fingerprint, changed.semantic_fingerprint
        )
        with self.assertRaises(ImpactSynthesisValidationError):
            self.validate(changed)

    def test_33_serialization_round_trip(self) -> None:
        loaded = impact_synthesis_from_json(self.result.to_json())
        self.assertTrue(self.result.semantically_equals(loaded))

    def test_34_stored_fingerprint_is_verified(self) -> None:
        value = self.result.to_json().replace(
            self.result.semantic_fingerprint,
            "sha256:" + "0" * 64,
            1,
        )
        with self.assertRaises(ImpactSynthesisSerializationError):
            impact_synthesis_from_json(value)

    def test_35_export_and_load_public_api(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = export_impact_synthesis(
                self.result, Path(directory) / "impact.json"
            )
            loaded = load_impact_synthesis(path)
        self.assertTrue(self.result.semantically_equals(loaded))

    def test_36_public_fingerprint_helper_matches(self) -> None:
        self.assertEqual(
            impact_synthesis_semantic_fingerprint(self.result),
            self.result.semantic_fingerprint,
        )

    def test_37_input_artifacts_unchanged(self) -> None:
        after = {
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in PATHS
        }
        self.assertEqual(self.before_hashes, after)
        self.assertTrue(
            all(item.unchanged for item in self.result.input_artifact_hashes)
        )

    def test_38_offline_execution(self) -> None:
        with patch.object(
            socket, "create_connection", side_effect=AssertionError
        ), patch.object(socket.socket, "connect", side_effect=AssertionError):
            result = self.build(23)
        self.assertEqual(
            result.decision_disposition,
            DecisionDisposition.HOLD_FOR_REVIEW,
        )

    def test_39_secret_scanning(self) -> None:
        self.assertFalse(contains_secret(self.result.to_dict()))

    def test_40_read_only_query_api(self) -> None:
        self.assertIs(get_change_assessment(self.result), self.result.assessment)
        self.assertEqual(
            get_disposition(self.result), self.result.decision_disposition
        )
        self.assertEqual(
            get_blocking_questions(self.result),
            self.result.blocking_questions,
        )
        self.assertEqual(
            get_required_evidence(self.result),
            self.result.required_evidence,
        )
        self.assertEqual(
            get_decision_reasons(self.result),
            self.result.decision_reasons,
        )
        self.assertIs(get_scope_summary(self.result), self.result.scope_summary)
        self.assertEqual(
            get_representative_paths(self.result),
            self.result.representative_evidence_paths,
        )
        self.assertEqual(
            get_context_highlights(self.result),
            self.result.context_highlights,
        )

    def test_41_models_are_immutable(self) -> None:
        with self.assertRaises(FrozenInstanceError):
            self.result.assessment.narrative = "changed"

    def test_42_ambiguous_rule_precedence_fails_closed(self) -> None:
        duplicate = replace(
            DEFAULT_DECISION_RULES[1], rule_id="duplicate-hold-rule"
        )
        with self.assertRaises(ImpactSynthesisValidationError):
            evaluate_decision(
                self.result.change_severity_profile,
                rules=(
                    DEFAULT_DECISION_RULES[1],
                    duplicate,
                ),
            )

    def test_43_missing_rule_id_fails_closed(self) -> None:
        invalid_assessment = replace(
            self.result.assessment, decision_rule_id="missing-rule"
        )
        with self.assertRaises(ValueError):
            replace(self.result, assessment=invalid_assessment)

    def test_44_dangling_question_fails_closed(self) -> None:
        invalid_assessment = replace(
            self.result.assessment,
            blocking_question_ids=("missing-question",),
        )
        with self.assertRaises(ValueError):
            replace(self.result, assessment=invalid_assessment)

    def test_45_dangling_required_evidence_fails_closed(self) -> None:
        question = replace(
            self.result.blocking_questions[0],
            required_evidence_ids=("missing-evidence",),
        )
        with self.assertRaises(ValueError):
            replace(self.result, blocking_questions=(question,))

    def test_46_technical_state_mutation_fails_closed(self) -> None:
        altered = replace(
            self.technical.aggregate_metrics, unresolved_fields=24
        )
        invalid = replace(self.technical, aggregate_metrics=altered)
        with self.assertRaises(ImpactSynthesisEntryError):
            self.derive(technical=invalid)

    def test_47_severity_mutation_fails_closed(self) -> None:
        profile = replace(
            self.severity.change_level_profile,
            severity_if_realized=SeverityIfRealized.MODERATE,
        )
        invalid = replace(self.severity, change_level_profile=profile)
        with self.assertRaises(ImpactSynthesisEntryError):
            self.derive(severity=invalid)

    def test_48_breadth_mutation_fails_closed(self) -> None:
        profile = replace(
            self.severity.change_level_profile,
            exposure_breadth=ExposureBreadth.BROAD,
        )
        invalid = replace(self.severity, change_level_profile=profile)
        with self.assertRaises(ImpactSynthesisEntryError):
            self.derive(severity=invalid)

    def test_49_criticality_mutation_fails_closed(self) -> None:
        profile = replace(
            self.severity.change_level_profile,
            context_criticality=ContextCriticality.EXPLICITLY_CRITICAL,
        )
        invalid = replace(self.severity, change_level_profile=profile)
        with self.assertRaises(ImpactSynthesisEntryError):
            self.derive(severity=invalid)

    def test_50_unknown_cannot_become_confirmed(self) -> None:
        profile = replace(
            self.severity.change_level_profile,
            technical_consequence=TechnicalConsequence.CONFIRMED_IMPACT,
        )
        invalid = replace(self.severity, change_level_profile=profile)
        with self.assertRaises(ImpactSynthesisEntryError):
            self.derive(severity=invalid)

    def test_51_narrative_preserves_careful_language(self) -> None:
        narrative = self.result.assessment.narrative.lower()
        self.assertIn("not been proven incompatible", narrative)
        self.assertIn("does not assert a confirmed failure", narrative)
        self.assertIn("high if", narrative)
        self.assertNotIn("high probability", narrative)
        self.assertNotIn("mission-critical", narrative)

    def test_52_resolution_semantics_are_evidence_only(self) -> None:
        question = self.result.blocking_questions[0]
        self.assertEqual(
            set(question.required_evidence_ids),
            {
                item.required_evidence_id
                for item in self.result.required_evidence
            },
        )
        self.assertNotIn("modify", question.reason.lower())

    def test_53_source_not_counted_as_downstream(self) -> None:
        self.assertNotIn(
            self.result.source_change.current_field,
            self.result.scope_summary.downstream_field_keys,
        )
        self.assertNotIn(
            self.result.source_change.candidate_field,
            self.result.scope_summary.downstream_field_keys,
        )

    def test_54_reason_set_matches_selected_rule(self) -> None:
        self.assertEqual(
            tuple(item.reason_code for item in self.result.decision_reasons),
            self.result.decision_reason_codes,
        )
        self.assertIn(
            DecisionReasonCode.UNRESOLVED_SOURCE_COMPATIBILITY,
            self.result.decision_reason_codes,
        )

    def test_55_builder_has_no_live_client_or_llm_authority(self) -> None:
        source = (
            ROOT / "src" / "chronos" / "impact_synthesis" / "builder.py"
        ).read_text(encoding="utf-8").lower()
        self.assertNotIn("chronos.datahub", source)
        self.assertNotIn("requests", source)
        self.assertNotIn("openai", source)


if __name__ == "__main__":
    unittest.main()
