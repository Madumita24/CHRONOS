from __future__ import annotations

import hashlib
import socket
import tempfile
import unittest
from dataclasses import FrozenInstanceError, fields, is_dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from chronos.change_semantics import load_contract
from chronos.compatibility_evaluation import (
    CompatibilityEntryPreconditionError,
    CompatibilityEvaluationResult,
    CompatibilityEvaluationState,
    CompatibilityReasonCode,
    CompatibilityState,
    CompatibilityValidationError,
    EvidenceStrength,
    ExplicitRenameBehavior,
    RenameCompatibilityEvidence,
    compatibility_semantic_fingerprint,
    evaluate_compatibility,
    evaluate_compatibility_from_artifacts,
    evaluate_field_rename_evidence,
    export_compatibility_evaluation,
    load_compatibility_evaluation,
    roll_up_field_compatibility,
    roll_up_path_compatibility,
    validate_compatibility_evaluation,
)
from chronos.counterfactual_source import InputArtifactHash, load_source_state
from chronos.dependency_propagation import load_dependency_propagation
from chronos.future_graph import (
    FutureRelationshipState,
    load_future_graph,
)
from chronos.phase2_certification import load_certification
from chronos.proposal import CANONICAL_DATASET_URN, load_proposal
from chronos.proposal_validation import load_validation_result
from chronos.snapshot import FieldMachineKey, load_snapshot
from chronos.snapshot.serialization import contains_secret


ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "artifacts"
SNAPSHOT_PATH = ARTIFACTS / "current_metadata_snapshot.json"
PROPOSAL_PATH = ARTIFACTS / "change_proposal.json"
VALIDATION_PATH = ARTIFACTS / "change_proposal_validation.json"
CONTRACT_PATH = ARTIFACTS / "change_semantic_contract.json"
CERTIFICATION_PATH = ARTIFACTS / "phase_2_certification.json"
SOURCE_STATE_PATH = ARTIFACTS / "counterfactual_source_state.json"
FUTURE_GRAPH_PATH = ARTIFACTS / "future_metadata_graph.json"
PROPAGATION_PATH = ARTIFACTS / "dependency_propagation.json"
COMPATIBILITY_PATH = ARTIFACTS / "compatibility_evaluation.json"
INPUT_PATHS = (
    SNAPSHOT_PATH,
    PROPOSAL_PATH,
    VALIDATION_PATH,
    CONTRACT_PATH,
    CERTIFICATION_PATH,
    SOURCE_STATE_PATH,
    FUTURE_GRAPH_PATH,
    PROPAGATION_PATH,
)
CURRENT_SOURCE = FieldMachineKey(CANONICAL_DATASET_URN, "order_total")
CANDIDATE_SOURCE = FieldMachineKey(CANONICAL_DATASET_URN, "order_amount")


def fixed_clock(hour: int):
    return lambda: datetime(2026, 7, 28, hour, tzinfo=timezone.utc)


class CompatibilityEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.input_hashes = {
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in INPUT_PATHS
        }
        cls.snapshot = load_snapshot(SNAPSHOT_PATH)
        cls.proposal = load_proposal(PROPOSAL_PATH)
        cls.validation = load_validation_result(VALIDATION_PATH)
        cls.contract = load_contract(CONTRACT_PATH)
        cls.certification = load_certification(CERTIFICATION_PATH)
        cls.source_state = load_source_state(SOURCE_STATE_PATH)
        cls.future_graph = load_future_graph(FUTURE_GRAPH_PATH)
        cls.propagation = load_dependency_propagation(PROPAGATION_PATH)
        cls.result = cls.build(1)

    @classmethod
    def build(cls, hour: int) -> CompatibilityEvaluationResult:
        return evaluate_compatibility_from_artifacts(
            SNAPSHOT_PATH,
            PROPOSAL_PATH,
            VALIDATION_PATH,
            CONTRACT_PATH,
            CERTIFICATION_PATH,
            SOURCE_STATE_PATH,
            FUTURE_GRAPH_PATH,
            PROPAGATION_PATH,
            clock=fixed_clock(hour),
        )

    def test_01_authoritative_artifact_cross_references_validate(self) -> None:
        self.assertEqual(
            self.result.future_graph_fingerprint,
            self.future_graph.semantic_fingerprint,
        )
        self.assertEqual(
            self.result.dependency_propagation_fingerprint,
            self.propagation.semantic_fingerprint,
        )
        self.assertEqual(self.result.proposal_id, self.proposal.proposal_id)

    def test_02_source_change_identity_is_exact(self) -> None:
        self.assertEqual(
            self.result.source_change.current_field,
            CURRENT_SOURCE,
        )
        self.assertEqual(
            self.result.source_change.candidate_field,
            CANDIDATE_SOURCE,
        )

    def test_03_exactly_twenty_seven_relationships_are_evaluated(self) -> None:
        self.assertEqual(len(self.result.relationship_evaluations), 27)
        self.assertTrue(
            all(
                item.evaluation_state
                is CompatibilityEvaluationState.EVALUATED
                for item in self.result.relationship_evaluations
            )
        )

    def test_04_exactly_twenty_five_fields_are_evaluated(self) -> None:
        self.assertEqual(len(self.result.field_evaluations), 25)
        self.assertEqual(
            {item.field_key for item in self.result.field_evaluations},
            {
                item.field_key
                for item in self.propagation.field_exposure_registry
                if item.field_key != CANDIDATE_SOURCE
            },
        )

    def test_05_exactly_forty_eight_paths_are_evaluated(self) -> None:
        self.assertEqual(len(self.result.path_evaluations), 48)
        self.assertEqual(
            {item.path_id for item in self.result.path_evaluations},
            {item.path_id for item in self.propagation.path_registry},
        )

    def test_06_exactly_twenty_dataset_summaries_exist(self) -> None:
        self.assertEqual(len(self.result.dataset_summaries), 20)

    def test_07_source_rebased_edge_is_explicitly_unknown(self) -> None:
        edge = self.source_edge()
        self.assertIs(edge.structural_state, FutureRelationshipState.COUNTERFACTUAL_PROJECTED)
        self.assertIs(edge.compatibility_state, CompatibilityState.UNKNOWN)
        self.assertIs(edge.evidence_strength, EvidenceStrength.INSUFFICIENT)
        self.assertIs(
            edge.reason_code,
            CompatibilityReasonCode.SOURCE_RENAME_SEMANTICS_UNKNOWN,
        )

    def test_08_missing_transform_and_query_semantics_are_visible(self) -> None:
        edge = self.source_edge()
        self.assertEqual(edge.transform_operations, ())
        self.assertEqual(edge.query_evidence, ())
        self.assertIn("Missing transform semantics", edge.explanation)
        self.assertIn("query semantics", edge.explanation)

    def test_09_same_name_fields_do_not_imply_compatibility(self) -> None:
        evidence = self.synthetic_evidence(
            current_upstream_path="order_total",
            candidate_upstream_path="order_total",
        )
        decision = evaluate_field_rename_evidence(evidence)
        self.assertIs(
            decision.compatibility_state,
            CompatibilityState.CONDITIONALLY_COMPATIBLE,
        )
        self.assertIsNot(
            decision.compatibility_state,
            CompatibilityState.COMPATIBLE,
        )

    def test_10_direct_lineage_does_not_imply_compatibility(self) -> None:
        graph_by_id = {
            item.relationship_id: item
            for item in self.future_graph.relationship_registry
        }
        direct = next(
            item
            for item in self.result.relationship_evaluations
            if graph_by_id[item.relationship_id].current_classification
            == "direct"
        )
        self.assertIsNot(
            direct.compatibility_state,
            CompatibilityState.COMPATIBLE,
        )

    def test_11_none_transform_does_not_imply_compatibility(self) -> None:
        record = next(
            item
            for item in self.result.relationship_evaluations
            if "NONE" in item.transform_operations
        )
        self.assertIs(
            record.compatibility_state,
            CompatibilityState.CONDITIONALLY_COMPATIBLE,
        )

    def test_12_confidence_is_provenance_not_probability(self) -> None:
        high_confidence = next(
            item
            for item in self.result.relationship_evaluations
            if 1.0 in item.lineage_confidence_provenance
        )
        self.assertIsNot(
            high_confidence.compatibility_state,
            CompatibilityState.COMPATIBLE,
        )
        self.assertNotIsInstance(
            high_confidence.compatibility_state.value,
            float,
        )

    def test_13_explicit_compatible_evidence_is_supported(self) -> None:
        decision = evaluate_field_rename_evidence(
            self.synthetic_evidence(
                behavior=ExplicitRenameBehavior.ACCEPTS_RENAMED_INPUT,
            )
        )
        self.assertIs(decision.compatibility_state, CompatibilityState.COMPATIBLE)
        self.assertIs(decision.evidence_strength, EvidenceStrength.EXPLICIT)

    def test_14_explicit_incompatible_evidence_is_supported(self) -> None:
        decision = evaluate_field_rename_evidence(
            self.synthetic_evidence(
                behavior=ExplicitRenameBehavior.REJECTS_RENAMED_INPUT,
            )
        )
        self.assertIs(
            decision.compatibility_state,
            CompatibilityState.INCOMPATIBLE,
        )
        self.assertIs(
            decision.reason_code,
            CompatibilityReasonCode.EXPLICIT_TRANSFORM_INCOMPATIBLE,
        )

    def test_15_explicit_conditional_evidence_is_supported(self) -> None:
        decision = evaluate_field_rename_evidence(
            self.synthetic_evidence(
                behavior=ExplicitRenameBehavior.CONDITIONAL,
            )
        )
        self.assertIs(
            decision.compatibility_state,
            CompatibilityState.CONDITIONALLY_COMPATIBLE,
        )
        self.assertIs(decision.evidence_strength, EvidenceStrength.EXPLICIT)

    def test_16_insufficient_evidence_remains_unknown(self) -> None:
        decision = evaluate_field_rename_evidence(
            self.synthetic_evidence()
        )
        self.assertIs(decision.compatibility_state, CompatibilityState.UNKNOWN)
        self.assertIs(decision.evidence_strength, EvidenceStrength.INSUFFICIENT)

    def test_17_incompatible_edge_makes_path_incompatible(self) -> None:
        decision = roll_up_path_compatibility(
            (
                CompatibilityState.COMPATIBLE,
                CompatibilityState.INCOMPATIBLE,
            )
        )
        self.assertIs(
            decision.compatibility_state,
            CompatibilityState.INCOMPATIBLE,
        )

    def test_18_unknown_edge_makes_path_unknown(self) -> None:
        decision = roll_up_path_compatibility(
            (
                CompatibilityState.COMPATIBLE,
                CompatibilityState.UNKNOWN,
            )
        )
        self.assertIs(decision.compatibility_state, CompatibilityState.UNKNOWN)

    def test_19_conditional_edge_makes_path_conditional(self) -> None:
        decision = roll_up_path_compatibility(
            (
                CompatibilityState.COMPATIBLE,
                CompatibilityState.CONDITIONALLY_COMPATIBLE,
            )
        )
        self.assertIs(
            decision.compatibility_state,
            CompatibilityState.CONDITIONALLY_COMPATIBLE,
        )

    def test_20_all_compatible_edges_make_path_compatible(self) -> None:
        decision = roll_up_path_compatibility(
            (
                CompatibilityState.COMPATIBLE,
                CompatibilityState.COMPATIBLE,
            )
        )
        self.assertIs(decision.compatibility_state, CompatibilityState.COMPATIBLE)

    def test_21_mixed_multipath_rollup_preserves_uncertainty(self) -> None:
        decision = roll_up_field_compatibility(
            (
                CompatibilityState.COMPATIBLE,
                CompatibilityState.INCOMPATIBLE,
            )
        )
        self.assertIs(decision.compatibility_state, CompatibilityState.UNKNOWN)
        self.assertIs(
            decision.reason_code,
            CompatibilityReasonCode.MULTIPATH_MIXED_COMPATIBILITY,
        )

    def test_22_uniform_multipath_rollup_is_deterministic(self) -> None:
        decision = roll_up_field_compatibility(
            (
                CompatibilityState.CONDITIONALLY_COMPATIBLE,
                CompatibilityState.CONDITIONALLY_COMPATIBLE,
            )
        )
        self.assertIs(
            decision.compatibility_state,
            CompatibilityState.CONDITIONALLY_COMPATIBLE,
        )

    def test_23_all_canonical_paths_are_unknown(self) -> None:
        self.assertEqual(self.result.aggregate.path_counts.unknown, 48)
        self.assertTrue(
            all(
                item.compatibility_state is CompatibilityState.UNKNOWN
                for item in self.result.path_evaluations
            )
        )

    def test_24_unknown_paths_identify_the_source_edge(self) -> None:
        source_id = self.source_edge().relationship_id
        self.assertTrue(
            all(
                source_id in item.uncertain_relationship_ids
                for item in self.result.path_evaluations
            )
        )
        self.assertTrue(
            all(not item.blocking_relationship_ids for item in self.result.path_evaluations)
        )

    def test_25_all_canonical_fields_are_unknown(self) -> None:
        self.assertEqual(self.result.aggregate.field_counts.unknown, 25)
        self.assertTrue(
            all(
                item.compatibility_state is CompatibilityState.UNKNOWN
                and item.evidence_strength is EvidenceStrength.INSUFFICIENT
                for item in self.result.field_evaluations
            )
        )

    def test_26_all_dataset_summaries_preserve_unknown(self) -> None:
        self.assertEqual(self.result.aggregate.dataset_counts.unknown, 20)
        for item in self.result.dataset_summaries:
            self.assertEqual(
                item.unknown_exposed_fields,
                len(item.exposed_field_keys),
            )
            self.assertIs(item.compatibility_state, CompatibilityState.UNKNOWN)

    def test_27_relationship_aggregate_emerges_from_evidence(self) -> None:
        counts = self.result.aggregate.relationship_counts
        self.assertEqual(counts.compatible, 0)
        self.assertEqual(counts.incompatible, 0)
        self.assertEqual(counts.conditionally_compatible, 26)
        self.assertEqual(counts.unknown, 1)

    def test_28_evidence_strength_distribution_is_explicit(self) -> None:
        counts = self.result.aggregate.relationship_evidence_strength
        self.assertEqual(counts.explicit, 0)
        self.assertEqual(counts.derived, 26)
        self.assertEqual(counts.insufficient, 1)

    def test_29_relationship_records_preserve_mapping_evidence(self) -> None:
        graph_by_id = {
            item.relationship_id: item
            for item in self.future_graph.relationship_registry
        }
        for item in self.result.relationship_evaluations:
            source = graph_by_id[item.relationship_id]
            self.assertEqual(
                item.mapping_group_ids,
                source.current_mapping_group_ids,
            )
            self.assertEqual(
                item.lineage_confidence_provenance,
                source.current_confidence_scores,
            )

    def test_30_every_unknown_field_is_explainable_without_traversal(self) -> None:
        for item in self.result.field_evaluations:
            self.assertTrue(item.supporting_path_ids)
            self.assertTrue(item.incoming_relationship_ids)
            self.assertTrue(item.reason_codes)
            self.assertTrue(item.current_provenance_ids)
            self.assertTrue(item.counterfactual_provenance_ids)

    def test_31_no_downstream_field_is_renamed(self) -> None:
        self.assertNotIn(
            CANDIDATE_SOURCE,
            {item.field_key for item in self.result.field_evaluations},
        )
        self.assertEqual(
            {item.field_key for item in self.result.field_evaluations},
            {
                item.field_key
                for item in self.propagation.field_exposure_registry
                if item.field_key != CANDIDATE_SOURCE
            },
        )

    def test_32_future_graph_and_propagation_are_not_mutated(self) -> None:
        graph_before = self.future_graph.to_json()
        propagation_before = self.propagation.to_json()
        self.build(2)
        self.assertEqual(self.future_graph.to_json(), graph_before)
        self.assertEqual(self.propagation.to_json(), propagation_before)

    def test_33_all_prior_artifacts_are_unchanged(self) -> None:
        self.build(3)
        for path, expected in self.input_hashes.items():
            self.assertEqual(
                hashlib.sha256(path.read_bytes()).hexdigest(),
                expected,
            )

    def test_34_no_datahub_or_network_access(self) -> None:
        with patch.object(
            socket,
            "create_connection",
            side_effect=AssertionError("network access attempted"),
        ):
            result = evaluate_compatibility(
                self.snapshot,
                self.proposal,
                self.validation,
                self.contract,
                self.certification,
                self.source_state,
                self.future_graph,
                self.propagation,
                input_artifact_hashes=self.result.input_artifact_hashes,
                clock=fixed_clock(4),
            )
        self.assertEqual(len(result.relationship_evaluations), 27)

    def test_35_serialization_is_deterministic(self) -> None:
        self.assertEqual(self.build(5).to_json(), self.build(5).to_json())

    def test_36_timestamp_does_not_change_semantic_fingerprint(self) -> None:
        first = self.build(6)
        second = self.build(7)
        self.assertNotEqual(first.evaluated_at, second.evaluated_at)
        self.assertEqual(
            first.semantic_fingerprint,
            second.semantic_fingerprint,
        )
        self.assertTrue(first.semantically_equals(second))

    def test_37_semantic_mutation_changes_fingerprint(self) -> None:
        first = self.result.relationship_evaluations[0]
        relationships = (
            replace(first, explanation=first.explanation + " Probe."),
            *self.result.relationship_evaluations[1:],
        )
        changed = replace(
            self.result,
            relationship_evaluations=relationships,
        )
        self.assertNotEqual(
            changed.semantic_fingerprint,
            self.result.semantic_fingerprint,
        )
        with self.assertRaises(CompatibilityValidationError):
            validate_compatibility_evaluation(
                changed,
                self.future_graph,
                self.propagation,
            )

    def test_38_round_trip_deserialization(self) -> None:
        restored = CompatibilityEvaluationResult.from_json(
            self.result.to_json()
        )
        self.assertEqual(restored, self.result)

    def test_39_export_and_load_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "compatibility.json"
            export_compatibility_evaluation(self.result, path)
            self.assertEqual(
                load_compatibility_evaluation(path),
                self.result,
            )

    def test_40_result_is_immutable(self) -> None:
        with self.assertRaises(FrozenInstanceError):
            self.result.evaluated_at = "changed"  # type: ignore[misc]

    def test_41_secret_shape_scanning_passes(self) -> None:
        self.assertFalse(contains_secret(self.result.to_dict()))

    def test_42_public_model_contains_no_impact_risk_or_repair_fields(
        self,
    ) -> None:
        forbidden = {
            "impact",
            "severity",
            "risk",
            "criticality",
            "repair",
            "priority",
        }
        model_types = self.public_model_types()
        for model_type in model_types:
            names = {item.name.lower() for item in fields(model_type)}
            for name in names:
                self.assertTrue(
                    all(token not in name for token in forbidden),
                    f"{model_type.__name__}.{name}",
                )

    def test_43_wrong_future_graph_fingerprint_fails_closed(self) -> None:
        changed = replace(
            self.result,
            future_graph_fingerprint="sha256:" + ("0" * 64),
        )
        with self.assertRaises(CompatibilityValidationError):
            validate_compatibility_evaluation(
                changed,
                self.future_graph,
                self.propagation,
            )

    def test_44_wrong_propagation_fingerprint_fails_closed(self) -> None:
        changed = replace(
            self.result,
            dependency_propagation_fingerprint="sha256:" + ("f" * 64),
        )
        with self.assertRaises(CompatibilityValidationError):
            validate_compatibility_evaluation(
                changed,
                self.future_graph,
                self.propagation,
            )

    def test_45_dangling_mapping_group_fails_entry_preconditions(self) -> None:
        first = self.future_graph.relationship_registry[0]
        graph = replace(
            self.future_graph,
            relationship_registry=(
                replace(
                    first,
                    current_mapping_group_ids=("missing-mapping-group",),
                ),
                *self.future_graph.relationship_registry[1:],
            ),
        )
        with self.assertRaises(CompatibilityEntryPreconditionError):
            evaluate_compatibility(
                self.snapshot,
                self.proposal,
                self.validation,
                self.contract,
                self.certification,
                self.source_state,
                graph,
                self.propagation,
                input_artifact_hashes=self.result.input_artifact_hashes,
                clock=fixed_clock(8),
            )

    def test_46_changed_input_hash_fails_closed(self) -> None:
        first, *rest = self.result.input_artifact_hashes
        after = "f" * 64
        if after == first.before_sha256:
            after = "e" * 64
        hashes = (
            InputArtifactHash(
                first.artifact_name,
                first.before_sha256,
                after,
            ),
            *rest,
        )
        with self.assertRaises(CompatibilityEntryPreconditionError):
            evaluate_compatibility(
                self.snapshot,
                self.proposal,
                self.validation,
                self.contract,
                self.certification,
                self.source_state,
                self.future_graph,
                self.propagation,
                input_artifact_hashes=hashes,
                clock=fixed_clock(9),
            )

    def test_47_evaluation_scope_mismatch_fails_validation(self) -> None:
        with self.assertRaises(ValueError):
            replace(
                self.result,
                relationship_evaluations=(
                    self.result.relationship_evaluations[:-1]
                ),
                aggregate=replace(
                    self.result.aggregate,
                    relationship_counts=replace(
                        self.result.aggregate.relationship_counts,
                        conditionally_compatible=25,
                    ),
                    relationship_evidence_strength=replace(
                        self.result.aggregate.relationship_evidence_strength,
                        derived=25,
                    ),
                ),
            )

    def test_48_canonical_artifact_matches_evaluation(self) -> None:
        artifact = load_compatibility_evaluation(COMPATIBILITY_PATH)
        self.assertTrue(artifact.semantically_equals(self.result))

    def test_49_semantic_fingerprint_reproduces(self) -> None:
        self.assertEqual(
            compatibility_semantic_fingerprint(self.result),
            self.result.semantic_fingerprint,
        )

    def test_50_unknown_is_not_a_phase_failure(self) -> None:
        self.assertEqual(self.result.validation_state.value, "valid")
        self.assertEqual(self.result.aggregate.field_counts.unknown, 25)
        self.assertIn(
            "UNKNOWN is a successful evidence-limited evaluation",
            self.result.warnings[2],
        )

    def source_edge(self):
        return next(
            item
            for item in self.result.relationship_evaluations
            if item.upstream_field == CANDIDATE_SOURCE
        )

    def synthetic_evidence(
        self,
        *,
        current_upstream_path: str = "order_total",
        candidate_upstream_path: str = "order_amount",
        behavior: ExplicitRenameBehavior | None = None,
    ) -> RenameCompatibilityEvidence:
        current_upstream = FieldMachineKey(
            "urn:li:dataset:(urn:li:dataPlatform:test,source,PROD)",
            current_upstream_path,
        )
        candidate_upstream = FieldMachineKey(
            current_upstream.dataset_urn,
            candidate_upstream_path,
        )
        downstream = FieldMachineKey(
            "urn:li:dataset:(urn:li:dataPlatform:test,target,PROD)",
            "order_total",
        )
        return RenameCompatibilityEvidence(
            current_upstream=current_upstream,
            current_downstream=downstream,
            candidate_upstream=candidate_upstream,
            candidate_downstream=downstream,
            transform_operations=(),
            queries=(),
            explicit_rename_behavior=behavior,
        )

    def public_model_types(self):
        from chronos.compatibility_evaluation import models

        return tuple(
            value
            for value in vars(models).values()
            if isinstance(value, type)
            and is_dataclass(value)
            and value.__module__ == models.__name__
        )


if __name__ == "__main__":
    unittest.main()
