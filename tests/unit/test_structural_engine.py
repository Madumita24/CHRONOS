from __future__ import annotations

import copy
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
from io import StringIO
from pathlib import Path

from chronos import analyze_structural_change
from chronos.cli import main as cli_main
from chronos.phase4_certification import load_phase4_certification
from chronos.snapshot import load_snapshot
from chronos.structural_engine import (
    ARTIFACT_FILENAMES,
    CertificationError,
    OutputSafetyError,
    ProposalValidationError,
    TargetResolutionError,
    parse_proposal,
)
from chronos.structural_engine.certification import certify_artifacts


ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_PATH = ROOT / "artifacts" / "current_metadata_snapshot.json"
EXAMPLES = ROOT / "examples"
GOLDEN_PHASE4_FINGERPRINT = (
    "sha256:3e8444ec904e0ba1c55c5ae22d69edfa8e722310f51ab30fc783b8175a87ac4a"
)


class StructuralEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.snapshot = load_snapshot(SNAPSHOT_PATH)
        cls.scratch_parent = ROOT / ".pytest_tmp"
        cls.scratch_parent.mkdir(exist_ok=True)

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(
            prefix="phase61-", dir=self.scratch_parent
        )
        self.work = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def proposal(self, operation: str) -> dict:
        folder = {
            "FIELD_RENAME": "field_rename",
            "FIELD_DELETE": "field_delete",
            "FIELD_TYPE_CHANGE": "field_type_change",
        }[operation]
        return json.loads(
            (EXAMPLES / folder / "change.json").read_text(encoding="utf-8")
        )

    def analyze(self, operation: str, name: str = "analysis", **changes):
        proposal = self.proposal(operation)
        proposal.update(changes)
        return analyze_structural_change(
            snapshot=self.snapshot,
            proposal=proposal,
            output_dir=self.work / name,
        )

    def test_01_strict_union_parses_rename(self):
        self.assertEqual(parse_proposal(self.proposal("FIELD_RENAME")).operation.value, "FIELD_RENAME")

    def test_02_strict_union_parses_delete(self):
        self.assertEqual(parse_proposal(self.proposal("FIELD_DELETE")).operation.value, "FIELD_DELETE")

    def test_03_strict_union_parses_type_change(self):
        self.assertEqual(parse_proposal(self.proposal("FIELD_TYPE_CHANGE")).operation.value, "FIELD_TYPE_CHANGE")

    def test_04_rename_shared_pipeline(self):
        result = self.analyze("FIELD_RENAME")
        self.assertEqual(result.disposition, "hold_for_review")
        self.assertEqual(result.certification_status, "certified")

    def test_05_delete_shared_pipeline(self):
        result = self.analyze("FIELD_DELETE")
        self.assertEqual(result.disposition, "block_confirmed_incompatibility")

    def test_06_type_change_shared_pipeline(self):
        result = self.analyze("FIELD_TYPE_CHANGE")
        self.assertEqual(result.disposition, "hold_for_review")

    def test_07_rename_counterfactual_invariants(self):
        result = self.analyze("FIELD_RENAME")
        artifact = result.artifacts["counterfactual_source_state.json"]
        self.assertEqual(artifact["current_source_schema"]["field_count"], artifact["projected_source_schema"]["field_count"])
        paths = [item["field_path"] for item in artifact["projected_source_schema"]["fields"]]
        self.assertNotIn("order_total", paths)
        self.assertEqual(paths.count("order_amount"), 1)

    def test_08_delete_counterfactual_invariants(self):
        result = self.analyze("FIELD_DELETE")
        artifact = result.artifacts["counterfactual_source_state.json"]
        self.assertEqual(artifact["projected_source_schema"]["field_count"], artifact["current_source_schema"]["field_count"] - 1)
        self.assertNotIn("order_total", [item["field_path"] for item in artifact["projected_source_schema"]["fields"]])

    def test_09_type_counterfactual_invariants(self):
        result = self.analyze("FIELD_TYPE_CHANGE")
        fields = result.artifacts["counterfactual_source_state.json"]["projected_source_schema"]["fields"]
        changed = next(item for item in fields if item["field_path"] == "order_total")
        self.assertEqual((changed["native_type"], changed["normalized_type"]), ("TEXT", "STRING"))

    def test_10_operation_identity_mappings(self):
        expected = {
            "FIELD_RENAME": "RENAMED",
            "FIELD_DELETE": "DELETED",
            "FIELD_TYPE_CHANGE": "IDENTITY_PRESERVED_TYPE_CHANGED",
        }
        for index, (operation, classification) in enumerate(expected.items()):
            result = self.analyze(operation, f"mapping-{index}")
            contract = result.artifacts["change_semantic_contract.json"]
            self.assertEqual(contract["identity_mapping"]["classification"], classification)

    def test_11_graph_counts_derive_from_snapshot(self):
        result = self.analyze("FIELD_RENAME")
        graph = result.artifacts["future_metadata_graph.json"]
        self.assertEqual(len(graph["relationships"]), len(self.snapshot.lineage_edges))

    def test_12_path_counts_derive_from_snapshot(self):
        result = self.analyze("FIELD_RENAME")
        propagation = result.artifacts["dependency_propagation.json"]
        expected = sum(
            bool(path.node_keys) and path.node_keys[0] == self.snapshot.source_field_key
            for path in self.snapshot.lineage_paths
        )
        self.assertEqual(propagation["metrics"]["path_count"], expected)

    def test_13_context_counts_derive_from_selected_relationships(self):
        result = self.analyze("FIELD_RENAME")
        context = result.artifacts["business_context_propagation.json"]
        self.assertEqual(sum(context["category_counts"].values()), len(context["context_relationships"]))

    def test_14_different_proposal_and_analysis_ids_work(self):
        result = self.analyze(
            "FIELD_RENAME",
            proposal_id="ANOTHER-PROPOSAL",
            analysis_id="ANOTHER-ANALYSIS",
        )
        self.assertEqual(result.identity.proposal_id, "ANOTHER-PROPOSAL")
        self.assertEqual(result.identity.analysis_id, "ANOTHER-ANALYSIS")

    def test_15_different_field_works_without_golden_lineage(self):
        result = self.analyze(
            "FIELD_RENAME",
            current_field_path="order_date",
            proposed_field_path="purchase_date",
        )
        self.assertEqual(result.disposition, "proceed")
        self.assertEqual(result.artifacts["dependency_propagation.json"]["metrics"]["relationship_count"], 0)

    def test_16_decision_derives_from_run_inputs(self):
        golden = self.analyze("FIELD_RENAME", "with-lineage")
        isolated = self.analyze(
            "FIELD_RENAME",
            "without-lineage",
            current_field_path="order_date",
            proposed_field_path="purchase_date",
        )
        self.assertNotEqual(golden.disposition, isolated.disposition)

    def test_17_root_cause_is_operation_specific(self):
        reasons = set()
        for index, operation in enumerate(("FIELD_RENAME", "FIELD_DELETE", "FIELD_TYPE_CHANGE")):
            result = self.analyze(operation, f"cause-{index}")
            reasons.add(result.artifacts["technical_impact_analysis.json"]["root_causes"][0]["reason_code"])
        self.assertEqual(len(reasons), 3)

    def test_18_blocking_question_is_operation_specific(self):
        rename = self.analyze("FIELD_RENAME", "rename-question")
        type_change = self.analyze("FIELD_TYPE_CHANGE", "type-question")
        rename_q = rename.artifacts["impact_synthesis.json"]["blocking_questions"][0]["question"]
        type_q = type_change.artifacts["impact_synthesis.json"]["blocking_questions"][0]["question"]
        self.assertIn("renamed input", rename_q)
        self.assertIn("input type", type_q)

    def test_19_required_evidence_is_rule_specific(self):
        rename = self.analyze("FIELD_RENAME", "rename-evidence")
        type_change = self.analyze("FIELD_TYPE_CHANGE", "type-evidence")
        first = rename.artifacts["compatibility_evaluation.json"]["root_evaluation"]["required_evidence"]
        second = type_change.artifacts["compatibility_evaluation.json"]["root_evaluation"]["required_evidence"]
        self.assertNotEqual(first, second)

    def test_20_artifact_package_is_complete_and_isolated(self):
        first = self.analyze("FIELD_RENAME", "first")
        second = self.analyze("FIELD_DELETE", "second")
        self.assertEqual({item.name for item in first.artifact_paths}, set(ARTIFACT_FILENAMES))
        self.assertNotEqual(first.output_dir, second.output_dir)

    def test_21_rerun_semantic_fingerprint_is_deterministic(self):
        first = self.analyze("FIELD_DELETE", "one")
        second = self.analyze("FIELD_DELETE", "two")
        self.assertEqual(first.semantic_fingerprint, second.semantic_fingerprint)

    def test_22_timestamp_does_not_change_semantic_fingerprint(self):
        first = self.analyze("FIELD_RENAME", "one-time", created_at="2026-01-01T00:00:00Z")
        second = self.analyze("FIELD_RENAME", "two-time", created_at="2027-01-01T00:00:00Z")
        self.assertEqual(first.semantic_fingerprint, second.semantic_fingerprint)

    def test_23_nonexistent_dataset_rejected(self):
        with self.assertRaises(TargetResolutionError):
            self.analyze("FIELD_DELETE", dataset_urn="urn:li:dataset:(urn:li:dataPlatform:postgres,missing,PROD)")

    def test_24_nonexistent_field_rejected(self):
        with self.assertRaises(TargetResolutionError):
            self.analyze("FIELD_DELETE", current_field_path="not_a_field")

    def test_25_ambiguous_field_rejected(self):
        duplicate_schema = replace(
            self.snapshot.source_schema,
            fields=self.snapshot.source_schema.fields + (self.snapshot.source_schema.fields[5],),
        )
        ambiguous = replace(self.snapshot, source_schema=duplicate_schema)
        with self.assertRaises(TargetResolutionError):
            analyze_structural_change(self.proposal("FIELD_DELETE"), ambiguous, self.work / "ambiguous")

    def test_26_rename_to_same_name_rejected(self):
        with self.assertRaises(ProposalValidationError):
            self.analyze("FIELD_RENAME", proposed_field_path="order_total")

    def test_27_rename_collision_rejected(self):
        with self.assertRaises(ProposalValidationError):
            self.analyze("FIELD_RENAME", proposed_field_path="order_date")

    def test_28_delete_replacement_rejected(self):
        proposal = self.proposal("FIELD_DELETE")
        proposal["proposed_field_path"] = "replacement"
        with self.assertRaises(ProposalValidationError):
            analyze_structural_change(proposal, self.snapshot, self.work / "delete-replacement")

    def test_29_same_effective_type_rejected(self):
        with self.assertRaises(ProposalValidationError):
            self.analyze("FIELD_TYPE_CHANGE", proposed_native_type="DOUBLE PRECISION", proposed_normalized_type="NUMBER")

    def test_30_unsupported_type_family_rejected(self):
        with self.assertRaises(ProposalValidationError):
            self.analyze("FIELD_TYPE_CHANGE", proposed_normalized_type="MAGIC")

    def test_31_malformed_and_invalid_discriminator_rejected(self):
        for proposal in ({}, {**self.proposal("FIELD_DELETE"), "operation": "FIELD_MOVE"}):
            with self.assertRaises(ProposalValidationError):
                parse_proposal(proposal)

    def test_32_snapshot_fingerprint_mismatch_rejected(self):
        with self.assertRaises(ProposalValidationError):
            self.analyze("FIELD_DELETE", source_snapshot_fingerprint="sha256:" + "0" * 64)

    def test_33_output_overwrite_requires_permission(self):
        self.analyze("FIELD_DELETE", "same")
        with self.assertRaises(OutputSafetyError):
            self.analyze("FIELD_DELETE", "same")

    def test_34_tampered_predecessor_artifact_rejected(self):
        result = self.analyze("FIELD_DELETE")
        artifacts = copy.deepcopy(result.artifacts)
        del artifacts["analysis_certification.json"]
        del artifacts["manifest.json"]
        artifacts["technical_impact_analysis.json"]["proposal_id"] = "tampered"
        with self.assertRaises(CertificationError):
            certify_artifacts(result.identity, artifacts)

    def test_35_dangling_graph_endpoint_rejected(self):
        result = self.analyze("FIELD_DELETE")
        artifacts = copy.deepcopy(result.artifacts)
        del artifacts["analysis_certification.json"]
        del artifacts["manifest.json"]
        artifacts["future_metadata_graph.json"]["relationships"][0]["upstream_key"] = "missing|field"
        with self.assertRaises(CertificationError):
            certify_artifacts(result.identity, artifacts)

    def test_36_malformed_urn_rejected(self):
        with self.assertRaises(ProposalValidationError):
            self.analyze("FIELD_DELETE", dataset_urn="not-a-urn")

    def test_37_output_outside_repository_rejected(self):
        with tempfile.TemporaryDirectory() as outside:
            with self.assertRaises(OutputSafetyError):
                analyze_structural_change(self.proposal("FIELD_DELETE"), self.snapshot, Path(outside) / "analysis")

    def test_38_no_absolute_path_or_secret_in_artifacts(self):
        result = self.analyze("FIELD_TYPE_CHANGE")
        serialized = json.dumps(result.artifacts)
        self.assertNotIn(str(ROOT), serialized)
        self.assertNotIn("token", serialized.lower())

    def test_39_golden_phase4_fingerprint_unchanged(self):
        certification = load_phase4_certification(ROOT / "artifacts" / "phase_4_certification.json")
        self.assertEqual(certification.semantic_fingerprint, GOLDEN_PHASE4_FINGERPRINT)

    def test_40_manifest_has_no_absolute_output_path(self):
        result = self.analyze("FIELD_DELETE")
        manifest = result.artifacts["manifest.json"]
        self.assertNotIn("output_dir", manifest)
        self.assertEqual(manifest["certification_status"], "certified")

    def test_41_cli_success_is_concise_json(self):
        stdout = StringIO()
        with redirect_stdout(stdout):
            status = cli_main(
                [
                    "analyze-structural-change",
                    "--snapshot",
                    str(SNAPSHOT_PATH),
                    "--proposal",
                    str(EXAMPLES / "field_delete" / "change.json"),
                    "--output",
                    str(self.work / "cli"),
                ]
            )
        response = json.loads(stdout.getvalue())
        self.assertEqual(status, 0)
        self.assertEqual(response["status"], "succeeded")

    def test_42_cli_failure_has_no_stack_trace(self):
        stderr = StringIO()
        with redirect_stderr(stderr):
            status = cli_main(
                [
                    "analyze-structural-change",
                    "--snapshot",
                    str(SNAPSHOT_PATH),
                    "--proposal",
                    str(self.work / "missing.json"),
                    "--output",
                    str(self.work / "cli-failure"),
                ]
            )
        response = json.loads(stderr.getvalue())
        self.assertEqual(status, 2)
        self.assertEqual(response["status"], "failed")
        self.assertNotIn("Traceback", stderr.getvalue())

    def test_43_explicit_overwrite_of_analysis_package_works(self):
        proposal = self.proposal("FIELD_DELETE")
        output = self.work / "overwrite"
        first = analyze_structural_change(proposal, self.snapshot, output)
        second = analyze_structural_change(
            proposal, self.snapshot, output, overwrite=True
        )
        self.assertEqual(first.semantic_fingerprint, second.semantic_fingerprint)

    def test_44_public_result_exposes_manifest_and_summary(self):
        result = self.analyze("FIELD_TYPE_CHANGE")
        self.assertEqual(result.manifest["analysis_id"], result.identity.analysis_id)
        self.assertEqual(result.key_summary, result.artifacts["impact_synthesis.json"]["summary"])


if __name__ == "__main__":
    unittest.main()
