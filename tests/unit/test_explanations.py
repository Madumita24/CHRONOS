from __future__ import annotations

import hashlib
import json
import socket
import tempfile
import unittest
from dataclasses import FrozenInstanceError, fields, is_dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from chronos.compatibility_evaluation import (
    CompatibilityState,
    EvidenceStrength,
    load_compatibility_evaluation,
)
from chronos.counterfactual_source import load_source_state
from chronos.dependency_propagation import load_dependency_propagation
from chronos.explanations import (
    ExplanationSerializationError,
    ExplanationStepType,
    ExplanationValidationError,
    ExplanationValidationState,
    build_explanation_bundle_from_artifacts,
    export_explanation_bundle,
    load_explanation_bundle,
    validate_explanation_bundle,
)
from chronos.future_graph import load_future_graph
from chronos.proposal import CANONICAL_DATASET_URN
from chronos.snapshot import FieldMachineKey, load_snapshot


ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "artifacts"
PATHS = (
    ARTIFACTS / "current_metadata_snapshot.json",
    ARTIFACTS / "change_proposal.json",
    ARTIFACTS / "change_proposal_validation.json",
    ARTIFACTS / "change_semantic_contract.json",
    ARTIFACTS / "phase_2_certification.json",
    ARTIFACTS / "counterfactual_source_state.json",
    ARTIFACTS / "future_metadata_graph.json",
    ARTIFACTS / "dependency_propagation.json",
    ARTIFACTS / "compatibility_evaluation.json",
)
CURRENT_SOURCE = FieldMachineKey(CANONICAL_DATASET_URN, "order_total")
CANDIDATE_SOURCE = FieldMachineKey(CANONICAL_DATASET_URN, "order_amount")
SOURCE_EDGE_ID = "future-lineage-68f7e0269dbea7279911b809"


def fixed_clock(hour: int):
    return lambda: datetime(2026, 7, 28, hour, tzinfo=timezone.utc)


class ExplanationBundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.before_hashes = {
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in PATHS
        }
        cls.snapshot = load_snapshot(PATHS[0])
        cls.source_state = load_source_state(PATHS[5])
        cls.future_graph = load_future_graph(PATHS[6])
        cls.propagation = load_dependency_propagation(PATHS[7])
        cls.compatibility = load_compatibility_evaluation(PATHS[8])
        cls.bundle = cls.build(4)

    @classmethod
    def build(cls, hour: int):
        return build_explanation_bundle_from_artifacts(
            *PATHS,
            clock=fixed_clock(hour),
        )

    def source_edge(self):
        return self.bundle.explain_relationship(SOURCE_EDGE_ID)

    def validate(self, bundle) -> None:
        validate_explanation_bundle(
            bundle,
            self.snapshot,
            self.source_state,
            self.future_graph,
            self.propagation,
            self.compatibility,
        )

    def test_01_canonical_bundle_succeeds(self) -> None:
        self.assertIs(
            self.bundle.validation_state,
            ExplanationValidationState.VALID,
        )
        self.assertTrue(self.bundle.semantic_fingerprint.startswith("sha256:"))

    def test_02_source_explanation_is_exact(self) -> None:
        source = self.bundle.explain_source_change()
        self.assertEqual(source.current_field, CURRENT_SOURCE)
        self.assertEqual(source.candidate_field, CANDIDATE_SOURCE)
        self.assertEqual(source.current_native_type, "DOUBLE PRECISION")
        self.assertEqual(source.current_normalized_type, "Number")
        self.assertTrue(source.nullable)
        self.assertFalse(source.is_part_of_key)

    def test_03_all_relationships_are_explained(self) -> None:
        self.assertEqual(len(self.bundle.relationship_explanations), 27)

    def test_04_all_paths_are_explained(self) -> None:
        self.assertEqual(len(self.bundle.path_explanations), 48)

    def test_05_all_fields_are_explained(self) -> None:
        self.assertEqual(len(self.bundle.field_explanations), 25)

    def test_06_all_datasets_are_explained(self) -> None:
        self.assertEqual(len(self.bundle.dataset_explanations), 20)

    def test_07_first_boundary_is_unknown_with_insufficient_evidence(self) -> None:
        edge = self.source_edge()
        self.assertIs(edge.compatibility_state, CompatibilityState.UNKNOWN)
        self.assertIs(edge.evidence_strength, EvidenceStrength.INSUFFICIENT)
        self.assertEqual(edge.transform_operations, ())
        self.assertEqual(edge.query_evidence, ())
        self.assertEqual(edge.lineage_confidence_provenance, (0.5,))

    def test_08_no_same_name_inference_is_made(self) -> None:
        edge = self.source_edge()
        self.assertNotEqual(
            edge.candidate_upstream.field_path,
            edge.candidate_downstream.field_path,
        )
        self.assertIn("cannot determine", edge.human_explanation)

    def test_09_conditional_relationships_distinguish_local_and_end_to_end(self) -> None:
        conditional = tuple(
            item
            for item in self.bundle.relationship_explanations
            if item.compatibility_state
            is CompatibilityState.CONDITIONALLY_COMPATIBLE
        )
        self.assertEqual(len(conditional), 26)
        for item in conditional:
            self.assertIn("Local structural continuity", item.human_explanation)
            self.assertIn("not end-to-end compatibility", item.human_explanation)

    def test_10_unknown_fields_remain_unknown(self) -> None:
        self.assertTrue(
            all(
                item.compatibility_state is CompatibilityState.UNKNOWN
                for item in self.bundle.field_explanations
            )
        )

    def test_11_compatibility_states_match_phase_3_4(self) -> None:
        expected = {
            item.relationship_id: item.compatibility_state
            for item in self.compatibility.relationship_evaluations
        }
        actual = {
            item.relationship_id: item.compatibility_state
            for item in self.bundle.relationship_explanations
        }
        self.assertEqual(actual, expected)

    def test_12_exposure_states_match_phase_3_3(self) -> None:
        expected = {
            item.relationship_id: item.exposure_state
            for item in self.propagation.relationship_exposure_registry
        }
        actual = {
            item.relationship_id: item.exposure_state
            for item in self.bundle.relationship_explanations
        }
        self.assertEqual(actual, expected)

    def test_13_relationship_identities_match_phase_3_2(self) -> None:
        expected = {
            item.relationship_id: (
                item.current_upstream,
                item.current_downstream,
                item.upstream,
                item.downstream,
            )
            for item in self.future_graph.relationship_registry
        }
        actual = {
            item.relationship_id: (
                item.current_upstream,
                item.current_downstream,
                item.candidate_upstream,
                item.candidate_downstream,
            )
            for item in self.bundle.relationship_explanations
        }
        self.assertEqual(actual, expected)

    def test_14_source_matches_phase_3_1(self) -> None:
        renamed = next(
            item
            for item in self.source_state.field_identity_mappings
            if item.current_identity.field_path == "order_total"
        )
        self.assertEqual(renamed.candidate_identity.field_path, "order_amount")
        self.assertEqual(
            self.bundle.source_explanation.candidate_field,
            CANDIDATE_SOURCE,
        )

    def test_15_current_source_claim_traces_to_phase_1(self) -> None:
        known = set(self.snapshot.evidence_by_id())
        current_step = self.bundle.source_explanation.steps[0]
        self.assertTrue(current_step.provenance_ids)
        self.assertTrue(set(current_step.provenance_ids).issubset(known))

    def test_16_multipath_fields_list_every_relevant_path(self) -> None:
        expected = {
            item.field_key: item.supporting_path_ids
            for item in self.propagation.field_exposure_registry
            if len(item.supporting_path_ids) > 1
            and item.field_key != CANDIDATE_SOURCE
        }
        actual = {
            item.field_key: item.supporting_path_ids
            for item in self.bundle.field_explanations
            if len(item.supporting_path_ids) > 1
        }
        self.assertEqual(actual, expected)

    def test_17_each_path_identifies_its_first_blocker(self) -> None:
        self.assertTrue(
            all(
                item.first_uncertain_or_blocking_relationship_id
                == SOURCE_EDGE_ID
                for item in self.bundle.path_explanations
            )
        )

    def test_18_uncertainty_record_is_explicit(self) -> None:
        uncertainty = self.bundle.explain_uncertainty(
            "uncertainty-source-rename-boundary"
        )
        self.assertEqual(uncertainty.subject, SOURCE_EDGE_ID)
        self.assertEqual(len(uncertainty.affected_relationship_ids), 27)
        self.assertEqual(len(uncertainty.affected_path_ids), 48)
        self.assertEqual(len(uncertainty.affected_field_keys), 25)

    def test_19_missing_evidence_classes_are_represented(self) -> None:
        missing = self.bundle.uncertainties[0].missing_evidence_types
        self.assertIn("spark_transformation_configuration", missing)
        self.assertIn("input_column_reference_query_or_code", missing)
        self.assertIn("explicit_rename_mapping", missing)
        self.assertIn("validated_execution_result", missing)

    def test_20_generation_does_not_retrieve_external_evidence(self) -> None:
        with patch.object(
            socket,
            "create_connection",
            side_effect=AssertionError("network access attempted"),
        ):
            result = self.build(5)
        self.assertEqual(result.semantic_fingerprint, self.bundle.semantic_fingerprint)

    def test_21_human_explanations_are_deterministic(self) -> None:
        other = self.build(6)
        self.assertEqual(
            other.canonical_narrative,
            self.bundle.canonical_narrative,
        )
        self.assertEqual(
            tuple(item.human_explanation for item in other.path_explanations),
            tuple(
                item.human_explanation
                for item in self.bundle.path_explanations
            ),
        )

    def test_22_machine_explanations_are_deterministic(self) -> None:
        other = self.build(7)
        self.assertEqual(other.semantic_json(), self.bundle.semantic_json())

    def test_23_no_fake_numeric_explanation_confidence_exists(self) -> None:
        keys: set[str] = set()

        def collect(value) -> None:
            if is_dataclass(value):
                for field in fields(value):
                    keys.add(field.name)
                    collect(getattr(value, field.name))
            elif isinstance(value, tuple):
                for item in value:
                    collect(item)

        collect(self.bundle)
        self.assertNotIn("explanation_confidence", keys)
        self.assertNotIn("confidence_score", keys)

    def test_24_no_risk_score_is_present(self) -> None:
        self.assertNotIn("risk score", self.bundle.to_json().lower())

    def test_25_no_severity_is_present(self) -> None:
        self.assertNotIn("severity", self.bundle.to_json().lower())

    def test_26_no_repair_recommendation_is_present(self) -> None:
        self.assertNotIn("repair recommendation", self.bundle.to_json().lower())

    def test_27_no_business_impact_conclusion_is_present(self) -> None:
        self.assertNotIn("business impact", self.bundle.to_json().lower())

    def test_28_generation_does_not_mutate_artifacts(self) -> None:
        before = PATHS[8].read_bytes()
        self.build(8)
        self.assertEqual(PATHS[8].read_bytes(), before)

    def test_29_all_input_artifacts_remain_unchanged(self) -> None:
        after = {
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in PATHS
        }
        self.assertEqual(after, self.before_hashes)
        self.assertTrue(
            all(item.unchanged for item in self.bundle.input_artifact_hashes)
        )

    def test_30_serialization_is_deterministic(self) -> None:
        self.assertEqual(self.bundle.to_json(), self.bundle.to_json())

    def test_31_fingerprint_is_timestamp_independent(self) -> None:
        other = self.build(9)
        self.assertNotEqual(other.created_at, self.bundle.created_at)
        self.assertEqual(other.semantic_fingerprint, self.bundle.semantic_fingerprint)

    def test_32_semantic_change_alters_fingerprint(self) -> None:
        changed = replace(
            self.bundle,
            canonical_narrative=self.bundle.canonical_narrative + " changed",
        )
        self.assertNotEqual(
            changed.semantic_fingerprint,
            self.bundle.semantic_fingerprint,
        )

    def test_33_serialization_round_trip(self) -> None:
        loaded = type(self.bundle).from_json(self.bundle.to_json())
        self.assertTrue(loaded.semantically_equals(self.bundle))

    def test_34_secret_shape_scanning_blocks_export(self) -> None:
        secret = replace(
            self.bundle,
            canonical_narrative=(
                "Authorization: Bearer abcdefghijklmnopqrstuvwxyz"
            ),
        )
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ExplanationSerializationError):
                export_explanation_bundle(secret, Path(directory) / "bundle.json")

    def test_35_query_api_returns_exact_records(self) -> None:
        relationship = self.bundle.relationship_explanations[0]
        path = self.bundle.path_explanations[0]
        field = self.bundle.field_explanations[0]
        dataset = self.bundle.dataset_explanations[0]
        uncertainty = self.bundle.uncertainties[0]
        self.assertIs(
            self.bundle.explain_relationship(relationship.relationship_id),
            relationship,
        )
        self.assertIs(self.bundle.explain_path(path.path_id), path)
        self.assertIs(self.bundle.explain_field(field.field_key), field)
        self.assertIs(
            self.bundle.explain_dataset(dataset.dataset_urn),
            dataset,
        )
        self.assertIs(
            self.bundle.explain_uncertainty(uncertainty.uncertainty_id),
            uncertainty,
        )

    def test_36_query_api_fails_closed_for_unknown_subjects(self) -> None:
        with self.assertRaises(KeyError):
            self.bundle.explain_relationship("missing")
        with self.assertRaises(KeyError):
            self.bundle.explain_path("missing")
        with self.assertRaises(KeyError):
            self.bundle.explain_field(FieldMachineKey("missing", "missing"))
        with self.assertRaises(KeyError):
            self.bundle.explain_dataset("missing")
        with self.assertRaises(KeyError):
            self.bundle.explain_uncertainty("missing")

    def test_37_source_steps_are_typed_and_ordered(self) -> None:
        self.assertEqual(
            tuple(
                item.step_type for item in self.bundle.source_explanation.steps
            ),
            (
                ExplanationStepType.CURRENT_FACT,
                ExplanationStepType.PROPOSED_CHANGE,
                ExplanationStepType.COUNTERFACTUAL_DERIVATION,
            ),
        )

    def test_38_evidence_chain_contains_all_nine_inputs(self) -> None:
        chain = self.bundle.evidence_chains[0]
        self.assertEqual(len(chain.references), 9)
        self.assertEqual(
            {item.artifact_name for item in chain.references},
            {path.name for path in PATHS},
        )

    def test_39_every_explanation_references_the_evidence_chain(self) -> None:
        chain_id = self.bundle.evidence_chains[0].chain_id
        values = (
            (self.bundle.source_explanation,)
            + self.bundle.relationship_explanations
            + self.bundle.path_explanations
            + self.bundle.field_explanations
            + self.bundle.dataset_explanations
            + self.bundle.uncertainties
        )
        self.assertTrue(
            all(item.evidence_chain_id == chain_id for item in values)
        )

    def test_40_all_step_provenance_resolves(self) -> None:
        known = set(self.snapshot.evidence_by_id()) | {
            item.provenance_id
            for item in self.future_graph.provenance_registry
        }
        steps = (
            self.bundle.source_explanation.steps
            + tuple(
                step
                for item in self.bundle.relationship_explanations
                for step in item.steps
            )
            + tuple(
                step
                for item in self.bundle.path_explanations
                for step in item.steps
            )
            + tuple(
                step
                for item in self.bundle.field_explanations
                for step in item.steps
            )
            + tuple(
                step
                for item in self.bundle.dataset_explanations
                for step in item.steps
            )
        )
        self.assertTrue(
            all(set(step.provenance_ids).issubset(known) for step in steps)
        )

    def test_41_paths_preserve_order_depth_and_edge_states(self) -> None:
        expected = {
            item.path_id: item for item in self.compatibility.path_evaluations
        }
        for item in self.bundle.path_explanations:
            source = expected[item.path_id]
            self.assertEqual(item.ordered_relationship_ids, source.relationship_ids)
            self.assertEqual(item.depth, source.depth)
            self.assertEqual(
                item.edge_compatibility_states,
                source.edge_compatibility_states,
            )

    def test_42_dataset_summary_is_technical_not_health_verdict(self) -> None:
        for item in self.bundle.dataset_explanations:
            self.assertIn(
                "technical compatibility summary",
                item.human_explanation,
            )
            self.assertIn("not a business-impact", item.human_explanation)
            self.assertIn("or health verdict", item.human_explanation)

    def test_43_twenty_one_fields_are_multipath_exposed(self) -> None:
        multipath = tuple(
            item
            for item in self.bundle.field_explanations
            if len(item.supporting_path_ids) > 1
        )
        self.assertEqual(len(multipath), 21)
        self.assertTrue(
            all(item.all_paths_share_first_uncertainty for item in multipath)
        )
        self.assertTrue(
            all(not item.path_conclusions_differ for item in multipath)
        )

    def test_44_models_are_immutable(self) -> None:
        with self.assertRaises(FrozenInstanceError):
            self.bundle.canonical_narrative = "changed"

    def test_45_fingerprint_chain_mismatch_fails_closed(self) -> None:
        changed = replace(
            self.bundle,
            compatibility_fingerprint="sha256:" + "0" * 64,
        )
        with self.assertRaises(ExplanationValidationError):
            self.validate(changed)

    def test_46_changed_relationship_conclusion_fails_closed(self) -> None:
        first = self.bundle.relationship_explanations[0]
        replacement = replace(
            first,
            compatibility_state=CompatibilityState.COMPATIBLE,
        )
        changed = replace(
            self.bundle,
            relationship_explanations=(
                replacement,
            )
            + self.bundle.relationship_explanations[1:],
        )
        with self.assertRaises(ExplanationValidationError):
            self.validate(changed)

    def test_47_unknown_path_edge_fails_closed(self) -> None:
        first = self.bundle.path_explanations[0]
        replacement = replace(
            first,
            ordered_relationship_ids=("missing-edge",)
            + first.ordered_relationship_ids[1:],
        )
        changed = replace(
            self.bundle,
            path_explanations=(replacement,)
            + self.bundle.path_explanations[1:],
        )
        with self.assertRaises(ExplanationValidationError):
            self.validate(changed)

    def test_48_dangling_provenance_fails_closed(self) -> None:
        relationship = self.bundle.relationship_explanations[0]
        step = replace(
            relationship.steps[0],
            provenance_ids=("missing-evidence",),
        )
        replacement = replace(
            relationship,
            steps=(step,) + relationship.steps[1:],
        )
        changed = replace(
            self.bundle,
            relationship_explanations=(replacement,)
            + self.bundle.relationship_explanations[1:],
        )
        with self.assertRaises(ExplanationValidationError):
            self.validate(changed)

    def test_49_human_and_typed_conclusion_disagreement_fails_closed(self) -> None:
        relationship = self.source_edge()
        replacement = replace(
            relationship,
            human_explanation="The existing conclusion is COMPATIBLE.",
        )
        changed = replace(
            self.bundle,
            relationship_explanations=tuple(
                replacement if item.relationship_id == SOURCE_EDGE_ID else item
                for item in self.bundle.relationship_explanations
            ),
        )
        with self.assertRaises(ExplanationValidationError):
            self.validate(changed)

    def test_50_exported_bundle_loads_as_read_only_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = export_explanation_bundle(
                self.bundle,
                Path(directory) / "explanation_bundle.json",
            )
            loaded = load_explanation_bundle(path)
        self.assertTrue(loaded.semantically_equals(self.bundle))

    def test_51_source_explanation_contains_no_downstream_conclusion(self) -> None:
        text = self.bundle.source_explanation.human_explanation
        self.assertNotIn("downstream", text.lower())
        self.assertNotIn("UNKNOWN", text)

    def test_52_malformed_serialized_types_fail_closed(self) -> None:
        raw = json.loads(self.bundle.to_json())
        raw["relationship_explanations"] = "not-an-array"
        with self.assertRaises(ExplanationSerializationError):
            type(self.bundle).from_json(json.dumps(raw))


if __name__ == "__main__":
    unittest.main()
