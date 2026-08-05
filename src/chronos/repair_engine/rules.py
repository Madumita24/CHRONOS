"""Centralized deterministic repair-rule registry."""

from __future__ import annotations

from .models import EditOperation, RepairRule


_STATIC_ALIGNMENT_EVIDENCE = (
    "certified_predecessor",
    "matching_head_content_fingerprint",
    "exact_current_static_value",
    "one_coherent_future_identity",
    "one_parser_confirmed_target",
    "no_competing_future_identity",
)
_STATIC_CHECKS = (
    "candidate_parses",
    "exact_intended_target_changed",
    "untargeted_structure_equivalent",
    "generated_diff_matches_candidate",
    "patch_applies_to_certified_head_copy",
)


class RepairRuleRegistry:
    """Immutable registry; planning never embeds ad-hoc editor decisions."""

    def __init__(self) -> None:
        self.rules = (
            RepairRule(
                "repair.stale-field.dag-static.v1",
                ("STALE_PIPELINE_OR_QUALITY_REFERENCE", "FIELD_REFERENCE_CHANGED"),
                ("PIPELINE_DAG",), _STATIC_ALIGNMENT_EVIDENCE,
                ("static_string_argument",), EditOperation.UPDATE_DAG_STATIC_ARGUMENT,
                "python_dag_static_editor", _STATIC_CHECKS + ("dag_dependencies_unchanged",),
                ("phase_7_dag_parse_and_execution",),
                "Align the exact stale DAG field argument {current} to the certified future identity {future}.",
            ),
            RepairRule(
                "repair.stale-field.quality-config.v1",
                ("STALE_PIPELINE_OR_QUALITY_REFERENCE", "QUALITY_EXPECTATION_CHANGED"),
                ("QUALITY_CONFIG",), _STATIC_ALIGNMENT_EVIDENCE,
                ("allowlisted_structured_reference",), EditOperation.UPDATE_QUALITY_REFERENCE,
                "structured_config_editor", _STATIC_CHECKS,
                ("phase_7_quality_validation",),
                "Align the exact stale quality reference {current} to the certified future identity {future}.",
            ),
            RepairRule(
                "repair.stale-field.pipeline-config.v1",
                ("STALE_PIPELINE_OR_QUALITY_REFERENCE", "FIELD_REFERENCE_CHANGED", "CONFIGURATION_CHANGED"),
                ("PIPELINE_CONFIG",), _STATIC_ALIGNMENT_EVIDENCE,
                ("allowlisted_structured_reference",), EditOperation.UPDATE_PIPELINE_CONFIG_REFERENCE,
                "structured_config_editor", _STATIC_CHECKS,
                ("phase_7_pipeline_validation",),
                "Align the exact stale pipeline reference {current} to the certified future identity {future}.",
            ),
            RepairRule(
                "repair.stale-dataset.static-reference.v1",
                ("STALE_PIPELINE_OR_QUALITY_REFERENCE", "DATASET_REFERENCE_CHANGED", "CONFIGURATION_CHANGED"),
                ("PIPELINE_DAG", "PIPELINE_CONFIG", "QUALITY_CONFIG"),
                _STATIC_ALIGNMENT_EVIDENCE,
                ("exact_dataset_or_model_transition",), EditOperation.REPLACE_STATIC_SCALAR,
                "static_reference_editor", _STATIC_CHECKS,
                ("phase_7_dataset_resolution_and_execution",),
                "Align the exact stale dataset reference {current} to {future}.",
            ),
            RepairRule(
                "repair.schema.column-name.v1",
                ("STALE_PIPELINE_OR_QUALITY_REFERENCE", "CONTRACT_CHANGE", "STRUCTURAL_CHANGE"),
                ("DBT_SCHEMA",), _STATIC_ALIGNMENT_EVIDENCE,
                ("exact_model_and_column",), EditOperation.UPDATE_DBT_COLUMN_NAME,
                "dbt_schema_editor", _STATIC_CHECKS,
                ("phase_7_dbt_compile_and_contract_validation",),
                "Align the dbt schema column {current} to {future}.",
            ),
            RepairRule(
                "repair.contract.field.v1",
                ("STALE_PIPELINE_OR_QUALITY_REFERENCE", "CONTRACT_CHANGE", "STRUCTURAL_CHANGE"),
                ("SCHEMA_CONTRACT",), _STATIC_ALIGNMENT_EVIDENCE,
                ("exact_contract_field",), EditOperation.UPDATE_CONTRACT_FIELD,
                "structured_contract_editor", _STATIC_CHECKS,
                ("phase_7_contract_validation",),
                "Align the bounded contract field {current} to {future}.",
            ),
            RepairRule(
                "repair.sql.identifier.v1",
                ("FIELD_REFERENCE_CHANGED", "DATASET_REFERENCE_CHANGED", "STRUCTURAL_CHANGE"),
                ("SQL_MODEL",), _STATIC_ALIGNMENT_EVIDENCE,
                ("one_sqlglot_ast_target",), EditOperation.UPDATE_SQL_IDENTIFIER,
                "sqlglot_ast_editor",
                _STATIC_CHECKS + ("sql_aggregation_filter_join_expression_protected",),
                ("phase_7_sql_execution_and_data_comparison",),
                "Update one exact SQL AST identifier from {current} to {future} without changing protected semantics.",
            ),
            RepairRule(
                "repair.dbt.static-model-reference.v1",
                ("DATASET_REFERENCE_CHANGED", "CONFIGURATION_CHANGED", "STRUCTURAL_CHANGE"),
                ("DBT_MODEL", "PIPELINE_DAG", "PIPELINE_CONFIG"),
                _STATIC_ALIGNMENT_EVIDENCE + ("exact_static_ref_source_mapping",),
                ("bounded_static_dbt_or_model_file_reference",),
                EditOperation.UPDATE_MODEL_FILE_REFERENCE, "static_reference_editor",
                _STATIC_CHECKS + ("arbitrary_jinja_unchanged",),
                ("phase_7_dbt_compile_or_pipeline_validation",),
                "Align the exact static model reference {current} to {future}.",
            ),
            RepairRule(
                "repair.delete.structured-stale-reference.v1",
                ("STRUCTURAL_CHANGE", "QUALITY_EXPECTATION_CHANGED", "CONFIGURATION_CHANGED"),
                ("QUALITY_CONFIG", "PIPELINE_CONFIG", "SCHEMA_CONTRACT", "DBT_SCHEMA"),
                (
                    "certified_explicit_deletion", "no_replacement_identity",
                    "one_parser_confirmed_target", "target_has_no_independent_purpose",
                ),
                ("approved_explicit_delete_without_replacement",),
                EditOperation.REMOVE_STALE_STATIC_REFERENCE,
                "structured_config_editor", _STATIC_CHECKS,
                ("phase_7_consumer_and_quality_validation",),
                "Remove one static declaration that only references the explicitly deleted identity {current}.",
                conditional=True,
            ),
            RepairRule(
                "repair.type.declaration-alignment.v1",
                ("CONTRACT_CHANGE", "STRUCTURAL_CHANGE"),
                ("DBT_SCHEMA", "SCHEMA_CONTRACT", "QUALITY_CONFIG", "PIPELINE_CONFIG"),
                (
                    "certified_explicit_type_transition", "one_proposed_future_type",
                    "one_parser_confirmed_declaration", "no_runtime_cast_required",
                ),
                ("approved_declaration_type_transition",),
                EditOperation.UPDATE_CONTRACT_TYPE,
                "structured_config_editor", _STATIC_CHECKS,
                ("phase_7_runtime_conversion_and_contract_validation",),
                "Align the declared type {current} to the explicit certified future type {future}; no cast is added.",
                conditional=True,
            ),
        )
        ids = [item.repair_rule_id for item in self.rules]
        if len(ids) != len(set(ids)):
            raise RuntimeError("Duplicate repair-rule identity.")

    def get(self, rule_id: str) -> RepairRule:
        for rule in self.rules:
            if rule.repair_rule_id == rule_id:
                return rule
        raise KeyError(rule_id)

    def for_target(self, root_type: str, file_category: str) -> tuple[RepairRule, ...]:
        return tuple(
            rule for rule in self.rules
            if root_type in rule.supported_root_types
            and file_category in rule.supported_file_categories
        )

    def artifact_records(self) -> list[dict[str, object]]:
        return [
            {
                "repair_rule_id": rule.repair_rule_id,
                "supported_root_types": list(rule.supported_root_types),
                "supported_file_categories": list(rule.supported_file_categories),
                "required_evidence": list(rule.required_evidence),
                "preconditions": list(rule.preconditions),
                "edit_strategy": rule.edit_operation.value,
                "editor_name": rule.editor_name,
                "post_generation_static_checks": list(rule.post_generation_static_checks),
                "remaining_evidence_requirements": list(rule.remaining_evidence_requirements),
                "explanation_template": rule.explanation_template,
                "conditional": rule.conditional,
            }
            for rule in self.rules
        ]
