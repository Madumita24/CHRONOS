from __future__ import annotations

import copy
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from chronos import analyze_semantic_code_change
from chronos.cli import main as cli_main
from chronos.semantic_engine import (
    SEMANTIC_ARTIFACT_FILENAMES,
    DeltaType,
    SemanticCertificationError,
    SemanticProposalError,
    SemanticResolutionError,
    SqlParseError,
    UnsafeCodeInputError,
    UnsupportedDbtError,
    parse_model,
    parse_semantic_proposal,
)
from chronos.semantic_engine.certification import certify_semantic_artifacts
from chronos.semantic_engine.deltas import detect_deltas
from chronos.semantic_engine.intake import safe_repository_path
from chronos.snapshot import load_snapshot


ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_PATH = ROOT / "artifacts" / "current_metadata_snapshot.json"
EXAMPLES = ROOT / "examples"
MODEL_URN = "urn:li:dataset:(urn:li:dataPlatform:dbt,b2fd91.ORDER_ENTRY_DB.analytics.order_details,PROD)"
SOURCE_URN = "urn:li:dataset:(urn:li:dataPlatform:postgres,b2fd91.order_entry_db.order_entry.orders,PROD)"


class SemanticEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.snapshot = load_snapshot(SNAPSHOT_PATH)
        cls.scratch = ROOT / ".pytest_tmp"
        cls.scratch.mkdir(exist_ok=True)

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="phase62-", dir=self.scratch)
        self.work = Path(self.temp.name)
        self.counter = 0

    def tearDown(self) -> None:
        self.temp.cleanup()

    def example_proposal(self, name: str, file_name: str = "change.json") -> dict:
        return json.loads(
            (EXAMPLES / name / file_name).read_text(encoding="utf-8")
        )

    def analyze_example(self, name: str, *, output: str | None = None, file_name: str = "change.json"):
        proposal = self.example_proposal(name, file_name)
        return analyze_semantic_code_change(
            snapshot=self.snapshot,
            proposal=proposal,
            before_sql=proposal["before_code_reference"],
            after_sql=proposal["after_code_reference"],
            output_dir=self.work / (output or name),
            dbt_manifest=proposal.get("dbt_manifest_reference"),
        )

    def analyze_sql(
        self,
        before: str,
        after: str,
        *,
        dialect: str = "postgres",
        model_urn: str = MODEL_URN,
        model_relation: str = "order_entry_db.analytics.order_details",
        before_name: str = "before.sql",
        after_name: str = "after.sql",
        manifest: dict | None = None,
        **proposal_changes,
    ):
        self.counter += 1
        folder = self.work / f"case-{self.counter}"
        folder.mkdir()
        before_path = folder / before_name
        after_path = folder / after_name
        before_path.write_text(before, encoding="utf-8")
        after_path.write_text(after, encoding="utf-8")
        before_ref = before_path.relative_to(ROOT).as_posix()
        after_ref = after_path.relative_to(ROOT).as_posix()
        proposal = {
            "proposal_id": f"TEST-PROPOSAL-{self.counter}",
            "analysis_id": f"TEST-ANALYSIS-{self.counter}",
            "operation": "SEMANTIC_CODE_CHANGE",
            "model_dataset_urn": model_urn,
            "model_relation": model_relation,
            "sql_dialect": dialect,
            "before_code_reference": before_ref,
            "after_code_reference": after_ref,
            "source_snapshot_fingerprint": self.snapshot.semantic_fingerprint,
            "source_snapshot_id": self.snapshot.metadata.snapshot_id,
        }
        manifest_ref = None
        if manifest is not None:
            manifest_path = folder / "manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            manifest_ref = manifest_path.relative_to(ROOT).as_posix()
            proposal["dbt_manifest_reference"] = manifest_ref
        proposal.update(proposal_changes)
        return analyze_semantic_code_change(
            self.snapshot,
            proposal,
            before_ref,
            after_ref,
            folder / "output",
            dbt_manifest=manifest_ref,
        )

    def delta_types(self, before: str, after: str, dialect: str = "postgres"):
        old = parse_model(before, dialect=dialect)
        new = parse_model(after, dialect=dialect)
        structural, semantic = detect_deltas(old, new, model_dataset_urn=MODEL_URN)
        return structural, semantic

    def test_01_strict_semantic_proposal(self):
        proposal = parse_semantic_proposal(self.example_proposal("semantic_aggregation"))
        self.assertEqual(proposal.operation.value, "SEMANTIC_CODE_CHANGE")

    def test_02_parser_contract_captures_required_semantics(self):
        model = parse_model(
            "SELECT customer_id, SUM(order_total) AS order_total FROM orders WHERE order_status = 1 GROUP BY customer_id ORDER BY customer_id",
            dialect="postgres",
        )
        self.assertEqual(model.statement_type, "SELECT")
        self.assertEqual(model.output_columns[1].aggregations[0].function, "SUM")
        self.assertIsNotNone(model.filter_predicate)
        self.assertEqual(model.grouping, ("customer_id",))
        self.assertTrue(model.ordering)

    def test_03_sum_to_avg(self):
        _, deltas = self.delta_types(
            "SELECT SUM(x) AS metric FROM t",
            "SELECT AVG(x) AS metric FROM t",
        )
        self.assertEqual(deltas[0].delta_type, DeltaType.AGGREGATION_CHANGE)
        self.assertIn("function_changed", deltas[0].change_components)

    def test_04_count_to_count_distinct(self):
        _, deltas = self.delta_types(
            "SELECT COUNT(x) AS metric FROM t",
            "SELECT COUNT(DISTINCT x) AS metric FROM t",
        )
        self.assertIn("distinct_changed", deltas[0].change_components)

    def test_05_aggregation_input_changed(self):
        _, deltas = self.delta_types(
            "SELECT SUM(x) AS metric FROM t",
            "SELECT SUM(y) AS metric FROM t",
        )
        self.assertIn("input_changed", deltas[0].change_components)

    def test_06_filter_added(self):
        _, deltas = self.delta_types(
            "SELECT x AS x FROM t",
            "SELECT x AS x FROM t WHERE status = 'completed'",
        )
        self.assertEqual(deltas[0].delta_type, DeltaType.FILTER_CHANGE)
        self.assertIn("filter_added", deltas[0].change_components)

    def test_07_filter_removed(self):
        _, deltas = self.delta_types(
            "SELECT x AS x FROM t WHERE status = 'completed'",
            "SELECT x AS x FROM t",
        )
        self.assertIn("filter_removed", deltas[0].change_components)

    def test_08_filter_literal_changed(self):
        _, deltas = self.delta_types(
            "SELECT x AS x FROM t WHERE amount > 0",
            "SELECT x AS x FROM t WHERE amount > 100",
        )
        self.assertEqual(deltas[0].delta_type, DeltaType.FILTER_CHANGE)
        self.assertIn("predicate_modified", deltas[0].change_components)

    def test_09_filter_operator_changed(self):
        _, deltas = self.delta_types(
            "SELECT x AS x FROM t WHERE amount > 0",
            "SELECT x AS x FROM t WHERE amount >= 0",
        )
        self.assertEqual(deltas[0].before_representation, "amount > 0")
        self.assertEqual(deltas[0].after_representation, "amount >= 0")

    def test_10_left_to_inner_join(self):
        _, deltas = self.delta_types(
            "SELECT a.x AS x FROM a LEFT JOIN b ON a.id = b.id",
            "SELECT a.x AS x FROM a INNER JOIN b ON a.id = b.id",
        )
        self.assertEqual(deltas[0].delta_type, DeltaType.JOIN_TYPE_CHANGE)

    def test_11_join_predicate_changed(self):
        _, deltas = self.delta_types(
            "SELECT a.x AS x FROM a JOIN b ON a.id = b.id",
            "SELECT a.x AS x FROM a JOIN b ON a.email = b.email",
        )
        self.assertEqual(deltas[0].delta_type, DeltaType.JOIN_PREDICATE_CHANGE)

    def test_12_joined_relation_changed(self):
        _, deltas = self.delta_types(
            "SELECT a.x AS x FROM a JOIN b ON a.id = b.id",
            "SELECT a.x AS x FROM a JOIN c ON a.id = c.id",
        )
        self.assertIn(DeltaType.JOINED_RELATION_CHANGE, {item.delta_type for item in deltas})

    def test_13_expression_operator_changed(self):
        _, deltas = self.delta_types(
            "SELECT price * quantity AS value FROM t",
            "SELECT price + quantity AS value FROM t",
        )
        self.assertIn("operator_changed", deltas[0].change_components)

    def test_14_expression_function_changed(self):
        _, deltas = self.delta_types(
            "SELECT LOWER(x) AS value FROM t",
            "SELECT UPPER(x) AS value FROM t",
        )
        self.assertIn("function_changed", deltas[0].change_components)

    def test_15_expression_literal_changed(self):
        _, deltas = self.delta_types(
            "SELECT x * 1.0 AS value FROM t",
            "SELECT x * 0.9 AS value FROM t",
        )
        self.assertIn("literal_changed", deltas[0].change_components)

    def test_16_case_expression_changed(self):
        _, deltas = self.delta_types(
            "SELECT CASE WHEN status = 'a' THEN 1 ELSE 0 END AS value FROM t",
            "SELECT CASE WHEN status = 'b' THEN 1 ELSE 0 END AS value FROM t",
        )
        self.assertIn("case_structure_changed", deltas[0].change_components)

    def test_17_whitespace_comment_and_case_are_equivalent(self):
        before = parse_model("SELECT SUM(x) AS y FROM t", dialect="postgres")
        after = parse_model("  select sum(x) as y from t -- comment\n", dialect="postgres")
        self.assertEqual(before.canonical_ast_fingerprint, after.canonical_ast_fingerprint)

    def test_18_parentheses_are_equivalent(self):
        before = parse_model("SELECT (x) AS y FROM t", dialect="postgres")
        after = parse_model("SELECT x AS y FROM t", dialect="postgres")
        self.assertEqual(before.canonical_ast_fingerprint, after.canonical_ast_fingerprint)

    def test_19_alias_quoting_is_equivalent(self):
        before = parse_model('SELECT x AS "value" FROM t', dialect="postgres")
        after = parse_model("SELECT x AS value FROM t", dialect="postgres")
        self.assertEqual(before.canonical_ast_fingerprint, after.canonical_ast_fingerprint)

    def test_20_no_change_returns_no_delta(self):
        structural, semantic = self.delta_types(
            "SELECT x AS x FROM t", "select x as x from t -- comment"
        )
        self.assertEqual((structural, semantic), ((), ()))

    def test_21_aggregation_example_certifies(self):
        result = self.analyze_example("semantic_aggregation")
        self.assertEqual(result.certification_status, "certified")
        self.assertEqual(result.detected_deltas[0].delta_type, DeltaType.AGGREGATION_CHANGE)
        self.assertEqual(result.disposition, "hold_for_review")

    def test_22_filter_example_certifies(self):
        result = self.analyze_example("semantic_filter")
        self.assertEqual(result.detected_deltas[0].delta_type, DeltaType.FILTER_CHANGE)

    def test_23_join_example_certifies(self):
        result = self.analyze_example("semantic_join")
        self.assertEqual(result.detected_deltas[0].delta_type, DeltaType.JOIN_TYPE_CHANGE)

    def test_24_expression_example_certifies(self):
        result = self.analyze_example("semantic_expression")
        self.assertEqual(result.detected_deltas[0].delta_type, DeltaType.DERIVED_EXPRESSION_CHANGE)

    def test_25_output_identity_preserved_semantics_changed(self):
        result = self.analyze_example("semantic_aggregation")
        mapping = result.artifacts["entity_resolution.json"]["output_mappings"][0]
        self.assertEqual(mapping["mapping_state"], "IDENTITY_PRESERVED_SEMANTICS_CHANGED")

    def test_26_combined_single_model_has_multiple_deltas(self):
        result = self.analyze_example(
            "semantic_aggregation", file_name="combined_change.json"
        )
        self.assertEqual(
            {item.delta_type for item in result.detected_deltas},
            {DeltaType.AGGREGATION_CHANGE, DeltaType.FILTER_CHANGE},
        )

    def test_27_structural_and_semantic_compatibility_are_separate(self):
        result = self.analyze_example("semantic_aggregation")
        compatibility = result.artifacts["compatibility_evaluation.json"]
        self.assertEqual(compatibility["structural_compatibility"], "STRUCTURALLY_COMPATIBLE")
        self.assertEqual(compatibility["semantic_compatibility"], "SEMANTIC_COMPATIBILITY_UNKNOWN")
        self.assertEqual(compatibility["execution_validity"], "NOT_EXECUTED")

    def test_28_graph_uses_observed_edges_only(self):
        result = self.analyze_example("semantic_aggregation")
        graph = result.artifacts["future_metadata_graph.json"]
        observed_ids = {item.edge_id for item in self.snapshot.lineage_edges}
        self.assertTrue(all(item["current_edge_id"] in observed_ids for item in graph["relationships"]))

    def test_29_counts_derive_from_graph(self):
        result = self.analyze_example("semantic_filter")
        graph = result.artifacts["future_metadata_graph.json"]
        metrics = result.artifacts["dependency_propagation.json"]["metrics"]
        self.assertEqual(metrics["relationship_count"], len(graph["relationships"]))
        self.assertEqual(metrics["path_count"], len(graph["paths"]))

    def test_30_delta_specific_questions_and_evidence(self):
        aggregation = self.analyze_example("semantic_aggregation", output="agg")
        join = self.analyze_example("semantic_join", output="join")
        agg_synthesis = aggregation.artifacts["impact_synthesis.json"]
        join_synthesis = join.artifacts["impact_synthesis.json"]
        self.assertIn("aggregation", agg_synthesis["blocking_questions"][0]["question"].lower())
        self.assertIn("row-preservation", join_synthesis["blocking_questions"][0]["question"].lower())
        self.assertNotEqual(
            agg_synthesis["required_evidence"][0]["requirement_type"],
            join_synthesis["required_evidence"][0]["requirement_type"],
        )

    def test_31_root_causes_derive_from_delta_types(self):
        combined = self.analyze_example(
            "semantic_aggregation", file_name="combined_change.json"
        )
        reasons = {
            item["reason_code"]
            for item in combined.artifacts["technical_impact_analysis.json"]["root_causes"]
        }
        self.assertEqual(
            reasons,
            {"semantic-aggregation-definition-changed", "semantic-row-filter-changed"},
        )

    def test_32_package_has_eighteen_artifacts(self):
        result = self.analyze_example("semantic_expression")
        self.assertEqual({item.name for item in result.artifact_paths}, set(SEMANTIC_ARTIFACT_FILENAMES))

    def test_33_every_example_is_deterministic(self):
        for name in ("semantic_aggregation", "semantic_filter", "semantic_join", "semantic_expression"):
            first = self.analyze_example(name, output=f"{name}-one")
            second = self.analyze_example(name, output=f"{name}-two")
            self.assertEqual(first.semantic_fingerprint, second.semantic_fingerprint)

    def test_34_not_tied_to_order_total(self):
        result = self.analyze_sql(
            "SELECT o.order_date AS order_date FROM order_entry_db.order_entry.orders AS o",
            "SELECT COALESCE(o.order_date, 'unknown') AS order_date FROM order_entry_db.order_entry.orders AS o",
            model_urn=SOURCE_URN,
            model_relation="order_entry_db.order_entry.orders",
        )
        self.assertEqual(result.affected_outputs, ("order_date",))
        self.assertEqual(result.disposition, "proceed_with_conditions")

    def test_35_plain_and_compiled_sql_boundary(self):
        result = self.analyze_example("semantic_aggregation")
        validation = result.artifacts["proposal_validation.json"]
        self.assertEqual(validation["before_input_kind"], "plain_or_compiled_sql")

    def test_36_bounded_raw_dbt_ref_is_resolved_without_execution(self):
        manifest = {
            "nodes": {
                "model.shop.orders": {
                    "resource_type": "model",
                    "name": "orders",
                    "alias": "orders",
                    "relation_name": "order_entry_db.order_entry.orders",
                }
            },
            "sources": {},
        }
        result = self.analyze_sql(
            "SELECT order_total AS order_total FROM {{ ref('orders') }}",
            "SELECT order_total * 0.9 AS order_total FROM {{ ref('orders') }}",
            manifest=manifest,
        )
        validation = result.artifacts["proposal_validation.json"]
        self.assertEqual(validation["before_input_kind"], "raw_dbt_resolved_from_manifest")
        self.assertEqual(validation["dbt_references"], ["ref:orders"])

    def test_37_single_source_star_expansion_is_evidence_backed(self):
        result = self.analyze_sql(
            "SELECT * FROM order_entry_db.order_entry.orders",
            "SELECT * FROM order_entry_db.order_entry.orders",
        )
        expansion = result.artifacts["entity_resolution.json"]["star_expansions"]
        self.assertEqual(len(expansion[0]["expanded_field_paths"]), len(self.snapshot.source_schema.fields))

    def test_38_invalid_sql_rejected(self):
        with self.assertRaises(SqlParseError):
            self.analyze_sql("SELECT FROM", "SELECT x AS x FROM t")

    def test_39_multiple_statements_rejected(self):
        with self.assertRaises(SqlParseError):
            self.analyze_sql("SELECT 1 AS x; SELECT 2 AS x", "SELECT 1 AS x")

    def test_40_dynamic_sql_rejected(self):
        with self.assertRaises(SqlParseError):
            self.analyze_sql("EXECUTE query_name", "SELECT 1 AS x")

    def test_41_unresolved_target_model_rejected(self):
        with self.assertRaises(SemanticResolutionError):
            self.analyze_sql(
                "SELECT o.order_total AS order_total FROM order_entry_db.order_entry.orders o",
                "SELECT o.order_total * 2 AS order_total FROM order_entry_db.order_entry.orders o",
                model_urn="urn:li:dataset:(urn:li:dataPlatform:dbt,missing,PROD)",
                model_relation="missing",
            )

    def test_42_snapshot_mismatch_rejected(self):
        with self.assertRaises(SemanticProposalError):
            self.analyze_sql(
                "SELECT o.order_total AS order_total FROM order_entry_db.order_entry.orders o",
                "SELECT o.order_total * 2 AS order_total FROM order_entry_db.order_entry.orders o",
                source_snapshot_fingerprint="sha256:" + "0" * 64,
            )

    def test_43_dialect_override_mismatch_rejected(self):
        proposal = self.example_proposal("semantic_aggregation")
        with self.assertRaises(SemanticProposalError):
            analyze_semantic_code_change(
                self.snapshot,
                proposal,
                proposal["before_code_reference"],
                proposal["after_code_reference"],
                self.work / "dialect",
                sql_dialect="snowflake",
            )

    def test_44_ambiguous_unqualified_column_rejected(self):
        with self.assertRaises(SemanticResolutionError):
            self.analyze_sql(
                "SELECT order_total AS order_total FROM order_entry_db.order_entry.orders o JOIN order_entry_db.order_entry.orders p ON o.order_total = p.order_total",
                "SELECT order_total * 2 AS order_total FROM order_entry_db.order_entry.orders o JOIN order_entry_db.order_entry.orders p ON o.order_total = p.order_total",
            )

    def test_45_ambiguous_star_rejected(self):
        with self.assertRaises(SemanticResolutionError):
            self.analyze_sql(
                "SELECT * FROM order_entry_db.order_entry.orders o JOIN order_entry_db.order_entry.orders p ON o.order_total = p.order_total",
                "SELECT * FROM order_entry_db.order_entry.orders o JOIN order_entry_db.order_entry.orders p ON o.order_total = p.order_total",
            )

    def test_46_unsupported_jinja_rejected(self):
        with self.assertRaises(UnsupportedDbtError):
            self.analyze_sql(
                "{% if execute %} SELECT 1 AS order_total {% endif %}",
                "SELECT 1 AS order_total",
            )

    def test_47_unknown_relation_rejected(self):
        with self.assertRaises(SemanticResolutionError):
            self.analyze_sql(
                "SELECT x AS order_total FROM unknown_database.unknown_schema.unknown_table",
                "SELECT x * 2 AS order_total FROM unknown_database.unknown_schema.unknown_table",
            )

    def test_48_unsafe_absolute_code_path_rejected(self):
        proposal = self.example_proposal("semantic_aggregation")
        with self.assertRaises(UnsafeCodeInputError):
            analyze_semantic_code_change(
                self.snapshot,
                proposal,
                ROOT / proposal["before_code_reference"],
                proposal["after_code_reference"],
                self.work / "unsafe",
            )

    def test_49_output_overwrite_rejected_without_permission(self):
        proposal = self.example_proposal("semantic_aggregation")
        output = self.work / "same"
        analyze_semantic_code_change(
            self.snapshot, proposal, proposal["before_code_reference"], proposal["after_code_reference"], output
        )
        with self.assertRaises(UnsafeCodeInputError):
            analyze_semantic_code_change(
                self.snapshot, proposal, proposal["before_code_reference"], proposal["after_code_reference"], output
            )

    def test_50_tampered_artifact_rejected(self):
        result = self.analyze_example("semantic_filter")
        artifacts = copy.deepcopy(result.artifacts)
        artifacts.pop("analysis_certification.json")
        artifacts.pop("manifest.json")
        artifacts["semantic_diff.json"]["proposal_id"] = "tampered"
        with self.assertRaises(SemanticCertificationError):
            certify_semantic_artifacts(result.identity, artifacts)

    def test_51_dangling_graph_rejected(self):
        result = self.analyze_example("semantic_join")
        artifacts = copy.deepcopy(result.artifacts)
        artifacts.pop("analysis_certification.json")
        artifacts.pop("manifest.json")
        artifacts["future_metadata_graph.json"]["relationships"][0]["upstream_key"] = "missing|field"
        with self.assertRaises(SemanticCertificationError):
            certify_semantic_artifacts(result.identity, artifacts)

    def test_52_malformed_and_unknown_proposal_rejected(self):
        with self.assertRaises(SemanticProposalError):
            parse_semantic_proposal({})
        proposal = self.example_proposal("semantic_aggregation")
        proposal["command"] = "run"
        with self.assertRaises(SemanticProposalError):
            parse_semantic_proposal(proposal)

    def test_53_output_rename_is_structural_not_semantic(self):
        structural, semantic = self.delta_types(
            "SELECT x AS old_name FROM t", "SELECT x AS new_name FROM t"
        )
        self.assertEqual(structural[0].delta_type, DeltaType.OUTPUT_COLUMN_RENAME)
        self.assertEqual(semantic, ())

    def test_54_output_order_change_requires_review(self):
        structural, semantic = self.delta_types(
            "SELECT x AS x, y AS y FROM t", "SELECT y AS y, x AS x FROM t"
        )
        self.assertEqual(structural[0].delta_type, DeltaType.OUTPUT_ORDER_CHANGE)
        self.assertEqual(structural[0].certainty, "REQUIRES_REVIEW")
        self.assertEqual(semantic, ())

    def test_55_no_change_decision_can_proceed(self):
        result = self.analyze_sql(
            "SELECT o.order_total AS order_total FROM order_entry_db.order_entry.orders o",
            "select o.order_total as order_total from order_entry_db.order_entry.orders o -- format",
        )
        self.assertEqual(result.disposition, "proceed")
        self.assertEqual(result.semantic_compatibility.value, "SEMANTICALLY_COMPATIBLE")

    def test_56_comment_change_does_not_change_analysis_fingerprint(self):
        before = "SELECT o.order_total AS order_total FROM order_entry_db.order_entry.orders o"
        after = "SELECT o.order_total * 2 AS order_total FROM order_entry_db.order_entry.orders o"
        first = self.analyze_sql(before, after)
        proposal = json.loads(json.dumps(first.artifacts["semantic_change_proposal.json"]["proposal"]))
        before_path = ROOT / proposal["before_code_reference"]
        after_path = ROOT / proposal["after_code_reference"]
        before_path.write_text(before + " -- comment one\n", encoding="utf-8")
        after_path.write_text(after + " -- comment two\n", encoding="utf-8")
        second = analyze_semantic_code_change(
            self.snapshot,
            proposal,
            proposal["before_code_reference"],
            proposal["after_code_reference"],
            self.work / "comment-rerun",
        )
        self.assertEqual(first.semantic_fingerprint, second.semantic_fingerprint)

    def test_57_cli_success_and_failure_are_bounded(self):
        proposal = self.example_proposal("semantic_aggregation")
        stdout = StringIO()
        with redirect_stdout(stdout):
            status = cli_main(
                [
                    "analyze-semantic-change",
                    "--snapshot", str(SNAPSHOT_PATH),
                    "--proposal", str(EXAMPLES / "semantic_aggregation" / "change.json"),
                    "--before", proposal["before_code_reference"],
                    "--after", proposal["after_code_reference"],
                    "--output", str(self.work / "cli"),
                    "--dialect", "postgres",
                    "--fixture",
                ]
            )
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(stdout.getvalue())["delta_count"], 1)
        stderr = StringIO()
        with redirect_stderr(stderr):
            failed = cli_main(
                [
                    "analyze-semantic-change",
                    "--snapshot", str(SNAPSHOT_PATH),
                    "--proposal", str(self.work / "missing.json"),
                    "--before", "missing-before.sql",
                    "--after", "missing-after.sql",
                    "--output", str(self.work / "failed"),
                ]
            )
        self.assertEqual(failed, 2)
        self.assertNotIn("Traceback", stderr.getvalue())

    def test_58_artifacts_have_no_absolute_paths_or_credentials(self):
        result = self.analyze_example("semantic_aggregation")
        serialized = json.dumps(result.artifacts)
        self.assertNotIn(str(ROOT), serialized)
        for token in ("password", "access_token", "api_key"):
            self.assertNotIn(token, serialized.lower())

    def test_59_grouping_key_change_is_aggregation_delta(self):
        _, deltas = self.delta_types(
            "SELECT SUM(x) AS metric FROM t GROUP BY region",
            "SELECT SUM(x) AS metric FROM t GROUP BY country",
        )
        self.assertIn("grouping_changed", deltas[0].change_components)

    def test_60_filter_literal_component_is_explicit(self):
        _, deltas = self.delta_types(
            "SELECT x AS x FROM t WHERE amount > 0",
            "SELECT x AS x FROM t WHERE amount > 100",
        )
        self.assertIn("literal_changed", deltas[0].change_components)

    def test_61_filter_operator_component_is_explicit(self):
        _, deltas = self.delta_types(
            "SELECT x AS x FROM t WHERE amount > 0",
            "SELECT x AS x FROM t WHERE amount >= 0",
        )
        self.assertIn(
            "logical_or_comparison_operator_changed",
            deltas[0].change_components,
        )

    def test_62_filter_referenced_column_component_is_explicit(self):
        _, deltas = self.delta_types(
            "SELECT x AS x FROM t WHERE amount > 0",
            "SELECT x AS x FROM t WHERE balance > 0",
        )
        self.assertIn("referenced_column_changed", deltas[0].change_components)

    def test_63_dbt_source_is_resolved_from_supplied_manifest(self):
        manifest = {
            "sources": {
                "source.chronos.order_entry.orders": {
                    "resource_type": "source",
                    "source_name": "order_entry",
                    "name": "orders",
                    "identifier": "orders",
                    "database": "order_entry_db",
                    "schema": "order_entry",
                    "relation_name": "order_entry_db.order_entry.orders",
                }
            }
        }
        result = self.analyze_sql(
            "SELECT o.order_total AS order_total FROM {{ source('order_entry', 'orders') }} o",
            "SELECT o.order_total * 0.9 AS order_total FROM {{ source('order_entry', 'orders') }} o",
            manifest=manifest,
        )
        self.assertEqual(len(result.detected_deltas), 1)
        self.assertEqual(
            result.artifacts["proposal_validation.json"]["before_input_kind"],
            "raw_dbt_resolved_from_manifest",
        )

    def test_64_raw_dbt_without_manifest_is_rejected(self):
        with self.assertRaises(UnsupportedDbtError):
            self.analyze_sql(
                "SELECT order_total FROM {{ ref('orders') }}",
                "SELECT order_total * 2 AS order_total FROM {{ ref('orders') }}",
            )

    def test_65_output_addition_is_structural(self):
        structural, semantic = self.delta_types(
            "SELECT x AS x FROM t",
            "SELECT x AS x, y AS y FROM t",
        )
        self.assertEqual(structural[0].delta_type, DeltaType.OUTPUT_COLUMN_ADDED)
        self.assertEqual(semantic, ())

    def test_66_output_removal_is_structural(self):
        structural, semantic = self.delta_types(
            "SELECT x AS x, y AS y FROM t",
            "SELECT x AS x FROM t",
        )
        self.assertEqual(structural[0].delta_type, DeltaType.OUTPUT_COLUMN_REMOVED)
        self.assertEqual(semantic, ())

    def test_67_aggregation_addition_and_removal_are_explicit(self):
        _, added = self.delta_types("SELECT x AS metric FROM t", "SELECT SUM(x) AS metric FROM t")
        _, removed = self.delta_types("SELECT SUM(x) AS metric FROM t", "SELECT x AS metric FROM t")
        self.assertIn("aggregate_added", added[0].change_components)
        self.assertIn("aggregate_removed", removed[0].change_components)

    def test_68_line_endings_do_not_change_parsed_identity(self):
        unix = parse_model("SELECT x AS x\nFROM t\nWHERE y > 0", dialect="postgres")
        windows = parse_model("SELECT x AS x\r\nFROM t\r\nWHERE y > 0", dialect="postgres")
        self.assertEqual(unix.canonical_ast_fingerprint, windows.canonical_ast_fingerprint)

    def test_69_created_at_does_not_change_semantic_fingerprint(self):
        proposal = self.example_proposal("semantic_expression")
        first_proposal = {**proposal, "created_at": "2026-01-01T00:00:00Z"}
        second_proposal = {**proposal, "created_at": "2026-08-05T12:34:56Z"}
        first = analyze_semantic_code_change(
            self.snapshot,
            first_proposal,
            proposal["before_code_reference"],
            proposal["after_code_reference"],
            self.work / "timestamp-one",
        )
        second = analyze_semantic_code_change(
            self.snapshot,
            second_proposal,
            proposal["before_code_reference"],
            proposal["after_code_reference"],
            self.work / "timestamp-two",
        )
        self.assertEqual(first.semantic_fingerprint, second.semantic_fingerprint)

    def test_70_url_code_reference_is_rejected(self):
        with self.assertRaises(UnsafeCodeInputError):
            safe_repository_path("https://example.com/model.sql", repository_root=ROOT)

    def test_71_parent_traversal_code_reference_is_rejected(self):
        with self.assertRaises(UnsafeCodeInputError):
            safe_repository_path("../model.sql", repository_root=ROOT)

    def test_72_unknown_relation_alias_is_rejected(self):
        with self.assertRaises(SemanticResolutionError):
            self.analyze_sql(
                "SELECT z.order_total AS order_total FROM order_entry_db.order_entry.orders o",
                "SELECT z.order_total * 2 AS order_total FROM order_entry_db.order_entry.orders o",
            )

    def test_73_external_output_directory_is_rejected(self):
        proposal = self.example_proposal("semantic_aggregation")
        with self.assertRaises(UnsafeCodeInputError):
            analyze_semantic_code_change(
                self.snapshot,
                proposal,
                proposal["before_code_reference"],
                proposal["after_code_reference"],
                ROOT.parent / "phase62-outside-repository",
            )


if __name__ == "__main__":
    unittest.main()
