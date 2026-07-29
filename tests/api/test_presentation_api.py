"""Phase 5.1 certified presentation API tests."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from chronos.presentation import (
    EXPECTED_PHASE4_CERTIFICATION_FINGERPRINT,
    create_app,
)


ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "artifacts"
REVIEW_URL = "/api/reviews/CHRONOS-DEMO-001"
REQUIRED_ARTIFACTS = (
    "phase_4_certification.json",
    "change_proposal.json",
    "impact_synthesis.json",
    "counterfactual_source_state.json",
)


class PresentationApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(create_app(artifact_dir=ARTIFACTS))
        response = cls.client.get(REVIEW_URL)
        if response.status_code != 200:
            raise AssertionError(response.text)
        cls.payload = response.json()

    def test_health_is_ready(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ready")

    def test_health_reports_supported_review(self) -> None:
        payload = self.client.get("/health").json()
        self.assertEqual(payload["reviewId"], "CHRONOS-DEMO-001")

    def test_health_reports_expected_certification(self) -> None:
        payload = self.client.get("/health").json()
        self.assertEqual(
            payload["certificationFingerprint"],
            EXPECTED_PHASE4_CERTIFICATION_FINGERPRINT,
        )

    def test_review_uses_json_content_type(self) -> None:
        response = self.client.get(REVIEW_URL)
        self.assertTrue(
            response.headers["content-type"].startswith("application/json")
        )

    def test_review_contract_uses_camel_case(self) -> None:
        self.assertIn("technicalSummary", self.payload)
        self.assertNotIn("technical_summary", self.payload)
        self.assertIn("certifiedAt", self.payload["certification"])

    def test_review_is_certified(self) -> None:
        certification = self.payload["certification"]
        self.assertEqual(certification["status"], "certified")
        self.assertEqual(certification["checksPassed"], 49)
        self.assertEqual(certification["checkCount"], 49)

    def test_review_fingerprint_is_frozen(self) -> None:
        self.assertEqual(
            self.payload["certification"]["fingerprint"],
            EXPECTED_PHASE4_CERTIFICATION_FINGERPRINT,
        )

    def test_review_disposition_is_hold_for_review(self) -> None:
        decision = self.payload["decision"]
        self.assertEqual(decision["disposition"], "hold_for_review")
        self.assertEqual(decision["dispositionLabel"], "Hold For Review")

    def test_decision_and_technical_certainty_remain_distinct(self) -> None:
        decision = self.payload["decision"]
        self.assertEqual(decision["decisionCertainty"], "high_confidence")
        self.assertEqual(decision["technicalCertainty"], "unresolved")

    def test_technical_summary_matches_certified_baseline(self) -> None:
        summary = self.payload["technicalSummary"]
        self.assertEqual(summary["confirmedDownstreamFailures"], 0)
        self.assertEqual(summary["unresolvedFields"], 25)
        self.assertEqual(summary["downstreamDatasets"], 20)
        self.assertEqual(summary["unresolvedPaths"], 48)

    def test_scope_summary_matches_certified_baseline(self) -> None:
        scope = self.payload["scopeSummary"]
        self.assertEqual(scope["connectedContextAssets"], 66)
        self.assertEqual(scope["contextRelationships"], 211)
        self.assertEqual(scope["fieldToContextMappings"], 257)

    def test_severity_profile_preserves_conditional_wording(self) -> None:
        severity = self.payload["severityProfile"]
        self.assertEqual(severity["severityIfRealized"], "high")
        self.assertEqual(severity["breadth"], "widespread")
        self.assertEqual(severity["technicalCertainty"], "unresolved")

    def test_blocking_question_is_present(self) -> None:
        questions = self.payload["blockingQuestions"]
        self.assertEqual(len(questions), 1)
        self.assertEqual(questions[0]["resolutionState"], "unresolved")
        self.assertIn("Spark export", questions[0]["question"])

    def test_required_evidence_is_present(self) -> None:
        evidence = self.payload["requiredEvidence"]
        self.assertEqual(len(evidence), 4)
        self.assertTrue(
            all(
                item["state"] == "required_for_decision_resolution"
                for item in evidence
            )
        )

    def test_representative_paths_are_present(self) -> None:
        paths = self.payload["representativePaths"]
        self.assertEqual(len(paths), 3)
        self.assertEqual(
            {item["kind"] for item in paths},
            {"short", "deep", "multipath"},
        )
        self.assertEqual(
            [item["hopCount"] for item in paths],
            [1, 7, 3],
        )

    def test_context_highlights_are_certified_selection(self) -> None:
        highlights = self.payload["contextHighlights"]
        self.assertEqual(len(highlights), 11)
        self.assertIn(
            "Popular Products",
            {item["displayName"] for item in highlights},
        )

    def test_change_identity_is_preserved(self) -> None:
        change = self.payload["change"]
        self.assertEqual(change["operation"], "field_rename")
        self.assertEqual(change["currentField"], "order_total")
        self.assertEqual(change["requestedField"], "order_amount")

    def test_current_and_counterfactual_state_are_separate(self) -> None:
        current = self.payload["currentState"]
        candidate = self.payload["counterfactualState"]
        self.assertEqual(current["classification"], "certified_current")
        self.assertEqual(candidate["classification"], "counterfactual")
        self.assertEqual(current["fieldPath"], "order_total")
        self.assertEqual(candidate["fieldPath"], "order_amount")
        self.assertEqual(current["nativeType"], candidate["nativeType"])

    def test_unknown_review_returns_404(self) -> None:
        response = self.client.get("/api/reviews/CHRONOS-DEMO-999")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json()["detail"]["code"],
            "certified_review_not_found",
        )

    def test_missing_certification_returns_integrity_error(self) -> None:
        with self._artifact_copy() as artifact_dir:
            (artifact_dir / "phase_4_certification.json").unlink()
            response = TestClient(
                create_app(artifact_dir=artifact_dir)
            ).get(REVIEW_URL)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["detail"]["code"],
            "certification_integrity_error",
        )

    def test_corrupt_certification_returns_integrity_error(self) -> None:
        with self._artifact_copy() as artifact_dir:
            target = artifact_dir / "phase_4_certification.json"
            payload = json.loads(target.read_text(encoding="utf-8"))
            payload["scope_statement"] = "tampered"
            target.write_text(json.dumps(payload), encoding="utf-8")
            response = TestClient(
                create_app(artifact_dir=artifact_dir)
            ).get(REVIEW_URL)
        self.assertEqual(response.status_code, 503)

    def test_missing_synthesis_returns_integrity_error(self) -> None:
        with self._artifact_copy() as artifact_dir:
            (artifact_dir / "impact_synthesis.json").unlink()
            response = TestClient(
                create_app(artifact_dir=artifact_dir)
            ).get(REVIEW_URL)
        self.assertEqual(response.status_code, 503)

    def test_integrity_error_does_not_leak_local_paths(self) -> None:
        with self._artifact_copy() as artifact_dir:
            (artifact_dir / "change_proposal.json").unlink()
            response = TestClient(
                create_app(artifact_dir=artifact_dir)
            ).get(REVIEW_URL)
        body = response.text
        self.assertNotIn(str(artifact_dir), body)
        self.assertNotIn("Traceback", body)

    def test_allowed_local_origin_receives_cors_header(self) -> None:
        response = self.client.get(
            REVIEW_URL,
            headers={"Origin": "http://localhost:3000"},
        )
        self.assertEqual(
            response.headers["access-control-allow-origin"],
            "http://localhost:3000",
        )

    def test_unlisted_origin_receives_no_cors_header(self) -> None:
        response = self.client.get(
            REVIEW_URL,
            headers={"Origin": "https://example.invalid"},
        )
        self.assertNotIn(
            "access-control-allow-origin",
            response.headers,
        )

    def _artifact_copy(self):
        temporary = tempfile.TemporaryDirectory()
        target = Path(temporary.name)
        for name in REQUIRED_ARTIFACTS:
            shutil.copy2(ARTIFACTS / name, target / name)

        class Context:
            def __enter__(self):
                return target

            def __exit__(self, *_):
                temporary.cleanup()

        return Context()


if __name__ == "__main__":
    unittest.main()
