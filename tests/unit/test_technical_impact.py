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
    CompatibilityState,
    load_compatibility_evaluation,
)
from chronos.counterfactual_source import load_source_state
from chronos.dependency_propagation import load_dependency_propagation
from chronos.explanations import load_explanation_bundle
from chronos.future_graph import load_future_graph
from chronos.phase2_certification import load_certification
from chronos.phase3_certification import (
    Phase3SemanticFingerprints,
    load_phase3_certification,
)
from chronos.proposal import CANONICAL_DATASET_URN, load_proposal
from chronos.proposal_validation import load_validation_result
from chronos.snapshot import FieldMachineKey, contains_secret, load_snapshot
from chronos.technical_impact import (
    SourceTechnicalRole,
    TechnicalImpactEntryError,
    TechnicalImpactReasonCode,
    TechnicalImpactState,
    TechnicalImpactValidationError,
    derive_technical_impact,
    derive_technical_impact_from_artifacts,
    derive_technical_impact_state,
    export_technical_impact,
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
)
PATHS = tuple(ARTIFACTS / name for name in NAMES)
CANDIDATE = FieldMachineKey(CANONICAL_DATASET_URN, "order_amount")
SOURCE_EDGE_ID = "future-lineage-68f7e0269dbea7279911b809"


def fixed_clock(hour: int):
    return lambda: datetime(2026, 7, 28, hour, tzinfo=timezone.utc)


class TechnicalImpactTests(unittest.TestCase):
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
        cls.phase3 = load_phase3_certification(PATHS[10])
        cls.result = cls.build(6)

    @classmethod
    def build(cls, hour: int):
        return derive_technical_impact_from_artifacts(
            *PATHS,
            clock=fixed_clock(hour),
        )

    def validate(self, result) -> None:
        validate_technical_impact(
            result,
            self.source,
            self.graph,
            self.propagation,
            self.compatibility,
            self.explanations,
            self.phase3,
        )

    def source_relationship(self):
        return next(
            item
            for item in self.result.relationship_impacts
            if item.relationship_id == SOURCE_EDGE_ID
        )

    def test_01_canonical_derivation_succeeds(self) -> None:
        self.validate(self.result)
        self.assertTrue(self.result.semantic_fingerprint.startswith("sha256:"))

    def test_02_phase_3_certification_is_required(self) -> None:
        invalid_fingerprints = replace(
            self.phase3.phase_3_semantic_fingerprints,
            explanation_bundle="sha256:" + "0" * 64,
        )
        invalid_phase3 = replace(
            self.phase3,
            phase_3_semantic_fingerprints=invalid_fingerprints,
        )
        with self.assertRaises(TechnicalImpactEntryError):
            derive_technical_impact(
                self.snapshot,
                self.proposal,
                self.validation,
                self.contract,
                self.phase2,
                self.source,
                self.graph,
                self.propagation,
                self.compatibility,
                self.explanations,
                invalid_phase3,
                input_artifact_hashes=self.result.input_artifact_hashes,
                clock=fixed_clock(7),
            )

    def test_03_exactly_twenty_seven_relationship_impacts(self) -> None:
        self.assertEqual(len(self.result.relationship_impacts), 27)

    def test_04_exactly_forty_eight_path_impacts(self) -> None:
        self.assertEqual(len(self.result.path_impacts), 48)

    def test_05_exactly_twenty_five_field_impacts(self) -> None:
        self.assertEqual(len(self.result.field_impacts), 25)

    def test_06_exactly_twenty_dataset_summaries(self) -> None:
        self.assertEqual(len(self.result.dataset_summaries), 20)

    def test_07_source_boundary_is_unresolved_impact(self) -> None:
        self.assertIs(
            self.source_relationship().technical_impact_state,
            TechnicalImpactState.UNRESOLVED_IMPACT,
        )

    def test_08_unknown_does_not_become_confirmed_breakage(self) -> None:
        source = self.source_relationship()
        self.assertIs(source.compatibility_state, CompatibilityState.UNKNOWN)
        self.assertIsNot(
            source.technical_impact_state,
            TechnicalImpactState.CONFIRMED_IMPACT,
        )

    def test_09_conditional_relationship_is_not_guaranteed_safe(self) -> None:
        conditional = next(
            item
            for item in self.result.relationship_impacts
            if item.compatibility_state
            is CompatibilityState.CONDITIONALLY_COMPATIBLE
        )
        self.assertIs(
            conditional.technical_impact_state,
            TechnicalImpactState.POTENTIAL_IMPACT,
        )
        self.assertIn("not a confirmed failure", conditional.human_explanation)

    def test_10_source_is_excluded_from_downstream_impact(self) -> None:
        self.assertIs(
            self.result.source_change.role,
            SourceTechnicalRole.CHANGE_ORIGIN,
        )
        self.assertNotIn(
            CANDIDATE,
            {item.field_key for item in self.result.field_impacts},
        )

    def test_11_root_cause_is_consolidated(self) -> None:
        self.assertEqual(len(self.result.technical_impact_causes), 1)
        cause = self.result.technical_impact_causes[0]
        self.assertEqual(len(cause.affected_field_keys), 25)
        self.assertEqual(len(cause.affected_relationship_ids), 27)

    def test_12_all_downstream_records_trace_to_root_cause(self) -> None:
        cause_id = self.result.technical_impact_causes[0].cause_id
        self.assertTrue(
            all(
                cause_id in item.upstream_cause_ids
                for item in self.result.relationship_impacts
            )
        )
        self.assertTrue(
            all(cause_id in item.cause_ids for item in self.result.path_impacts)
        )
        self.assertTrue(
            all(cause_id in item.cause_ids for item in self.result.field_impacts)
        )

    def test_13_multipath_is_not_double_counted(self) -> None:
        for item in self.result.field_impacts:
            self.assertEqual(
                item.path_count,
                len(set(item.supporting_path_ids)),
            )
        self.assertEqual(len(self.result.field_impacts), 25)

    def test_14_depth_does_not_determine_impact_state(self) -> None:
        by_depth = {}
        for item in self.result.field_impacts:
            by_depth.setdefault(item.minimum_depth, set()).add(
                item.technical_impact_state
            )
        self.assertGreater(len(by_depth), 1)
        self.assertEqual(
            {state for states in by_depth.values() for state in states},
            {TechnicalImpactState.UNRESOLVED_IMPACT},
        )

    def test_15_path_count_does_not_determine_state(self) -> None:
        self.assertGreater(
            len({item.path_count for item in self.result.field_impacts}),
            1,
        )
        self.assertTrue(
            all(
                item.technical_impact_state
                is TechnicalImpactState.UNRESOLVED_IMPACT
                for item in self.result.field_impacts
            )
        )

    def test_16_context_metadata_is_not_used(self) -> None:
        names = self.model_field_names()
        for value in (
            "owners",
            "domains",
            "tags",
            "glossary",
            "data_products",
            "dashboards",
            "business_terms",
        ):
            self.assertNotIn(value, names)

    def test_17_no_severity_field(self) -> None:
        self.assertFalse(
            any("severity" in value for value in self.model_field_names())
        )

    def test_18_no_risk_field(self) -> None:
        self.assertFalse(
            any("risk" in value for value in self.model_field_names())
        )

    def test_19_no_business_criticality_field(self) -> None:
        names = self.model_field_names()
        self.assertNotIn("business_criticality", names)
        self.assertNotIn("criticality", names)

    def test_20_no_repair_recommendation(self) -> None:
        self.assertNotIn("repair recommendation", self.result.to_json().lower())

    def test_21_no_deployment_verdict(self) -> None:
        self.assertNotIn("deployment is unsafe", self.result.to_json().lower())
        self.assertNotIn("safe to deploy", self.result.to_json().lower())

    def test_22_incompatible_fixture_produces_confirmed_impact(self) -> None:
        state, reasons = derive_technical_impact_state(
            CompatibilityState.INCOMPATIBLE
        )
        self.assertIs(state, TechnicalImpactState.CONFIRMED_IMPACT)
        self.assertIn(
            TechnicalImpactReasonCode.CONFIRMED_INCOMPATIBLE_DEPENDENCY,
            reasons,
        )

    def test_23_compatible_fixture_produces_no_demonstrated_impact(self) -> None:
        state, _ = derive_technical_impact_state(
            CompatibilityState.COMPATIBLE
        )
        self.assertIs(state, TechnicalImpactState.NO_DEMONSTRATED_IMPACT)

    def test_24_unknown_fixture_remains_unresolved(self) -> None:
        state, _ = derive_technical_impact_state(CompatibilityState.UNKNOWN)
        self.assertIs(state, TechnicalImpactState.UNRESOLVED_IMPACT)

    def test_25_conditional_fixture_preserves_conditional_consequence(self) -> None:
        state, reasons = derive_technical_impact_state(
            CompatibilityState.CONDITIONALLY_COMPATIBLE
        )
        self.assertIs(state, TechnicalImpactState.POTENTIAL_IMPACT)
        self.assertIn(
            TechnicalImpactReasonCode.CONDITIONAL_LOCAL_CONTINUITY,
            reasons,
        )

    def test_26_ordering_is_deterministic(self) -> None:
        self.assertEqual(
            tuple(item.relationship_id for item in self.result.relationship_impacts),
            tuple(
                sorted(
                    item.relationship_id
                    for item in self.result.relationship_impacts
                )
            ),
        )
        self.assertEqual(
            tuple(item.path_id for item in self.result.path_impacts),
            tuple(sorted(item.path_id for item in self.result.path_impacts)),
        )

    def test_27_serialization_is_deterministic(self) -> None:
        self.assertEqual(self.result.to_json(), self.result.to_json())

    def test_28_fingerprint_is_timestamp_independent(self) -> None:
        other = replace(
            self.result,
            created_at="2026-07-29T06:00:00+00:00",
        )
        self.assertEqual(other.semantic_fingerprint, self.result.semantic_fingerprint)

    def test_29_semantic_mutation_changes_fingerprint(self) -> None:
        changed = replace(
            self.result,
            canonical_narrative=self.result.canonical_narrative + " changed",
        )
        self.assertNotEqual(
            changed.semantic_fingerprint,
            self.result.semantic_fingerprint,
        )

    def test_30_serialization_round_trip(self) -> None:
        loaded = type(self.result).from_json(self.result.to_json())
        self.assertTrue(loaded.semantically_equals(self.result))

    def test_31_provenance_closes(self) -> None:
        known = {item.provenance_id for item in self.graph.provenance_registry}
        referenced = {
            value
            for registry in (
                self.result.relationship_impacts,
                self.result.path_impacts,
                self.result.field_impacts,
            )
            for item in registry
            for value in (
                item.current_provenance_ids
                + item.counterfactual_provenance_ids
            )
        }
        self.assertTrue(referenced.issubset(known))
        self.assertEqual(
            len(self.result.causal_chains[0].ordered_references),
            11,
        )

    def test_32_all_prior_artifacts_unchanged(self) -> None:
        after = {
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in PATHS
        }
        self.assertEqual(after, self.hashes)
        self.assertTrue(
            all(item.unchanged for item in self.result.input_artifact_hashes)
        )

    def test_33_network_blocked_derivation_succeeds(self) -> None:
        with patch.object(
            socket,
            "create_connection",
            side_effect=AssertionError("network attempted"),
        ):
            other = self.build(8)
        self.assertEqual(other.semantic_fingerprint, self.result.semantic_fingerprint)

    def test_34_no_datahub_client_is_used(self) -> None:
        source = (
            ROOT / "src" / "chronos" / "technical_impact" / "builder.py"
        ).read_text(encoding="utf-8").lower()
        self.assertNotIn("datahubgraph", source)
        self.assertNotIn("graphql", source)
        self.assertNotIn("requests.", source)

    def test_35_secret_scanning_passes(self) -> None:
        self.assertFalse(contains_secret(self.result.to_dict()))

    def test_36_phase_3_certification_regression_passes(self) -> None:
        self.assertEqual(self.phase3.certification_status.value, "certified")

    def test_37_aggregate_metrics_are_derived(self) -> None:
        metrics = self.result.aggregate_metrics
        self.assertEqual(metrics.technical_impact_causes, 1)
        self.assertEqual(metrics.confirmed_impacted_relationships, 0)
        self.assertEqual(metrics.potential_impacted_relationships, 26)
        self.assertEqual(metrics.unresolved_relationships, 1)
        self.assertEqual(metrics.unresolved_paths, 48)
        self.assertEqual(metrics.unresolved_fields, 25)

    def test_38_dataset_summaries_are_technical_only(self) -> None:
        self.assertTrue(
            all(
                item.technical_impact_state
                is TechnicalImpactState.UNRESOLVED_IMPACT
                for item in self.result.dataset_summaries
            )
        )
        self.assertTrue(
            all(
                "technical-only" in item.human_explanation
                for item in self.result.dataset_summaries
            )
        )

    def test_39_dangling_compatibility_record_fails(self) -> None:
        first = self.result.relationship_impacts[0]
        changed_first = replace(
            first,
            supporting_compatibility_record_id="missing",
        )
        changed = replace(
            self.result,
            relationship_impacts=(changed_first,)
            + self.result.relationship_impacts[1:],
        )
        with self.assertRaises(TechnicalImpactValidationError):
            self.validate(changed)

    def test_40_dangling_propagation_record_fails(self) -> None:
        first = self.result.relationship_impacts[0]
        replacement_state = next(
            state
            for state in type(first.exposure_state)
            if state is not first.exposure_state
        )
        changed_first = replace(first, exposure_state=replacement_state)
        changed = replace(
            self.result,
            relationship_impacts=(changed_first,)
            + self.result.relationship_impacts[1:],
        )
        with self.assertRaises(TechnicalImpactValidationError):
            self.validate(changed)

    def test_41_dangling_path_fails(self) -> None:
        first = self.result.field_impacts[0]
        changed_first = replace(
            first,
            supporting_path_ids=("missing-path",),
            supporting_path_impact_states=(
                TechnicalImpactState.UNRESOLVED_IMPACT,
            ),
            path_count=1,
        )
        changed = replace(
            self.result,
            field_impacts=(changed_first,) + self.result.field_impacts[1:],
        )
        with self.assertRaises(TechnicalImpactValidationError):
            self.validate(changed)

    def test_42_unknown_to_confirmed_fails(self) -> None:
        source = self.source_relationship()
        changed_source = replace(
            source,
            technical_impact_state=TechnicalImpactState.CONFIRMED_IMPACT,
            reason_codes=(
                TechnicalImpactReasonCode.CONFIRMED_INCOMPATIBLE_DEPENDENCY,
            ),
        )
        changed = replace(
            self.result,
            relationship_impacts=tuple(
                changed_source if item.relationship_id == SOURCE_EDGE_ID else item
                for item in self.result.relationship_impacts
            ),
        )
        with self.assertRaises(TechnicalImpactValidationError):
            self.validate(changed)

    def test_43_conditional_to_guaranteed_safe_fails(self) -> None:
        first = next(
            item
            for item in self.result.relationship_impacts
            if item.compatibility_state
            is CompatibilityState.CONDITIONALLY_COMPATIBLE
        )
        replacement = replace(
            first,
            technical_impact_state=(
                TechnicalImpactState.NO_DEMONSTRATED_IMPACT
            ),
        )
        changed = replace(
            self.result,
            relationship_impacts=tuple(
                replacement if item.relationship_id == first.relationship_id else item
                for item in self.result.relationship_impacts
            ),
        )
        with self.assertRaises(TechnicalImpactValidationError):
            self.validate(changed)

    def test_44_duplicate_impact_cause_fails(self) -> None:
        with self.assertRaises(ValueError):
            replace(
                self.result,
                technical_impact_causes=(
                    self.result.technical_impact_causes[0],
                    self.result.technical_impact_causes[0],
                ),
            )

    def test_45_duplicate_field_impact_fails(self) -> None:
        with self.assertRaises(ValueError):
            replace(
                self.result,
                field_impacts=(
                    self.result.field_impacts[0],
                    self.result.field_impacts[0],
                )
                + self.result.field_impacts[1:],
            )

    def test_46_multipath_double_counting_fails(self) -> None:
        first = next(
            item for item in self.result.field_impacts if item.path_count > 1
        )
        replacement = replace(first, path_count=first.path_count + 1)
        changed = replace(
            self.result,
            field_impacts=tuple(
                replacement if item.field_key == first.field_key else item
                for item in self.result.field_impacts
            ),
        )
        with self.assertRaises(TechnicalImpactValidationError):
            self.validate(changed)

    def test_47_unsupported_deployment_verdict_fails(self) -> None:
        changed = replace(
            self.result,
            canonical_narrative="Deployment is unsafe.",
        )
        with self.assertRaises(TechnicalImpactValidationError):
            self.validate(changed)

    def test_48_models_are_immutable(self) -> None:
        with self.assertRaises(FrozenInstanceError):
            self.result.canonical_narrative = "changed"

    def test_49_export_and_load(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = export_technical_impact(
                self.result,
                Path(directory) / "technical_impact_analysis.json",
            )
            loaded = load_technical_impact(path)
        self.assertTrue(loaded.semantically_equals(self.result))

    def test_50_canonical_narrative_is_evidence_derived(self) -> None:
        self.assertIn("25 downstream fields", self.result.canonical_narrative)
        self.assertIn("20 datasets", self.result.canonical_narrative)
        self.assertIn("single unresolved source boundary", self.result.canonical_narrative)
        self.assertNotIn("broken", self.result.canonical_narrative.lower())

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

        visit(self.result)
        return names


if __name__ == "__main__":
    unittest.main()
