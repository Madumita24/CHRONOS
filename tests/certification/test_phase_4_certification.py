from __future__ import annotations

import hashlib
import json
import shutil
import socket
import tempfile
import unittest
from collections import Counter
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from chronos.business_context import (
    ContextCategory,
    load_business_context,
)
from chronos.change_semantics import load_contract
from chronos.compatibility_evaluation import (
    CompatibilityState,
    EvidenceStrength,
    load_compatibility_evaluation,
)
from chronos.counterfactual_source import load_source_state
from chronos.dependency_propagation import load_dependency_propagation
from chronos.explanations import load_explanation_bundle
from chronos.future_graph import load_future_graph
from chronos.impact_synthesis import (
    DecisionCertainty,
    DecisionDisposition,
    evaluate_decision,
    load_impact_synthesis,
)
from chronos.phase2_certification import (
    Phase2CertificationState,
    load_certification,
)
from chronos.phase3_certification import (
    Phase3CertificationStatus,
    load_phase3_certification,
    validate_phase3_certification,
)
from chronos.phase4_certification import (
    CertificationCheckCategory,
    CertificationCheckStatus,
    Phase4CertificationInputError,
    Phase4CertificationSerializationError,
    Phase4CertificationStatus,
    Phase4CertificationValidationError,
    certify_phase4,
    certify_phase4_from_artifacts,
    export_phase4_certification,
    load_phase4_certification,
    phase4_certification_from_json,
    phase4_certification_semantic_fingerprint,
    validate_phase4_certification,
)
from chronos.proposal import load_proposal
from chronos.proposal_validation import load_validation_result
from chronos.severity_criticality import (
    ContextCriticality,
    EvidenceCertainty,
    ExposureBreadth,
    SeverityIfRealized,
    TechnicalConsequence,
    derive_breadth,
    derive_severity_if_realized,
    load_severity_analysis,
)
from chronos.snapshot import (
    SnapshotValidationState,
    contains_secret,
    load_snapshot,
    validate_snapshot,
)
from chronos.technical_impact import (
    TechnicalImpactState,
    load_technical_impact,
)


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
    "impact_synthesis.json",
)
PATHS = tuple(ARTIFACTS / name for name in NAMES)
CAUSE = "technical-impact-cause-source-rename-semantics"
ROOT_EDGE = "future-lineage-68f7e0269dbea7279911b809"


def fixed_clock(hour: int):
    return lambda: datetime(2026, 7, 28, hour, tzinfo=timezone.utc)


class Phase4CertificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.before_hashes = {
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in PATHS
        }
        cls.snapshot = load_snapshot(PATHS[0])
        cls.proposal = load_proposal(PATHS[1])
        cls.validation = load_validation_result(PATHS[2])
        cls.contract = load_contract(PATHS[3])
        cls.phase2 = load_certification(PATHS[4])
        cls.source = load_source_state(PATHS[5])
        cls.graph = load_future_graph(PATHS[6])
        cls.propagation = load_dependency_propagation(PATHS[7])
        cls.compatibility = load_compatibility_evaluation(PATHS[8])
        cls.explanations = load_explanation_bundle(PATHS[9])
        cls.phase3 = load_phase3_certification(PATHS[10])
        cls.technical = load_technical_impact(PATHS[11])
        cls.context = load_business_context(PATHS[12])
        cls.severity = load_severity_analysis(PATHS[13])
        cls.synthesis = load_impact_synthesis(PATHS[14])
        cls.objects = (
            cls.snapshot,
            cls.proposal,
            cls.validation,
            cls.contract,
            cls.phase2,
            cls.source,
            cls.graph,
            cls.propagation,
            cls.compatibility,
            cls.explanations,
            cls.phase3,
            cls.technical,
            cls.context,
            cls.severity,
            cls.synthesis,
        )
        cls.result = cls.build(1)

    @classmethod
    def build(cls, hour: int):
        return certify_phase4_from_artifacts(
            *PATHS, clock=fixed_clock(hour)
        )

    def certify(self, **changes):
        objects = list(self.objects)
        indexes = {
            "snapshot": 0,
            "proposal": 1,
            "validation": 2,
            "contract": 3,
            "phase2": 4,
            "source": 5,
            "graph": 6,
            "propagation": 7,
            "compatibility": 8,
            "explanations": 9,
            "phase3": 10,
            "technical": 11,
            "context": 12,
            "severity": 13,
            "synthesis": 14,
        }
        for name, value in changes.items():
            objects[indexes[name]] = value
        return certify_phase4(
            *objects,
            input_artifact_identities=(
                self.result.input_artifact_identities
            ),
            artifact_immutability=self.result.artifact_immutability,
            reconstructed_fingerprints=(
                self.result.phase_4_semantic_fingerprints
            ),
            clock=fixed_clock(2),
        )

    def check(self, check_id: str):
        return next(
            item
            for item in self.result.certification_checks
            if item.check_id == check_id
        )

    def assert_failed(self, **changes) -> None:
        result = self.certify(**changes)
        self.assertIs(
            result.certification_status,
            Phase4CertificationStatus.FAILED,
        )

    def test_01_canonical_certification_succeeds(self) -> None:
        self.assertIs(
            self.result.certification_status,
            Phase4CertificationStatus.CERTIFIED,
        )
        validate_phase4_certification(self.result)

    def test_02_all_15_authoritative_artifacts_load(self) -> None:
        self.assertEqual(len(self.result.input_artifact_identities), 15)
        self.assertEqual(
            tuple(
                item.artifact_name
                for item in self.result.input_artifact_identities
            ),
            NAMES,
        )

    def test_03_all_fingerprints_reproduce(self) -> None:
        self.assertIs(
            self.check("determinism.phase_4_reconstruction").status,
            CertificationCheckStatus.PASS,
        )

    def test_04_complete_predecessor_chain_matches(self) -> None:
        self.assertIs(
            self.check("cross_reference.complete_artifact_chain").status,
            CertificationCheckStatus.PASS,
        )

    def test_05_demonstration_consistent(self) -> None:
        self.assertEqual(self.result.demonstration_id, "CHRONOS-DEMO-001")

    def test_06_proposal_consistent(self) -> None:
        self.assertEqual(
            self.result.proposal_id,
            "CHRONOS-DEMO-001-PROPOSAL-001",
        )

    def test_07_source_change_consistent(self) -> None:
        self.assertEqual(
            self.technical.source_change.current_field.field_path,
            "order_total",
        )
        self.assertEqual(
            self.technical.source_change.candidate_field.field_path,
            "order_amount",
        )

    def test_08_phase3_remains_certified(self) -> None:
        self.assertIs(
            self.phase3.certification_status,
            Phase3CertificationStatus.CERTIFIED,
        )
        validate_phase3_certification(self.phase3)

    def test_09_phase41_remains_valid(self) -> None:
        self.assertEqual(self.technical.validation_state.value, "valid")

    def test_10_one_technical_root_cause(self) -> None:
        self.assertEqual(len(self.technical.technical_impact_causes), 1)
        self.assertEqual(
            self.technical.technical_impact_causes[0].cause_id, CAUSE
        )

    def test_11_relationship_impact_count(self) -> None:
        self.assertEqual(len(self.technical.relationship_impacts), 27)

    def test_12_path_impact_count(self) -> None:
        self.assertEqual(len(self.technical.path_impacts), 48)

    def test_13_field_impact_count(self) -> None:
        self.assertEqual(len(self.technical.field_impacts), 25)

    def test_14_dataset_summary_count(self) -> None:
        self.assertEqual(len(self.technical.dataset_summaries), 20)

    def test_15_zero_confirmed_failures(self) -> None:
        self.assertEqual(
            self.result.technical_baseline.confirmed_downstream_failures,
            0,
        )

    def test_16_potential_relationship_count(self) -> None:
        self.assertEqual(
            self.result.technical_baseline.potential_relationships, 26
        )

    def test_17_one_unresolved_relationship(self) -> None:
        self.assertEqual(
            self.result.technical_baseline.unresolved_relationships, 1
        )

    def test_18_all_paths_unresolved(self) -> None:
        self.assertEqual(
            Counter(
                item.technical_impact_state
                for item in self.technical.path_impacts
            ),
            Counter({TechnicalImpactState.UNRESOLVED_IMPACT: 48}),
        )

    def test_19_all_fields_unresolved(self) -> None:
        self.assertEqual(
            Counter(
                item.technical_impact_state
                for item in self.technical.field_impacts
            ),
            Counter({TechnicalImpactState.UNRESOLVED_IMPACT: 25}),
        )

    def test_20_phase42_remains_valid(self) -> None:
        self.assertEqual(self.context.validation_state.value, "valid")

    def test_21_unique_context_assets(self) -> None:
        ids = {item.asset_id for item in self.context.context_asset_registry}
        self.assertEqual(len(ids), 66)
        self.assertEqual(len(ids), len(self.context.context_asset_registry))

    def test_22_scoped_context_relationships(self) -> None:
        self.assertEqual(len(self.context.context_link_registry), 211)

    def test_23_field_to_context_mappings(self) -> None:
        self.assertEqual(
            len(self.context.technical_to_context_mappings), 257
        )

    def test_24_context_deduplication(self) -> None:
        self.assertNotEqual(
            len(self.context.context_asset_registry),
            len(self.context.technical_to_context_mappings),
        )

    def test_25_context_scope_anchored(self) -> None:
        fields = {item.field_key for item in self.technical.field_impacts}
        self.assertTrue(
            all(
                item.technical_field_key in fields
                and item.technical_field_key.dataset_urn
                == item.dataset_urn
                for item in self.context.technical_to_context_mappings
            )
        )

    def test_26_unresolved_context_preserved(self) -> None:
        self.assertEqual(len(self.context.unresolved_context_references), 1)

    def test_27_phase43_remains_valid(self) -> None:
        self.assertEqual(self.severity.validation_state.value, "valid")

    def test_28_criticality_and_breadth_distinct(self) -> None:
        profile = self.severity.change_level_profile
        self.assertIs(
            profile.context_criticality,
            ContextCriticality.ELEVATED_CONTEXT,
        )
        self.assertIs(
            profile.exposure_breadth, ExposureBreadth.WIDESPREAD
        )

    def test_29_sensitivity_and_criticality_distinct(self) -> None:
        profile = self.severity.change_level_profile
        self.assertEqual(profile.sensitivity_state.value, "pii")
        self.assertIsNot(
            profile.context_criticality,
            ContextCriticality.EXPLICITLY_CRITICAL,
        )

    def test_30_canonical_criticality_elevated(self) -> None:
        self.assertEqual(
            self.result.severity_baseline.context_criticality,
            "elevated_context",
        )

    def test_31_explicit_criticality_absent(self) -> None:
        self.assertFalse(
            any(
                item.explicit_semantic_identity is not None
                for item in self.severity.criticality_evidence
            )
        )

    def test_32_canonical_breadth_widespread(self) -> None:
        self.assertEqual(
            self.result.severity_baseline.breadth, "widespread"
        )

    def test_33_breadth_rule_replay(self) -> None:
        profile = self.severity.change_level_profile
        metrics = next(
            item
            for item in self.severity.breadth_metrics
            if item.breadth_metrics_id == profile.breadth_metrics_id
        )
        state, rule = derive_breadth(
            supporting_datasets=metrics.supporting_datasets,
            consumer_assets=metrics.consumer_assets,
            context_assets=metrics.unique_context_assets,
            rules=self.severity.breadth_rule_registry,
        )
        self.assertIs(state, ExposureBreadth.WIDESPREAD)
        self.assertEqual(rule, "breadth-widespread-multi-channel")

    def test_34_canonical_certainty_unresolved(self) -> None:
        self.assertEqual(
            self.result.severity_baseline.technical_certainty,
            "unresolved",
        )

    def test_35_severity_rule_registry_valid(self) -> None:
        rules = self.severity.severity_rule_registry
        self.assertEqual(len(rules), 11)
        self.assertEqual(len({item.rule_id for item in rules}), 11)
        self.assertEqual(len({item.precedence for item in rules}), 11)

    def replay(self, assessment) -> None:
        result = derive_severity_if_realized(
            assessment.severity_rule_inputs.technical_consequence,
            assessment.severity_rule_inputs.context_criticality,
            assessment.severity_rule_inputs.exposure_breadth,
            assessment.severity_rule_inputs.evidence_certainty,
            rules=self.severity.severity_rule_registry,
        )
        self.assertEqual(result.rule_id, assessment.severity_rule_id)
        self.assertIs(
            result.severity_if_realized,
            assessment.severity_if_realized,
        )
        self.assertEqual(
            result.reason_codes, assessment.severity_reason_codes
        )

    def test_36_all_field_severity_rules_replay(self) -> None:
        for item in self.severity.field_assessments:
            self.replay(item)

    def test_37_all_dataset_severity_rules_replay(self) -> None:
        for item in self.severity.dataset_assessments:
            self.replay(item)

    def test_38_change_level_severity_rule_replays(self) -> None:
        self.replay(self.severity.change_level_profile)

    def test_39_canonical_severity_high(self) -> None:
        self.assertEqual(
            self.result.severity_baseline.severity_if_realized, "high"
        )

    def test_40_field_severity_distribution(self) -> None:
        observed = Counter(
            item.severity_if_realized.value
            for item in self.severity.field_assessments
        )
        self.assertEqual(
            observed, Counter({"high": 3, "moderate": 6, "low": 16})
        )

    def test_41_dataset_severity_distribution(self) -> None:
        observed = Counter(
            item.severity_if_realized.value
            for item in self.severity.dataset_assessments
        )
        self.assertEqual(
            observed, Counter({"high": 3, "moderate": 4, "low": 13})
        )

    def test_42_phase44_remains_valid(self) -> None:
        self.assertEqual(self.synthesis.validation_state.value, "valid")

    def test_43_decision_registry_valid(self) -> None:
        rules = self.synthesis.decision_rule_registry
        self.assertEqual(len({item.rule_id for item in rules}), len(rules))
        self.assertEqual(
            len({item.precedence for item in rules}), len(rules)
        )

    def test_44_canonical_decision_inputs_reproduce(self) -> None:
        inputs = self.synthesis.change_severity_profile
        profile = self.severity.change_level_profile
        self.assertIs(
            inputs.technical_consequence, profile.technical_consequence
        )
        self.assertIs(inputs.impact_certainty, profile.evidence_certainty)
        self.assertIs(
            inputs.severity_if_realized, profile.severity_if_realized
        )
        self.assertIs(inputs.breadth, profile.exposure_breadth)
        self.assertIs(inputs.criticality, profile.context_criticality)
        self.assertFalse(inputs.has_explicit_conditions)

    def test_45_canonical_decision_rule_replays(self) -> None:
        selected = evaluate_decision(
            self.synthesis.change_severity_profile,
            rules=self.synthesis.decision_rule_registry,
        )
        self.assertEqual(
            selected.rule_id,
            "decision-hold-unresolved-material-broad",
        )

    def test_46_disposition_hold_for_review(self) -> None:
        self.assertIs(
            self.synthesis.decision_disposition,
            DecisionDisposition.HOLD_FOR_REVIEW,
        )

    def test_47_decision_certainty_high_confidence(self) -> None:
        self.assertIs(
            self.synthesis.decision_certainty,
            DecisionCertainty.HIGH_CONFIDENCE,
        )

    def test_48_technical_certainty_stays_unresolved(self) -> None:
        self.assertIs(
            self.synthesis.change_severity_profile.impact_certainty,
            EvidenceCertainty.UNRESOLVED,
        )

    def test_49_confirmed_broken_fields_zero(self) -> None:
        self.assertEqual(
            self.synthesis.scope_summary.confirmed_downstream_failures, 0
        )

    def test_50_blocking_question_resolves(self) -> None:
        question = self.synthesis.blocking_questions[0]
        self.assertEqual(
            question.question_id,
            "blocking-question-spark-export-rename-compatibility",
        )
        self.assertEqual(question.root_cause_id, CAUSE)
        self.assertEqual(question.subject, ROOT_EDGE)
        self.assertEqual(len(question.affected_field_keys), 25)
        self.assertEqual(len(question.affected_dataset_urns), 20)
        self.assertEqual(len(question.affected_path_ids), 48)

    def test_51_four_required_evidence_classes(self) -> None:
        self.assertEqual(
            {
                item.evidence_class
                for item in self.synthesis.required_evidence
            },
            {
                "spark_transformation_configuration",
                "input_column_reference_query_or_code",
                "explicit_rename_mapping",
                "validated_execution_result",
            },
        )

    def test_52_decision_reasons_resolve(self) -> None:
        ids = {
            item.evidence_id for item in self.synthesis.decision_evidence
        }
        self.assertTrue(
            all(
                item.evidence_ids and set(item.evidence_ids) <= ids
                for item in self.synthesis.decision_reasons
            )
        )

    def test_53_representative_paths_resolve(self) -> None:
        ids = {item.path_id for item in self.technical.path_impacts}
        self.assertEqual(
            {item.kind.value for item in self.synthesis.representative_evidence_paths},
            {"short", "deep", "multipath"},
        )
        self.assertTrue(
            all(
                item.technical_path_id in ids
                for item in self.synthesis.representative_evidence_paths
            )
        )

    def test_54_context_highlights_deterministic(self) -> None:
        ids = tuple(
            item.highlight_id for item in self.synthesis.context_highlights
        )
        self.assertEqual(ids, tuple(dict.fromkeys(ids)))
        self.assertTrue(
            all(
                "highest risk" not in item.selection_basis.lower()
                for item in self.synthesis.context_highlights
            )
        )

    def test_55_all_provenance_closes(self) -> None:
        self.assertIs(
            self.check("provenance.recursive_closure").status,
            CertificationCheckStatus.PASS,
        )

    def test_56_no_numeric_risk_score(self) -> None:
        self.assertNotIn(
            "risk_score",
            _all_field_names(
                (self.technical, self.context, self.severity, self.synthesis)
            ),
        )

    def test_57_no_probability(self) -> None:
        self.assertNotIn(
            "failure_probability",
            _all_field_names((self.severity, self.synthesis)),
        )

    def test_58_no_repair_instructions(self) -> None:
        fields = _all_field_names((self.severity, self.synthesis))
        self.assertNotIn("repair_recommendation", fields)
        self.assertNotIn("remediation_order", fields)

    def test_59_no_notification_workflow(self) -> None:
        self.assertNotIn(
            "notification_priority",
            _all_field_names((self.context, self.synthesis)),
        )

    def test_60_no_llm_decision_authority(self) -> None:
        source = (
            ROOT / "src" / "chronos" / "impact_synthesis" / "builder.py"
        ).read_text(encoding="utf-8").lower()
        self.assertNotIn("openai", source)
        self.assertNotIn("llm", source)

    def test_61_deterministic_phase41_reconstruction(self) -> None:
        self.assertEqual(
            self.result.phase_4_semantic_fingerprints.technical_impact,
            self.technical.semantic_fingerprint,
        )

    def test_62_deterministic_phase42_reconstruction(self) -> None:
        self.assertEqual(
            self.result.phase_4_semantic_fingerprints.business_context,
            self.context.semantic_fingerprint,
        )

    def test_63_deterministic_phase43_reconstruction(self) -> None:
        self.assertEqual(
            self.result.phase_4_semantic_fingerprints.severity_criticality,
            self.severity.semantic_fingerprint,
        )

    def test_64_deterministic_phase44_reconstruction(self) -> None:
        self.assertEqual(
            self.result.phase_4_semantic_fingerprints.impact_synthesis,
            self.synthesis.semantic_fingerprint,
        )

    def test_65_timestamp_independence(self) -> None:
        other = self.certify()
        later = replace(
            other, certified_at="2026-07-29T23:00:00+00:00"
        )
        self.assertEqual(
            other.semantic_fingerprint, later.semantic_fingerprint
        )

    def test_66_certification_fingerprint_deterministic(self) -> None:
        other = self.certify()
        self.assertEqual(
            self.result.semantic_fingerprint, other.semantic_fingerprint
        )

    def test_67_serialization_round_trip(self) -> None:
        loaded = phase4_certification_from_json(self.result.to_json())
        self.assertTrue(self.result.semantically_equals(loaded))

    def test_68_all_predecessors_byte_identical(self) -> None:
        after = {
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in PATHS
        }
        self.assertEqual(self.before_hashes, after)
        self.assertTrue(
            all(item.unchanged for item in self.result.artifact_immutability)
        )

    def test_69_secret_scan_passes(self) -> None:
        self.assertTrue(
            all(not contains_secret(obj.to_dict()) for obj in self.objects)
        )
        self.assertFalse(contains_secret(self.result.to_dict()))

    def test_70_offline_network_blocked_certification(self) -> None:
        with patch.object(
            socket, "create_connection", side_effect=AssertionError
        ), patch.object(socket.socket, "connect", side_effect=AssertionError):
            result = self.certify()
        self.assertIs(
            result.certification_status,
            Phase4CertificationStatus.CERTIFIED,
        )

    def test_71_fingerprint_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            copied = []
            for path in PATHS:
                target = Path(directory) / path.name
                shutil.copyfile(path, target)
                copied.append(target)
            raw = json.loads(copied[-1].read_text(encoding="utf-8"))
            raw["semantic_fingerprint"] = "sha256:" + "0" * 64
            copied[-1].write_text(
                json.dumps(raw, sort_keys=True, separators=(",", ":")),
                encoding="utf-8",
            )
            with self.assertRaises(Phase4CertificationInputError):
                certify_phase4_from_artifacts(*copied)

    def test_72_technical_impact_mutation_fails(self) -> None:
        metrics = replace(
            self.technical.aggregate_metrics, unresolved_fields=24
        )
        self.assert_failed(
            technical=replace(
                self.technical, aggregate_metrics=metrics
            )
        )

    def test_73_context_mutation_fails(self) -> None:
        metrics = replace(
            self.context.aggregate_metrics,
            total_unique_context_assets=65,
        )
        self.assert_failed(
            context=replace(self.context, aggregate_metrics=metrics)
        )

    def test_74_severity_mutation_fails(self) -> None:
        profile = replace(
            self.severity.change_level_profile,
            severity_if_realized=SeverityIfRealized.MODERATE,
        )
        self.assert_failed(
            severity=replace(
                self.severity, change_level_profile=profile
            )
        )

    def test_75_breadth_mutation_fails(self) -> None:
        profile = replace(
            self.severity.change_level_profile,
            exposure_breadth=ExposureBreadth.BROAD,
        )
        self.assert_failed(
            severity=replace(
                self.severity, change_level_profile=profile
            )
        )

    def test_76_decision_mutation_fails(self) -> None:
        assessment = replace(
            self.synthesis.assessment,
            disposition=DecisionDisposition.PROCEED,
        )
        invalid = replace(
            self.synthesis,
            decision_disposition=DecisionDisposition.PROCEED,
            assessment=assessment,
        )
        self.assert_failed(synthesis=invalid)

    def test_77_rule_ambiguity_fails(self) -> None:
        rule = self.synthesis.decision_rule_registry[1]
        duplicate = replace(rule, rule_id="duplicate-hold-rule")
        invalid = replace(
            self.synthesis,
            decision_rule_registry=(
                *self.synthesis.decision_rule_registry,
                duplicate,
            ),
        )
        with self.assertRaises(Exception):
            self.certify(synthesis=invalid)

    def test_78_dangling_provenance_fails(self) -> None:
        path = replace(
            self.synthesis.representative_evidence_paths[0],
            context_asset_id="urn:li:missing:context",
        )
        invalid = replace(
            self.synthesis,
            representative_evidence_paths=(
                path,
                *self.synthesis.representative_evidence_paths[1:],
            ),
        )
        self.assert_failed(synthesis=invalid)

    def test_79_blocking_question_corruption_fails(self) -> None:
        question = replace(
            self.synthesis.blocking_questions[0],
            affected_path_ids=(
                self.synthesis.blocking_questions[0].affected_path_ids[:-1]
            ),
        )
        invalid = replace(
            self.synthesis, blocking_questions=(question,)
        )
        self.assert_failed(synthesis=invalid)

    def test_80_certification_categories_complete(self) -> None:
        self.assertEqual(
            {item.category for item in self.result.certification_checks},
            set(CertificationCheckCategory),
        )

    def test_81_phase3_certification_regression_passes(self) -> None:
        validate_phase3_certification(self.phase3)
        self.assertIs(
            self.phase3.certification_status,
            Phase3CertificationStatus.CERTIFIED,
        )

    def test_82_phase1_and_phase2_prerequisites(self) -> None:
        self.assertIs(
            validate_snapshot(self.snapshot).state,
            SnapshotValidationState.VALID,
        )
        self.assertIs(
            self.phase2.certification_state,
            Phase2CertificationState.CERTIFIED,
        )

    def test_83_root_boundary_exact(self) -> None:
        cause = self.technical.technical_impact_causes[0]
        self.assertEqual(cause.root_relationship_id, ROOT_EDGE)
        self.assertEqual(cause.upstream_field.field_path, "order_amount")
        self.assertEqual(cause.downstream_field.field_path, "order_total")
        self.assertIs(cause.evidence_strength, EvidenceStrength.INSUFFICIENT)
        relationship = next(
            item
            for item in self.technical.relationship_impacts
            if item.relationship_id == ROOT_EDGE
        )
        self.assertIs(
            relationship.compatibility_state, CompatibilityState.UNKNOWN
        )

    def test_84_models_are_immutable(self) -> None:
        with self.assertRaises(FrozenInstanceError):
            self.result.scope_statement = "changed"

    def test_85_export_and_load_public_api(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = export_phase4_certification(
                self.result, Path(directory) / "certification.json"
            )
            loaded = load_phase4_certification(path)
        self.assertTrue(self.result.semantically_equals(loaded))

    def test_86_stored_fingerprint_verified(self) -> None:
        value = self.result.to_json().replace(
            self.result.semantic_fingerprint,
            "sha256:" + "0" * 64,
            1,
        )
        with self.assertRaises(Phase4CertificationSerializationError):
            phase4_certification_from_json(value)

    def test_87_public_fingerprint_helper_matches(self) -> None:
        self.assertEqual(
            phase4_certification_semantic_fingerprint(self.result),
            self.result.semantic_fingerprint,
        )

    def test_88_semantic_mutation_changes_fingerprint(self) -> None:
        changed = replace(
            self.result,
            warnings=(*self.result.warnings, "Additional warning."),
        )
        self.assertNotEqual(
            changed.semantic_fingerprint, self.result.semantic_fingerprint
        )

    def test_89_scope_statement_is_phase5_boundary(self) -> None:
        self.assertIn("Phase 5", self.result.scope_statement)
        self.assertIn(
            "must not independently re-derive",
            self.result.scope_statement,
        )
        self.assertNotIn("frontend code", self.result.scope_statement)

    def test_90_certification_validation_rejects_baseline_mutation(self) -> None:
        baseline = replace(
            self.result.technical_baseline, downstream_fields=24
        )
        invalid = replace(self.result, technical_baseline=baseline)
        with self.assertRaises(Phase4CertificationValidationError):
            validate_phase4_certification(invalid)


def _all_field_names(values) -> set[str]:
    names: set[str] = set()

    def visit(value) -> None:
        if hasattr(value, "__dataclass_fields__"):
            for name in value.__dataclass_fields__:
                names.add(name)
                visit(getattr(value, name))
        elif isinstance(value, (tuple, list)):
            for item in value:
                visit(item)
        elif isinstance(value, dict):
            names.update(value)
            for item in value.values():
                visit(item)

    for value in values:
        visit(value)
    return names


if __name__ == "__main__":
    unittest.main()
