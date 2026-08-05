from __future__ import annotations

import copy
import hashlib
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from chronos import generate_repair
from chronos.cli import main as cli_main
from chronos.pr_engine import analyze_pull_request
from chronos.repair_engine import (
    EditOperation,
    PredecessorTrustError,
    REPAIR_ARTIFACT_FILENAMES,
    RepairDisposition,
    RepairEditError,
    RepairMode,
    RepairOutputError,
    RepairProposalError,
    RepairRuleRegistry,
    RepairSelectionError,
    RepairabilityState,
    parse_repair_proposal,
)
from chronos.repair_engine.editors import EditorRegistry
from chronos.repair_engine.models import RepairAction
from chronos.repair_engine.planning import _classify_stale
from chronos.repair_engine.trust import load_trusted_predecessor
from chronos.snapshot import load_snapshot
from chronos.structural_engine.serialization import semantic_fingerprint


ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / "artifacts" / "current_metadata_snapshot.json"
EXAMPLES = ROOT / "examples"


class RepairEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = load_snapshot(SNAPSHOT)
        cls.scratch = ROOT / ".pytest_tmp"
        cls.scratch.mkdir(exist_ok=True)
        cls.class_temp = tempfile.TemporaryDirectory(prefix="phase64-suite-", dir=cls.scratch)
        cls.work = Path(cls.class_temp.name)
        cls.scenarios = {
            "primary": ("multifile_pr_primary", "repair_primary"),
            "coherent": ("multifile_pr_coherent", "repair_coherent"),
            "no_material": ("multifile_pr_no_material", "repair_no_material"),
            "conflict": ("multifile_pr_conflict", "repair_conflict"),
            "delete": ("multifile_pr_delete_repair", "repair_delete"),
            "type": ("multifile_pr_type_alignment", "repair_type_alignment"),
        }
        cls.predecessors = {}
        cls.results = {}
        cls.fixture_hashes_before = cls._fixture_hashes()
        for name, (bundle_name, repair_name) in cls.scenarios.items():
            bundle = EXAMPLES / bundle_name
            predecessor_dir = cls.work / f"predecessor-{name}"
            cls.predecessors[name] = analyze_pull_request(
                cls.snapshot,
                bundle / "proposal.json",
                predecessor_dir,
                bundle=bundle,
            )
            cls.results[name] = generate_repair(
                predecessor_dir,
                EXAMPLES / repair_name / "repair_proposal.json",
                bundle,
                cls.work / f"repair-{name}",
                snapshot=cls.snapshot,
            )

    @classmethod
    def tearDownClass(cls):
        cls.class_temp.cleanup()

    @classmethod
    def _fixture_hashes(cls):
        values = {}
        for bundle_name, _ in cls.scenarios.values():
            for path in sorted((EXAMPLES / bundle_name).rglob("*")):
                if path.is_file():
                    values[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        return values

    def setUp(self):
        self.case_temp = tempfile.TemporaryDirectory(prefix="case-", dir=self.work)
        self.case = Path(self.case_temp.name)

    def tearDown(self):
        self.case_temp.cleanup()

    def proposal(self, name="primary"):
        repair_name = self.scenarios[name][1]
        return json.loads((EXAMPLES / repair_name / "repair_proposal.json").read_text(encoding="utf-8"))

    def generate(self, name="primary", *, proposal=None, output=None, overwrite=False, bundle=None, predecessor=None):
        bundle_name, repair_name = self.scenarios[name]
        return generate_repair(
            predecessor or self.predecessors[name].output_dir,
            proposal or EXAMPLES / repair_name / "repair_proposal.json",
            bundle or EXAMPLES / bundle_name,
            output or self.case / f"repair-{name}",
            snapshot=self.snapshot,
            overwrite=overwrite,
        )

    def action(self, *, operation, editor, path, current, future, location=None, kind="field", task_id=None, sql_kind=None):
        evidence = {"value": current, "kind": kind, "editor_name": editor}
        if task_id:
            evidence["task_id"] = task_id
        if sql_kind:
            evidence["sql_target_kind"] = sql_kind
        return RepairAction(
            repair_action_id="repair-action-test",
            repair_rule_id="repair.test.v1",
            root_cause_id="root-test",
            logical_change_group_id="group-test",
            target_file_change_id="file-test",
            target_path=path,
            file_category="TEST",
            current_evidence=evidence,
            intended_future_evidence={"value": future},
            edit_operation=operation,
            expected_changed_identities=tuple(str(item) for item in (current, future) if item is not None),
            dependency_actions=(),
            confidence="CERTIFIED_STATIC_EXACT",
            preconditions=("exact_target",),
            static_validation_requirements=("parse",),
            remaining_evidence_requirements=("phase_7",),
            human_explanation="test",
            target_location=location,
        )

    # Positive contract and primary-scenario tests.

    def test_001_strict_repair_proposal(self):
        value = parse_repair_proposal(self.proposal())
        self.assertEqual(value.repair_mode, RepairMode.ALL_SUPPORTED)

    def test_002_proposal_model_is_frozen(self):
        value = parse_repair_proposal(self.proposal())
        with self.assertRaises(Exception):
            value.proposal_id = "changed"

    def test_003_predecessor_loads_and_recertifies(self):
        value = parse_repair_proposal(self.proposal())
        trusted = load_trusted_predecessor(
            self.predecessors["primary"].output_dir,
            EXAMPLES / "multifile_pr_primary",
            value,
            self.snapshot,
        )
        self.assertEqual(len(trusted.trust_checks), 9)

    def test_004_primary_is_certified_candidate(self):
        result = self.results["primary"]
        self.assertEqual(result.certification_status, "certified")
        self.assertEqual(result.repair_disposition, RepairDisposition.PARTIAL_REPAIR_CANDIDATE)

    def test_005_stale_field_roots_auto_repairable(self):
        classes = self.results["primary"].artifacts["repairability_classification.json"]["classifications"]
        stale = [item for item in classes if item["root_type"] == "STALE_PIPELINE_OR_QUALITY_REFERENCE"]
        self.assertEqual({item["repairability"] for item in stale}, {"AUTO_REPAIRABLE"})

    def test_006_stale_dataset_rule_auto_eligible(self):
        trusted = load_trusted_predecessor(
            self.predecessors["primary"].output_dir,
            EXAMPLES / "multifile_pr_primary",
            parse_repair_proposal(self.proposal()), self.snapshot,
        )
        root = {
            "root_cause_id": "dataset-root", "root_type": "STALE_PIPELINE_OR_QUALITY_REFERENCE",
            "contributing_file_ids": ["dataset-file"], "delta_ids": [],
            "resolved_entities": ["old_model", "new_model"], "logical_change_id": None,
        }
        group = {
            "logical_change_id": "dataset-group", "current_field": "old_model",
            "future_fields": ["new_model"], "contributing_file_ids": ["dataset-file"],
            "counterfactual_entities": ["new_model"], "resolved_current_entities": ["old_model"],
            "evidence_references": ["rename-evidence"],
        }
        inventory = {"dataset-file": {
            "file_change_id": "dataset-file", "category": "PIPELINE_CONFIG",
            "head_path": "pipelines/config.yml", "base_path": "pipelines/config.yml",
            "head_content_fingerprint": "sha256:" + "1" * 64,
        }}
        results = {"dataset-file": {
            "parser": {"name": "bounded", "version": "1"},
            "parsed_head": {"references": [{"kind": "model", "value": "old_model", "location": "pipeline.model"}]},
        }}
        classification, actions = _classify_stale(
            trusted, RepairRuleRegistry(), root, group, inventory, results
        )
        self.assertEqual(classification.repairability, RepairabilityState.AUTO_REPAIRABLE)
        self.assertEqual(actions[0].repair_rule_id, "repair.stale-dataset.static-reference.v1")

    def test_007_primary_generates_two_actions(self):
        self.assertEqual(len(self.results["primary"].repair_actions), 2)

    def test_008_primary_action_dependencies_are_deterministic(self):
        plan = self.results["primary"].artifacts["repair_plan.json"]["plan"]
        self.assertEqual(len(plan["application_order"]), 2)
        self.assertEqual(len(plan["edit_dependencies"]), 1)

    def test_009_primary_dag_static_argument_alignment(self):
        candidate = self.results["primary"].output_dir / "repairs/repaired_files/dags/orders_pipeline.py"
        self.assertIn('output_field="order_amount"', candidate.read_text(encoding="utf-8"))

    def test_010_primary_quality_reference_alignment(self):
        candidate = self.results["primary"].output_dir / "repairs/repaired_files/quality/order_checks.yml"
        self.assertIn("field: order_amount", candidate.read_text(encoding="utf-8"))

    def test_011_primary_preserves_avg(self):
        patch = (self.results["primary"].output_dir / "repairs/patches/combined.patch").read_text(encoding="utf-8")
        self.assertNotIn("AVG", patch)
        self.assertEqual(
            (EXAMPLES / "multifile_pr_primary/head/models/order_details.sql").read_text(encoding="utf-8"),
            "SELECT AVG(o.order_total) AS order_amount\nFROM order_entry_db.order_entry.orders AS o\n",
        )

    def test_012_primary_unified_diff_has_two_hunks(self):
        manifest = self.results["primary"].artifact_manifest
        self.assertEqual(manifest["patch_hunk_count"], 2)

    def test_013_primary_candidate_previews_exist(self):
        self.assertEqual(len(self.results["primary"].candidate_file_paths), 2)

    def test_014_patch_applies_to_certified_head_copy(self):
        records = self.results["primary"].artifacts["file_patch_records.json"]["files"]
        self.assertTrue(all(item["patch_applies_to_certified_head_copy"] for item in records))

    def test_015_primary_projected_phase63_reanalysis(self):
        projected = self.results["primary"].artifacts["projected_pr_analysis.json"]
        self.assertEqual(projected["projection_state"], "STATIC_PROJECTED")

    def test_016_primary_projected_coherence_improves(self):
        comparison = self.results["primary"].artifacts["repair_comparison.json"]
        self.assertEqual((comparison["original_coherence"], comparison["projected_coherence"]), ("INCONSISTENT", "COHERENT"))

    def test_017_primary_stale_references_close(self):
        comparison = self.results["primary"].artifacts["repair_comparison.json"]
        self.assertEqual((comparison["original_stale_reference_count"], comparison["projected_stale_reference_count"]), (2, 0))

    def test_018_semantic_root_remains(self):
        remaining = self.results["primary"].artifacts["remaining_findings.json"]["remaining_predecessor_roots"]
        self.assertIn("SEMANTIC_DEFINITION_CHANGED", {item["root_type"] for item in remaining})

    def test_019_no_new_unresolved_roots(self):
        self.assertEqual(self.results["primary"].artifacts["repair_comparison.json"]["new_unresolved_root_ids"], [])

    def test_020_no_new_conflicts(self):
        self.assertEqual(self.results["primary"].artifacts["repair_comparison.json"]["new_conflict_ids"], [])

    def test_021_protected_dag_dependencies_unchanged(self):
        protected = self.results["primary"].artifacts["protected_semantics_validation.json"]
        self.assertFalse(protected["dag_dependency_graph_changed_by_repair"])

    def test_022_protected_sql_semantics_unchanged(self):
        protected = self.results["primary"].artifacts["protected_semantics_validation.json"]
        self.assertFalse(protected["sql_aggregation_filter_join_expression_changed_by_repair"])

    def test_023_exact_27_artifact_package(self):
        top = {item.name for item in self.results["primary"].output_dir.iterdir() if item.is_file()}
        self.assertEqual(top, set(REPAIR_ARTIFACT_FILENAMES))

    def test_024_manifest_has_no_raw_patch(self):
        self.assertFalse(self.results["primary"].patch_manifest["raw_patch_in_semantic_json"])

    def test_025_python_api_returns_paths(self):
        result = self.results["primary"]
        self.assertTrue(result.patch_paths and result.candidate_file_paths)

    def test_026_cli_returns_concise_json(self):
        out, err = StringIO(), StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli_main([
                "generate-repair", "--analysis", str(self.predecessors["primary"].output_dir),
                "--proposal", str(EXAMPLES / "repair_primary/repair_proposal.json"),
                "--bundle", str(EXAMPLES / "multifile_pr_primary"),
                "--output", str(self.case / "cli-output"),
                "--snapshot", str(SNAPSHOT),
            ])
        self.assertEqual(code, 0)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["repair_action_count"], 2)
        self.assertFalse(payload["runtime_verified"])
        self.assertEqual(err.getvalue(), "")

    def test_027_cli_selected_root_mode(self):
        root_id = next(
            item["root_cause_id"] for item in self.predecessors["primary"].root_causes
            if item["root_type"] == "STALE_PIPELINE_OR_QUALITY_REFERENCE"
        )
        out, err = StringIO(), StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli_main([
                "generate-repair", "--analysis", str(self.predecessors["primary"].output_dir),
                "--proposal", str(EXAMPLES / "repair_primary/repair_proposal.json"),
                "--bundle", str(EXAMPLES / "multifile_pr_primary"),
                "--output", str(self.case / "cli-selected"), "--root", root_id,
            ])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out.getvalue())["repair_action_count"], 1)

    def test_028_sql_ast_identifier_editor(self):
        action = self.action(
            operation=EditOperation.UPDATE_SQL_IDENTIFIER,
            editor="sqlglot_ast_editor", path="models/x.sql",
            current="order_total", future="order_amount", sql_kind="column",
        )
        result = EditorRegistry().apply(
            action,
            "SELECT SUM(order_total) AS total FROM orders WHERE active = TRUE\n",
        )
        self.assertIn("SUM(order_amount)", result.candidate_content)
        self.assertIn("active = TRUE", result.candidate_content)

    def test_029_sql_output_alias_editor(self):
        action = self.action(
            operation=EditOperation.UPDATE_SQL_OUTPUT_ALIAS,
            editor="sqlglot_ast_editor", path="models/x.sql",
            current="old_total", future="new_total", sql_kind="output_alias",
        )
        result = EditorRegistry().apply(action, "SELECT SUM(amount) AS old_total FROM orders\n")
        self.assertIn("AS new_total", result.candidate_content)

    def test_030_yaml_exact_scalar_editor(self):
        action = self.action(
            operation=EditOperation.UPDATE_QUALITY_REFERENCE,
            editor="structured_config_editor", path="quality/x.yml",
            current="old", future="new", location="quality.field",
        )
        result = EditorRegistry().apply(action, "quality:\n  field: old\n  threshold: 1\n")
        self.assertEqual(result.candidate_content, "quality:\n  field: new\n  threshold: 1\n")

    def test_031_json_allowlisted_path_editor(self):
        action = self.action(
            operation=EditOperation.UPDATE_PIPELINE_CONFIG_REFERENCE,
            editor="structured_config_editor", path="pipelines/x.json",
            current="old", future="new", location="pipeline.output_field",
        )
        result = EditorRegistry().apply(action, '{"pipeline":{"output_field":"old","keep":1}}')
        self.assertEqual(json.loads(result.candidate_content)["pipeline"]["output_field"], "new")

    def test_032_python_ast_static_editor(self):
        action = self.action(
            operation=EditOperation.UPDATE_DAG_STATIC_ARGUMENT,
            editor="python_dag_static_editor", path="dags/x.py",
            current="old", future="new", kind="output_field", task_id="publish",
        )
        result = EditorRegistry().apply(
            action, 'task = Operator(task_id="publish", output_field="old")\n'
        )
        self.assertIn('output_field="new"', result.candidate_content)

    def test_033_bounded_dbt_static_ref_editor(self):
        action = self.action(
            operation=EditOperation.UPDATE_MODEL_FILE_REFERENCE,
            editor="static_reference_editor", path="models/x.sql",
            current="old_model", future="new_model", kind="model_file",
        )
        result = EditorRegistry().apply(action, "SELECT * FROM {{ ref('old_model') }}\n")
        self.assertIn("ref('new_model')", result.candidate_content)

    def test_034_delete_example_one_exact_removal(self):
        result = self.results["delete"]
        self.assertEqual(len(result.repair_actions), 1)
        patch = (result.output_dir / "repairs/patches/combined.patch").read_text(encoding="utf-8")
        self.assertIn("-    - order_total", patch)
        self.assertIn("     - order_status", patch)

    def test_035_type_example_declaration_only(self):
        result = self.results["type"]
        patch = (result.output_dir / "repairs/patches/combined.patch").read_text(encoding="utf-8")
        self.assertIn("-  type: integer", patch)
        self.assertIn("+  type: numeric", patch)
        self.assertNotIn("CAST", patch.upper())

    def test_036_conditional_classifications_expose_preconditions(self):
        for name in ("delete", "type"):
            item = self.results[name].artifacts["repairability_classification.json"]["classifications"][0]
            self.assertEqual(item["repairability"], "CONDITIONALLY_REPAIRABLE")
            self.assertTrue(item["required_preconditions"])

    # Fail-closed and negative tests.

    def test_037_unknown_proposal_property_rejected(self):
        value = self.proposal()
        value["command"] = "run anything"
        with self.assertRaises(RepairProposalError):
            parse_repair_proposal(value)

    def test_038_invalid_operation_rejected(self):
        value = self.proposal()
        value["operation"] = "APPLY_REPAIR"
        with self.assertRaises(RepairProposalError):
            parse_repair_proposal(value)

    def test_039_selected_roots_requires_ids(self):
        value = self.proposal()
        value["repair_mode"] = "SELECTED_ROOTS"
        with self.assertRaises(RepairProposalError):
            parse_repair_proposal(value)

    def test_040_tampered_predecessor_rejected(self):
        target = self.case / "tampered"
        shutil.copytree(self.predecessors["primary"].output_dir, target)
        path = target / "technical_impact_analysis.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["root_causes"][0]["scope"] = "tampered"
        path.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaises(PredecessorTrustError):
            self.generate(predecessor=target)

    def test_041_manifest_fingerprint_mismatch_rejected(self):
        value = self.proposal()
        value["predecessor_manifest_fingerprint"] = "sha256:" + "0" * 64
        with self.assertRaises(PredecessorTrustError):
            self.generate(proposal=value)

    def test_042_repository_identity_mismatch_rejected(self):
        value = self.proposal()
        value["repository_identity"]["repository_name"] = "wrong"
        with self.assertRaises(PredecessorTrustError):
            self.generate(proposal=value)

    def test_043_base_identity_mismatch_rejected(self):
        value = self.proposal()
        value["base_revision"] = "wrong"
        with self.assertRaises(PredecessorTrustError):
            self.generate(proposal=value)

    def test_044_unknown_root_rejected(self):
        value = self.proposal()
        value["repair_mode"] = "SELECTED_ROOTS"
        value["target_root_cause_ids"] = ["unknown-root"]
        with self.assertRaises(RepairSelectionError):
            self.generate(proposal=value)

    def test_045_unknown_group_rejected(self):
        value = self.proposal()
        value["repair_mode"] = "SELECTED_GROUPS"
        value["target_logical_change_group_ids"] = ["unknown-group"]
        with self.assertRaises(RepairSelectionError):
            self.generate(proposal=value)

    def test_046_head_content_mismatch_rejected(self):
        bundle = self.case / "bundle"
        shutil.copytree(EXAMPLES / "multifile_pr_primary", bundle)
        (bundle / "head/dags/orders_pipeline.py").write_text("tampered\n", encoding="utf-8")
        with self.assertRaises(PredecessorTrustError):
            self.generate(bundle=bundle)

    def test_047_unknown_predecessor_artifact_rejected(self):
        target = self.case / "extra-artifact"
        shutil.copytree(self.predecessors["primary"].output_dir, target)
        (target / "copied-summary.txt").write_text("not trusted", encoding="utf-8")
        with self.assertRaises(PredecessorTrustError):
            self.generate(predecessor=target)

    def test_048_missing_predecessor_artifact_rejected(self):
        target = self.case / "missing-artifact"
        shutil.copytree(self.predecessors["primary"].output_dir, target)
        (target / "manifest.json").unlink()
        with self.assertRaises(PredecessorTrustError):
            self.generate(predecessor=target)

    def test_049_duplicate_json_key_rejected(self):
        target = self.case / "duplicate"
        shutil.copytree(self.predecessors["primary"].output_dir, target)
        path = target / "proposal_validation.json"
        path.write_text('{"analysis_id":"a","analysis_id":"b"}', encoding="utf-8")
        with self.assertRaises(PredecessorTrustError):
            self.generate(predecessor=target)

    def test_050_external_output_rejected(self):
        external = Path(tempfile.gettempdir()) / "chronos-phase64-external-output"
        with self.assertRaises(RepairOutputError):
            self.generate(output=external)

    def test_051_source_tree_output_rejected(self):
        with self.assertRaises(RepairOutputError):
            self.generate(output=ROOT / "src/repair-output")

    def test_052_frozen_artifact_output_rejected(self):
        with self.assertRaises(RepairOutputError):
            self.generate(output=ROOT / "artifacts/repairs/test")

    def test_053_uncontrolled_overwrite_rejected(self):
        output = self.case / "already"
        self.generate(output=output)
        with self.assertRaises(RepairOutputError):
            self.generate(output=output)

    def test_054_recognized_overwrite_allowed(self):
        output = self.case / "overwrite"
        first = self.generate(output=output)
        second = self.generate(output=output, overwrite=True)
        self.assertEqual(first.semantic_fingerprint, second.semantic_fingerprint)

    def test_055_nonpackage_overwrite_rejected(self):
        output = self.case / "not-package"
        output.mkdir()
        (output / "user.txt").write_text("keep", encoding="utf-8")
        with self.assertRaises(RepairOutputError):
            self.generate(output=output, overwrite=True)

    def test_056_dynamic_python_target_rejected(self):
        action = self.action(
            operation=EditOperation.UPDATE_DAG_STATIC_ARGUMENT,
            editor="python_dag_static_editor", path="dags/x.py",
            current="old", future="new", kind="output_field", task_id="publish",
        )
        with self.assertRaises(RepairEditError):
            EditorRegistry().apply(
                action, 'task = Operator(task_id="publish", output_field=f"{prefix}_old")\n'
            )

    def test_057_multiple_python_targets_rejected(self):
        action = self.action(
            operation=EditOperation.UPDATE_DAG_STATIC_ARGUMENT,
            editor="python_dag_static_editor", path="dags/x.py",
            current="old", future="new", kind="output_field",
        )
        source = 'a = Operator(task_id="a", output_field="old")\nb = Operator(task_id="b", output_field="old")\n'
        with self.assertRaises(RepairEditError):
            EditorRegistry().apply(action, source)

    def test_058_arbitrary_jinja_rejected(self):
        action = self.action(
            operation=EditOperation.UPDATE_MODEL_FILE_REFERENCE,
            editor="static_reference_editor", path="models/x.sql",
            current="old", future="new", kind="model_file",
        )
        with self.assertRaises(RepairEditError):
            EditorRegistry().apply(action, "{% for x in models %} {{ ref(x) }} {% endfor %}")

    def test_059_duplicate_yaml_key_rejected(self):
        action = self.action(
            operation=EditOperation.UPDATE_QUALITY_REFERENCE,
            editor="structured_config_editor", path="quality/x.yml",
            current="old", future="new", location="quality.field",
        )
        with self.assertRaises(RepairEditError):
            EditorRegistry().apply(action, "quality:\n  field: old\n  field: old\n")

    def test_060_duplicate_json_key_rejected_by_editor(self):
        action = self.action(
            operation=EditOperation.UPDATE_PIPELINE_CONFIG_REFERENCE,
            editor="structured_config_editor", path="pipelines/x.json",
            current="old", future="new", location="pipeline.field",
        )
        with self.assertRaises(RepairEditError):
            EditorRegistry().apply(action, '{"pipeline":{"field":"old","field":"old"}}')

    def test_061_stale_current_value_rejected(self):
        action = self.action(
            operation=EditOperation.UPDATE_QUALITY_REFERENCE,
            editor="structured_config_editor", path="quality/x.yml",
            current="missing", future="new", location="quality.field",
        )
        with self.assertRaises(RepairEditError):
            EditorRegistry().apply(action, "quality:\n  field: old\n")

    def test_062_unsafe_editor_path_rejected(self):
        action = self.action(
            operation=EditOperation.UPDATE_QUALITY_REFERENCE,
            editor="structured_config_editor", path="../quality/x.yml",
            current="old", future="new", location="quality.field",
        )
        with self.assertRaises(Exception):
            EditorRegistry().apply(action, "quality:\n  field: old\n")

    def test_063_binary_or_changed_head_bundle_rejected(self):
        bundle = self.case / "binary"
        shutil.copytree(EXAMPLES / "multifile_pr_primary", bundle)
        (bundle / "head/dags/orders_pipeline.py").write_bytes(b"\x00binary")
        with self.assertRaises(PredecessorTrustError):
            self.generate(bundle=bundle)

    def test_064_credential_shaped_bundle_rejected(self):
        bundle = self.case / "credential"
        shutil.copytree(EXAMPLES / "multifile_pr_primary", bundle)
        (bundle / "head/dags/orders_pipeline.py").write_text("api_token = 'secret-value-123456789'\n", encoding="utf-8")
        with self.assertRaises(PredecessorTrustError):
            self.generate(bundle=bundle)

    def test_065_certification_tampering_rejected(self):
        target = self.case / "cert-tamper"
        shutil.copytree(self.predecessors["primary"].output_dir, target)
        path = target / "analysis_certification.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["certification_status"] = "uncertified"
        path.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaises(PredecessorTrustError):
            self.generate(predecessor=target)

    # Valid no-repair states and determinism.

    def test_066_coherent_scenario_has_no_patch(self):
        result = self.results["coherent"]
        self.assertEqual(result.repair_disposition, RepairDisposition.NO_SUPPORTED_AUTOMATIC_REPAIR)
        self.assertEqual(len(result.patch_paths), 0)

    def test_067_no_material_scenario_has_no_patch(self):
        result = self.results["no_material"]
        self.assertEqual(len(result.repair_actions), 0)
        self.assertEqual(result.patch_manifest["patch_hunk_count"], 0)

    def test_068_conflict_is_blocked_without_patch(self):
        result = self.results["conflict"]
        self.assertEqual(result.repair_disposition, RepairDisposition.REPAIR_BLOCKED_BY_CONFLICT)
        self.assertEqual(len(result.patch_paths), 0)

    def test_069_conflict_preserves_alternatives(self):
        classes = self.results["conflict"].artifacts["repairability_classification.json"]["classifications"]
        self.assertIn("BLOCKED_BY_CONFLICT", {item["repairability"] for item in classes})
        predecessor_conflicts = self.results["conflict"].artifacts["projected_coherence_evaluation.json"]["conflicts"]
        self.assertEqual(predecessor_conflicts[0]["proposed_future_fields"], ["order_amount", "total_amount"])

    def test_070_metric_redefinition_is_manual(self):
        classes = self.results["primary"].artifacts["repairability_classification.json"]["classifications"]
        semantic = next(item for item in classes if item["root_type"] == "SEMANTIC_DEFINITION_CHANGED")
        self.assertEqual(semantic["repairability"], "MANUAL_DECISION_REQUIRED")

    def test_071_no_patch_is_certified_result(self):
        for name in ("coherent", "no_material", "conflict"):
            self.assertEqual(self.results[name].certification_status, "certified")

    def test_072_repository_fixtures_remain_byte_identical(self):
        self.assertEqual(self.fixture_hashes_before, self._fixture_hashes())

    def test_073_runtime_is_never_certified(self):
        for result in self.results.values():
            self.assertFalse(result.artifact_manifest["runtime_correctness_certified"])

    def test_074_human_review_is_always_required(self):
        for result in self.results.values():
            self.assertTrue(result.artifact_manifest["human_review_required"])

    def test_075_artifacts_have_no_forbidden_verification_language(self):
        for result in self.results.values():
            serialized = json.dumps(result.artifacts)
            for value in ("SAFE_TO_MERGE", "VERIFIED_FIXED", "EXECUTION_PASSED"):
                self.assertNotIn(value, serialized)

    def test_076_primary_deterministic_rerun(self):
        first = self.generate("primary", output=self.case / "first")
        second = self.generate("primary", output=self.case / "second")
        self.assertEqual(first.semantic_fingerprint, second.semantic_fingerprint)
        self.assertEqual(
            (first.output_dir / "repairs/patches/combined.patch").read_bytes(),
            (second.output_dir / "repairs/patches/combined.patch").read_bytes(),
        )

    def test_077_all_examples_deterministic(self):
        for name in self.scenarios:
            first = self.generate(name, output=self.case / f"{name}-a")
            second = self.generate(name, output=self.case / f"{name}-b")
            self.assertEqual(first.semantic_fingerprint, second.semantic_fingerprint)
            self.assertEqual(first.artifact_manifest["patch_fingerprints"], second.artifact_manifest["patch_fingerprints"])

    def test_078_output_location_does_not_affect_fingerprint(self):
        first = self.generate(output=self.case / "nested/a")
        second = self.generate(output=self.case / "other/b")
        self.assertEqual(first.semantic_fingerprint, second.semantic_fingerprint)

    def test_079_editor_registry_is_explicit(self):
        records = EditorRegistry().records()
        self.assertEqual({item["editor_name"] for item in records}, {
            "dbt_schema_editor", "python_dag_static_editor", "sqlglot_ast_editor",
            "static_reference_editor", "structured_config_editor", "structured_contract_editor",
        })
        self.assertTrue(all(item["executes_content"] is False for item in records))

    def test_080_rule_registry_is_explicit_and_unique(self):
        records = RepairRuleRegistry().artifact_records()
        ids = [item["repair_rule_id"] for item in records]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(item["required_evidence"] and item["post_generation_static_checks"] for item in records))

    def test_081_patch_json_omits_raw_candidate_content(self):
        artifacts = self.results["primary"].artifacts
        self.assertNotIn('from airflow.operators.python import PythonOperator', json.dumps(artifacts))

    def test_082_required_phase7_validation_is_complete(self):
        required = self.results["primary"].artifacts["required_phase_7_validation.json"]
        self.assertFalse(required["execution_performed_in_phase_6_4"])
        self.assertTrue(required["validations"])

    def test_083_patch_paths_are_portable(self):
        manifest = self.results["primary"].patch_manifest
        for path in [manifest["combined_patch_path"], *manifest["file_patch_paths"], *manifest["candidate_preview_paths"]]:
            self.assertNotIn("\\", path)
            self.assertNotRegex(path, r"^[A-Za-z]:")

    def test_084_repair_action_evidence_chain_complete(self):
        for action in self.results["primary"].repair_actions:
            self.assertTrue(action["root_cause_id"])
            self.assertTrue(action["logical_change_group_id"])
            self.assertTrue(action["current_evidence"]["head_content_fingerprint"])
            self.assertTrue(action["intended_future_evidence"]["identity_claim_evidence"])
            self.assertTrue(action["generation"]["edit_provenance"])

    def test_085_frozen_dependency_versions_remain(self):
        text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('sqlglot==30.13.0', text)
        self.assertIn('PyYAML==6.0.3', text)


if __name__ == "__main__":
    unittest.main()
