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
    BusinessContextEntryError,
    BusinessContextSerializationError,
    BusinessContextValidationError,
    ContextAssetType,
    ContextCategory,
    ContextExposureType,
    ContextLinkageState,
    ContextResolutionState,
    business_context_from_json,
    business_context_semantic_fingerprint,
    export_business_context,
    get_bi_context_for_technical_scope,
    get_context_for_dataset,
    get_context_for_field,
    get_data_products_for_technical_scope,
    get_documents_for_technical_scope,
    get_domains_for_technical_scope,
    get_owners_for_technical_scope,
    get_pipeline_context_for_technical_scope,
    get_technical_sources_for_context_asset,
    load_business_context,
    propagate_business_context,
    propagate_business_context_from_artifacts,
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
from chronos.proposal import CANONICAL_DATASET_URN, load_proposal
from chronos.proposal_validation import load_validation_result
from chronos.snapshot import FieldMachineKey, contains_secret, load_snapshot
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
)
PATHS = tuple(ARTIFACTS / name for name in NAMES)
UNRESOLVED_TAG = "urn:li:tag:b2fd91.ecommerce"
SOURCE_DATASET = CANONICAL_DATASET_URN


def fixed_clock(hour: int):
    return lambda: datetime(2026, 7, 28, hour, tzinfo=timezone.utc)


class BusinessContextTests(unittest.TestCase):
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
        cls.result = cls.build(8)

    @classmethod
    def build(cls, hour: int):
        return propagate_business_context_from_artifacts(
            *PATHS,
            clock=fixed_clock(hour),
        )

    def derive(self, *, phase3=None, technical=None):
        return propagate_business_context(
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
            input_artifact_hashes=self.result.input_artifact_hashes,
            clock=fixed_clock(9),
        )

    def validate(self, result) -> None:
        validate_business_context(
            result,
            self.snapshot,
            self.graph,
            self.technical,
            self.phase3,
        )

    def asset(self, asset_id: str):
        return next(
            item
            for item in self.result.context_asset_registry
            if item.asset_id == asset_id
        )

    def test_01_canonical_propagation_succeeds(self) -> None:
        self.validate(self.result)
        self.assertTrue(self.result.semantic_fingerprint.startswith("sha256:"))

    def test_02_phase_3_certification_is_required(self) -> None:
        bad_fingerprints = replace(
            self.phase3.phase_3_semantic_fingerprints,
            explanation_bundle="sha256:" + "0" * 64,
        )
        invalid = replace(
            self.phase3,
            phase_3_semantic_fingerprints=bad_fingerprints,
        )
        with self.assertRaises(BusinessContextEntryError):
            self.derive(phase3=invalid)

    def test_03_phase_4_1_validity_is_required(self) -> None:
        invalid = replace(
            self.technical,
            canonical_narrative="unsupported technical narrative",
        )
        with self.assertRaises(BusinessContextEntryError):
            self.derive(technical=invalid)

    def test_04_all_20_technical_datasets_are_handled(self) -> None:
        self.assertEqual(len(self.result.dataset_context_summaries), 20)
        self.assertEqual(
            {item.dataset_urn for item in self.result.dataset_context_summaries},
            {item.dataset_urn for item in self.technical.dataset_summaries},
        )

    def test_05_field_dataset_context_chains_resolve(self) -> None:
        fields = {item.field_key for item in self.technical.field_impacts}
        links = {
            item.context_relationship_id: item
            for item in self.result.context_link_registry
        }
        for mapping in self.result.technical_to_context_mappings:
            self.assertIn(mapping.technical_field_key, fields)
            self.assertEqual(
                mapping.dataset_urn,
                mapping.technical_field_key.dataset_urn,
            )
            self.assertEqual(
                links[mapping.context_relationship_id].anchor_dataset_urn,
                mapping.dataset_urn,
            )

    def test_06_ownership_propagates(self) -> None:
        owners = get_owners_for_technical_scope(self.result)
        self.assertEqual(len(owners), 12)
        self.assertTrue(
            all(item.category is ContextCategory.OWNERSHIP for item in owners)
        )

    def test_07_domain_propagates(self) -> None:
        self.assertEqual(
            len(get_domains_for_technical_scope(self.result)),
            3,
        )

    def test_08_tag_propagates(self) -> None:
        tags = [
            item
            for item in self.result.context_asset_registry
            if item.category is ContextCategory.TAG
        ]
        self.assertEqual(len(tags), 5)

    def test_09_glossary_propagates(self) -> None:
        glossary = [
            item
            for item in self.result.context_asset_registry
            if item.category is ContextCategory.GLOSSARY
        ]
        self.assertEqual(len(glossary), 6)

    def test_10_structured_properties_propagate(self) -> None:
        metrics = self.result.aggregate_metrics
        self.assertEqual(metrics.structured_property_assignments, 100)
        self.assertEqual(metrics.structured_property_definitions, 5)

    def test_11_data_products_propagate(self) -> None:
        self.assertEqual(
            len(get_data_products_for_technical_scope(self.result)),
            3,
        )

    def test_12_documents_propagate(self) -> None:
        self.assertEqual(
            len(get_documents_for_technical_scope(self.result)),
            9,
        )

    def test_13_pipeline_context_propagates_by_field_anchor(self) -> None:
        assets = get_pipeline_context_for_technical_scope(self.result)
        self.assertEqual(len(assets), 4)
        links = [
            item
            for item in self.result.context_link_registry
            if item.context_category is ContextCategory.PIPELINE
        ]
        self.assertEqual(len(links), 3)
        self.assertTrue(all(item.anchor_field_key is not None for item in links))

    def test_14_bi_context_propagates(self) -> None:
        assets = get_bi_context_for_technical_scope(self.result)
        self.assertEqual(len(assets), 19)
        self.assertEqual(self.result.aggregate_metrics.charts, 12)
        self.assertEqual(self.result.aggregate_metrics.dashboards, 3)

    def test_15_direct_and_reachable_context_are_distinct(self) -> None:
        types = {
            item.context_exposure_type
            for item in self.result.context_link_registry
        }
        self.assertEqual(
            types,
            {
                ContextExposureType.DIRECT_CONTEXT,
                ContextExposureType.REACHABLE_CONTEXT,
            },
        )
        self.assertTrue(
            all(
                (
                    item.context_exposure_type
                    is ContextExposureType.REACHABLE_CONTEXT
                )
                == (item.context_category is ContextCategory.BI)
                for item in self.result.context_link_registry
            )
        )

    def test_16_context_outside_technical_scope_is_excluded(self) -> None:
        self.assertNotIn(
            SOURCE_DATASET,
            {
                item.anchor_dataset_urn
                for item in self.result.context_link_registry
            },
        )
        self.assertEqual(
            self.result.aggregate_metrics.excluded_context_relationships,
            14,
        )

    def test_17_unique_context_assets_are_deduplicated(self) -> None:
        ids = [item.asset_id for item in self.result.context_asset_registry]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(ids), 66)

    def test_18_same_owner_can_map_to_multiple_datasets(self) -> None:
        owner = next(
            item
            for item in self.result.context_asset_registry
            if item.category is ContextCategory.OWNERSHIP
            and len(item.supporting_dataset_urns) > 1
        )
        self.assertGreater(len(owner.supporting_dataset_urns), 1)

    def test_19_dashboard_can_map_through_multiple_fields(self) -> None:
        dashboard = next(
            item
            for item in self.result.context_asset_registry
            if item.asset_type is ContextAssetType.DASHBOARD
            and len(item.supporting_field_keys) > 1
        )
        self.assertGreater(len(dashboard.supporting_field_keys), 1)
        self.assertEqual(
            len(
                {
                    item.asset_id
                    for item in self.result.context_asset_registry
                    if item.asset_id == dashboard.asset_id
                }
            ),
            1,
        )

    def test_20_root_cause_is_preserved_once(self) -> None:
        self.assertEqual(len(self.result.technical_root_causes), 1)
        self.assertEqual(
            self.result.technical_root_causes[0].cause_id,
            "technical-impact-cause-source-rename-semantics",
        )

    def test_21_technical_state_is_preserved_unchanged(self) -> None:
        by_field = {
            item.field_key: item.technical_impact_state
            for item in self.technical.field_impacts
        }
        self.assertTrue(
            all(
                item.technical_impact_state
                is by_field[item.technical_field_key]
                for item in self.result.technical_to_context_mappings
            )
        )

    def test_22_context_does_not_recompute_compatibility(self) -> None:
        names = {
            item.name
            for value in (
                type(self.result),
                type(self.result.context_asset_registry[0]),
                type(self.result.technical_to_context_mappings[0]),
            )
            for item in fields(value)
        }
        self.assertNotIn("compatibility_state", names)

    def test_23_context_does_not_change_technical_impact(self) -> None:
        before = self.technical.semantic_fingerprint
        self.build(10)
        self.assertEqual(self.technical.semantic_fingerprint, before)

    def test_24_unresolved_context_reference_is_preserved(self) -> None:
        self.assertEqual(len(self.result.unresolved_context_references), 1)
        reference = self.result.unresolved_context_references[0]
        self.assertEqual(reference.context_asset_id, UNRESOLVED_TAG)
        self.assertIs(
            reference.preserved_state,
            ContextResolutionState.UNRESOLVED,
        )
        self.assertIs(
            self.asset(UNRESOLVED_TAG).resolution_state,
            ContextResolutionState.UNRESOLVED,
        )

    def test_25_all_asset_identities_are_certified(self) -> None:
        certified = {
            value
            for item in self.graph.context_relationship_registry
            for value in (
                item.source_key,
                item.target_key,
                *item.relationship_path,
            )
        }
        self.assertTrue(
            {
                item.asset_id
                for item in self.result.context_asset_registry
            }
            <= certified
        )

    def test_26_dashboards_have_no_breakage_state(self) -> None:
        dashboard = next(
            item
            for item in self.result.context_asset_registry
            if item.asset_type is ContextAssetType.DASHBOARD
        )
        self.assertFalse(hasattr(dashboard, "breakage_state"))
        self.assertFalse(hasattr(dashboard, "technical_impact_state"))

    def test_27_charts_have_no_breakage_state(self) -> None:
        chart = next(
            item
            for item in self.result.context_asset_registry
            if item.asset_type is ContextAssetType.CHART
        )
        self.assertFalse(hasattr(chart, "breakage_state"))
        self.assertFalse(hasattr(chart, "technical_impact_state"))

    def test_28_no_severity_field(self) -> None:
        self.assertNotIn("severity", _all_keys(self.result.to_dict()))

    def test_29_no_risk_score(self) -> None:
        keys = _all_keys(self.result.to_dict())
        self.assertNotIn("risk", keys)
        self.assertNotIn("risk_score", keys)

    def test_30_no_criticality_score(self) -> None:
        keys = _all_keys(self.result.to_dict())
        self.assertNotIn("criticality", keys)
        self.assertNotIn("criticality_score", keys)

    def test_31_no_repair_priority(self) -> None:
        self.assertNotIn("repair_priority", _all_keys(self.result.to_dict()))

    def test_32_no_notification_priority(self) -> None:
        self.assertNotIn(
            "notification_priority",
            _all_keys(self.result.to_dict()),
        )

    def test_33_field_query_uses_materialized_reverse_index(self) -> None:
        index = next(
            item
            for item in self.result.reverse_indexes.by_field
            if item.context_asset_ids
        )
        assets = get_context_for_field(self.result, index.field_key)
        self.assertEqual(
            {item.asset_id for item in assets},
            set(index.context_asset_ids),
        )

    def test_34_dataset_query_uses_materialized_reverse_index(self) -> None:
        index = next(
            item
            for item in self.result.reverse_indexes.by_dataset
            if item.context_asset_ids
        )
        assets = get_context_for_dataset(self.result, index.dataset_urn)
        self.assertEqual(
            {item.asset_id for item in assets},
            set(index.context_asset_ids),
        )

    def test_35_context_asset_reverse_query_works(self) -> None:
        asset = next(
            item
            for item in self.result.context_asset_registry
            if len(item.supporting_field_keys) > 1
        )
        mappings = get_technical_sources_for_context_asset(
            self.result,
            asset.asset_id,
        )
        self.assertEqual(
            {item.technical_field_key for item in mappings},
            set(asset.supporting_field_keys),
        )

    def test_36_provenance_closes(self) -> None:
        self.assertTrue(
            all(
                item.technical_provenance_ids
                and item.context_provenance_ids
                and item.root_technical_cause_ids
                and item.supporting_path_ids
                for item in self.result.technical_to_context_mappings
            )
        )
        self.assertTrue(
            all(
                item.current_evidence_ids
                and item.future_graph_provenance_ids
                for item in self.result.context_asset_registry
            )
        )

    def test_37_ordering_is_deterministic(self) -> None:
        self.assertEqual(
            tuple(item.asset_id for item in self.result.context_asset_registry),
            tuple(
                sorted(
                    item.asset_id
                    for item in self.result.context_asset_registry
                )
            ),
        )
        self.assertEqual(
            tuple(
                item.context_relationship_id
                for item in self.result.context_link_registry
            ),
            tuple(
                sorted(
                    item.context_relationship_id
                    for item in self.result.context_link_registry
                )
            ),
        )

    def test_38_serialization_is_deterministic(self) -> None:
        other = self.build(8)
        self.assertEqual(self.result.to_json(), other.to_json())

    def test_39_timestamp_is_excluded_from_fingerprint(self) -> None:
        other = self.build(15)
        self.assertNotEqual(self.result.created_at, other.created_at)
        self.assertEqual(
            self.result.semantic_fingerprint,
            other.semantic_fingerprint,
        )

    def test_40_semantic_mutation_changes_fingerprint(self) -> None:
        changed = replace(
            self.result,
            canonical_narrative=self.result.canonical_narrative + " Changed.",
        )
        self.assertNotEqual(
            changed.semantic_fingerprint,
            self.result.semantic_fingerprint,
        )

    def test_41_serialization_round_trip(self) -> None:
        loaded = business_context_from_json(self.result.to_json())
        self.assertTrue(self.result.semantically_equals(loaded))

    def test_42_all_inputs_are_unchanged(self) -> None:
        after = {
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in PATHS
        }
        self.assertEqual(self.before_hashes, after)
        self.assertTrue(
            all(item.unchanged for item in self.result.input_artifact_hashes)
        )

    def test_43_runtime_has_no_datahub_dependency(self) -> None:
        source = (
            ROOT / "src" / "chronos" / "business_context" / "builder.py"
        ).read_text(encoding="utf-8").lower()
        self.assertNotIn("chronos.datahub", source)
        self.assertNotIn("datahub.", source)

    def test_44_runtime_has_no_network_dependency(self) -> None:
        with patch.object(
            socket,
            "create_connection",
            side_effect=AssertionError("network attempted"),
        ):
            result = self.build(11)
        self.assertEqual(
            result.semantic_fingerprint,
            self.result.semantic_fingerprint,
        )

    def test_45_secret_scanner_passes(self) -> None:
        self.assertFalse(contains_secret(self.result.to_dict()))

    def test_46_phase_4_1_validation_remains_green(self) -> None:
        validate_technical_impact(
            self.technical,
            self.source,
            self.graph,
            self.propagation,
            self.compatibility,
            self.explanations,
            self.phase3,
        )

    def test_47_phase_3_certification_remains_green(self) -> None:
        validate_phase3_certification(self.phase3)

    def test_48_aggregate_scope_is_computed_from_certified_graph(self) -> None:
        metrics = self.result.aggregate_metrics
        self.assertEqual(metrics.certified_graph_context_relationships, 225)
        self.assertEqual(metrics.scoped_context_relationships, 211)
        self.assertEqual(
            metrics.certified_graph_context_relationships,
            metrics.scoped_context_relationships
            + metrics.excluded_context_relationships,
        )

    def test_49_fingerprint_mismatch_fails_closed(self) -> None:
        invalid = replace(
            self.result,
            technical_impact_fingerprint="sha256:" + "0" * 64,
        )
        with self.assertRaises(BusinessContextValidationError):
            self.validate(invalid)

    def test_50_unknown_dataset_reference_fails_closed(self) -> None:
        mapping = replace(
            self.result.technical_to_context_mappings[0],
            dataset_urn="urn:li:dataset:(unknown,unknown,PROD)",
        )
        with self.assertRaises(ValueError):
            replace(
                self.result,
                technical_to_context_mappings=(
                    mapping,
                    *self.result.technical_to_context_mappings[1:],
                ),
            )

    def test_51_dangling_field_reference_fails_closed(self) -> None:
        mapping = replace(
            self.result.technical_to_context_mappings[0],
            technical_field_key=FieldMachineKey(
                self.result.dataset_context_summaries[0].dataset_urn,
                "unknown_field",
            ),
        )
        with self.assertRaises(ValueError):
            replace(
                self.result,
                technical_to_context_mappings=(
                    mapping,
                    *self.result.technical_to_context_mappings[1:],
                ),
            )

    def test_52_dangling_context_relationship_fails_closed(self) -> None:
        mapping = replace(
            self.result.technical_to_context_mappings[0],
            context_relationship_id="unknown-relationship",
        )
        with self.assertRaises(ValueError):
            replace(
                self.result,
                technical_to_context_mappings=(
                    mapping,
                    *self.result.technical_to_context_mappings[1:],
                ),
            )

    def test_53_unknown_context_asset_fails_closed(self) -> None:
        mapping = replace(
            self.result.technical_to_context_mappings[0],
            context_asset_id="urn:li:dashboard:(fake,fake)",
        )
        with self.assertRaises(ValueError):
            replace(
                self.result,
                technical_to_context_mappings=(
                    mapping,
                    *self.result.technical_to_context_mappings[1:],
                ),
            )

    def test_54_duplicate_context_asset_fails_closed(self) -> None:
        with self.assertRaises(ValueError):
            replace(
                self.result,
                context_asset_registry=(
                    *self.result.context_asset_registry,
                    self.result.context_asset_registry[0],
                ),
            )

    def test_55_duplicate_mapping_fails_closed(self) -> None:
        with self.assertRaises(ValueError):
            replace(
                self.result,
                technical_to_context_mappings=(
                    *self.result.technical_to_context_mappings,
                    self.result.technical_to_context_mappings[0],
                ),
            )

    def test_56_attempt_to_alter_technical_state_fails_closed(self) -> None:
        original = self.result.technical_to_context_mappings[0]
        altered = replace(
            original,
            technical_impact_state=TechnicalImpactState.POTENTIAL_IMPACT,
            context_linkage_state=(
                ContextLinkageState
                .CONTEXT_LINKED_TO_POTENTIAL_TECHNICAL_STATE
            ),
        )
        invalid = replace(
            self.result,
            technical_to_context_mappings=(
                altered,
                *self.result.technical_to_context_mappings[1:],
            ),
        )
        with self.assertRaises(BusinessContextValidationError):
            self.validate(invalid)

    def test_57_dashboard_broken_claim_fails_closed(self) -> None:
        index = next(
            i
            for i, item in enumerate(
                self.result.technical_to_context_mappings
            )
            if self.asset(item.context_asset_id).asset_type
            is ContextAssetType.DASHBOARD
        )
        mappings = list(self.result.technical_to_context_mappings)
        mappings[index] = replace(
            mappings[index],
            human_explanation="Dashboard is broken.",
        )
        invalid = replace(
            self.result,
            technical_to_context_mappings=tuple(mappings),
        )
        with self.assertRaises(BusinessContextValidationError):
            self.validate(invalid)

    def test_58_notification_priority_claim_fails_closed(self) -> None:
        invalid = replace(
            self.result,
            canonical_narrative="Notification priority must be assigned.",
        )
        with self.assertRaises(BusinessContextValidationError):
            self.validate(invalid)

    def test_59_query_results_are_immutable_tuples(self) -> None:
        owners = get_owners_for_technical_scope(self.result)
        self.assertIsInstance(owners, tuple)
        with self.assertRaises(FrozenInstanceError):
            owners[0].display_name = "Changed"

    def test_60_export_and_load_use_public_artifact_api(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = export_business_context(
                self.result,
                Path(directory) / "business_context.json",
            )
            loaded = load_business_context(path)
        self.assertTrue(self.result.semantically_equals(loaded))

    def test_61_stored_fingerprint_is_verified_on_load(self) -> None:
        value = self.result.to_json().replace(
            self.result.semantic_fingerprint,
            "sha256:" + "0" * 64,
            1,
        )
        with self.assertRaises(BusinessContextSerializationError):
            business_context_from_json(value)

    def test_62_public_fingerprint_helper_matches_model(self) -> None:
        self.assertEqual(
            business_context_semantic_fingerprint(self.result),
            self.result.semantic_fingerprint,
        )

    def test_63_tag_cannot_be_used_as_severity(self) -> None:
        index = next(
            i
            for i, item in enumerate(
                self.result.technical_to_context_mappings
            )
            if item.context_category is ContextCategory.TAG
        )
        mappings = list(self.result.technical_to_context_mappings)
        mappings[index] = replace(
            mappings[index],
            human_explanation="The tag makes this high risk.",
        )
        invalid = replace(
            self.result,
            technical_to_context_mappings=tuple(mappings),
        )
        with self.assertRaises(BusinessContextValidationError):
            self.validate(invalid)


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
