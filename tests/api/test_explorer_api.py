"""Phase 5.3 certified impact and evidence explorer API tests."""

from __future__ import annotations

import inspect
import json
import shutil
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from fastapi.testclient import TestClient
from pydantic import ValidationError

import chronos.presentation.explorer_service as explorer_service_module
from chronos.presentation import (
    EXPECTED_PHASE4_CERTIFICATION_FINGERPRINT,
    CertifiedImpactExplorer,
    CertifiedImpactExplorerService,
    create_app,
)


ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "artifacts"
EXPLORER_URL = "/api/reviews/CHRONOS-DEMO-001/explorer"
EXPLORER_ARTIFACTS = (
    "phase_4_certification.json",
    "current_metadata_snapshot.json",
    "future_metadata_graph.json",
    "dependency_propagation.json",
    "compatibility_evaluation.json",
    "explanation_bundle.json",
    "technical_impact_analysis.json",
    "business_context_propagation.json",
    "severity_criticality_analysis.json",
    "impact_synthesis.json",
)


class ImpactExplorerApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(create_app(artifact_dir=ARTIFACTS))
        response = cls.client.get(EXPLORER_URL)
        if response.status_code != 200:
            raise AssertionError(response.text)
        cls.payload = response.json()

    def test_explorer_endpoint_returns_json(self) -> None:
        response = self.client.get(EXPLORER_URL)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            response.headers["content-type"].startswith("application/json")
        )

    def test_phase4_certification_is_the_explorer_gate(self) -> None:
        certification = self.payload["certification"]
        self.assertEqual(certification["status"], "certified")
        self.assertEqual(
            certification["fingerprint"],
            EXPECTED_PHASE4_CERTIFICATION_FINGERPRINT,
        )
        self.assertEqual(certification["checksPassed"], 49)

    def test_summary_has_canonical_scope_totals(self) -> None:
        summary = self.payload["summary"]
        self.assertEqual(summary["downstreamFields"], 25)
        self.assertEqual(summary["downstreamDatasets"], 20)
        self.assertEqual(summary["dependencyPaths"], 48)
        self.assertEqual(summary["structuralRelationships"], 27)

    def test_summary_has_canonical_context_totals(self) -> None:
        summary = self.payload["summary"]
        self.assertEqual(summary["contextAssets"], 66)
        self.assertEqual(summary["contextRelationships"], 211)
        self.assertEqual(summary["fieldToContextMappings"], 257)

    def test_summary_has_one_shared_root_cause(self) -> None:
        summary = self.payload["summary"]
        self.assertEqual(summary["rootCauses"], 1)
        self.assertEqual(summary["blockingQuestions"], 1)
        self.assertEqual(summary["requiredEvidenceClasses"], 4)

    def test_summary_does_not_claim_failures(self) -> None:
        summary = self.payload["summary"]
        self.assertEqual(summary["confirmedFailures"], 0)
        self.assertEqual(summary["unresolvedFields"], 25)

    def test_relationship_compatibility_distribution_is_certified(self) -> None:
        summary = self.payload["summary"]
        self.assertEqual(summary["compatibilityUnknown"], 1)
        self.assertEqual(summary["compatibilityConditional"], 26)
        self.assertEqual(summary["compatibilityCompatible"], 0)
        self.assertEqual(summary["compatibilityIncompatible"], 0)

    def test_field_severity_distribution_is_certified(self) -> None:
        self.assertEqual(
            self.payload["summary"]["fieldSeverityDistribution"],
            {
                "critical": 0,
                "high": 3,
                "moderate": 6,
                "low": 16,
                "undetermined": 0,
            },
        )

    def test_dataset_severity_distribution_is_certified(self) -> None:
        self.assertEqual(
            self.payload["summary"]["datasetSeverityDistribution"],
            {
                "critical": 0,
                "high": 3,
                "moderate": 4,
                "low": 13,
                "undetermined": 0,
            },
        )

    def test_change_level_semantics_are_explicit(self) -> None:
        summary = self.payload["summary"]
        self.assertEqual(summary["technicalConsequence"], "unresolved_impact")
        self.assertEqual(summary["technicalCertainty"], "unresolved")
        self.assertEqual(summary["decisionCertainty"], "high_confidence")
        self.assertEqual(summary["severityIfRealized"], "high")
        self.assertEqual(summary["breadth"], "widespread")
        self.assertEqual(summary["criticality"], "elevated_context")
        self.assertEqual(summary["sensitivity"], "pii")
        self.assertFalse(summary["explicitBusinessCriticalityPresent"])

    def test_all_explorer_collections_have_canonical_cardinality(self) -> None:
        expected = {
            "fields": 25,
            "datasets": 20,
            "paths": 48,
            "relationships": 27,
            "contextAssets": 66,
            "contextRelationships": 211,
            "contextMappings": 257,
        }
        for key, count in expected.items():
            self.assertEqual(len(self.payload[key]), count, key)

    def test_collection_identifiers_are_unique(self) -> None:
        keys = {
            "fields": "fieldId",
            "datasets": "datasetId",
            "paths": "pathId",
            "relationships": "relationshipId",
            "contextAssets": "contextAssetId",
            "contextRelationships": "relationshipId",
            "contextMappings": "mappingId",
        }
        for collection, key in keys.items():
            values = [item[key] for item in self.payload[collection]]
            self.assertEqual(len(values), len(set(values)), collection)

    def test_root_cause_identity_is_canonical(self) -> None:
        cause = self.payload["rootCause"]
        self.assertEqual(
            cause["causeId"],
            "technical-impact-cause-source-rename-semantics",
        )
        self.assertEqual(cause["compatibilityState"], "unknown")
        self.assertEqual(cause["evidenceState"], "insufficient")

    def test_root_cause_shows_projected_source_boundary(self) -> None:
        cause = self.payload["rootCause"]
        self.assertEqual(cause["proposedSource"]["fieldPath"], "order_amount")
        self.assertEqual(
            cause["firstDownstreamDependency"]["fieldPath"],
            "order_total",
        )
        self.assertEqual(cause["affectedFields"], 25)
        self.assertEqual(cause["affectedDatasets"], 20)
        self.assertEqual(cause["affectedPaths"], 48)

    def test_root_cause_steps_separate_certainty_classes(self) -> None:
        classes = {
            item["classification"]
            for item in self.payload["rootCause"]["steps"]
        }
        self.assertEqual(
            classes,
            {
                "proposed",
                "counterfactual",
                "unresolved",
                "conditional",
                "decision",
            },
        )

    def test_blocking_question_points_to_root_cause(self) -> None:
        question = self.payload["blockingQuestion"]
        cause = self.payload["rootCause"]
        self.assertEqual(question["rootCauseId"], cause["causeId"])
        self.assertEqual(
            question["rootRelationshipId"],
            cause["rootRelationshipId"],
        )
        self.assertEqual(question["resolutionState"], "unresolved")

    def test_required_evidence_classes_are_exact(self) -> None:
        classes = {
            item["evidenceClass"]
            for item in self.payload["requiredEvidence"]
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

    def test_required_evidence_is_explicitly_unavailable(self) -> None:
        self.assertTrue(
            all(
                item["availability"] == "not_available_required"
                for item in self.payload["requiredEvidence"]
            )
        )

    def test_all_fields_share_the_certified_root_cause(self) -> None:
        root_id = self.payload["rootCause"]["causeId"]
        self.assertTrue(
            all(item["rootCauseId"] == root_id for item in self.payload["fields"])
        )

    def test_all_fields_remain_unresolved(self) -> None:
        self.assertEqual(
            Counter(
                item["technicalImpactState"]
                for item in self.payload["fields"]
            ),
            {"unresolved_impact": 25},
        )

    def test_field_severity_records_match_summary(self) -> None:
        counts = Counter(
            item["severityIfRealized"] for item in self.payload["fields"]
        )
        self.assertEqual(counts, {"low": 16, "moderate": 6, "high": 3})

    def test_dataset_severity_records_match_summary(self) -> None:
        counts = Counter(
            item["severityIfRealized"] for item in self.payload["datasets"]
        )
        self.assertEqual(counts, {"low": 13, "moderate": 4, "high": 3})

    def test_path_references_close_over_fields_and_relationships(self) -> None:
        fields = {item["fieldId"] for item in self.payload["fields"]}
        relationships = {
            item["relationshipId"] for item in self.payload["relationships"]
        }
        for path in self.payload["paths"]:
            self.assertIn(path["targetFieldId"], fields)
            self.assertLessEqual(set(path["relationshipIds"]), relationships)

    def test_context_mappings_close_over_assets_relationships_and_fields(self) -> None:
        fields = {item["fieldId"] for item in self.payload["fields"]}
        assets = {
            item["contextAssetId"] for item in self.payload["contextAssets"]
        }
        relationships = {
            item["relationshipId"]
            for item in self.payload["contextRelationships"]
        }
        for mapping in self.payload["contextMappings"]:
            self.assertIn(mapping["fieldId"], fields)
            self.assertIn(mapping["contextAssetId"], assets)
            self.assertIn(
                mapping["contextRelationshipId"],
                relationships,
            )

    def test_context_assets_are_grouped_without_business_criticality_inference(
        self,
    ) -> None:
        groups = {item["group"] for item in self.payload["contextAssets"]}
        self.assertEqual(groups, {"governance", "operational", "consumer"})
        self.assertFalse(
            self.payload["summary"]["explicitBusinessCriticalityPresent"]
        )

    def test_relationship_distribution_matches_records(self) -> None:
        counts = Counter(
            item["compatibilityState"]
            for item in self.payload["relationships"]
        )
        self.assertEqual(
            counts,
            {"conditionally_compatible": 26, "unknown": 1},
        )

    def test_only_one_relationship_is_the_root_uncertainty(self) -> None:
        roots = [
            item
            for item in self.payload["relationships"]
            if item["isRootUncertainty"]
        ]
        self.assertEqual(len(roots), 1)
        self.assertEqual(
            roots[0]["relationshipId"],
            self.payload["rootCause"]["rootRelationshipId"],
        )

    def test_decision_explanation_is_hold_for_review(self) -> None:
        decision = self.payload["decisionExplanation"]
        self.assertEqual(decision["disposition"], "hold_for_review")
        self.assertEqual(decision["decisionCertainty"], "high_confidence")
        self.assertEqual(decision["technicalCertainty"], "unresolved")

    def test_decision_explanation_distinguishes_failure_from_uncertainty(
        self,
    ) -> None:
        distinction = self.payload["decisionExplanation"][
            "confirmedFailureDistinction"
        ]
        self.assertIn("not a confirmed failure", distinction)
        self.assertIn("Zero downstream failures", distinction)

    def test_explorer_contract_rejects_extra_fields(self) -> None:
        changed = json.loads(json.dumps(self.payload))
        changed["invented"] = True
        with self.assertRaises(ValidationError):
            CertifiedImpactExplorer.model_validate(changed)

    def test_explorer_contract_rejects_wrong_cardinality(self) -> None:
        changed = json.loads(json.dumps(self.payload))
        changed["fields"].pop()
        with self.assertRaises(ValidationError):
            CertifiedImpactExplorer.model_validate(changed)

    def test_explorer_service_is_deterministic(self) -> None:
        service = CertifiedImpactExplorerService(ARTIFACTS)
        first = service.get_explorer("CHRONOS-DEMO-001").model_dump_json()
        second = service.get_explorer("CHRONOS-DEMO-001").model_dump_json()
        self.assertEqual(first, second)

    def test_unknown_review_returns_stable_404(self) -> None:
        response = self.client.get("/api/reviews/not-present/explorer")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json()["detail"]["code"],
            "certified_review_not_found",
        )

    def test_missing_certification_returns_stable_503(self) -> None:
        with self._artifact_copy() as artifact_dir:
            (artifact_dir / "phase_4_certification.json").unlink()
            response = TestClient(
                create_app(artifact_dir=artifact_dir)
            ).get(EXPLORER_URL)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["detail"]["code"],
            "certification_integrity_error",
        )

    def test_tampered_certified_input_returns_stable_503(self) -> None:
        with self._artifact_copy() as artifact_dir:
            target = artifact_dir / "business_context_propagation.json"
            target.write_text(
                target.read_text(encoding="utf-8") + " ",
                encoding="utf-8",
            )
            response = TestClient(
                create_app(artifact_dir=artifact_dir)
            ).get(EXPLORER_URL)
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(str(artifact_dir), response.text)

    def test_service_does_not_import_reasoning_builders(self) -> None:
        source = inspect.getsource(explorer_service_module)
        forbidden = (
            "build_future_graph",
            "propagate_dependencies",
            "evaluate_compatibility",
            "analyze_technical_impact",
            "propagate_business_context",
            "analyze_severity",
            "synthesize_impact",
        )
        for name in forbidden:
            self.assertNotIn(name, source)

    def test_payload_does_not_expose_filesystem_paths(self) -> None:
        encoded = json.dumps(self.payload)
        self.assertNotIn(str(ARTIFACTS), encoded)
        self.assertNotIn("\\\\", encoded)

    def test_payload_uses_camel_case_boundary(self) -> None:
        encoded = json.dumps(self.payload)
        self.assertNotIn('"downstream_fields"', encoded)
        self.assertNotIn('"root_cause"', encoded)
        self.assertIn('"downstreamFields"', encoded)
        self.assertIn('"rootCause"', encoded)

    @staticmethod
    def _artifact_copy() -> tempfile.TemporaryDirectory[str]:
        temporary = tempfile.TemporaryDirectory()
        destination = Path(temporary.name)
        for name in EXPLORER_ARTIFACTS:
            shutil.copy2(ARTIFACTS / name, destination / name)
        return _TemporaryDirectoryContext(temporary)


class _TemporaryDirectoryContext:
    def __init__(self, temporary: tempfile.TemporaryDirectory[str]) -> None:
        self._temporary = temporary

    def __enter__(self) -> Path:
        return Path(self._temporary.name)

    def __exit__(self, *_args: object) -> None:
        self._temporary.cleanup()


if __name__ == "__main__":
    unittest.main()
