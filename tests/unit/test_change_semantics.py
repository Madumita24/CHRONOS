from __future__ import annotations

import hashlib
import inspect
import tempfile
import unittest
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
from pathlib import Path

from chronos.change_semantics import (
    ChangeSemanticContract,
    ChangeSemanticContractSerializationError,
    ConsequenceStatus,
    EvaluationStatus,
    IdentityClassification,
    RuleDisposition,
    SemanticCategory,
    SemanticContractPreconditionError,
    SemanticRuleCode,
    build_change_semantic_contract,
    build_contract_from_artifacts,
    export_contract,
    load_contract,
)
from chronos.proposal import RequestedFieldState, load_proposal
from chronos.proposal_validation import (
    ProposalValidationState,
    load_validation_result,
    validate_proposal,
)
from chronos.snapshot import load_snapshot


ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_PATH = ROOT / "artifacts" / "current_metadata_snapshot.json"
PROPOSAL_PATH = ROOT / "artifacts" / "change_proposal.json"
VALIDATION_PATH = ROOT / "artifacts" / "change_proposal_validation.json"
CONTRACT_PATH = ROOT / "artifacts" / "change_semantic_contract.json"


def clock(hour: int):
    return lambda: datetime(2026, 7, 27, hour, tzinfo=timezone.utc)


class ChangeSemanticContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.snapshot = load_snapshot(SNAPSHOT_PATH)
        cls.proposal = load_proposal(PROPOSAL_PATH)
        cls.validation = load_validation_result(VALIDATION_PATH)
        cls.input_hashes = {
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (SNAPSHOT_PATH, PROPOSAL_PATH, VALIDATION_PATH)
        }
        cls.contract = build_change_semantic_contract(
            cls.snapshot,
            cls.proposal,
            cls.validation,
            clock=clock(6),
        )

    def test_01_canonical_semantic_contract_builds(self) -> None:
        self.assertIsInstance(self.contract, ChangeSemanticContract)
        self.assertEqual(self.contract.change_type.value, "field_rename")
        self.assertEqual(
            self.contract.proposal_id,
            "CHRONOS-DEMO-001-PROPOSAL-001",
        )

    def test_02_builder_loads_all_three_certified_artifacts(self) -> None:
        contract = build_contract_from_artifacts(
            SNAPSHOT_PATH,
            PROPOSAL_PATH,
            VALIDATION_PATH,
            clock=clock(6),
        )
        self.assertTrue(contract.semantically_equals(self.contract))

    def test_03_valid_phase_2_2_result_is_required(self) -> None:
        invalid = replace(
            self.validation,
            validation_state=ProposalValidationState.INVALID,
        )
        with self.assertRaises(SemanticContractPreconditionError):
            build_change_semantic_contract(
                self.snapshot,
                self.proposal,
                invalid,
            )

    def test_04_changed_set_contains_only_path_and_name(self) -> None:
        self.assertEqual(
            {item.property_name for item in self.contract.changed_properties},
            {"field_path", "field_name"},
        )
        self.assertTrue(
            all(
                item.category is SemanticCategory.CHANGED
                for item in self.contract.changed_properties
            )
        )

    def test_05_changed_values_are_exact(self) -> None:
        values = {
            item.property_name: (item.before, item.after)
            for item in self.contract.changed_properties
        }
        self.assertEqual(
            values,
            {
                "field_path": ("order_total", "order_amount"),
                "field_name": ("order_total", "order_amount"),
            },
        )

    def test_06_dataset_urn_remains_unchanged(self) -> None:
        self.assertEqual(
            self.contract.current_target.dataset_urn,
            self.contract.counterfactual_candidate.dataset_urn,
        )

    def test_07_platform_and_environment_are_unchanged(self) -> None:
        unchanged = self.unchanged()
        self.assertEqual(unchanged["platform"], "postgres")
        self.assertEqual(unchanged["environment"], "PROD")

    def test_08_native_and_normalized_types_are_unchanged(self) -> None:
        unchanged = self.unchanged()
        self.assertEqual(unchanged["native_type"], "DOUBLE PRECISION")
        self.assertEqual(unchanged["normalized_type"], "Number")

    def test_09_nullable_is_unchanged_when_verified(self) -> None:
        self.assertIs(self.unchanged()["nullable"], True)

    def test_10_key_status_is_unchanged_when_verified(self) -> None:
        self.assertIs(self.unchanged()["is_part_of_key"], False)

    def test_11_other_fourteen_source_fields_are_unchanged(self) -> None:
        fields = self.unchanged()["other_source_fields"]
        self.assertEqual(len(fields), 14)
        self.assertNotIn("order_total", fields)
        self.assertNotIn("order_amount", fields)

    def test_12_all_unchanged_properties_are_typed(self) -> None:
        self.assertTrue(
            all(
                item.category is SemanticCategory.UNCHANGED_BY_PROPOSAL
                for item in self.contract.unchanged_properties
            )
        )

    def test_13_downstream_field_rename_remains_unknown(self) -> None:
        self.assertUnknown("downstream_field_names_change")

    def test_14_pipeline_compatibility_remains_unknown(self) -> None:
        for item in (
            "spark_jobs_remain_valid",
            "dbt_models_remain_valid",
            "snowflake_transformations_remain_valid",
        ):
            self.assertUnknown(item)

    def test_15_bi_compatibility_remains_unknown(self) -> None:
        for item in (
            "looker_assets_remain_valid",
            "power_bi_assets_remain_valid",
            "tableau_assets_remain_valid",
            "charts_or_dashboards_break",
        ):
            self.assertUnknown(item)

    def test_16_governance_and_documentation_remain_unknown(self) -> None:
        for item in (
            "governance_should_propagate",
            "data_products_require_updates",
            "documentation_requires_updates",
            "repair_is_possible",
        ):
            self.assertUnknown(item)

    def test_17_no_impact_categories_are_introduced(self) -> None:
        categories = {
            item.category.value
            for item in (
                self.contract.changed_properties
                + self.contract.unchanged_properties
                + self.contract.unknown_consequences
                + self.contract.preconditions
            )
        }
        self.assertEqual(
            categories,
            {
                "changed",
                "unchanged_by_proposal",
                "unknown_consequence",
                "precondition",
            },
        )
        generated = self.contract.to_json().casefold()
        for term in ("impacted", "safe", "risky", "repair_required"):
            self.assertNotIn(term, generated)

    def test_18_current_and_candidate_machine_keys_differ(self) -> None:
        self.assertNotEqual(
            self.contract.current_target.machine_key,
            self.contract.counterfactual_candidate.machine_key,
        )
        self.assertEqual(
            self.contract.current_target.machine_key[1],
            "order_total",
        )
        self.assertEqual(
            self.contract.counterfactual_candidate.machine_key[1],
            "order_amount",
        )

    def test_19_candidate_identity_is_counterfactual(self) -> None:
        self.assertEqual(
            self.contract.counterfactual_candidate.classification,
            IdentityClassification.COUNTERFACTUAL_CANDIDATE,
        )

    def test_20_candidate_schema_field_urn_is_not_fabricated(self) -> None:
        self.assertIsNone(
            self.contract.counterfactual_candidate.schema_field_urn
        )

    def test_21_source_schema_cardinality_invariant_is_fifteen(self) -> None:
        schema = self.contract.source_schema_contract
        self.assertEqual(schema.current_field_count, 15)
        self.assertEqual(schema.counterfactual_candidate_field_count, 15)
        self.assertFalse(schema.transformed_schema_materialized)

    def test_22_non_propagation_rule_is_forbidden(self) -> None:
        rule = self.rule(SemanticRuleCode.AUTOMATIC_DOWNSTREAM_RENAME)
        self.assertEqual(rule.disposition, RuleDisposition.FORBIDDEN)

    def test_23_current_snapshot_mutation_is_forbidden(self) -> None:
        rule = self.rule(SemanticRuleCode.MUTATE_CURRENT_SNAPSHOT)
        self.assertEqual(rule.disposition, RuleDisposition.FORBIDDEN)

    def test_24_new_counterfactual_representation_is_required(self) -> None:
        rule = self.rule(
            SemanticRuleCode.CREATE_COUNTERFACTUAL_REPRESENTATION
        )
        self.assertEqual(rule.disposition, RuleDisposition.REQUIRED)

    def test_25_current_evidence_provenance_is_preserved(self) -> None:
        preserve = self.rule(
            SemanticRuleCode.PRESERVE_EVIDENCE_PROVENANCE
        )
        reinterpret = self.rule(
            SemanticRuleCode.REINTERPRET_CURRENT_EVIDENCE_AS_COUNTERFACTUAL
        )
        self.assertEqual(preserve.disposition, RuleDisposition.REQUIRED)
        self.assertEqual(reinterpret.disposition, RuleDisposition.FORBIDDEN)

    def test_26_all_required_preconditions_are_frozen(self) -> None:
        self.assertEqual(
            {item.precondition for item in self.contract.preconditions},
            {
                "baseline_snapshot_fingerprint_matches",
                "proposal_fingerprint_matches_validation",
                "validation_state",
                "target_dataset_exists",
                "target_field_exists",
                "before_state_matches",
                "requested_field_collision_count",
                "proposal_type",
            },
        )

    def test_27_mismatched_validation_proposal_fingerprint_fails(self) -> None:
        validation = replace(
            self.validation,
            proposal_fingerprint="sha256:" + ("0" * 64),
        )
        with self.assertRaises(SemanticContractPreconditionError):
            build_change_semantic_contract(
                self.snapshot,
                self.proposal,
                validation,
            )

    def test_28_snapshot_proposal_and_validation_remain_immutable(self) -> None:
        snapshot_json = self.snapshot.to_json()
        proposal_json = self.proposal.to_json()
        validation_json = self.validation.to_json()
        build_change_semantic_contract(
            self.snapshot,
            self.proposal,
            self.validation,
        )
        self.assertEqual(self.snapshot.to_json(), snapshot_json)
        self.assertEqual(self.proposal.to_json(), proposal_json)
        self.assertEqual(self.validation.to_json(), validation_json)

    def test_29_input_artifact_hashes_remain_unchanged(self) -> None:
        build_change_semantic_contract(
            self.snapshot,
            self.proposal,
            self.validation,
        )
        for path, expected in self.input_hashes.items():
            self.assertEqual(
                hashlib.sha256(path.read_bytes()).hexdigest(),
                expected,
            )

    def test_30_contract_is_deeply_immutable(self) -> None:
        with self.assertRaises(FrozenInstanceError):
            self.contract.proposal_id = "changed"
        with self.assertRaises(FrozenInstanceError):
            self.contract.current_target.field_path = "changed"
        with self.assertRaises(FrozenInstanceError):
            self.contract.changed_properties[0].after = "changed"

    def test_31_serialization_and_round_trip_are_deterministic(self) -> None:
        self.assertEqual(self.contract.to_json(), self.contract.to_json())
        reloaded = ChangeSemanticContract.from_json(self.contract.to_json())
        self.assertEqual(reloaded, self.contract)

    def test_32_fingerprint_is_stable_across_timestamps(self) -> None:
        later = build_change_semantic_contract(
            self.snapshot,
            self.proposal,
            self.validation,
            clock=clock(10),
        )
        self.assertNotEqual(self.contract.created_at, later.created_at)
        self.assertTrue(self.contract.semantically_equals(later))

    def test_33_proposal_semantic_change_alters_contract_fingerprint(self) -> None:
        change = replace(
            self.proposal.change,
            requested_after=RequestedFieldState(
                field_path="total_amount",
                field_name="total_amount",
            ),
        )
        proposal = replace(self.proposal, change=change)
        validation = validate_proposal(
            self.snapshot,
            proposal,
            clock=clock(6),
        )
        changed = build_change_semantic_contract(
            self.snapshot,
            proposal,
            validation,
            clock=clock(6),
        )
        self.assertNotEqual(
            changed.semantic_fingerprint,
            self.contract.semantic_fingerprint,
        )

    def test_34_snapshot_fingerprint_change_alters_contract_fingerprint(
        self,
    ) -> None:
        changed = replace(
            self.contract,
            baseline_snapshot_fingerprint="sha256:" + ("1" * 64),
        )
        self.assertNotEqual(
            changed.semantic_fingerprint,
            self.contract.semantic_fingerprint,
        )

    def test_35_validation_fingerprint_change_alters_contract_fingerprint(
        self,
    ) -> None:
        changed = replace(
            self.contract,
            validation_fingerprint="sha256:" + ("2" * 64),
        )
        self.assertNotEqual(
            changed.semantic_fingerprint,
            self.contract.semantic_fingerprint,
        )

    def test_36_export_and_load_preserve_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = export_contract(
                self.contract,
                Path(directory) / "contract.json",
            )
            exported = load_contract(path)
        self.assertEqual(exported, self.contract)

    def test_37_tampered_contract_fingerprint_is_rejected(self) -> None:
        value = self.contract.to_json().replace(
            self.contract.semantic_fingerprint,
            "sha256:" + ("0" * 64),
        )
        with self.assertRaises(ChangeSemanticContractSerializationError):
            ChangeSemanticContract.from_json(value)

    def test_38_no_datahub_client_or_live_request_is_required(self) -> None:
        source = inspect.getsource(build_change_semantic_contract).casefold()
        for term in ("datahubgraph", "graphql", "requests.", "httpx", "gms"):
            self.assertNotIn(term, source)
        self.assertFalse(hasattr(self.contract, "_client"))
        self.assertFalse(hasattr(self.contract, "_transport"))

    def test_39_no_future_graph_is_created(self) -> None:
        self.assertFalse(hasattr(self.contract, "future_graph"))
        self.assertFalse(hasattr(self.contract, "lineage_edges"))
        self.assertFalse(hasattr(self.contract, "lineage_paths"))

    def test_40_no_datahub_write_path_is_exposed(self) -> None:
        public = {
            item for item in dir(self.contract) if not item.startswith("_")
        }
        self.assertTrue(
            public.isdisjoint(
                {"emit", "upsert", "patch", "delete", "mutation", "write"}
            )
        )
        self.assertEqual(
            self.rule(SemanticRuleCode.WRITE_DATAHUB).disposition,
            RuleDisposition.FORBIDDEN,
        )

    def test_41_human_summary_has_required_boundaries(self) -> None:
        summary = self.contract.summary()
        self.assertIn("Operation: FIELD_RENAME", summary)
        self.assertIn("order_total -> order_amount", summary)
        self.assertIn("Unknown consequences: NOT_EVALUATED", summary)
        self.assertIn("Current snapshot mutation: FORBIDDEN", summary)
        self.assertIn("Automatic downstream rename: FORBIDDEN", summary)

    def test_42_canonical_contract_artifact_loads(self) -> None:
        artifact = load_contract(CONTRACT_PATH)
        self.assertTrue(artifact.semantically_equals(self.contract))

    def unchanged(self) -> dict[str, object]:
        return {
            item.property_name: item.value
            for item in self.contract.unchanged_properties
        }

    def assertUnknown(self, name: str) -> None:
        consequence = next(
            item
            for item in self.contract.unknown_consequences
            if item.consequence == name
        )
        self.assertEqual(consequence.status, ConsequenceStatus.UNKNOWN)
        self.assertEqual(
            consequence.evaluation,
            EvaluationStatus.NOT_EVALUATED,
        )
        self.assertEqual(
            consequence.category,
            SemanticCategory.UNKNOWN_CONSEQUENCE,
        )

    def rule(self, code: SemanticRuleCode):
        return next(
            item for item in self.contract.semantic_rules if item.code is code
        )


if __name__ == "__main__":
    unittest.main()
