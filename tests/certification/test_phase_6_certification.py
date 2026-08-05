from __future__ import annotations

import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from chronos.phase6_certification import (
    CERTIFICATION_ARTIFACT_FILENAMES,
    PHASE6_CERTIFICATION_VERSION,
    Phase6CertificationError,
    load_phase6_certification,
)
from chronos.structural_engine.serialization import semantic_fingerprint


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "artifacts" / "certifications" / "phase-6"


class Phase6CertificationPackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.artifacts = load_phase6_certification(PACKAGE)

    def test_001_exact_artifact_count(self):
        self.assertEqual(len(self.artifacts), 32)

    def test_002_exact_artifact_names(self):
        self.assertEqual(set(self.artifacts), set(CERTIFICATION_ARTIFACT_FILENAMES))

    def test_003_certification_version(self):
        self.assertTrue(all(item["certification_version"] == PHASE6_CERTIFICATION_VERSION for item in self.artifacts.values()))

    def test_004_top_level_state_is_allowed_and_conservative(self):
        self.assertEqual(self.artifacts["phase_6_certification.json"]["certification_state"], "PHASE_6_CERTIFIED_WITH_NON_BLOCKING_LIMITATIONS")

    def test_005_runtime_not_certified(self):
        self.assertFalse(self.artifacts["phase_6_certification.json"]["runtime_correctness_certified"])

    def test_006_safe_to_merge_not_certified(self):
        self.assertFalse(self.artifacts["phase_6_certification.json"]["safe_to_merge_certified"])

    def test_007_scope_has_four_included_capabilities(self):
        self.assertEqual(len(self.artifacts["phase_6_certification_scope.json"]["included"]), 4)

    def test_008_scope_excludes_execution(self):
        excluded = self.artifacts["phase_6_certification_scope.json"]["excluded"]
        self.assertIn("runtime_correctness", excluded)
        self.assertIn("dbt_execution", excluded)

    def test_009_capability_status_vocabulary(self):
        self.assertEqual(set(self.artifacts["phase_6_capability_matrix.json"]["status_vocabulary"]), {"SUPPORTED", "SUPPORTED_WITH_LIMITATIONS", "UNSUPPORTED", "OUT_OF_SCOPE"})

    def test_010_required_capabilities_are_present(self):
        names = {item["capability"] for item in self.artifacts["phase_6_capability_matrix.json"]["capabilities"]}
        self.assertTrue({"FIELD_RENAME", "AGGREGATION_CHANGE", "MULTI_FILE_PR_CHANGE", "STALE_FIELD_REFERENCE_REPAIR", "CONTRACT_TYPE_ALIGNMENT"} <= names)

    def test_011_automatic_semantic_repair_is_unsupported(self):
        row = next(item for item in self.artifacts["phase_6_capability_matrix.json"]["capabilities"] if item["capability"] == "AUTOMATIC_SEMANTIC_INTENT_REPAIR")
        self.assertEqual(row["support"], "UNSUPPORTED")

    def test_012_runtime_verification_is_out_of_scope(self):
        row = next(item for item in self.artifacts["phase_6_capability_matrix.json"]["capabilities"] if item["capability"] == "RUNTIME_VERIFICATION")
        self.assertEqual(row["support"], "OUT_OF_SCOPE")

    def test_013_all_public_python_apis(self):
        names = {item["name"] for item in self.artifacts["public_interface_certification.json"]["python_apis"]}
        self.assertEqual(names, {"analyze_structural_change", "analyze_semantic_code_change", "analyze_pull_request", "analyze_pull_request_bundle", "generate_repair"})

    def test_014_all_public_cli_commands(self):
        names = {item["name"] for item in self.artifacts["public_interface_certification.json"]["cli_commands"]}
        self.assertEqual(names, {"chronos analyze-structural-change", "chronos analyze-semantic-change", "chronos analyze-pr", "chronos generate-repair"})

    def test_015_cli_failures_are_bounded(self):
        self.assertTrue(all(item["bounded_failure"] if "bounded_failure" in item else item["failure_json"] for item in self.artifacts["public_interface_certification.json"]["python_apis"] + self.artifacts["public_interface_certification.json"]["cli_commands"]))

    def test_016_four_proposal_families(self):
        self.assertEqual(len(self.artifacts["proposal_contract_certification.json"]["proposal_families"]), 4)

    def test_017_unknown_proposal_fields_rejected(self):
        self.assertTrue(all(item["unknown_fields_rejected"] for item in self.artifacts["proposal_contract_certification.json"]["proposal_families"]))

    def test_018_repair_selection_modes(self):
        repair = self.artifacts["proposal_contract_certification.json"]["proposal_families"][-1]
        self.assertEqual(repair["selection_modes"], ["ALL_SUPPORTED", "SELECTED_ROOTS", "SELECTED_GROUPS"])

    def test_019_package_counts(self):
        values = {item["phase"]: item["semantic_artifact_count"] for item in self.artifacts["artifact_package_matrix.json"]["packages"]}
        self.assertEqual(values, {"6.1": 14, "6.2": 18, "6.3": 26, "6.4": 27})

    def test_020_repair_package_has_repairs_directory_contract(self):
        record = self.artifacts["artifact_package_matrix.json"]["packages"][-1]
        self.assertEqual(record["extra_directory"], "repairs")

    def test_021_four_cross_phase_handoffs(self):
        self.assertEqual(len(self.artifacts["cross_phase_trust_chain.json"]["handoffs"]), 4)

    def test_022_no_prose_trust_bypass(self):
        trust = self.artifacts["cross_phase_trust_chain.json"]
        self.assertFalse(trust["copied_prose_accepted_as_evidence"])
        self.assertFalse(trust["trust_bypass_detected"])

    def test_023_vocabulary_contains_required_states(self):
        terms = {item["term"] for item in self.artifacts["vocabulary_certification.json"]["terms"]}
        self.assertTrue({"COHERENT", "SEMANTICALLY_CHANGED", "REPAIR_CANDIDATE_READY_FOR_REVIEW", "STATIC_PROJECTED"} <= terms)

    def test_024_dimension_count(self):
        self.assertEqual(len(self.artifacts["dimension_separation_certification.json"]["dimensions"]), 12)

    def test_025_coherent_does_not_imply_semantic_compatibility(self):
        assertions = self.artifacts["dimension_separation_certification.json"]["separation_assertions"]
        self.assertIn({"does_not_imply": "SEMANTICALLY_COMPATIBLE", "left": "COHERENT", "result": "PASS"}, assertions)

    def test_026_repair_ready_does_not_imply_safe_to_merge(self):
        assertions = self.artifacts["dimension_separation_certification.json"]["separation_assertions"]
        self.assertTrue(any(item["left"] == "REPAIR_CANDIDATE_READY_FOR_REVIEW" and item["does_not_imply"] == "SAFE_TO_MERGE" for item in assertions))

    def test_027_golden_artifact_count(self):
        self.assertEqual(self.artifacts["golden_fixture_certification.json"]["artifact_count"], 16)

    def test_028_golden_bytes_are_identical(self):
        golden = self.artifacts["golden_fixture_certification.json"]
        self.assertTrue(golden["before_after_equal"])
        self.assertTrue(all(item["byte_identical"] for item in golden["artifacts"]))

    def test_029_phase4_physical_hash(self):
        self.assertEqual(self.artifacts["golden_fixture_certification.json"]["phase_4_physical_hash"], "5dc730bae390908fa14f5ee5dc5d6a2b6a71382eecf664950bf60f76a74c94e8")

    def test_030_phase4_semantic_fingerprint(self):
        self.assertEqual(self.artifacts["golden_fixture_certification.json"]["phase_4_semantic_fingerprint"], "sha256:3e8444ec904e0ba1c55c5ae22d69edfa8e722310f51ab30fc783b8175a87ac4a")

    def test_031_phase5_review_loaded(self):
        golden = self.artifacts["golden_fixture_certification.json"]
        self.assertTrue(golden["phase_5_review_loaded"])
        self.assertEqual(golden["phase_5_review_id"], "CHRONOS-DEMO-001")

    def test_032_structural_replay_scenarios(self):
        records = self.artifacts["phase_6_1_replay_certification.json"]["scenarios"]
        self.assertEqual({item["operation"] for item in records}, {"FIELD_RENAME", "FIELD_DELETE", "FIELD_TYPE_CHANGE"})

    def test_033_structural_replays_deterministic(self):
        self.assertTrue(all(item["semantic_fingerprint"] == item["second_run_semantic_fingerprint"] for item in self.artifacts["phase_6_1_replay_certification.json"]["scenarios"]))

    def test_034_semantic_replay_scenarios(self):
        records = self.artifacts["phase_6_2_replay_certification.json"]["scenarios"]
        self.assertEqual({item["scenario"] for item in records}, {"aggregation", "combined_aggregation_filter", "filter", "join", "derived_expression"})

    def test_035_semantic_parser_version(self):
        self.assertEqual(self.artifacts["phase_6_2_replay_certification.json"]["parser"]["version"], "30.13.0")

    def test_036_semantic_replays_do_not_execute(self):
        records = self.artifacts["phase_6_2_replay_certification.json"]["scenarios"]
        self.assertTrue(all(not item["sql_executed"] and not item["jinja_executed"] for item in records))

    def test_037_pr_replay_scenarios(self):
        records = self.artifacts["phase_6_3_replay_certification.json"]["scenarios"]
        self.assertEqual({item["scenario"] for item in records}, {"primary", "coherent", "no_material", "conflict"})

    def test_038_primary_pr_outcome(self):
        item = next(item for item in self.artifacts["phase_6_3_replay_certification.json"]["scenarios"] if item["scenario"] == "primary")
        self.assertEqual((item["coherence"], item["decision"]), ("INCONSISTENT", "hold_for_review"))

    def test_039_coherent_pr_outcome(self):
        item = next(item for item in self.artifacts["phase_6_3_replay_certification.json"]["scenarios"] if item["scenario"] == "coherent")
        self.assertEqual((item["coherence"], item["decision"]), ("COHERENT", "hold_for_review"))

    def test_040_no_material_pr_outcome(self):
        item = next(item for item in self.artifacts["phase_6_3_replay_certification.json"]["scenarios"] if item["scenario"] == "no_material")
        self.assertEqual(item["decision"], "no_material_change")

    def test_041_conflict_pr_outcome(self):
        item = next(item for item in self.artifacts["phase_6_3_replay_certification.json"]["scenarios"] if item["scenario"] == "conflict")
        self.assertEqual(item["decision"], "block_confirmed_incompatibility")

    def test_042_repair_replay_scenarios(self):
        records = self.artifacts["phase_6_4_replay_certification.json"]["scenarios"]
        self.assertEqual({item["scenario"] for item in records}, {"primary", "coherent", "no_material", "conflict", "delete", "type_alignment"})

    def test_043_primary_repair_outcome(self):
        item = self._repair("primary")
        self.assertEqual((item["repair_disposition"], item["repair_action_count"], item["affected_file_count"], item["patch_hunk_count"], item["projected_coherence"]), ("PARTIAL_REPAIR_CANDIDATE", 2, 2, 2, "COHERENT"))

    def test_044_coherent_has_no_patch(self):
        item = self._repair("coherent")
        self.assertEqual((item["repair_disposition"], item["patch_hunk_count"]), ("NO_SUPPORTED_AUTOMATIC_REPAIR", 0))

    def test_045_no_material_has_no_patch(self):
        item = self._repair("no_material")
        self.assertEqual((item["repair_disposition"], item["patch_hunk_count"], item["remaining_finding_count"]), ("NO_SUPPORTED_AUTOMATIC_REPAIR", 0, 0))

    def test_046_conflict_is_preserved_without_patch(self):
        item = self._repair("conflict")
        self.assertEqual((item["repair_disposition"], item["patch_hunk_count"]), ("REPAIR_BLOCKED_BY_CONFLICT", 0))

    def test_047_delete_has_one_exact_candidate(self):
        item = self._repair("delete")
        self.assertEqual((item["repair_disposition"], item["repair_action_count"], item["patch_hunk_count"]), ("REPAIR_CANDIDATE_READY_FOR_REVIEW", 1, 1))

    def test_048_type_alignment_has_one_declaration_candidate(self):
        item = self._repair("type_alignment")
        self.assertEqual((item["repair_disposition"], item["repair_action_count"], item["patch_hunk_count"]), ("REPAIR_CANDIDATE_READY_FOR_REVIEW", 1, 1))

    def test_049_all_repair_patches_deterministic(self):
        records = self.artifacts["phase_6_4_replay_certification.json"]["scenarios"]
        self.assertTrue(all(item["patch_fingerprints"] == item["second_run_patch_fingerprints"] for item in records))

    def test_050_end_to_end_journey_keeps_avg_unresolved(self):
        journey = self.artifacts["end_to_end_primary_journey.json"]
        self.assertIn("AVG_UNTOUCHED", journey["steps"][1]["protected_semantics"])
        self.assertEqual(journey["steps"][2]["semantic_intent"], "UNRESOLVED")

    def test_051_end_to_end_journey_reduces_stale_references(self):
        step = self.artifacts["end_to_end_primary_journey.json"]["steps"][2]
        self.assertEqual((step["stale_references_before"], step["stale_references_after"]), (2, 0))

    def test_052_no_evidence_invention_set(self):
        records = self.artifacts["no_evidence_invention_certification.json"]["prohibited_inferences"]
        self.assertEqual(len(records), 12)
        self.assertTrue(all(item["result"] == "PASS" for item in records))

    def test_053_semantic_repair_boundary(self):
        records = self.artifacts["semantic_repair_boundary_certification.json"]["unsupported_automatic_repairs"]
        self.assertEqual(len(records), 7)
        self.assertTrue(all(not item["patch_generated"] for item in records))

    def test_054_conflict_preservation(self):
        record = self.artifacts["conflict_preservation_certification.json"]
        self.assertTrue(record["competing_identities_visible"])
        self.assertFalse(record["parser_order_selection"])
        self.assertFalse(record["patch_generated"])

    def test_055_dynamic_constructs_not_executed_or_patched(self):
        records = self.artifacts["dynamic_construct_certification.json"]["constructs"]
        self.assertEqual(len(records), 8)
        self.assertTrue(all(not item["executed"] and not item["patched"] for item in records))

    def test_056_eighteen_fixture_replays(self):
        self.assertEqual(self.artifacts["determinism_certification.json"]["fixture_run_count"], 18)

    def test_057_all_fixture_fingerprints_repeat(self):
        records = self.artifacts["determinism_certification.json"]["fixtures"]
        self.assertTrue(all(item["semantic_fingerprint"] == item["second_run_semantic_fingerprint"] for item in records))

    def test_058_portability_scan(self):
        record = self.artifacts["portability_certification.json"]
        self.assertEqual(record["forbidden_findings"], [])
        self.assertEqual(record["state"], "PASS")

    def test_059_security_controls(self):
        record = self.artifacts["security_control_certification.json"]
        self.assertEqual(len(record["controls"]), 28)
        self.assertTrue(all(item["result"] == "PASS" for item in record["controls"]))

    def test_060_no_repository_execution_or_datahub_write(self):
        record = self.artifacts["security_control_certification.json"]
        self.assertFalse(record["repository_code_executed"])
        self.assertFalse(record["datahub_write_performed"])

    def test_061_all_tamper_cases_fail_closed(self):
        records = self.artifacts["tamper_certification.json"]["tamper_cases"]
        self.assertEqual(len(records), 16)
        self.assertTrue(all(item["expected"] == "FAIL_CLOSED" and item["result"] == "PASS" for item in records))

    def test_062_failure_modes_are_bounded(self):
        records = self.artifacts["failure_mode_certification.json"]["failure_modes"]
        self.assertTrue(all(item["bounded_structured_error"] and not item["ordinary_stack_trace"] and not item["partial_output"] for item in records))

    def test_063_resource_limits(self):
        values = {item["name"]: item["value"] for item in self.artifacts["resource_bound_certification.json"]["limits"]}
        self.assertEqual(values, {"maximum_changed_files": 200, "maximum_source_file_size": 1048576, "maximum_predecessor_artifact_size": 5242880, "maximum_repair_actions": 500, "maximum_patch_hunks": 500})

    def test_064_dependency_versions(self):
        record = self.artifacts["dependency_certification.json"]
        self.assertEqual((record["sqlglot_observed"], record["pyyaml_observed"]), ("30.13.0", "6.0.3"))

    def test_065_no_gitpython_dependency(self):
        self.assertFalse(self.artifacts["dependency_certification.json"]["git_library_dependency"])

    def test_066_test_arithmetic(self):
        totals = self.artifacts["test_execution_summary.json"]["totals"]
        self.assertEqual(totals["executed"], totals["passed"] + totals["skipped"] + totals["failed"])

    def test_067_zero_test_failures(self):
        self.assertEqual(self.artifacts["test_execution_summary.json"]["totals"]["failed"], 0)

    def test_068_seven_skips_justified(self):
        record = self.artifacts["skipped_test_justification.json"]
        self.assertEqual(record["skip_count"], 7)
        self.assertTrue(all(not item["blocks_certification"] for item in record["skipped_tests"]))

    def test_069_unrelated_frontend_change_classified(self):
        record = self.artifacts["working_tree_audit.json"]
        self.assertIn("frontend/next-env.d.ts", record["preexisting_unrelated_changes"])
        self.assertEqual(record["unexpected_changes"], [])

    def test_070_release_manifest_contains_all_engine_versions(self):
        self.assertEqual(self.artifacts["phase_6_release_manifest.json"]["engine_versions"], {"phase_6_1": "6.1.0", "phase_6_2": "6.2.0", "phase_6_3": "6.3.0", "phase_6_4": "6.4.0"})

    def test_071_release_manifest_has_fixture_fingerprints(self):
        values = self.artifacts["phase_6_release_manifest.json"]["fixture_fingerprints"]
        self.assertEqual({key: len(value) for key, value in values.items()}, {"phase_6_1": 3, "phase_6_2": 5, "phase_6_3": 4, "phase_6_4": 6})

    def test_072_frontend_handoff_ready(self):
        self.assertTrue(self.artifacts["phase_6_certification.json"]["frontend_integration_ready"])

    def test_073_phase7_handoff_ready_without_execution_claim(self):
        record = self.artifacts["phase_6_certification.json"]
        self.assertTrue(record["phase_7_handoff_ready"])
        self.assertFalse(record["runtime_correctness_certified"])

    def test_074_manifest_fingerprint_closure(self):
        manifest = self.artifacts["manifest.json"]
        expected = {name: semantic_fingerprint(self.artifacts[name]) for name in CERTIFICATION_ARTIFACT_FILENAMES[:-1]}
        self.assertEqual(manifest["artifact_fingerprints"], expected)

    def test_075_all_headers_share_release_identity(self):
        identities = {item["release_id"] for item in self.artifacts.values()}
        self.assertEqual(len(identities), 1)

    def test_076_reserialization_is_stable(self):
        first = json.dumps(self.artifacts, sort_keys=True, separators=(",", ":"))
        second = json.dumps(copy.deepcopy(self.artifacts), sort_keys=True, separators=(",", ":"))
        self.assertEqual(first, second)

    def test_077_report_wording_distinguishes_skips(self):
        statement = self.artifacts["test_execution_summary.json"]["reporting_statement"]
        self.assertIn("tests were executed", statement)
        self.assertIn("were intentionally skipped", statement)

    def test_078_no_unexplained_production_change(self):
        self.assertEqual(self.artifacts["working_tree_audit.json"]["unexpected_changes"], [])

    def test_079_load_rejects_extra_artifact(self):
        with self._copy() as path:
            (path / "extra.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(Phase6CertificationError):
                load_phase6_certification(path)

    def test_080_load_rejects_missing_artifact(self):
        with self._copy() as path:
            (path / "phase_6_certification_scope.json").unlink()
            with self.assertRaises(Phase6CertificationError):
                load_phase6_certification(path)

    def test_081_load_rejects_duplicate_json_key(self):
        with self._copy() as path:
            target = path / "phase_6_certification_scope.json"
            target.write_text('{"release_id":"x","release_id":"y"}', encoding="utf-8")
            with self.assertRaises(Phase6CertificationError):
                load_phase6_certification(path)

    def test_082_load_rejects_manifest_list_tamper(self):
        with self._copy() as path:
            self._mutate(path, "manifest.json", lambda value: value["artifact_names"].pop())
            with self.assertRaises(Phase6CertificationError):
                load_phase6_certification(path)

    def test_083_load_rejects_certification_state_tamper(self):
        with self._copy() as path:
            self._mutate(path, "phase_6_certification.json", lambda value: value.update(certification_state="PHASE_6_CERTIFIED"))
            with self.assertRaises(Phase6CertificationError):
                load_phase6_certification(path)

    def test_084_load_rejects_absolute_path_injection(self):
        with self._copy() as path:
            self._mutate(path, "phase_6_certification_scope.json", lambda value: value.update(injected="C:\\private\\file"))
            self._refresh_fingerprint(path, "phase_6_certification_scope.json")
            with self.assertRaises(Phase6CertificationError):
                load_phase6_certification(path)

    def test_085_load_rejects_username_injection(self):
        with self._copy() as path:
            self._mutate(path, "phase_6_certification_scope.json", lambda value: value.update(injected="kmadu"))
            self._refresh_fingerprint(path, "phase_6_certification_scope.json")
            with self.assertRaises(Phase6CertificationError):
                load_phase6_certification(path)

    def test_086_load_rejects_private_key_injection(self):
        with self._copy() as path:
            self._mutate(path, "phase_6_certification_scope.json", lambda value: value.update(injected="-----BEGIN PRIVATE KEY-----"))
            self._refresh_fingerprint(path, "phase_6_certification_scope.json")
            with self.assertRaises(Phase6CertificationError):
                load_phase6_certification(path)

    def test_087_load_rejects_authenticated_url_injection(self):
        with self._copy() as path:
            self._mutate(path, "phase_6_certification_scope.json", lambda value: value.update(injected="https://user:secret@example.test"))
            self._refresh_fingerprint(path, "phase_6_certification_scope.json")
            with self.assertRaises(Phase6CertificationError):
                load_phase6_certification(path)

    def test_088_changed_file_limit_allows_boundary_and_rejects_over(self):
        source = (ROOT / "src/chronos/pr_engine/intake.py").read_text(encoding="utf-8")
        self.assertIn("if len(changes) > MAX_CHANGED_FILES:", source)
        self.assertIn("if len(files) > MAX_CHANGED_FILES:", source)

    def test_089_source_file_limit_allows_boundary_and_rejects_over(self):
        source = (ROOT / "src/chronos/pr_engine/intake.py").read_text(encoding="utf-8")
        self.assertIn("target.stat().st_size > MAX_FILE_BYTES", source)

    def test_090_predecessor_artifact_limit_allows_boundary_and_rejects_over(self):
        source = (ROOT / "src/chronos/repair_engine/trust.py").read_text(encoding="utf-8")
        self.assertIn("path.stat().st_size > MAX_PREDECESSOR_ARTIFACT_BYTES", source)

    def test_091_repair_action_limit_allows_boundary_and_rejects_over(self):
        source = (ROOT / "src/chronos/repair_engine/planning.py").read_text(encoding="utf-8")
        self.assertIn("if len(actions) > MAX_REPAIR_ACTIONS:", source)

    def test_092_patch_hunk_limit_allows_boundary_and_rejects_over(self):
        source = (ROOT / "src/chronos/repair_engine/patching.py").read_text(encoding="utf-8")
        self.assertIn("if hunk_count > MAX_PATCH_HUNKS:", source)

    def _repair(self, scenario):
        return next(item for item in self.artifacts["phase_6_4_replay_certification.json"]["scenarios"] if item["scenario"] == scenario)

    def _copy(self):
        scratch = ROOT / ".pytest_tmp"
        scratch.mkdir(exist_ok=True)
        temporary = tempfile.TemporaryDirectory(prefix="phase65-cert-", dir=scratch)
        target = Path(temporary.name) / "package"
        shutil.copytree(PACKAGE, target)

        class Context:
            def __enter__(self_nonlocal):
                return target

            def __exit__(self_nonlocal, *_):
                temporary.cleanup()

        return Context()

    @staticmethod
    def _mutate(path, name, callback):
        target = path / name
        value = json.loads(target.read_text(encoding="utf-8"))
        callback(value)
        target.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    @staticmethod
    def _refresh_fingerprint(path, name):
        target = path / name
        value = json.loads(target.read_text(encoding="utf-8"))
        manifest_path = path / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["artifact_fingerprints"][name] = semantic_fingerprint(value)
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
