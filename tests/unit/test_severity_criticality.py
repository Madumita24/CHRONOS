from __future__ import annotations

import hashlib
import socket
import tempfile
import unittest
from dataclasses import FrozenInstanceError, fields, replace
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from chronos.business_context import (
    ContextCategory,
    load_business_context,
    validate_business_context,
)
from chronos.change_semantics import load_contract
from chronos.compatibility_evaluation import load_compatibility_evaluation
from chronos.counterfactual_source import load_source_state
from chronos.dependency_propagation import load_dependency_propagation
from chronos.explanations import load_explanation_bundle
from chronos.future_graph import load_future_graph
from chronos.phase2_certification import load_certification
from chronos.phase3_certification import (
    load_phase3_certification,
    validate_phase3_certification,
)
from chronos.proposal import load_proposal
from chronos.proposal_validation import load_validation_result
from chronos.severity_criticality import (
    ContextCriticality,
    ContextSignificance,
    DEFAULT_SEVERITY_RULES,
    EvidenceCertainty,
    ExposureBreadth,
    SensitivityState,
    SeverityCriticalityEntryError,
    SeverityCriticalitySerializationError,
    SeverityCriticalityValidationError,
    SeverityIfRealized,
    TechnicalConsequence,
    assess_severity_criticality,
    assess_severity_criticality_from_artifacts,
    derive_context_criticality,
    derive_severity_if_realized,
    export_severity_analysis,
    get_breadth_evidence,
    get_change_severity_profile,
    get_context_asset_assessment,
    get_criticality_evidence,
    get_dataset_assessment,
    get_field_assessment,
    get_missing_evidence,
    load_severity_analysis,
    severity_from_json,
    severity_semantic_fingerprint,
    validate_severity_criticality,
)
from chronos.snapshot import contains_secret, load_snapshot
from chronos.technical_impact import (
    TechnicalImpactState,
    load_technical_impact,
    validate_technical_impact,
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
)
PATHS = tuple(ARTIFACTS / name for name in NAMES)
PII_TAG = "urn:li:tag:b2fd91.PII_Data"


def fixed_clock(hour: int):
    return lambda: datetime(2026, 7, 28, hour, tzinfo=timezone.utc)


class SeverityCriticalityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.before_hashes = {
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in PATHS
        }
        cls.snapshot = load_snapshot(PATHS[0])
        cls.proposal = load_proposal(PATHS[1])
        cls.proposal_validation = load_validation_result(PATHS[2])
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
        cls.result = cls.build(10)

    @classmethod
    def build(cls, hour: int):
        return assess_severity_criticality_from_artifacts(
            *PATHS,
            clock=fixed_clock(hour),
        )

    def derive(self, *, phase3=None, technical=None, context=None):
        return assess_severity_criticality(
            self.snapshot,
            self.proposal,
            self.proposal_validation,
            self.contract,
            self.phase2,
            self.source,
            self.graph,
            self.propagation,
            self.compatibility,
            self.explanations,
            phase3 or self.phase3,
            technical or self.technical,
            context or self.context,
            input_artifact_hashes=self.result.input_artifact_hashes,
            clock=fixed_clock(11),
        )

    def validate(self, result) -> None:
        validate_severity_criticality(
            result,
            self.snapshot,
            self.graph,
            self.technical,
            self.context,
            self.phase3,
        )

    def criticality(self, evidence_id):
        return next(
            item
            for item in self.result.criticality_evidence
            if item.evidence_id == evidence_id
        )

    def sensitivity(self, evidence_id):
        return next(
            item
            for item in self.result.sensitivity_evidence
            if item.sensitivity_evidence_id == evidence_id
        )

    def test_01_canonical_assessment_succeeds(self) -> None:
        self.validate(self.result)
        self.assertTrue(self.result.semantic_fingerprint.startswith("sha256:"))

    def test_02_prerequisites_are_required(self) -> None:
        bad_fingerprints = replace(
            self.phase3.phase_3_semantic_fingerprints,
            explanation_bundle="sha256:" + "0" * 64,
        )
        invalid = replace(
            self.phase3,
            phase_3_semantic_fingerprints=bad_fingerprints,
        )
        with self.assertRaises(SeverityCriticalityEntryError):
            self.derive(phase3=invalid)

    def test_03_all_25_fields_are_assessed(self) -> None:
        self.assertEqual(len(self.result.field_assessments), 25)

    def test_04_all_20_datasets_are_assessed(self) -> None:
        self.assertEqual(len(self.result.dataset_assessments), 20)

    def test_05_all_context_assets_receive_significance(self) -> None:
        self.assertEqual(len(self.result.context_asset_assessments), 66)
        self.assertEqual(
            {
                item.context_asset_id
                for item in self.result.context_asset_assessments
            },
            {item.asset_id for item in self.context.context_asset_registry},
        )

    def test_06_root_cause_is_preserved(self) -> None:
        self.assertEqual(len(self.result.root_causes), 1)
        self.assertEqual(
            self.result.root_causes[0].cause_id,
            "technical-impact-cause-source-rename-semantics",
        )
        self.assertEqual(
            self.result.root_causes[0].source_evidence_strength,
            "insufficient",
        )

    def test_07_technical_states_are_unchanged(self) -> None:
        expected = {
            item.field_key: item.technical_impact_state
            for item in self.technical.field_impacts
        }
        self.assertTrue(
            all(
                item.technical_impact_state is expected[item.field_key]
                for item in self.result.field_assessments
            )
        )

    def test_08_business_context_is_unchanged(self) -> None:
        before = self.context.semantic_fingerprint
        self.build(11)
        self.assertEqual(self.context.semantic_fingerprint, before)

    def test_09_criticality_is_separate_from_breadth(self) -> None:
        profile = self.result.change_level_profile
        self.assertIs(
            profile.context_criticality,
            ContextCriticality.ELEVATED_CONTEXT,
        )
        self.assertIs(
            profile.exposure_breadth,
            ExposureBreadth.WIDESPREAD,
        )

    def test_10_sensitivity_is_separate_from_criticality(self) -> None:
        profile = self.result.change_level_profile
        self.assertIs(profile.sensitivity_state, SensitivityState.PII)
        self.assertIsNot(
            profile.context_criticality,
            ContextCriticality.EXPLICITLY_CRITICAL,
        )

    def test_11_pii_does_not_imply_criticality(self) -> None:
        state, reasons = derive_context_criticality(
            explicit_designation=False,
            context_categories=("tag",),
            supporting_datasets=1,
            sensitivity_state=SensitivityState.PII,
        )
        self.assertIs(state, ContextCriticality.STANDARD_CONTEXT)
        self.assertNotIn("explicitly_critical", {item.value for item in reasons})

    def test_12_owner_does_not_imply_high_severity(self) -> None:
        owner = next(
            item
            for item in self.result.context_asset_assessments
            if item.context_category is ContextCategory.OWNERSHIP
        )
        self.assertIs(
            owner.context_significance,
            ContextSignificance.ACCOUNTABILITY,
        )
        self.assertFalse(hasattr(owner, "severity_if_realized"))

    def test_13_dashboard_does_not_imply_criticality(self) -> None:
        dashboard = next(
            item
            for item in self.result.context_asset_assessments
            if item.context_asset_type.value == "dashboard"
        )
        evidence = self.criticality(dashboard.criticality_evidence_id)
        self.assertIs(
            evidence.criticality,
            ContextCriticality.STANDARD_CONTEXT,
        )

    def test_14_path_count_is_not_a_rule_input(self) -> None:
        self.assertNotIn(
            "path_count",
            {item.name for item in fields(self.result.change_level_profile.severity_rule_inputs)},
        )

    def test_15_depth_is_not_a_rule_input(self) -> None:
        self.assertNotIn(
            "depth",
            {item.name for item in fields(self.result.change_level_profile.severity_rule_inputs)},
        )

    def test_16_unknown_technical_state_remains_unresolved(self) -> None:
        self.assertTrue(
            all(
                item.technical_consequence
                is TechnicalConsequence.UNRESOLVED_IMPACT
                and item.evidence_certainty is EvidenceCertainty.UNRESOLVED
                for item in self.result.field_assessments
            )
        )

    def test_17_confirmed_explicit_broad_rule_is_critical(self) -> None:
        outcome = derive_severity_if_realized(
            TechnicalConsequence.CONFIRMED_IMPACT,
            ContextCriticality.EXPLICITLY_CRITICAL,
            ExposureBreadth.BROAD,
            EvidenceCertainty.ESTABLISHED,
        )
        self.assertIs(outcome.severity_if_realized, SeverityIfRealized.CRITICAL)

    def test_18_confirmed_standard_rule_is_moderate(self) -> None:
        outcome = derive_severity_if_realized(
            TechnicalConsequence.CONFIRMED_IMPACT,
            ContextCriticality.STANDARD_CONTEXT,
            ExposureBreadth.LIMITED,
            EvidenceCertainty.ESTABLISHED,
        )
        self.assertIs(outcome.severity_if_realized, SeverityIfRealized.MODERATE)

    def test_19_no_impact_plus_critical_context_is_undetermined(self) -> None:
        outcome = derive_severity_if_realized(
            TechnicalConsequence.NO_DEMONSTRATED_IMPACT,
            ContextCriticality.EXPLICITLY_CRITICAL,
            ExposureBreadth.WIDESPREAD,
            EvidenceCertainty.ESTABLISHED,
        )
        self.assertIs(
            outcome.severity_if_realized,
            SeverityIfRealized.UNDETERMINED,
        )

    def test_20_broad_unresolved_context_is_honest(self) -> None:
        outcome = derive_severity_if_realized(
            TechnicalConsequence.UNRESOLVED_IMPACT,
            ContextCriticality.ELEVATED_CONTEXT,
            ExposureBreadth.BROAD,
            EvidenceCertainty.UNRESOLVED,
        )
        self.assertIs(outcome.severity_if_realized, SeverityIfRealized.HIGH)
        self.assertIs(
            outcome.inputs.evidence_certainty,
            EvidenceCertainty.UNRESOLVED,
        )

    def test_21_criticality_unknown_is_supported(self) -> None:
        state, _ = derive_context_criticality(
            explicit_designation=False,
            context_categories=(),
            supporting_datasets=1,
            sensitivity_state=(
                SensitivityState.NO_CERTIFIED_SENSITIVITY_SIGNAL
            ),
        )
        self.assertIs(state, ContextCriticality.CRITICALITY_UNKNOWN)

    def test_22_change_has_severity_if_realized(self) -> None:
        profile = get_change_severity_profile(self.result)
        self.assertIs(profile.severity_if_realized, SeverityIfRealized.HIGH)
        self.assertIs(
            profile.evidence_certainty,
            EvidenceCertainty.UNRESOLVED,
        )

    def test_23_rule_ids_are_serialized(self) -> None:
        raw = self.result.to_dict()
        self.assertTrue(raw["severity_rule_registry"])
        self.assertTrue(
            all("rule_id" in item for item in raw["severity_rule_registry"])
        )

    def test_24_rule_inputs_are_serialized(self) -> None:
        raw = self.result.to_dict()
        self.assertIn(
            "severity_rule_inputs",
            raw["field_assessments"][0],
        )

    def test_25_rule_precedence_is_deterministic(self) -> None:
        precedences = [
            item.precedence for item in self.result.severity_rule_registry
        ]
        self.assertEqual(len(precedences), len(set(precedences)))

    def test_26_context_assets_are_not_double_counted(self) -> None:
        self.assertEqual(
            self.result.aggregate_metrics.unique_context_assets,
            66,
        )

    def test_27_mapping_count_is_retained_separately(self) -> None:
        self.assertEqual(
            self.result.aggregate_metrics.technical_to_context_mappings,
            257,
        )
        self.assertNotEqual(
            self.result.aggregate_metrics.technical_to_context_mappings,
            self.result.aggregate_metrics.unique_context_assets,
        )

    def test_28_missing_evidence_is_explicit(self) -> None:
        missing = get_missing_evidence(
            self.result,
            self.result.proposal_id,
        )
        self.assertEqual(len(missing), 1)
        self.assertEqual(len(missing[0].missing_classes), 5)

    def test_29_no_probability_calculation(self) -> None:
        keys = _all_keys(self.result.to_dict())
        self.assertNotIn("probability", keys)
        self.assertNotIn("likelihood", keys)
        self.assertNotIn("expected_loss", keys)

    def test_30_no_numeric_risk_score(self) -> None:
        keys = _all_keys(self.result.to_dict())
        self.assertNotIn("risk", keys)
        self.assertNotIn("risk_score", keys)

    def test_31_no_final_decision_field(self) -> None:
        keys = _all_keys(self.result.to_dict())
        self.assertFalse(
            {
                "deploy",
                "block",
                "hold",
                "approve",
                "reject",
                "safe_to_deploy",
                "do_not_deploy",
            }
            & keys
        )

    def test_32_no_repair_logic(self) -> None:
        keys = _all_keys(self.result.to_dict())
        self.assertNotIn("repair", keys)
        self.assertNotIn("remediation", keys)

    def test_33_deterministic_ordering(self) -> None:
        self.assertEqual(
            tuple(item.field_key.text for item in self.result.field_assessments),
            tuple(
                sorted(
                    item.field_key.text
                    for item in self.result.field_assessments
                )
            ),
        )
        self.assertEqual(
            tuple(
                item.context_asset_id
                for item in self.result.context_asset_assessments
            ),
            tuple(
                sorted(
                    item.context_asset_id
                    for item in self.result.context_asset_assessments
                )
            ),
        )

    def test_34_serialization_is_deterministic(self) -> None:
        other = self.build(10)
        self.assertEqual(self.result.to_json(), other.to_json())

    def test_35_timestamp_is_excluded_from_fingerprint(self) -> None:
        other = self.build(14)
        self.assertNotEqual(self.result.created_at, other.created_at)
        self.assertEqual(
            self.result.semantic_fingerprint,
            other.semantic_fingerprint,
        )

    def test_36_semantic_mutation_changes_fingerprint(self) -> None:
        changed = replace(
            self.result,
            canonical_narrative=self.result.canonical_narrative + " Changed.",
        )
        self.assertNotEqual(
            changed.semantic_fingerprint,
            self.result.semantic_fingerprint,
        )

    def test_37_serialization_round_trip(self) -> None:
        loaded = severity_from_json(self.result.to_json())
        self.assertTrue(self.result.semantically_equals(loaded))

    def test_38_provenance_closes(self) -> None:
        self.assertTrue(
            all(item.provenance_ids for item in self.result.field_assessments)
        )
        self.assertTrue(
            all(
                item.provenance_ids
                for item in self.result.context_asset_assessments
            )
        )
        self.assertTrue(
            all(
                item.supporting_context_relationship_ids
                and item.provenance_ids
                for item in self.result.criticality_evidence
            )
        )

    def test_39_inputs_are_unchanged(self) -> None:
        after = {
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in PATHS
        }
        self.assertEqual(self.before_hashes, after)
        self.assertTrue(
            all(item.unchanged for item in self.result.input_artifact_hashes)
        )

    def test_40_runtime_is_offline(self) -> None:
        with patch.object(
            socket,
            "create_connection",
            side_effect=AssertionError("network attempted"),
        ):
            other = self.build(12)
        self.assertEqual(
            other.semantic_fingerprint,
            self.result.semantic_fingerprint,
        )

    def test_41_secret_scanner_passes(self) -> None:
        self.assertFalse(contains_secret(self.result.to_dict()))

    def test_42_phase_4_1_regression_is_green(self) -> None:
        validate_technical_impact(
            self.technical,
            self.source,
            self.graph,
            self.propagation,
            self.compatibility,
            self.explanations,
            self.phase3,
        )

    def test_43_phase_4_2_regression_is_green(self) -> None:
        validate_business_context(
            self.context,
            self.snapshot,
            self.graph,
            self.technical,
            self.phase3,
        )

    def test_44_phase_3_certification_is_green(self) -> None:
        validate_phase3_certification(self.phase3)

    def test_45_change_profile_has_raw_breadth_metrics(self) -> None:
        metrics = get_breadth_evidence(self.result, self.result.proposal_id)
        self.assertEqual(len(metrics), 1)
        self.assertEqual(metrics[0].supporting_technical_fields, 25)
        self.assertEqual(metrics[0].supporting_datasets, 20)
        self.assertEqual(metrics[0].unique_context_assets, 66)
        self.assertEqual(metrics[0].context_relationship_count, 211)

    def test_46_field_query_works(self) -> None:
        expected = self.result.field_assessments[0]
        self.assertEqual(
            get_field_assessment(self.result, expected.field_key),
            expected,
        )

    def test_47_dataset_query_works(self) -> None:
        expected = self.result.dataset_assessments[0]
        self.assertEqual(
            get_dataset_assessment(self.result, expected.dataset_urn),
            expected,
        )

    def test_48_context_asset_query_works(self) -> None:
        expected = self.result.context_asset_assessments[0]
        self.assertEqual(
            get_context_asset_assessment(
                self.result,
                expected.context_asset_id,
            ),
            expected,
        )

    def test_49_criticality_query_works(self) -> None:
        evidence = get_criticality_evidence(
            self.result,
            self.result.proposal_id,
        )
        self.assertEqual(len(evidence), 1)

    def test_50_invalid_phase_4_1_fails_closed(self) -> None:
        invalid = replace(
            self.technical,
            canonical_narrative="invalid technical package",
        )
        with self.assertRaises(SeverityCriticalityEntryError):
            self.derive(technical=invalid)

    def test_51_invalid_phase_4_2_fails_closed(self) -> None:
        invalid = replace(
            self.context,
            canonical_narrative="invalid context package",
        )
        with self.assertRaises(SeverityCriticalityEntryError):
            self.derive(context=invalid)

    def test_52_fingerprint_mismatch_fails_closed(self) -> None:
        invalid = replace(
            self.result,
            business_context_fingerprint="sha256:" + "0" * 64,
        )
        with self.assertRaises(SeverityCriticalityValidationError):
            self.validate(invalid)

    def test_53_technical_state_mutation_fails_closed(self) -> None:
        altered = replace(
            self.result.field_assessments[0],
            technical_impact_state=TechnicalImpactState.POTENTIAL_IMPACT,
        )
        invalid = replace(
            self.result,
            field_assessments=(
                altered,
                *self.result.field_assessments[1:],
            ),
        )
        with self.assertRaises(SeverityCriticalityValidationError):
            self.validate(invalid)

    def test_54_context_mutation_fails_closed(self) -> None:
        altered = replace(
            self.result.context_asset_assessments[0],
            explanation="Altered context semantics.",
        )
        invalid = replace(
            self.result,
            context_asset_assessments=(
                altered,
                *self.result.context_asset_assessments[1:],
            ),
        )
        with self.assertRaises(SeverityCriticalityValidationError):
            self.validate(invalid)

    def test_55_pii_cannot_be_converted_to_explicit_criticality(self) -> None:
        evidence_index = next(
            i
            for i, item in enumerate(self.result.criticality_evidence)
            if item.subject_id == PII_TAG
        )
        values = list(self.result.criticality_evidence)
        values[evidence_index] = replace(
            values[evidence_index],
            criticality=ContextCriticality.EXPLICITLY_CRITICAL,
        )
        invalid = replace(
            self.result,
            criticality_evidence=tuple(values),
        )
        with self.assertRaises(SeverityCriticalityValidationError):
            self.validate(invalid)

    def test_56_missing_rule_reference_fails_closed(self) -> None:
        altered = replace(
            self.result.field_assessments[0],
            severity_rule_id="unknown-rule",
        )
        with self.assertRaises(ValueError):
            replace(
                self.result,
                field_assessments=(
                    altered,
                    *self.result.field_assessments[1:],
                ),
            )

    def test_57_ambiguous_rule_precedence_fails_closed(self) -> None:
        rule = DEFAULT_SEVERITY_RULES[0]
        duplicate = replace(rule, rule_id="duplicate-no-impact")
        with self.assertRaises(SeverityCriticalityValidationError):
            derive_severity_if_realized(
                TechnicalConsequence.NO_DEMONSTRATED_IMPACT,
                ContextCriticality.STANDARD_CONTEXT,
                ExposureBreadth.LOCAL,
                EvidenceCertainty.ESTABLISHED,
                rules=(rule, duplicate),
            )

    def test_58_duplicate_assessment_fails_closed(self) -> None:
        with self.assertRaises(ValueError):
            replace(
                self.result,
                field_assessments=(
                    *self.result.field_assessments,
                    self.result.field_assessments[0],
                ),
            )

    def test_59_unsupported_final_decision_fails_closed(self) -> None:
        invalid = replace(
            self.result,
            canonical_narrative="SAFE_TO_DEPLOY",
        )
        with self.assertRaises(SeverityCriticalityValidationError):
            self.validate(invalid)

    def test_60_repair_recommendation_fails_closed(self) -> None:
        invalid = replace(
            self.result,
            canonical_narrative="repair_recommendation",
        )
        with self.assertRaises(SeverityCriticalityValidationError):
            self.validate(invalid)

    def test_61_models_are_immutable(self) -> None:
        with self.assertRaises(FrozenInstanceError):
            self.result.change_level_profile.explanation = "changed"

    def test_62_export_and_load_use_public_api(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = export_severity_analysis(
                self.result,
                Path(directory) / "severity.json",
            )
            loaded = load_severity_analysis(path)
        self.assertTrue(self.result.semantically_equals(loaded))

    def test_63_stored_fingerprint_is_verified(self) -> None:
        value = self.result.to_json().replace(
            self.result.semantic_fingerprint,
            "sha256:" + "0" * 64,
            1,
        )
        with self.assertRaises(SeverityCriticalitySerializationError):
            severity_from_json(value)

    def test_64_public_fingerprint_helper_matches(self) -> None:
        self.assertEqual(
            severity_semantic_fingerprint(self.result),
            self.result.semantic_fingerprint,
        )

    def test_65_runtime_has_no_datahub_client_import(self) -> None:
        source = (
            ROOT
            / "src"
            / "chronos"
            / "severity_criticality"
            / "builder.py"
        ).read_text(encoding="utf-8").lower()
        self.assertNotIn("chronos.datahub", source)
        self.assertNotIn("requests", source)


def _all_keys(value) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        found.update(value)
        for item in value.values():
            found.update(_all_keys(item))
    elif isinstance(value, list):
        for item in value:
            found.update(_all_keys(item))
    return found


if __name__ == "__main__":
    unittest.main()
