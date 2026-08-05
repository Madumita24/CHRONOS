from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from chronos.presentation.api import create_app
from chronos.presentation.errors import CertifiedReviewNotFound, PresentationIntegrityError
from chronos.presentation.phase6_models import (
    PullRequestAnalysisView,
    RepairAnalysisView,
    SemanticAnalysisView,
    StructuralAnalysisView,
)
from chronos.presentation.phase6_service import Phase6PresentationService


ROOT = Path(__file__).resolve().parents[2]


class Phase6PresentationServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.service = Phase6PresentationService(ROOT)

    def test_release_preserves_certification_and_limitations(self):
        release = self.service.get_release()
        self.assertEqual(release.certification.state, "PHASE_6_CERTIFIED_WITH_NON_BLOCKING_LIMITATIONS")
        self.assertEqual(release.certification.limitations, ("seven live DataHub-dependent tests intentionally skipped",))
        self.assertFalse(release.certification.runtime_verified)

    def test_release_preserves_test_totals_and_golden_state(self):
        release = self.service.get_release()
        self.assertEqual(release.test_totals.model_dump(), {"executed": 1484, "passed": 1477, "skipped": 7, "failed": 0})
        self.assertEqual(release.golden_preservation_state, "PASS")

    def test_index_contains_only_approved_analyses(self):
        result = self.service.list_analyses()
        self.assertEqual(len(result.analyses), 17)
        self.assertEqual({item.analysis_type for item in result.analyses}, {"structural", "semantic", "pull_request", "repair"})

    def test_detail_union_discriminates_all_four_types(self):
        self.assertIsInstance(self.service.get_analysis("CHRONOS-DEMO-001-GENERALIZED-RENAME"), StructuralAnalysisView)
        self.assertIsInstance(self.service.get_analysis("CHRONOS-SEMANTIC-AGGREGATION-001"), SemanticAnalysisView)
        self.assertIsInstance(self.service.get_analysis("CHRONOS-PR-PRIMARY-001"), PullRequestAnalysisView)
        self.assertIsInstance(self.service.get_analysis("CHRONOS-REPAIR-PRIMARY-001"), RepairAnalysisView)

    def test_primary_pr_preserves_certified_counts_and_decision(self):
        result = self.service.get_analysis("CHRONOS-PR-PRIMARY-001")
        self.assertEqual(len(result.changed_files), 4)
        self.assertEqual(result.coherence, "INCONSISTENT")
        self.assertEqual(result.decision, "hold_for_review")
        self.assertEqual(len(result.conflicts), 0)
        self.assertEqual(result.confirmed_runtime_failures, 0)

    def test_primary_repair_preserves_actions_and_projection(self):
        result = self.service.get_repair("CHRONOS-REPAIR-PRIMARY-001")
        self.assertEqual(len(result.actions), 2)
        self.assertEqual(len(result.patches), 2)
        self.assertEqual(result.comparison.original_coherence, "INCONSISTENT")
        self.assertEqual(result.comparison.projected_coherence, "COHERENT")
        self.assertEqual(result.comparison.original_stale_references, 2)
        self.assertEqual(result.comparison.projected_stale_references, 0)
        self.assertEqual(result.comparison.execution_validity, "UNVERIFIED")
        self.assertIn("clean_patch_application", result.phase_7_requirements)
        self.assertIn("runtime_evidence_collection", result.phase_7_requirements)
        self.assertEqual(len(result.phase_7_requirements), 10)
        self.assertFalse(any(value.startswith("{") for value in result.phase_7_requirements))

    def test_patch_preview_is_bounded_and_unapplied(self):
        result = self.service.get_patch("CHRONOS-REPAIR-PRIMARY-001", "patch-0")
        self.assertLessEqual(len(result.lines), 200)
        self.assertEqual(result.label, "CANDIDATE - NOT APPLIED")
        self.assertFalse(result.runtime_verified)
        self.assertFalse(Path(result.file).is_absolute())

    def test_graph_has_closed_backend_supplied_references(self):
        graph = self.service.get_graph("CHRONOS-PR-PRIMARY-001")
        nodes = {item.node_id for item in graph.nodes}
        self.assertTrue(all(item.source in nodes and item.target in nodes for item in graph.edges))
        self.assertGreater(len(graph.representative_paths), 0)

    def test_graph_modes_are_backend_derived_and_analysis_specific(self):
        current = self.service.get_graph("CHRONOS-PR-PRIMARY-001", "CURRENT")
        proposed = self.service.get_graph("CHRONOS-PR-PRIMARY-001", "PROPOSED")
        difference = self.service.get_graph("CHRONOS-PR-PRIMARY-001", "DIFF")
        projected = self.service.get_graph("CHRONOS-REPAIR-PRIMARY-001", "PROJECTED_REPAIRED")
        self.assertEqual(current.available_modes, ("CURRENT", "PROPOSED", "DIFF"))
        self.assertTrue(all(edge.category == "OBSERVED_DATAHUB_EDGE" for edge in current.edges))
        self.assertEqual(proposed.mode, "PROPOSED")
        self.assertEqual(difference.mode, "DIFF")
        self.assertEqual(projected.available_modes, ("CURRENT", "PROPOSED", "PROJECTED_REPAIRED"))
        self.assertEqual(projected.mode, "PROJECTED_REPAIRED")

    def test_repair_graph_defaults_to_projected_repaired_state(self):
        graph = self.service.get_graph("CHRONOS-REPAIR-PRIMARY-001")
        self.assertEqual(graph.mode, "PROJECTED_REPAIRED")

    def test_unsupported_graph_mode_fails_closed(self):
        with self.assertRaises(PresentationIntegrityError):
            self.service.get_graph("CHRONOS-PR-PRIMARY-001", "PROJECTED_REPAIRED")

    def test_unknown_and_path_shaped_ids_fail_closed(self):
        with self.assertRaises(CertifiedReviewNotFound):
            self.service.get_analysis("CHRONOS-UNKNOWN-001")
        with self.assertRaises(CertifiedReviewNotFound):
            self.service.get_analysis("../../artifacts")

    def test_non_repair_patch_endpoint_fails_closed(self):
        with self.assertRaises(CertifiedReviewNotFound):
            self.service.get_patch("CHRONOS-PR-PRIMARY-001", "patch-0")

    def test_adapter_does_not_call_analysis_engines(self):
        source = (ROOT / "src" / "chronos" / "presentation" / "phase6_service.py").read_text(encoding="utf-8")
        for call in ("analyze_structural_change(", "analyze_semantic_code_change(", "analyze_pull_request(", "generate_repair("):
            self.assertNotIn(call, source)

    def test_tampered_package_fingerprint_fails_closed(self):
        with self._copy_repository() as copied:
            target = copied / "certified_packages" / "phase6" / "CHRONOS-PR-PRIMARY-001" / "coherence_evaluation.json"
            value = json.loads(target.read_text(encoding="utf-8"))
            value["state"] = "COHERENT"
            target.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaises(PresentationIntegrityError):
                Phase6PresentationService(copied).get_analysis("CHRONOS-PR-PRIMARY-001")

    def test_partial_package_fails_closed(self):
        with self._copy_repository() as copied:
            target = copied / "certified_packages" / "phase6" / "CHRONOS-SEMANTIC-FILTER-001" / "semantic_diff.json"
            target.unlink()
            with self.assertRaises(PresentationIntegrityError):
                Phase6PresentationService(copied).get_analysis("CHRONOS-SEMANTIC-FILTER-001")

    def test_unknown_schema_fails_closed(self):
        with self._copy_repository() as copied:
            target = copied / "certified_packages" / "phase6" / "CHRONOS-DEMO-001-GENERALIZED-RENAME" / "manifest.json"
            value = json.loads(target.read_text(encoding="utf-8"))
            value["artifact_schema_version"] = "99.0"
            target.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaises(PresentationIntegrityError):
                Phase6PresentationService(copied).get_analysis("CHRONOS-DEMO-001-GENERALIZED-RENAME")

    def test_absolute_path_in_artifact_fails_closed(self):
        with self._copy_repository() as copied:
            target = copied / "certified_packages" / "phase6" / "CHRONOS-PR-PRIMARY-001" / "changed_file_inventory.json"
            value = json.loads(target.read_text(encoding="utf-8"))
            value["files"][0]["head_path"] = "C:\\secret\\model.sql"
            target.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaises(PresentationIntegrityError):
                Phase6PresentationService(copied).get_analysis("CHRONOS-PR-PRIMARY-001")

    def _copy_repository(self):
        temporary = tempfile.TemporaryDirectory(dir=ROOT)
        root = Path(temporary.name)
        shutil.copytree(ROOT / "artifacts" / "certifications" / "phase-6-rerun", root / "artifacts" / "certifications" / "phase-6-rerun")
        shutil.copytree(ROOT / "certified_packages" / "phase6", root / "certified_packages" / "phase6")
        return _TemporaryRepository(temporary, root)


class Phase6PresentationApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(create_app(phase6_repository_root=ROOT))

    def test_release_endpoint(self):
        response = self.client.get("/api/phase6/release")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["skippedTestCount"], 7)

    def test_index_endpoint(self):
        response = self.client.get("/api/analyses")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["analyses"]), 17)

    def test_detail_graph_evidence_and_repair_endpoints(self):
        for path in (
            "/api/analyses/CHRONOS-PR-PRIMARY-001",
            "/api/analyses/CHRONOS-PR-PRIMARY-001/graph",
            "/api/analyses/CHRONOS-PR-PRIMARY-001/evidence",
            "/api/analyses/CHRONOS-REPAIR-PRIMARY-001/repair",
            "/api/analyses/CHRONOS-REPAIR-PRIMARY-001/patches/patch-0",
        ):
            self.assertEqual(self.client.get(path).status_code, 200, path)

    def test_graph_mode_query(self):
        response = self.client.get("/api/analyses/CHRONOS-PR-PRIMARY-001/graph?mode=CURRENT")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["mode"], "CURRENT")
        self.assertEqual(response.json()["availableModes"], ["CURRENT", "PROPOSED", "DIFF"])

    def test_unknown_analysis_returns_bounded_404(self):
        response = self.client.get("/api/analyses/CHRONOS-UNKNOWN-001")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"]["code"], "certified_analysis_not_found")
        self.assertNotIn(str(ROOT), response.text)


class _TemporaryRepository:
    def __init__(self, temporary, root):
        self._temporary = temporary
        self._root = root

    def __enter__(self):
        return self._root

    def __exit__(self, *_):
        self._temporary.cleanup()
