from __future__ import annotations

import hashlib
import json
import shutil
import socket
import tempfile
import unittest
from collections import Counter
from dataclasses import FrozenInstanceError, fields, is_dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from chronos.change_semantics import load_contract
from chronos.compatibility_evaluation import (
    CompatibilityReasonCode,
    CompatibilityState,
    EvidenceStrength,
    load_compatibility_evaluation,
)
from chronos.counterfactual_source import (
    FieldMappingClassification,
    load_source_state,
)
from chronos.dependency_propagation import (
    FieldExposureState,
    load_dependency_propagation,
)
from chronos.explanations import load_explanation_bundle
from chronos.future_graph import (
    FutureIdentityMappingClassification,
    GraphObjectState,
    ProvenanceKind,
    load_future_graph,
)
from chronos.phase2_certification import (
    Phase2CertificationState,
    load_certification,
)
from chronos.phase3_certification import (
    CertificationCheckCategory,
    CertificationCheckStatus,
    Phase3CertificationInputError,
    Phase3CertificationSerializationError,
    Phase3CertificationStatus,
    certify_phase3_from_artifacts,
    export_phase3_certification,
    load_phase3_certification,
    validate_phase3_certification,
)
from chronos.proposal import CANONICAL_DATASET_URN, load_proposal
from chronos.proposal_validation import load_validation_result
from chronos.snapshot import (
    FieldMachineKey,
    RelationshipCategory,
    SnapshotValidationState,
    contains_secret,
    load_snapshot,
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
)
PATHS = tuple(ARTIFACTS / name for name in NAMES)
CURRENT = FieldMachineKey(CANONICAL_DATASET_URN, "order_total")
CANDIDATE = FieldMachineKey(CANONICAL_DATASET_URN, "order_amount")
SOURCE_EDGE_ID = "future-lineage-68f7e0269dbea7279911b809"


def fixed_clock(hour: int):
    return lambda: datetime(2026, 7, 28, hour, tzinfo=timezone.utc)


class Phase3CertificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.hashes = {
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
        cls.result = cls.build(5)

    @classmethod
    def build(cls, hour: int):
        return certify_phase3_from_artifacts(
            *PATHS,
            clock=fixed_clock(hour),
        )

    def check(self, check_id: str):
        return next(
            item
            for item in self.result.certification_checks
            if item.check_id == check_id
        )

    def source_edge(self):
        return next(
            item
            for item in self.compatibility.relationship_evaluations
            if item.relationship_id == SOURCE_EDGE_ID
        )

    def assert_corruption_fails(self, name: str, mutate) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            copied = []
            for path in PATHS:
                target = root / path.name
                shutil.copyfile(path, target)
                copied.append(target)
            target = root / name
            raw = json.loads(target.read_text(encoding="utf-8"))
            mutate(raw)
            target.write_text(
                json.dumps(raw, sort_keys=True, separators=(",", ":")),
                encoding="utf-8",
            )
            with self.assertRaises(Phase3CertificationInputError):
                certify_phase3_from_artifacts(
                    *copied,
                    clock=fixed_clock(6),
                )

    def test_01_canonical_phase_3_certification_succeeds(self) -> None:
        self.assertIs(
            self.result.certification_status,
            Phase3CertificationStatus.CERTIFIED,
        )
        validate_phase3_certification(self.result)

    def test_02_all_ten_artifacts_load(self) -> None:
        self.assertEqual(len(self.result.input_artifact_identities), 10)
        self.assertEqual(
            tuple(item.artifact_name for item in self.result.input_artifact_identities),
            NAMES,
        )

    def test_03_every_fingerprint_reproduces(self) -> None:
        self.assertIs(
            self.check("determinism.semantic_fingerprints_reproduce").status,
            CertificationCheckStatus.PASS,
        )

    def test_04_predecessor_chain_matches(self) -> None:
        self.assertIs(
            self.check("cross_reference.complete_dependency_chain").status,
            CertificationCheckStatus.PASS,
        )

    def test_05_demonstration_identity_is_consistent(self) -> None:
        self.assertEqual(self.result.demonstration_id, "CHRONOS-DEMO-001")
        self.assertIs(
            self.check("cross_reference.demonstration_identity").status,
            CertificationCheckStatus.PASS,
        )

    def test_06_proposal_identity_is_consistent(self) -> None:
        self.assertIs(
            self.check("cross_reference.proposal_identity").status,
            CertificationCheckStatus.PASS,
        )

    def test_07_source_rename_is_consistent(self) -> None:
        renamed = tuple(
            item
            for item in self.source.field_identity_mappings
            if item.classification is FieldMappingClassification.RENAMED
        )
        self.assertEqual(len(renamed), 1)
        self.assertEqual(
            renamed[0].current_identity.machine_key,
            (CANONICAL_DATASET_URN, "order_total"),
        )
        self.assertEqual(
            renamed[0].candidate_identity.machine_key,
            (CANONICAL_DATASET_URN, "order_amount"),
        )

    def test_08_candidate_schema_cardinality_is_fifteen(self) -> None:
        self.assertEqual(len(self.source.candidate_source_schema.fields), 15)

    def test_09_order_total_is_absent_from_candidate_source(self) -> None:
        self.assertFalse(
            any(
                item.field_path == "order_total"
                for item in self.source.candidate_source_schema.fields
            )
        )

    def test_10_order_amount_exists_exactly_once(self) -> None:
        amount = tuple(
            item
            for item in self.source.candidate_source_schema.fields
            if item.field_path == "order_amount"
        )
        self.assertEqual(len(amount), 1)
        self.assertEqual(amount[0].position, 5)

    def test_11_future_graph_has_twenty_one_datasets(self) -> None:
        self.assertEqual(len(self.graph.dataset_registry), 21)

    def test_12_future_graph_has_twenty_six_active_fields(self) -> None:
        self.assertEqual(len(self.graph.field_registry), 26)

    def test_13_future_graph_has_twenty_five_downstream_fields(self) -> None:
        self.assertEqual(
            len({item.key for item in self.graph.field_registry} - {CANDIDATE}),
            25,
        )

    def test_14_future_graph_has_twenty_seven_structural_edges(self) -> None:
        self.assertEqual(len(self.graph.relationship_registry), 27)

    def test_15_future_graph_has_twenty_eight_mapping_groups(self) -> None:
        self.assertEqual(len(self.graph.mapping_group_registry), 28)

    def test_16_future_graph_has_forty_eight_paths(self) -> None:
        self.assertEqual(len(self.graph.path_registry), 48)

    def test_17_maximum_shortest_depth_is_five(self) -> None:
        self.assertEqual(
            self.propagation.summary.maximum_exposure_depth,
            5,
        )

    def test_18_every_edge_endpoint_resolves(self) -> None:
        keys = {item.key for item in self.graph.field_registry}
        self.assertTrue(
            all(
                item.upstream in keys and item.downstream in keys
                for item in self.graph.relationship_registry
            )
        )

    def test_19_path_node_edge_cardinality_is_valid(self) -> None:
        self.assertTrue(
            all(
                len(item.projected_relationship_ids)
                == len(item.projected_node_keys) - 1
                for item in self.graph.path_registry
            )
        )

    def test_20_every_path_edge_connects_adjacent_nodes(self) -> None:
        relationships = {
            item.relationship_id: item
            for item in self.graph.relationship_registry
        }
        for path in self.graph.path_registry:
            for index, relationship_id in enumerate(
                path.projected_relationship_ids
            ):
                relationship = relationships[relationship_id]
                self.assertEqual(
                    relationship.upstream,
                    path.projected_node_keys[index],
                )
                self.assertEqual(
                    relationship.downstream,
                    path.projected_node_keys[index + 1],
                )

    def test_21_multipath_counts_are_valid(self) -> None:
        for item in self.propagation.field_exposure_registry:
            self.assertEqual(
                item.path_count,
                len(set(item.supporting_path_ids)),
            )

    def test_22_propagation_contains_twenty_five_downstream_fields(self) -> None:
        self.assertEqual(
            self.propagation.summary.total_unique_downstream_exposed_fields,
            25,
        )

    def test_23_propagation_contains_twenty_datasets(self) -> None:
        self.assertEqual(
            self.propagation.summary.unique_downstream_exposed_datasets,
            20,
        )

    def test_24_source_changed_state_is_valid(self) -> None:
        source = next(
            item
            for item in self.propagation.field_exposure_registry
            if item.field_key == CANDIDATE
        )
        self.assertIs(source.exposure_state, FieldExposureState.SOURCE_CHANGED)

    def test_25_direct_exposure_is_valid(self) -> None:
        edge = next(
            item
            for item in self.graph.relationship_registry
            if item.relationship_id == SOURCE_EDGE_ID
        )
        direct = next(
            item
            for item in self.propagation.field_exposure_registry
            if item.field_key == edge.downstream
        )
        self.assertIs(
            direct.exposure_state,
            FieldExposureState.DIRECTLY_EXPOSED,
        )

    def test_26_compatibility_evaluates_twenty_seven_relationships(self) -> None:
        self.assertEqual(len(self.compatibility.relationship_evaluations), 27)

    def test_27_compatibility_evaluates_forty_eight_paths(self) -> None:
        self.assertEqual(len(self.compatibility.path_evaluations), 48)

    def test_28_compatibility_evaluates_twenty_five_fields(self) -> None:
        self.assertEqual(len(self.compatibility.field_evaluations), 25)

    def test_29_compatibility_evaluates_twenty_datasets(self) -> None:
        self.assertEqual(len(self.compatibility.dataset_summaries), 20)

    def test_30_source_boundary_is_unknown(self) -> None:
        self.assertIs(
            self.source_edge().compatibility_state,
            CompatibilityState.UNKNOWN,
        )

    def test_31_source_boundary_evidence_is_insufficient(self) -> None:
        self.assertIs(
            self.source_edge().evidence_strength,
            EvidenceStrength.INSUFFICIENT,
        )

    def test_32_source_boundary_reason_is_correct(self) -> None:
        self.assertIs(
            self.source_edge().reason_code,
            CompatibilityReasonCode.SOURCE_RENAME_SEMANTICS_UNKNOWN,
        )

    def test_33_twenty_six_relationships_are_conditional(self) -> None:
        self.assertEqual(
            sum(
                item.compatibility_state
                is CompatibilityState.CONDITIONALLY_COMPATIBLE
                for item in self.compatibility.relationship_evaluations
            ),
            26,
        )

    def test_34_all_canonical_paths_remain_unknown(self) -> None:
        self.assertTrue(
            all(
                item.compatibility_state is CompatibilityState.UNKNOWN
                for item in self.compatibility.path_evaluations
            )
        )

    def test_35_explanation_has_twenty_seven_relationships(self) -> None:
        self.assertEqual(len(self.explanations.relationship_explanations), 27)

    def test_36_explanation_has_forty_eight_paths(self) -> None:
        self.assertEqual(len(self.explanations.path_explanations), 48)

    def test_37_explanation_has_twenty_five_fields(self) -> None:
        self.assertEqual(len(self.explanations.field_explanations), 25)

    def test_38_explanation_has_twenty_datasets(self) -> None:
        self.assertEqual(len(self.explanations.dataset_explanations), 20)

    def test_39_explanations_do_not_change_compatibility(self) -> None:
        expected = {
            item.relationship_id: item.compatibility_state
            for item in self.compatibility.relationship_evaluations
        }
        actual = {
            item.relationship_id: item.compatibility_state
            for item in self.explanations.relationship_explanations
        }
        self.assertEqual(actual, expected)

    def test_40_root_uncertainty_resolves(self) -> None:
        uncertainty = self.explanations.explain_uncertainty(
            "uncertainty-source-rename-boundary"
        )
        self.assertEqual(uncertainty.subject, SOURCE_EDGE_ID)

    def test_41_all_provenance_closes(self) -> None:
        self.assertIs(
            self.check("provenance.full_closure").status,
            CertificationCheckStatus.PASS,
        )

    def test_42_current_and_counterfactual_are_not_conflated(self) -> None:
        current = tuple(
            item
            for item in self.graph.provenance_registry
            if item.kind is ProvenanceKind.CURRENT_EVIDENCE
        )
        projected = tuple(
            item
            for item in self.graph.provenance_registry
            if item.kind is ProvenanceKind.COUNTERFACTUAL_DERIVATION
        )
        self.assertEqual(len(current), 380)
        self.assertEqual(len(projected), 51)
        self.assertFalse(
            {item.provenance_id for item in current}
            & {item.provenance_id for item in projected}
        )

    def test_43_context_is_not_used_for_field_propagation(self) -> None:
        context = {
            item.current_relationship_id
            for item in self.graph.context_relationship_registry
        }
        propagated = {
            item.relationship_id
            for item in self.propagation.relationship_exposure_registry
        }
        self.assertFalse(context & propagated)

    def test_44_no_business_impact_model_exists(self) -> None:
        self.assertNotIn("business_impact", self.model_field_names())

    def test_45_no_severity_or_risk_model_exists(self) -> None:
        names = self.model_field_names()
        self.assertNotIn("severity_score", names)
        self.assertNotIn("risk_score", names)

    def test_46_no_repair_model_exists(self) -> None:
        names = self.model_field_names()
        self.assertNotIn("repair_priority", names)
        self.assertNotIn("repair_recommendation", names)

    def test_47_all_prior_artifacts_are_unchanged(self) -> None:
        after = {
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in PATHS
        }
        self.assertEqual(after, self.hashes)
        self.assertTrue(
            all(item.unchanged for item in self.result.artifact_immutability)
        )

    def test_48_phase_3_1_reconstructs_deterministically(self) -> None:
        self.assertEqual(
            self.result.phase_3_semantic_fingerprints.counterfactual_source,
            self.source.semantic_fingerprint,
        )

    def test_49_phase_3_2_reconstructs_deterministically(self) -> None:
        self.assertEqual(
            self.result.phase_3_semantic_fingerprints.future_graph,
            self.graph.semantic_fingerprint,
        )

    def test_50_phase_3_3_reconstructs_deterministically(self) -> None:
        self.assertEqual(
            self.result.phase_3_semantic_fingerprints.dependency_propagation,
            self.propagation.semantic_fingerprint,
        )

    def test_51_phase_3_4_reconstructs_deterministically(self) -> None:
        self.assertEqual(
            self.result.phase_3_semantic_fingerprints.compatibility_evaluation,
            self.compatibility.semantic_fingerprint,
        )

    def test_52_phase_3_5_reconstructs_deterministically(self) -> None:
        self.assertEqual(
            self.result.phase_3_semantic_fingerprints.explanation_bundle,
            self.explanations.semantic_fingerprint,
        )

    def test_53_certification_fingerprint_is_timestamp_independent(self) -> None:
        changed = replace(
            self.result,
            certified_at="2026-07-29T05:00:00+00:00",
        )
        self.assertEqual(
            changed.semantic_fingerprint,
            self.result.semantic_fingerprint,
        )

    def test_54_certification_fingerprint_is_deterministic(self) -> None:
        self.assertEqual(
            type(self.result).from_json(self.result.to_json()).semantic_fingerprint,
            self.result.semantic_fingerprint,
        )

    def test_55_certification_serialization_round_trip(self) -> None:
        loaded = type(self.result).from_json(self.result.to_json())
        self.assertTrue(loaded.semantically_equals(self.result))

    def test_56_secret_scanning_passes(self) -> None:
        self.assertFalse(contains_secret(self.result.to_dict()))

    def test_57_network_blocked_certification_succeeds(self) -> None:
        with patch.object(
            socket,
            "create_connection",
            side_effect=AssertionError("network attempted"),
        ):
            rebuilt = self.build(7)
        self.assertIs(
            rebuilt.certification_status,
            Phase3CertificationStatus.CERTIFIED,
        )

    def test_58_malformed_graph_fails_closed(self) -> None:
        self.assert_corruption_fails(
            "future_metadata_graph.json",
            lambda raw: raw.__setitem__("field_registry", []),
        )

    def test_59_malformed_path_fails_closed(self) -> None:
        self.assert_corruption_fails(
            "future_metadata_graph.json",
            lambda raw: raw["path_registry"][0].__setitem__(
                "projected_relationship_ids",
                [],
            ),
        )

    def test_60_dangling_provenance_fails_closed(self) -> None:
        self.assert_corruption_fails(
            "future_metadata_graph.json",
            lambda raw: raw["field_registry"][0].__setitem__(
                "provenance_ids",
                ["missing-provenance"],
            ),
        )

    def test_61_compatibility_mismatch_fails_closed(self) -> None:
        self.assert_corruption_fails(
            "compatibility_evaluation.json",
            lambda raw: raw["relationship_evaluations"][0].__setitem__(
                "compatibility_state",
                "compatible",
            ),
        )

    def test_62_explanation_mismatch_fails_closed(self) -> None:
        self.assert_corruption_fails(
            "explanation_bundle.json",
            lambda raw: raw["relationship_explanations"][0].__setitem__(
                "compatibility_state",
                "compatible",
            ),
        )

    def test_63_fingerprint_mismatch_fails_closed(self) -> None:
        self.assert_corruption_fails(
            "dependency_propagation.json",
            lambda raw: raw.__setitem__(
                "future_graph_fingerprint",
                "sha256:" + "0" * 64,
            ),
        )

    def test_64_current_artifact_mutation_fails_closed(self) -> None:
        self.assert_corruption_fails(
            "current_metadata_snapshot.json",
            lambda raw: raw.__setitem__(
                "source_dataset_urn",
                "urn:li:dataset:(urn:li:dataPlatform:postgres,wrong,PROD)",
            ),
        )

    def test_65_phase_1_certification_regression_passes(self) -> None:
        self.assertIs(
            self.snapshot.validation_result.state,
            SnapshotValidationState.VALID,
        )

    def test_66_phase_2_certification_regression_passes(self) -> None:
        self.assertIs(
            self.phase2.certification_state,
            Phase2CertificationState.CERTIFIED,
        )

    def test_67_complete_certification_has_no_failed_checks(self) -> None:
        self.assertTrue(
            all(
                item.status is CertificationCheckStatus.PASS
                for item in self.result.certification_checks
            )
        )

    def test_68_all_required_check_categories_exist(self) -> None:
        self.assertEqual(
            {item.category for item in self.result.certification_checks},
            set(CertificationCheckCategory),
        )

    def test_69_frozen_baseline_metrics_are_exact(self) -> None:
        self.assertEqual(
            (
                self.result.summary_metrics.datasets,
                self.result.summary_metrics.active_future_fields,
                self.result.summary_metrics.downstream_fields,
                self.result.summary_metrics.downstream_datasets,
                self.result.summary_metrics.structural_relationships,
                self.result.summary_metrics.mapping_groups,
                self.result.summary_metrics.supporting_paths,
            ),
            (21, 26, 25, 20, 27, 28, 48),
        )

    def test_70_longer_paths_do_not_change_minimum_depth(self) -> None:
        self.assertEqual(
            self.result.summary_metrics.maximum_shortest_exposure_depth,
            5,
        )
        self.assertEqual(
            self.result.summary_metrics.maximum_stored_path_depth,
            7,
        )

    def test_71_context_counts_are_preserved(self) -> None:
        current = Counter(
            item.category
            for item in self.snapshot.relationships
            if item.category is not RelationshipCategory.FIELD_LINEAGE
        )
        future = Counter(
            item.category for item in self.graph.context_relationship_registry
        )
        self.assertEqual(future, current)

    def test_72_context_remains_counterfactual_inherited(self) -> None:
        self.assertTrue(
            all(
                item.state is GraphObjectState.COUNTERFACTUAL_INHERITED
                for item in self.graph.context_relationship_registry
            )
        )

    def test_73_downstream_identity_mappings_are_preserved(self) -> None:
        mappings = tuple(
            item
            for item in self.graph.current_to_future_identity_mappings
            if item.classification
            is FutureIdentityMappingClassification.IDENTITY_PRESERVED
        )
        self.assertEqual(len(mappings), 25)
        self.assertTrue(
            all(item.current_identity == item.future_identity for item in mappings)
        )

    def test_74_no_candidate_schema_field_urn_is_fabricated(self) -> None:
        self.assertTrue(
            all(
                item.schema_field_urn is None
                for item in self.source.candidate_source_schema.fields
            )
        )

    def test_75_certification_models_are_immutable(self) -> None:
        with self.assertRaises(FrozenInstanceError):
            self.result.certification_status = Phase3CertificationStatus.FAILED

    def test_76_certification_export_and_load(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = export_phase3_certification(
                self.result,
                Path(directory) / "phase_3_certification.json",
            )
            loaded = load_phase3_certification(path)
        self.assertTrue(loaded.semantically_equals(self.result))

    def test_77_tampered_certification_fingerprint_fails(self) -> None:
        raw = json.loads(self.result.to_json())
        raw["semantic_fingerprint"] = "sha256:" + "0" * 64
        with self.assertRaises(Phase3CertificationSerializationError):
            type(self.result).from_json(json.dumps(raw))

    def test_78_check_records_are_typed_and_evidence_backed(self) -> None:
        self.assertTrue(
            all(
                item.check_id
                and item.description
                and item.evidence is not None
                and item.expected_value
                and item.observed_value
                and item.severity_if_failed.value == "blocking"
                for item in self.result.certification_checks
            )
        )

    def model_field_names(self) -> set[str]:
        names: set[str] = set()

        def visit(value) -> None:
            if is_dataclass(value):
                for item in fields(value):
                    names.add(item.name.lower())
                    visit(getattr(value, item.name))
            elif isinstance(value, tuple):
                for item in value:
                    visit(item)

        for root in (
            self.source,
            self.graph,
            self.propagation,
            self.compatibility,
            self.explanations,
        ):
            visit(root)
        return names


if __name__ == "__main__":
    unittest.main()
