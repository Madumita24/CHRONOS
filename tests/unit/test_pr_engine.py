from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from chronos import analyze_pull_request
from chronos.cli import main as cli_main
from chronos.pr_engine import (
    CoherenceState,
    FileParseError,
    FileSafetyError,
    PR_ARTIFACT_FILENAMES,
    PullRequestCertificationError,
    PullRequestProposalError,
    PullRequestResolutionError,
    RepositoryIntakeError,
    parse_pr_proposal,
)
from chronos.pr_engine.certification import certify_pr_artifacts
from chronos.pr_engine.intake import (
    _bundle_file,
    _content_fingerprint,
    _payload,
    load_exported_bundle,
    load_git_range,
    with_classification,
)
from chronos.pr_engine.models import FileCategory, FileStatus
from chronos.pr_engine.proposals import pr_proposal_to_dict
from chronos.pr_engine.registry import ParserRegistry
from chronos.snapshot import load_snapshot


ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / "artifacts" / "current_metadata_snapshot.json"
EXAMPLES = ROOT / "examples"
MODEL_URN = "urn:li:dataset:(urn:li:dataPlatform:dbt,b2fd91.ORDER_ENTRY_DB.analytics.order_details,PROD)"


class PullRequestEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = load_snapshot(SNAPSHOT)
        cls.scratch = ROOT / ".pytest_tmp"
        cls.scratch.mkdir(exist_ok=True)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="phase63-", dir=self.scratch)
        self.work = Path(self.temp.name)
        self.counter = 0

    def tearDown(self):
        self.temp.cleanup()

    def fixture(self, name, output=None):
        root = EXAMPLES / f"multifile_pr_{name}"
        return analyze_pull_request(
            self.snapshot,
            root / "proposal.json",
            self.work / (output or name),
            bundle=root,
        )

    def proposal(self, name="primary"):
        return json.loads(
            (EXAMPLES / f"multifile_pr_{name}" / "proposal.json").read_text(encoding="utf-8")
        )

    def make_bundle(self, files, *, name="case", proposal_changes=None):
        self.counter += 1
        root = self.work / f"bundle-{self.counter}"
        for side in ("base", "head"):
            for path, pair in files.items():
                content = pair[0 if side == "base" else 1]
                if content is None:
                    continue
                target = root / side / Path(*path.split("/"))
                target.parent.mkdir(parents=True, exist_ok=True)
                if isinstance(content, bytes):
                    target.write_bytes(content)
                else:
                    target.write_text(content, encoding="utf-8")
        base_rev = f"fixture-base-{self.counter}"
        head_rev = f"fixture-head-{self.counter}"
        records = []
        for path, (base, head) in sorted(files.items()):
            status = "ADDED" if base is None else "DELETED" if head is None else "MODIFIED"
            base_bytes = None if base is None else (base if isinstance(base, bytes) else base.encode())
            head_bytes = None if head is None else (head if isinstance(head, bytes) else head.encode())
            records.append({
                "status": status,
                "base_path": None if base is None else path,
                "head_path": None if head is None else path,
                "base_fingerprint": _content_fingerprint(base_bytes),
                "head_fingerprint": _content_fingerprint(head_bytes),
            })
        repo = {"repository_name": f"test-{name}", "repository_namespace": "chronos"}
        manifest = {
            "schema_version": "1.0", "repository_identity": repo,
            "base_revision": base_rev, "head_revision": head_rev, "files": records,
        }
        (root / "bundle.json").write_text(json.dumps(manifest), encoding="utf-8")
        mapping = []
        if "models/order_details.sql" in files:
            mapping = [{
                "path": "models/order_details.sql", "model_dataset_urn": MODEL_URN,
                "model_relation": "order_entry_db.analytics.order_details", "sql_dialect": "postgres",
            }]
        proposal = {
            "proposal_id": f"TEST-PR-PROPOSAL-{self.counter}",
            "analysis_id": f"TEST-PR-ANALYSIS-{self.counter}",
            "operation": "MULTI_FILE_PR_CHANGE",
            "source_snapshot_fingerprint": self.snapshot.semantic_fingerprint,
            "source_snapshot_id": self.snapshot.metadata.snapshot_id,
            "repository_identity": repo, "base_revision": base_rev,
            "head_revision": head_rev, "intake_mode": "EXPORTED_PR_BUNDLE",
            "file_model_mappings": mapping,
        }
        proposal.update(proposal_changes or {})
        return root, proposal

    def analyze_case(self, files, **kwargs):
        root, proposal = self.make_bundle(files, **kwargs)
        return analyze_pull_request(
            self.snapshot, proposal, root / "output", bundle=root
        )

    def test_01_strict_proposal(self):
        proposal = parse_pr_proposal(self.proposal())
        self.assertEqual(proposal.operation.value, "MULTI_FILE_PR_CHANGE")

    def test_02_primary_analyzes_four_files(self):
        result = self.fixture("primary")
        self.assertEqual(result.changed_file_summary["changed_file_count"], 4)
        self.assertEqual(result.certification_status, "certified")

    def test_03_sql_semantic_delta_reuses_phase_62(self):
        result = self.fixture("primary")
        deltas = result.artifacts["semantic_change_set.json"]["deltas"]
        self.assertEqual([item["delta_type"] for item in deltas], ["AGGREGATION_CHANGE"])
        self.assertTrue(all(item["delta_class"] == "SemanticSqlDelta" for item in deltas))

    def test_04_sql_structural_rename_and_semantic_change_coexist(self):
        result = self.fixture("primary")
        delta = result.artifacts["structural_change_set.json"]["deltas"][0]
        self.assertEqual(delta["delta_type"], "OUTPUT_COLUMN_RENAME")
        self.assertEqual((delta["before_representation"], delta["after_representation"]), ("order_total", "order_amount"))

    def test_05_dbt_schema_column_update(self):
        result = self.fixture("primary")
        types = {item["delta_type"] for item in result.artifacts["contract_quality_change_set.json"]["deltas"]}
        self.assertIn("COLUMN_REMOVED", types)
        self.assertIn("COLUMN_ADDED", types)

    def test_06_dbt_contract_enforcement_change(self):
        result = self.fixture("primary")
        types = {item["delta_type"] for item in result.artifacts["contract_quality_change_set.json"]["deltas"]}
        self.assertIn("CONTRACT_ENFORCEMENT_CHANGED", types)

    def test_07_quality_reference_update(self):
        result = self.fixture("coherent")
        deltas = result.artifacts["pipeline_change_set.json"]["deltas"]
        self.assertTrue(any(item["delta_class"] == "QualityExpectationDelta" for item in result.artifacts["contract_quality_change_set.json"]["deltas"]))
        self.assertTrue(any(item["delta_class"] == "FieldReferenceDelta" for item in deltas))

    def test_08_static_dag_task_detected(self):
        result = self.fixture("primary")
        dag = next(item for item in result.artifacts["file_analysis_results.json"]["results"] if item["category"] == "PIPELINE_DAG")
        self.assertEqual(dag["parsed_head"]["tasks"][0]["task_id"], "publish_orders")

    def test_09_static_dag_dependency_change(self):
        result = self.analyze_case({
            "dags/test.py": (
                'a = Operator(task_id="a")\nb = Operator(task_id="b")\na >> b\n',
                'a = Operator(task_id="a")\nb = Operator(task_id="b")\nb >> a\n',
            )
        })
        types = {item["delta_type"] for item in result.artifacts["pipeline_change_set.json"]["deltas"]}
        self.assertEqual(types, {"TASK_DEPENDENCY_ADDED", "TASK_DEPENDENCY_REMOVED"})

    def test_10_static_dataset_and_field_references(self):
        result = self.analyze_case({
            "dags/test.py": (
                'a = Operator(task_id="a", input_dataset="orders", output_field="order_total")\n',
                'a = Operator(task_id="a", input_dataset="orders", output_field="order_amount")\n',
            )
        })
        head = result.artifacts["file_analysis_results.json"]["results"][0]["parsed_head"]
        self.assertEqual({item["kind"] for item in head["references"]}, {"input_dataset", "output_field"})

    def test_11_cross_file_rename_correlation(self):
        result = self.fixture("primary")
        group = next(item for item in result.logical_change_groups if item["current_field"] == "order_total")
        self.assertEqual(group["future_fields"], ["order_amount"])
        self.assertGreaterEqual(len(group["contributing_file_ids"]), 3)

    def test_12_sql_schema_coherence(self):
        self.assertEqual(self.fixture("coherent").coherence_state, CoherenceState.COHERENT)

    def test_13_stale_dag_reference(self):
        findings = self.fixture("primary").artifacts["coherence_evaluation.json"]["findings"]
        self.assertTrue(any(item.get("file_path") == "dags/orders_pipeline.py" for item in findings))

    def test_14_stale_quality_reference(self):
        findings = self.fixture("primary").artifacts["coherence_evaluation.json"]["findings"]
        self.assertTrue(any(item.get("file_path") == "quality/order_checks.yml" for item in findings))

    def test_15_contract_conflict_detected(self):
        result = self.fixture("conflict")
        self.assertEqual(result.conflicts[0]["conflict_type"], "CONFLICTING_FUTURE_FIELD_IDENTITIES")
        self.assertEqual(result.conflicts[0]["proposed_future_fields"], ["order_amount", "total_amount"])

    def test_16_multiple_logical_groups(self):
        self.assertGreaterEqual(len(self.fixture("primary").logical_change_groups), 2)

    def test_17_multiple_root_causes(self):
        self.assertGreater(len(self.fixture("primary").root_causes), 1)

    def test_18_shared_downstream_targets_are_deduplicated(self):
        result = self.fixture("primary")
        findings = result.artifacts["dependency_propagation.json"]["findings"]
        keys = [item["target_field_key"] for item in findings]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertTrue(any(len(item["root_cause_ids"]) > 1 for item in findings))

    def test_19_coherent_distinguished_from_inconsistent(self):
        self.assertEqual(self.fixture("coherent").coherence_state.value, "COHERENT")
        self.assertEqual(self.fixture("primary").coherence_state.value, "INCONSISTENT")

    def test_20_no_material_change(self):
        result = self.fixture("no_material")
        self.assertEqual(result.disposition, "no_material_change")
        self.assertEqual(result.root_causes, ())

    def test_21_conflicting_future_identities_block(self):
        self.assertEqual(self.fixture("conflict").disposition, "block_confirmed_incompatibility")

    def test_22_unsupported_file_preserved(self):
        result = self.analyze_case({"assets/logo.svg": ("<svg/>", "<svg><!-- updated --></svg>")})
        inventory = result.artifacts["changed_file_inventory.json"]
        self.assertEqual(inventory["summary"]["unsupported_count"], 1)
        self.assertEqual(result.artifacts["file_analysis_results.json"]["results"][0]["analysis_status"], "UNSUPPORTED")

    def test_23_pr_decision_is_derived(self):
        result = self.fixture("primary")
        decision = result.artifacts["impact_synthesis.json"]["decision"]
        self.assertEqual(decision["decision_rule_id"], "pr-decision-material-unresolved")

    def test_24_root_file_path_traceability(self):
        result = self.fixture("primary")
        propagation = result.artifacts["dependency_propagation.json"]
        self.assertTrue(all(item["root_cause_ids"] and item["path_ids"] and item["contributing_file_ids"] for item in propagation["findings"]))

    def test_25_exact_twenty_six_artifacts(self):
        result = self.fixture("primary")
        self.assertEqual({item.name for item in result.artifact_paths}, set(PR_ARTIFACT_FILENAMES))

    def test_26_every_example_is_deterministic(self):
        for name in ("primary", "coherent", "no_material", "conflict"):
            first = self.fixture(name, f"{name}-one")
            second = self.fixture(name, f"{name}-two")
            self.assertEqual(first.semantic_fingerprint, second.semantic_fingerprint)

    def test_27_python_api_result_is_complete(self):
        result = self.fixture("primary")
        self.assertTrue(result.repository_identity["repository_fingerprint"])
        self.assertTrue(result.manifest["artifact_fingerprints"])
        self.assertTrue(result.future_graph_summary)

    def test_28_cli_bundle_success(self):
        root = EXAMPLES / "multifile_pr_primary"
        stdout = StringIO()
        with redirect_stdout(stdout):
            status = cli_main([
                "analyze-pr", "--snapshot", str(SNAPSHOT), "--proposal", str(root / "proposal.json"),
                "--bundle", str(root), "--output", str(self.work / "cli"),
            ])
        value = json.loads(stdout.getvalue())
        self.assertEqual(status, 0)
        self.assertEqual(value["changed_file_count"], 4)
        self.assertEqual(value["coherence_state"], "INCONSISTENT")

    def test_29_cli_failure_is_bounded(self):
        stderr = StringIO()
        with redirect_stderr(stderr):
            status = cli_main([
                "analyze-pr", "--snapshot", str(SNAPSHOT), "--proposal", str(self.work / "missing.json"),
                "--bundle", str(self.work), "--output", str(self.work / "out"),
            ])
        self.assertEqual(status, 2)
        self.assertNotIn("Traceback", stderr.getvalue())

    def test_30_local_git_range_mode(self):
        proposal = {
            "proposal_id": "LOCAL-TEST-PROP", "analysis_id": "LOCAL-TEST-ANALYSIS",
            "operation": "MULTI_FILE_PR_CHANGE", "source_snapshot_fingerprint": self.snapshot.semantic_fingerprint,
            "source_snapshot_id": self.snapshot.metadata.snapshot_id,
            "repository_identity": {"repository_name": "CHRONOS", "repository_namespace": "Madumita24"},
            "base_revision": "915bd4b", "head_revision": "4c77188", "intake_mode": "LOCAL_GIT_RANGE",
        }
        result = analyze_pull_request(
            self.snapshot, proposal, self.work / "git", repository=ROOT,
            base_revision="915bd4b", head_revision="4c77188",
        )
        self.assertEqual(result.certification_status, "certified")
        self.assertGreater(result.changed_file_summary["changed_file_count"], 1)

    def test_31_invalid_repository_path(self):
        proposal = parse_pr_proposal({
            **self.proposal(), "intake_mode": "LOCAL_GIT_RANGE",
        })
        with self.assertRaises(RepositoryIntakeError):
            load_git_range(self.work / "missing", proposal)

    def test_32_invalid_git_revision(self):
        raw = {**self.proposal(), "intake_mode": "LOCAL_GIT_RANGE", "base_revision": "--upload-pack=bad"}
        proposal = parse_pr_proposal(raw)
        with self.assertRaises(RepositoryIntakeError):
            load_git_range(ROOT, proposal)

    def test_33_base_equals_head_rejected(self):
        raw = self.proposal()
        raw["head_revision"] = raw["base_revision"]
        with self.assertRaises(PullRequestProposalError):
            parse_pr_proposal(raw)

    def test_34_bundle_fingerprint_mismatch(self):
        root = self.work / "copy"
        shutil.copytree(EXAMPLES / "multifile_pr_primary", root)
        (root / "head" / "models" / "order_details.sql").write_text("SELECT 1", encoding="utf-8")
        with self.assertRaises(RepositoryIntakeError):
            load_exported_bundle(root, parse_pr_proposal(self.proposal()))

    def test_35_bundle_path_traversal(self):
        root = self.work / "copy"
        shutil.copytree(EXAMPLES / "multifile_pr_primary", root)
        manifest = json.loads((root / "bundle.json").read_text())
        manifest["files"][0]["base_path"] = "../escape.py"
        (root / "bundle.json").write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaises(FileSafetyError):
            load_exported_bundle(root, parse_pr_proposal(self.proposal()))

    def test_36_unsafe_symlink_is_rejected(self):
        root, _ = self.make_bundle({"models/order_details.sql": ("SELECT 1 AS x", "SELECT 2 AS x")})
        with patch.object(Path, "is_symlink", return_value=True):
            with self.assertRaises(FileSafetyError):
                _bundle_file(root, "base", "models/order_details.sql")

    def test_37_binary_supported_category_is_isolated(self):
        payload = _payload(FileStatus.MODIFIED, "models/x.sql", "models/x.sql", b"a\0b", b"a\0c")
        category, parser, warnings = ParserRegistry().classify(payload)
        self.assertEqual(category, FileCategory.UNSUPPORTED)
        self.assertIn("binary_file_isolated", warnings)

    def test_38_oversized_file_rejected(self):
        root, _ = self.make_bundle({"models/order_details.sql": ("x", "y")})
        target = root / "base" / "models" / "order_details.sql"
        target.write_bytes(b"x" * (1_048_576 + 1))
        with self.assertRaises(FileSafetyError):
            _bundle_file(root, "base", "models/order_details.sql")

    def test_39_invalid_yaml_rejected(self):
        with self.assertRaises(FileParseError):
            self.analyze_case({"models/schema.yml": ("version: 2\nmodels: [", "version: 2\nmodels: []")})

    def test_40_invalid_json_rejected(self):
        with self.assertRaises(FileParseError):
            self.analyze_case({"contracts/model.json": ('{"contract":', '{"contract":{"model":"x"}}')})

    def test_41_invalid_python_rejected(self):
        with self.assertRaises(FileParseError):
            self.analyze_case({"dags/test.py": ("task = Operator(task_id='a')", "def broken(:")})

    def test_42_dynamic_dag_is_partial_not_executed(self):
        result = self.analyze_case({
            "dags/test.py": (
                'a = Operator(task_id="a", output_field="order_total")\n',
                'a = Operator(task_id="a", output_field=get_field())\n',
            )
        })
        file_result = result.artifacts["file_analysis_results.json"]["results"][0]
        self.assertEqual(file_result["analysis_status"], "PARTIAL")
        self.assertEqual(result.coherence_state, CoherenceState.PARTIALLY_COHERENT)

    def test_43_unsupported_jinja_rejected(self):
        with self.assertRaises(FileParseError):
            self.analyze_case({
                "models/order_details.sql": (
                    "SELECT order_total FROM order_entry_db.order_entry.orders",
                    "{% for x in xs %} SELECT {{ x }} {% endfor %}",
                )
            })

    def test_44_ambiguous_datahub_model_rejected(self):
        duplicate = replace(self.snapshot, datasets=self.snapshot.datasets + (next(item for item in self.snapshot.datasets if item.dataset_urn == MODEL_URN),))
        root = EXAMPLES / "multifile_pr_primary"
        with self.assertRaises(PullRequestResolutionError):
            analyze_pull_request(duplicate, root / "proposal.json", self.work / "ambiguous", bundle=root)

    def test_45_conflicting_repository_identity_rejected(self):
        raw = self.proposal()
        raw["repository_identity"] = {"repository_name": "wrong"}
        with self.assertRaises(RepositoryIntakeError):
            load_exported_bundle(EXAMPLES / "multifile_pr_primary", parse_pr_proposal(raw))

    def test_46_snapshot_mismatch_rejected(self):
        raw = self.proposal()
        raw["source_snapshot_fingerprint"] = "sha256:" + "0" * 64
        with self.assertRaises(PullRequestProposalError):
            analyze_pull_request(self.snapshot, raw, self.work / "mismatch", bundle=EXAMPLES / "multifile_pr_primary")

    def test_47_unknown_proposal_property_rejected(self):
        raw = self.proposal()
        raw["command"] = "git checkout"
        with self.assertRaises(PullRequestProposalError):
            parse_pr_proposal(raw)

    def test_48_duplicate_changed_file_rejected(self):
        root = self.work / "copy"
        shutil.copytree(EXAMPLES / "multifile_pr_primary", root)
        manifest = json.loads((root / "bundle.json").read_text())
        manifest["files"].append(copy.deepcopy(manifest["files"][0]))
        (root / "bundle.json").write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaises(RepositoryIntakeError):
            load_exported_bundle(root, parse_pr_proposal(self.proposal()))

    def test_49_missing_bundle_content_rejected(self):
        root = self.work / "copy"
        shutil.copytree(EXAMPLES / "multifile_pr_primary", root)
        (root / "head" / "models" / "schema.yml").unlink()
        with self.assertRaises(FileSafetyError):
            load_exported_bundle(root, parse_pr_proposal(self.proposal()))

    def test_50_dangling_logical_group_rejected(self):
        result = self.fixture("primary")
        artifacts = {name: copy.deepcopy(value) for name, value in result.artifacts.items() if name not in {"analysis_certification.json", "manifest.json"}}
        artifacts["logical_change_groups.json"]["groups"][0]["structural_delta_ids"].append("missing")
        with self.assertRaises(PullRequestCertificationError):
            certify_pr_artifacts(result.identity, artifacts)

    def test_51_dangling_graph_edge_rejected(self):
        result = self.fixture("primary")
        artifacts = {name: copy.deepcopy(value) for name, value in result.artifacts.items() if name not in {"analysis_certification.json", "manifest.json"}}
        artifacts["future_metadata_graph.json"]["relationships"][0]["target"] = "missing"
        with self.assertRaises(PullRequestCertificationError):
            certify_pr_artifacts(result.identity, artifacts)

    def test_52_dangling_path_rejected(self):
        result = self.fixture("primary")
        artifacts = {name: copy.deepcopy(value) for name, value in result.artifacts.items() if name not in {"analysis_certification.json", "manifest.json"}}
        artifacts["future_metadata_graph.json"]["paths"][0]["relationship_ids"].append("missing")
        with self.assertRaises(PullRequestCertificationError):
            certify_pr_artifacts(result.identity, artifacts)

    def test_53_uncontrolled_overwrite_rejected(self):
        root = EXAMPLES / "multifile_pr_primary"
        output = self.work / "same"
        analyze_pull_request(self.snapshot, root / "proposal.json", output, bundle=root)
        with self.assertRaises(RepositoryIntakeError):
            analyze_pull_request(self.snapshot, root / "proposal.json", output, bundle=root)

    def test_54_external_output_rejected(self):
        root = EXAMPLES / "multifile_pr_primary"
        with self.assertRaises(RepositoryIntakeError):
            analyze_pull_request(self.snapshot, root / "proposal.json", ROOT.parent / "outside-pr", bundle=root)

    def test_55_credential_shaped_content_rejected(self):
        with self.assertRaises(FileSafetyError):
            _payload(FileStatus.MODIFIED, "config.yml", "config.yml", b"name: x", b"api_key: secret-value")

    def test_56_sql_formatting_comments_equivalent(self):
        result = self.fixture("no_material")
        self.assertEqual(result.artifacts["semantic_change_set.json"]["deltas"], [])
        self.assertEqual(result.artifacts["structural_change_set.json"]["deltas"], [])

    def test_57_yaml_key_reordering_not_material(self):
        result = self.fixture("no_material")
        material = [item for item in result.artifacts["contract_quality_change_set.json"]["deltas"] if item["material"]]
        self.assertEqual(material, [])

    def test_58_python_comment_not_material(self):
        result = self.fixture("no_material")
        dag = next(item for item in result.artifacts["file_analysis_results.json"]["results"] if item["category"] == "PIPELINE_DAG")
        self.assertEqual(dag["detected_deltas"], [])

    def test_59_documentation_only_not_material(self):
        result = self.fixture("no_material")
        docs = [item for item in result.artifacts["contract_quality_change_set.json"]["deltas"] if item["delta_class"] == "DocumentationOnlyDelta"]
        self.assertTrue(docs)
        self.assertTrue(all(not item["material"] for item in docs))

    def test_60_partially_coherent_state(self):
        result = self.analyze_case({
            "dags/test.py": (
                'a = Operator(task_id="a", output_field="order_total")\n',
                'a = Operator(task_id="a", output_field=dynamic_name())\n',
            )
        })
        self.assertEqual(result.coherence_state.value, "PARTIALLY_COHERENT")

    def test_61_unresolved_state(self):
        result = self.analyze_case({"pipelines/config.yml": ("pipeline:\n  dependency: a\n", "pipeline:\n  dependency: b\n")})
        self.assertEqual(result.coherence_state.value, "UNRESOLVED")

    def test_62_coherence_does_not_imply_execution_validity(self):
        result = self.fixture("coherent")
        compatibility = result.artifacts["compatibility_evaluation.json"]
        self.assertEqual(compatibility["repository_coherence"], "COHERENT")
        self.assertEqual(compatibility["execution_validity"], "UNVERIFIED")
        self.assertEqual(result.disposition, "hold_for_review")

    def test_63_generic_contract_parser(self):
        result = self.analyze_case({
            "contracts/orders.yml": (
                "contract:\n  model: order_details\n  fields:\n    order_total:\n      type: numeric\n",
                "contract:\n  model: order_details\n  fields:\n    order_total:\n      type: string\n",
            )
        })
        types = {item["delta_type"] for item in result.artifacts["contract_quality_change_set.json"]["deltas"]}
        self.assertIn("CONTRACT_CHANGED", types)

    def test_64_pipeline_config_parser(self):
        result = self.analyze_case({
            "pipelines/orders.yml": (
                "pipeline:\n  source_field: order_total\n  target_dataset: order_details\n",
                "pipeline:\n  source_field: order_amount\n  target_dataset: order_details\n",
            )
        })
        self.assertTrue(result.artifacts["pipeline_change_set.json"]["deltas"])

    def test_65_bounded_raw_dbt_ref_reused(self):
        manifest = json.dumps({"nodes": {"model.test.orders": {"resource_type": "model", "name": "orders", "relation_name": "order_entry_db.order_entry.orders"}}, "sources": {}})
        files = {
            "models/order_details.sql": (
                "SELECT SUM(order_total) AS order_total FROM {{ ref('orders') }}",
                "SELECT AVG(order_total) AS order_total FROM {{ ref('orders') }}",
            ),
            "manifest.json": (manifest, manifest),
        }
        root, proposal = self.make_bundle(files)
        proposal["file_model_mappings"][0]["dbt_manifest_path"] = "manifest.json"
        result = analyze_pull_request(self.snapshot, proposal, root / "output", bundle=root)
        self.assertEqual(result.artifacts["semantic_change_set.json"]["deltas"][0]["delta_type"], "AGGREGATION_CHANGE")

    def test_66_added_and_deleted_files_inventory(self):
        result = self.analyze_case({
            "docs/added.md": (None, "added"),
            "docs/deleted.md": ("deleted", None),
        })
        statuses = {item["status"] for item in result.artifacts["changed_file_inventory.json"]["files"]}
        self.assertEqual(statuses, {"ADDED", "DELETED"})

    def test_67_timestamp_does_not_change_fingerprint(self):
        root = EXAMPLES / "multifile_pr_primary"
        proposal = self.proposal()
        first = analyze_pull_request(self.snapshot, {**proposal, "created_at": "2026-01-01T00:00:00Z"}, self.work / "time-one", bundle=root)
        second = analyze_pull_request(self.snapshot, {**proposal, "created_at": "2026-08-05T23:59:59Z"}, self.work / "time-two", bundle=root)
        self.assertEqual(first.semantic_fingerprint, second.semantic_fingerprint)

    def test_68_artifacts_have_no_absolute_paths_or_contents(self):
        result = self.fixture("primary")
        serialized = json.dumps(result.artifacts)
        self.assertNotIn(str(ROOT), serialized)
        self.assertNotIn("from airflow.operators", serialized)

    def test_69_structural_semantic_coherence_execution_are_separate(self):
        result = self.fixture("primary")
        compatibility = result.artifacts["compatibility_evaluation.json"]
        dimensions = {item["dimension"] for item in compatibility["evaluations"]}
        self.assertEqual(dimensions, {"STRUCTURAL_COMPATIBILITY", "SEMANTIC_COMPATIBILITY"})
        self.assertEqual(compatibility["repository_coherence"], "INCONSISTENT")
        self.assertEqual(compatibility["execution_validity"], "UNVERIFIED")

    def test_70_observed_edges_are_snapshot_edges(self):
        result = self.fixture("primary")
        observed = {item.edge_id for item in self.snapshot.lineage_edges}
        graph = result.artifacts["future_metadata_graph.json"]
        self.assertTrue(all(item["current_edge_id"] in observed for item in graph["relationships"] if item["edge_kind"] == "OBSERVED_DATAHUB_EDGE"))

    def test_71_counterfactual_edges_are_labeled(self):
        graph = self.fixture("primary").artifacts["future_metadata_graph.json"]
        self.assertTrue(any(item["edge_kind"] == "COUNTERFACTUAL_EDGE" for item in graph["relationships"]))
        self.assertTrue(any(item["edge_kind"] == "UNRESOLVED_REFERENCE" for item in graph["relationships"]))

    def test_72_questions_are_root_specific(self):
        synthesis = self.fixture("primary").artifacts["impact_synthesis.json"]
        root_ids = {item["root_cause_id"] for item in self.fixture("primary", "primary-two").root_causes}
        self.assertTrue(all(item["root_cause_id"] in root_ids for item in synthesis["blocking_questions"]))

    def test_73_required_evidence_is_not_repair(self):
        requirements = self.fixture("primary").artifacts["impact_synthesis.json"]["required_evidence"]
        self.assertTrue(all(item["instruction_type"] == "EVIDENCE_NOT_REPAIR" for item in requirements))

    def test_74_coherent_static_updates_are_code_derived_proposed_edges(self):
        graph = self.fixture("coherent").artifacts["future_metadata_graph.json"]
        self.assertTrue(any(item["edge_kind"] == "CODE_DERIVED_PROPOSED_EDGE" for item in graph["relationships"]))

    def test_75_removed_output_preserves_labeled_removed_edge(self):
        result = self.analyze_case({
            "models/order_details.sql": (
                "SELECT o.order_total AS order_total, o.order_status AS order_status FROM order_entry_db.order_entry.orders o",
                "SELECT o.order_status AS order_status FROM order_entry_db.order_entry.orders o",
            )
        })
        graph = result.artifacts["future_metadata_graph.json"]
        self.assertTrue(any(item["edge_kind"] == "REMOVED_EDGE" for item in graph["relationships"]))
        evaluations = result.artifacts["compatibility_evaluation.json"]["evaluations"]
        self.assertTrue(any(item["reason_code"] == "SOURCE_FIELD_REMOVED_WITH_ACTIVE_DEPENDENCY" for item in evaluations))


if __name__ == "__main__":
    unittest.main()
