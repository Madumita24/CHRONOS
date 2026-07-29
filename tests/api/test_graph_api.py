"""Phase 5.2 certified graph presentation API tests."""

from __future__ import annotations

import inspect
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from pydantic import ValidationError

import chronos.presentation.graph_service as graph_service_module
from chronos.presentation import (
    EXPECTED_PHASE4_CERTIFICATION_FINGERPRINT,
    CertifiedGraphReview,
    CertifiedGraphService,
    create_app,
)


ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "artifacts"
GRAPH_URL = "/api/reviews/CHRONOS-DEMO-001/graph"
GRAPH_ARTIFACTS = (
    "phase_4_certification.json",
    "current_metadata_snapshot.json",
    "counterfactual_source_state.json",
    "future_metadata_graph.json",
    "dependency_propagation.json",
    "compatibility_evaluation.json",
    "technical_impact_analysis.json",
    "impact_synthesis.json",
)


class GraphPresentationApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(create_app(artifact_dir=ARTIFACTS))
        response = cls.client.get(GRAPH_URL)
        if response.status_code != 200:
            raise AssertionError(response.text)
        cls.payload = response.json()

    def test_graph_endpoint_returns_json(self) -> None:
        response = self.client.get(GRAPH_URL)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            response.headers["content-type"].startswith("application/json")
        )

    def test_phase4_certification_is_the_graph_gate(self) -> None:
        certification = self.payload["certification"]
        self.assertEqual(certification["status"], "certified")
        self.assertEqual(
            certification["fingerprint"],
            EXPECTED_PHASE4_CERTIFICATION_FINGERPRINT,
        )
        self.assertEqual(certification["checksPassed"], 49)

    def test_current_graph_has_certified_cardinality(self) -> None:
        graph = self.payload["currentGraph"]
        self.assertEqual(graph["mode"], "current")
        self.assertEqual(len(graph["nodes"]), 26)
        self.assertEqual(len(graph["edges"]), 27)

    def test_current_source_is_order_total(self) -> None:
        source = self.payload["sourceChange"]["current"]
        self.assertEqual(source["fieldPath"], "order_total")
        current_keys = {
            item["machineKey"]
            for item in self.payload["currentGraph"]["nodes"]
        }
        self.assertIn(
            f"{source['datasetUrn']}|order_total",
            current_keys,
        )
        self.assertNotIn(
            f"{source['datasetUrn']}|order_amount",
            current_keys,
        )

    def test_future_graph_has_certified_cardinality(self) -> None:
        graph = self.payload["futureGraph"]
        self.assertEqual(graph["mode"], "future")
        self.assertEqual(len(graph["nodes"]), 26)
        self.assertEqual(len(graph["edges"]), 27)

    def test_future_source_is_order_amount_once(self) -> None:
        source = self.payload["sourceChange"]["future"]
        self.assertEqual(source["fieldPath"], "order_amount")
        nodes = self.payload["futureGraph"]["nodes"]
        source_nodes = [
            item
            for item in nodes
            if item["datasetUrn"] == source["datasetUrn"]
            and item["fieldPath"] == "order_amount"
        ]
        self.assertEqual(len(source_nodes), 1)
        self.assertFalse(
            any(
                item["datasetUrn"] == source["datasetUrn"]
                and item["fieldPath"] == "order_total"
                for item in nodes
            )
        )

    def test_diff_graph_has_explicit_source_replacement(self) -> None:
        graph = self.payload["diffGraph"]
        self.assertEqual(graph["mode"], "diff")
        self.assertEqual(len(graph["nodes"]), 27)
        self.assertEqual(len(graph["edges"]), 28)
        states = {item["diffState"] for item in graph["nodes"]}
        self.assertIn("removed_current_identity", states)
        self.assertIn("added_counterfactual_identity", states)
        self.assertIn("identity_preserved", states)

    def test_twenty_five_downstream_identities_are_preserved(self) -> None:
        mappings = self.payload["identityMappings"]
        self.assertEqual(len(mappings), 26)
        self.assertEqual(
            sum(
                item["classification"] == "identity_preserved"
                for item in mappings
            ),
            25,
        )
        self.assertEqual(
            sum(item["classification"] == "renamed" for item in mappings),
            1,
        )

    def test_root_edge_is_unknown_with_insufficient_evidence(self) -> None:
        root = self.payload["rootUncertainty"]
        self.assertEqual(root["compatibilityState"], "unknown")
        self.assertEqual(root["evidenceStrength"], "insufficient")
        self.assertEqual(
            root["reasonCode"],
            "source_rename_semantics_unknown",
        )
        self.assertEqual(root["pathParticipationCount"], 48)
        self.assertEqual(len(root["missingEvidence"]), 4)

    def test_root_edge_pairs_current_and_future_identity(self) -> None:
        root = self.payload["rootUncertainty"]
        self.assertEqual(root["currentSource"]["fieldPath"], "order_total")
        self.assertEqual(root["futureSource"]["fieldPath"], "order_amount")
        self.assertEqual(root["currentTarget"], root["futureTarget"])

    def test_future_graph_has_one_unknown_relationship(self) -> None:
        edges = self.payload["futureGraph"]["edges"]
        unknown = [
            item
            for item in edges
            if item["compatibilityState"] == "unknown"
        ]
        self.assertEqual(len(unknown), 1)
        self.assertTrue(unknown[0]["isRootUncertainty"])

    def test_future_graph_has_twenty_six_conditional_relationships(self) -> None:
        edges = self.payload["futureGraph"]["edges"]
        self.assertEqual(
            sum(
                item["compatibilityState"]
                == "conditionally_compatible"
                for item in edges
            ),
            26,
        )

    def test_unknown_is_not_incompatible(self) -> None:
        edges = self.payload["futureGraph"]["edges"]
        self.assertEqual(
            sum(
                item["compatibilityState"] == "incompatible"
                for item in edges
            ),
            0,
        )

    def test_current_graph_does_not_claim_future_compatibility(self) -> None:
        self.assertTrue(
            all(
                item["compatibilityState"] is None
                for item in self.payload["currentGraph"]["edges"]
            )
        )

    def test_all_certified_supporting_paths_are_preserved(self) -> None:
        paths = self.payload["supportingPaths"]
        self.assertEqual(len(paths), 48)
        self.assertEqual(len({item["pathId"] for item in paths}), 48)
        self.assertTrue(
            all(item["compatibilityState"] == "unknown" for item in paths)
        )

    def test_representative_paths_are_preserved(self) -> None:
        paths = self.payload["representativePaths"]
        self.assertEqual(len(paths), 3)
        self.assertEqual(
            {item["kind"] for item in paths},
            {"short", "deep", "multipath"},
        )
        path_ids = {
            item["pathId"] for item in self.payload["supportingPaths"]
        }
        self.assertTrue(
            all(item["supportingPathId"] in path_ids for item in paths)
        )

    def test_summary_is_the_frozen_certified_baseline(self) -> None:
        self.assertEqual(
            self.payload["summary"],
            {
                "currentFieldNodes": 26,
                "futureFieldNodes": 26,
                "downstreamFields": 25,
                "downstreamDatasets": 20,
                "structuralRelationships": 27,
                "supportingPaths": 48,
                "rootUnknownBoundaries": 1,
                "conditionalRelationships": 26,
                "multipathFields": 21,
                "confirmedFailures": 0,
                "maximumDepth": 5,
            },
        )

    def test_node_contract_contains_intentional_graph_facts(self) -> None:
        node = self.payload["futureGraph"]["nodes"][0]
        self.assertEqual(
            set(node),
            {
                "id",
                "machineKey",
                "label",
                "secondaryLabel",
                "entityType",
                "platform",
                "datasetUrn",
                "fieldPath",
                "graphState",
                "diffState",
                "exposureState",
                "compatibilityState",
                "technicalImpactState",
                "severityIfRealized",
                "certainty",
                "depth",
                "pathCount",
                "isChangeOrigin",
                "isRootBoundaryTarget",
                "supportingPathIds",
                "provenanceReferences",
            },
        )

    def test_edge_contract_contains_intentional_graph_facts(self) -> None:
        root_id = self.payload["rootUncertainty"]["futureEdgeId"]
        edge = next(
            item
            for item in self.payload["futureGraph"]["edges"]
            if item["id"] == root_id
        )
        self.assertEqual(edge["compatibilityState"], "unknown")
        self.assertEqual(edge["technicalImpactState"], "unresolved_impact")
        self.assertEqual(edge["exposureState"], "source_rebased_edge")
        self.assertEqual(edge["pathParticipationCount"], 48)

    def test_browser_provenance_references_are_bounded(self) -> None:
        records = (
            self.payload["currentGraph"]["nodes"]
            + self.payload["futureGraph"]["nodes"]
            + self.payload["diffGraph"]["nodes"]
            + self.payload["currentGraph"]["edges"]
            + self.payload["futureGraph"]["edges"]
            + self.payload["diffGraph"]["edges"]
            + self.payload["supportingPaths"]
        )
        self.assertTrue(records)
        self.assertLessEqual(
            max(len(item["provenanceReferences"]) for item in records),
            12,
        )

    def test_graph_dto_is_deterministic(self) -> None:
        service = CertifiedGraphService(ARTIFACTS)
        first = service.get_graph("CHRONOS-DEMO-001")
        second = service.get_graph("CHRONOS-DEMO-001")
        self.assertEqual(
            first.model_dump_json(by_alias=True),
            second.model_dump_json(by_alias=True),
        )

    def test_dangling_graph_reference_is_rejected(self) -> None:
        payload = json.loads(json.dumps(self.payload))
        payload["futureGraph"]["edges"][0]["source"] = "missing-node"
        with self.assertRaises(ValidationError):
            CertifiedGraphReview.model_validate(payload)

    def test_dangling_path_reference_is_rejected(self) -> None:
        payload = json.loads(json.dumps(self.payload))
        payload["supportingPaths"][0]["futureEdgeIds"][0] = "missing-edge"
        with self.assertRaises(ValidationError):
            CertifiedGraphReview.model_validate(payload)

    def test_unknown_review_returns_404(self) -> None:
        response = self.client.get(
            "/api/reviews/CHRONOS-DEMO-999/graph"
        )
        self.assertEqual(response.status_code, 404)

    def test_missing_certification_returns_503(self) -> None:
        with self._artifact_copy() as artifact_dir:
            (artifact_dir / "phase_4_certification.json").unlink()
            response = TestClient(
                create_app(artifact_dir=artifact_dir)
            ).get(GRAPH_URL)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["detail"]["code"],
            "certification_integrity_error",
        )

    def test_missing_future_graph_returns_503(self) -> None:
        with self._artifact_copy() as artifact_dir:
            (artifact_dir / "future_metadata_graph.json").unlink()
            response = TestClient(
                create_app(artifact_dir=artifact_dir)
            ).get(GRAPH_URL)
        self.assertEqual(response.status_code, 503)

    def test_tampered_future_graph_returns_503(self) -> None:
        with self._artifact_copy() as artifact_dir:
            target = artifact_dir / "future_metadata_graph.json"
            payload = json.loads(target.read_text(encoding="utf-8"))
            payload["demonstration_id"] = "tampered"
            target.write_text(json.dumps(payload), encoding="utf-8")
            response = TestClient(
                create_app(artifact_dir=artifact_dir)
            ).get(GRAPH_URL)
        self.assertEqual(response.status_code, 503)

    def test_graph_error_does_not_leak_filesystem_paths(self) -> None:
        with self._artifact_copy() as artifact_dir:
            (artifact_dir / "dependency_propagation.json").unlink()
            response = TestClient(
                create_app(artifact_dir=artifact_dir)
            ).get(GRAPH_URL)
        self.assertNotIn(str(artifact_dir), response.text)
        self.assertNotIn("Traceback", response.text)

    def test_graph_payload_excludes_credentials(self) -> None:
        text = json.dumps(self.payload).lower()
        for forbidden in (
            "datahub_token",
            "authorization: bearer",
            "client_secret",
            "password=",
            "c:\\users\\",
        ):
            self.assertNotIn(forbidden, text)

    def test_mapper_has_no_reasoning_or_traversal_entrypoints(self) -> None:
        source = inspect.getsource(graph_service_module)
        for forbidden in (
            "derive_technical_impact(",
            "evaluate_compatibility(",
            "propagate_dependencies(",
            "enumerate_dependency_paths(",
            "shortest_dependency_depths(",
            "synthesize_impact(",
        ):
            self.assertNotIn(forbidden, source)

    def test_graph_contract_uses_camel_case(self) -> None:
        self.assertIn("currentGraph", self.payload)
        self.assertIn("rootUncertainty", self.payload)
        self.assertNotIn("current_graph", self.payload)

    def test_legend_covers_required_semantics(self) -> None:
        keys = {item["key"] for item in self.payload["legend"]}
        self.assertEqual(
            keys,
            {
                "certified_current",
                "counterfactual_changed",
                "source_changed",
                "unknown",
                "conditionally_compatible",
                "compatible",
                "incompatible",
                "multipath_exposed",
            },
        )

    def _artifact_copy(self):
        temporary = tempfile.TemporaryDirectory()
        target = Path(temporary.name)
        for name in GRAPH_ARTIFACTS:
            shutil.copy2(ARTIFACTS / name, target / name)

        class Context:
            def __enter__(self):
                return target

            def __exit__(self, *_):
                temporary.cleanup()

        return Context()


if __name__ == "__main__":
    unittest.main()
