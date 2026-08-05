"""Deterministic parser-backed editors for bounded Phase 6.4 repairs."""

from __future__ import annotations

import ast
import copy
import json
import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

import sqlglot
from sqlglot import expressions as exp
import yaml
from yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode

from chronos.pr_engine.intake import _safe_repo_path
from chronos.pr_engine.parsers.config import safe_document
from chronos.structural_engine.serialization import canonicalize, semantic_fingerprint

from .errors import RepairEditError
from .models import EditOperation, RepairAction


_SAFE_PLAIN_SCALAR = re.compile(r"^[A-Za-z0-9_./:@()\-]+$")
_DBT_CALL = re.compile(
    r"\{\{\s*(?P<call>ref|source)\(\s*(?P<quote>['\"])(?P<first>[A-Za-z0-9_\-]+)(?P=quote)"
    r"(?:\s*,\s*(?P<quote2>['\"])(?P<second>[A-Za-z0-9_\-]+)(?P=quote2))?\s*\)\s*\}\}"
)


@dataclass(frozen=True)
class EditorResult:
    candidate_content: str
    editor_name: str
    editor_version: str
    provenance: dict[str, Any]
    formatting_changes: tuple[str, ...]
    protected_semantics: dict[str, Any]


class EditorRegistry:
    def __init__(self) -> None:
        self._editors = {
            "python_dag_static_editor": PythonDagEditor(),
            "structured_config_editor": StructuredDocumentEditor(),
            "structured_contract_editor": StructuredDocumentEditor(),
            "dbt_schema_editor": StructuredDocumentEditor(),
            "sqlglot_ast_editor": SqlGlotEditor(),
            "static_reference_editor": StaticReferenceEditor(),
        }

    def apply(self, action: RepairAction, content: str, *, sql_dialect: str = "postgres") -> EditorResult:
        editor_name = action.current_evidence.get("editor_name")
        if not isinstance(editor_name, str) or editor_name not in self._editors:
            raise RepairEditError("Repair action does not name a registered editor.")
        return self._editors[editor_name].apply(
            action, content, sql_dialect=sql_dialect
        )

    def records(self) -> list[dict[str, Any]]:
        return [
            {
                "editor_name": name,
                "editor_version": editor.version,
                "supported_operations": sorted(item.value for item in editor.operations),
                "executes_content": False,
            }
            for name, editor in sorted(self._editors.items())
        ]


class PythonDagEditor:
    version = "6.4.0/python-ast-source-span"
    operations = {EditOperation.UPDATE_DAG_STATIC_ARGUMENT, EditOperation.REPLACE_STATIC_SCALAR, EditOperation.UPDATE_MODEL_FILE_REFERENCE}

    def apply(self, action, content, **_):
        _operation(action, self.operations)
        try:
            tree = ast.parse(content, filename=action.target_path, mode="exec")
        except SyntaxError as exc:
            raise RepairEditError("Target Python DAG does not parse.") from exc
        current = _string_evidence(action.current_evidence, "value")
        future = _string_evidence(action.intended_future_evidence, "value")
        kind = _string_evidence(action.current_evidence, "kind")
        expected_task = action.current_evidence.get("task_id")
        matches: list[ast.Constant] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            task_id = _keyword_string(node, "task_id")
            if expected_task is not None and task_id != expected_task:
                continue
            for keyword in node.keywords:
                if (
                    keyword.arg == kind
                    and isinstance(keyword.value, ast.Constant)
                    and isinstance(keyword.value.value, str)
                    and keyword.value.value == current
                ):
                    matches.append(keyword.value)
        if len(matches) != 1:
            raise RepairEditError("Python DAG repair requires exactly one static string target.")
        node = matches[0]
        segment = ast.get_source_segment(content, node)
        if segment is None:
            raise RepairEditError("Python source position evidence is unavailable.")
        replacement = _python_literal(future, segment)
        start, end = _source_span(content, node)
        candidate = content[:start] + replacement + content[end:]
        try:
            after = ast.parse(candidate, filename=action.target_path, mode="exec")
        except SyntaxError as exc:
            raise RepairEditError("Generated Python candidate is invalid.") from exc
        before_structure = _python_protected_structure(tree)
        after_structure = _python_protected_structure(after)
        if before_structure != after_structure:
            raise RepairEditError("Python repair altered protected DAG task or dependency structure.")
        return EditorResult(
            candidate, "python_dag_static_editor", self.version,
            {
                "target_kind": kind,
                "task_id": expected_task,
                "source_span": {"start": start, "end": end},
                "current_value": current,
                "future_value": future,
                "target_count": 1,
            },
            (),
            {
                "dag_structure_before": semantic_fingerprint(before_structure),
                "dag_structure_after": semantic_fingerprint(after_structure),
                "unchanged": True,
            },
        )


class StructuredDocumentEditor:
    version = "6.4.0/pyyaml-6.0.3-json-stdlib"
    operations = {
        EditOperation.REPLACE_STATIC_SCALAR,
        EditOperation.RENAME_MAPPING_KEY,
        EditOperation.UPDATE_MAPPING_VALUE,
        EditOperation.UPDATE_DBT_COLUMN_NAME,
        EditOperation.UPDATE_CONTRACT_FIELD,
        EditOperation.UPDATE_CONTRACT_TYPE,
        EditOperation.UPDATE_QUALITY_REFERENCE,
        EditOperation.UPDATE_PIPELINE_CONFIG_REFERENCE,
        EditOperation.UPDATE_MODEL_FILE_REFERENCE,
        EditOperation.REMOVE_STALE_STATIC_REFERENCE,
    }

    def apply(self, action, content, **_):
        _operation(action, self.operations)
        path = action.target_path.lower()
        location = action.target_location or action.current_evidence.get("location")
        if not isinstance(location, str) or not location:
            raise RepairEditError("Structured repair requires an exact target location.")
        tokens = _location_tokens(location)
        current = action.current_evidence.get("value")
        future = action.intended_future_evidence.get("value")
        if path.endswith(".json"):
            return self._json(action, content, tokens, current, future)
        if not path.endswith((".yml", ".yaml")):
            raise RepairEditError("Structured editor supports only YAML or JSON.")
        return self._yaml(action, content, tokens, current, future)

    def _yaml(self, action, content, tokens, current, future):
        before = _strict_yaml(content, action.target_path)
        _require_current(before, tokens, current, action.edit_operation)
        formatting: tuple[str, ...] = ()
        if action.edit_operation is EditOperation.REMOVE_STALE_STATIC_REFERENCE:
            try:
                root = yaml.compose(content, Loader=yaml.SafeLoader)
            except yaml.YAMLError as exc:
                raise RepairEditError("Target YAML does not parse.") from exc
            target_node = _yaml_node_at(root, tokens)
            scalar_matches = (
                [item for item in target_node.value if isinstance(item, ScalarNode) and item.value == str(current)]
                if isinstance(target_node, SequenceNode) else []
            )
            if len(scalar_matches) == 1:
                scalar = scalar_matches[0]
                start = content.rfind("\n", 0, scalar.start_mark.index) + 1
                newline = content.find("\n", scalar.end_mark.index)
                end = len(content) if newline < 0 else newline + 1
                candidate = content[:start] + content[end:]
                after = _strict_yaml(candidate, action.target_path)
            else:
                after = copy.deepcopy(before)
                _remove_value(after, tokens, current)
                candidate = yaml.safe_dump(
                    after, sort_keys=False, allow_unicode=True, default_flow_style=False
                )
                formatting = ("yaml_canonicalized_for_structured_deletion",)
        else:
            try:
                root = yaml.compose(content, Loader=yaml.SafeLoader)
            except yaml.YAMLError as exc:
                raise RepairEditError("Target YAML does not parse.") from exc
            node = _yaml_node_at(root, tokens)
            if not isinstance(node, ScalarNode) or node.value != str(current):
                raise RepairEditError("YAML target is not one exact scalar with the certified current value.")
            replacement = _yaml_scalar(future, content[node.start_mark.index:node.end_mark.index])
            candidate = (
                content[: node.start_mark.index]
                + replacement
                + content[node.end_mark.index :]
            )
            after = _strict_yaml(candidate, action.target_path)
            if _value_at(after, tokens) != future:
                raise RepairEditError("YAML candidate does not contain the intended value.")
        protected_before = _without_target(before, tokens, action.edit_operation, current)
        protected_after = (
            copy.deepcopy(after)
            if action.edit_operation is EditOperation.REMOVE_STALE_STATIC_REFERENCE
            else _without_target(after, tokens, action.edit_operation, future)
        )
        if canonicalize(protected_before) != canonicalize(protected_after):
            raise RepairEditError("YAML repair altered untargeted bounded structure.")
        return EditorResult(
            candidate, action.current_evidence["editor_name"], self.version,
            {
                "structured_location": action.target_location,
                "current_value": current,
                "future_value": future,
                "target_count": 1,
            },
            formatting,
            {
                "untargeted_structure_before": semantic_fingerprint(protected_before),
                "untargeted_structure_after": semantic_fingerprint(protected_after),
                "unchanged": True,
            },
        )

    def _json(self, action, content, tokens, current, future):
        before = _strict_json(content, action.target_path)
        _require_current(before, tokens, current, action.edit_operation)
        after = copy.deepcopy(before)
        if action.edit_operation is EditOperation.REMOVE_STALE_STATIC_REFERENCE:
            _remove_value(after, tokens, current)
        else:
            _set_value(after, tokens, future)
        candidate = json.dumps(after, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        reparsed = _strict_json(candidate, action.target_path)
        if canonicalize(reparsed) != canonicalize(after):
            raise RepairEditError("JSON candidate failed deterministic round-trip validation.")
        protected_before = _without_target(before, tokens, action.edit_operation, current)
        protected_after = (
            copy.deepcopy(after)
            if action.edit_operation is EditOperation.REMOVE_STALE_STATIC_REFERENCE
            else _without_target(after, tokens, action.edit_operation, future)
        )
        if canonicalize(protected_before) != canonicalize(protected_after):
            raise RepairEditError("JSON repair altered untargeted structure.")
        return EditorResult(
            candidate, action.current_evidence["editor_name"], self.version,
            {
                "structured_location": action.target_location,
                "current_value": current,
                "future_value": future,
                "target_count": 1,
            },
            ("json_deterministic_serialization",),
            {
                "untargeted_structure_before": semantic_fingerprint(protected_before),
                "untargeted_structure_after": semantic_fingerprint(protected_after),
                "unchanged": True,
            },
        )


class SqlGlotEditor:
    version = "6.4.0/sqlglot-30.13.0"
    operations = {EditOperation.UPDATE_SQL_IDENTIFIER, EditOperation.UPDATE_SQL_OUTPUT_ALIAS}

    def apply(self, action, content, *, sql_dialect="postgres", **_):
        _operation(action, self.operations)
        if "{{" in content or "{%" in content or "{#" in content:
            raise RepairEditError("Raw dbt/Jinja SQL is outside the SQL AST round-trip boundary.")
        try:
            statements = sqlglot.parse(content, read=sql_dialect)
        except Exception as exc:
            raise RepairEditError("Target SQL does not parse with SQLGlot.") from exc
        if len(statements) != 1:
            raise RepairEditError("SQL repair requires exactly one statement.")
        tree = statements[0]
        current = _string_evidence(action.current_evidence, "value")
        future = _string_evidence(action.intended_future_evidence, "value")
        target_kind = action.current_evidence.get("sql_target_kind", "column")
        matches = _sql_targets(tree, target_kind, current)
        if len(matches) != 1:
            raise RepairEditError("SQL repair requires exactly one matching AST target.")
        protected_before = _normalized_sql_dump(tree, target_kind, current)
        _mutate_sql_target(matches[0], target_kind, future)
        protected_after = _normalized_sql_dump(tree, target_kind, future)
        if protected_before != protected_after:
            raise RepairEditError("SQL repair altered protected aggregation, filter, join, or expression structure.")
        candidate = tree.sql(dialect=sql_dialect, pretty=True) + "\n"
        try:
            reparsed = sqlglot.parse_one(candidate, read=sql_dialect)
        except Exception as exc:
            raise RepairEditError("Generated SQL candidate is invalid.") from exc
        if len(_sql_targets(reparsed, target_kind, future)) != 1:
            raise RepairEditError("Generated SQL candidate lacks the intended AST target.")
        return EditorResult(
            candidate, "sqlglot_ast_editor", self.version,
            {
                "sql_target_kind": target_kind,
                "current_value": current,
                "future_value": future,
                "target_count": 1,
                "dialect": sql_dialect,
            },
            ("sqlglot_canonical_serialization",),
            {
                "normalized_ast_before": semantic_fingerprint(protected_before),
                "normalized_ast_after": semantic_fingerprint(protected_after),
                "unchanged": True,
            },
        )


class StaticReferenceEditor:
    version = "6.4.0/static-reference-dispatch"
    operations = {
        EditOperation.REPLACE_STATIC_SCALAR,
        EditOperation.UPDATE_MODEL_FILE_REFERENCE,
    }

    def apply(self, action, content, *, sql_dialect="postgres", **_):
        _operation(action, self.operations)
        suffix = PurePosixPath(action.target_path).suffix.lower()
        if suffix == ".py":
            return PythonDagEditor().apply(action, content)
        if suffix in {".yml", ".yaml", ".json"}:
            return StructuredDocumentEditor().apply(action, content)
        if suffix == ".sql":
            return self._dbt_reference(action, content, sql_dialect)
        raise RepairEditError("Static reference editor does not support the target file.")

    def _dbt_reference(self, action, content, dialect):
        if "{%" in content or "{#" in content:
            raise RepairEditError("Arbitrary dbt Jinja is unsupported.")
        spans = list(_DBT_CALL.finditer(content))
        residual = _DBT_CALL.sub("__chronos_relation__", content)
        if "{{" in residual or "}}" in residual:
            raise RepairEditError("Only bounded static dbt ref/source calls are editable.")
        current = _string_evidence(action.current_evidence, "value")
        future = _string_evidence(action.intended_future_evidence, "value")
        matches = []
        for match in spans:
            values = [match.group("first"), match.group("second")]
            if current in values:
                matches.append(match)
        if len(matches) != 1:
            raise RepairEditError("dbt repair requires one exact static ref/source target.")
        match = matches[0]
        group = "first" if match.group("first") == current else "second"
        start, end = match.span(group)
        candidate = content[:start] + future + content[end:]
        if "{%" in candidate or "{#" in candidate:
            raise RepairEditError("Generated dbt candidate crossed the static boundary.")
        return EditorResult(
            candidate, "static_reference_editor", self.version,
            {
                "dbt_call": match.group("call"),
                "source_span": {"start": start, "end": end},
                "current_value": current,
                "future_value": future,
                "target_count": 1,
            },
            (),
            {
                "non_target_source_before": semantic_fingerprint(content[:start] + "__TARGET__" + content[end:]),
                "non_target_source_after": semantic_fingerprint(candidate[:start] + "__TARGET__" + candidate[start + len(future):]),
                "unchanged": True,
                "jinja_executed": False,
            },
        )


def _operation(action: RepairAction, supported: set[EditOperation]) -> None:
    _safe_repo_path(action.target_path)
    if action.edit_operation not in supported:
        raise RepairEditError("Editor does not support the requested typed operation.")


def _string_evidence(value: dict[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item or "\x00" in item:
        raise RepairEditError(f"Repair evidence requires a bounded string {key}.")
    return item


def _keyword_string(call: ast.Call, name: str) -> str | None:
    for keyword in call.keywords:
        if keyword.arg == name and isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
            return keyword.value.value
    return None


def _source_span(content: str, node: ast.AST) -> tuple[int, int]:
    if not all(hasattr(node, item) for item in ("lineno", "col_offset", "end_lineno", "end_col_offset")):
        raise RepairEditError("AST source span is unavailable.")
    lines = content.splitlines(keepends=True)
    start = sum(len(line) for line in lines[: node.lineno - 1]) + node.col_offset
    end = sum(len(line) for line in lines[: node.end_lineno - 1]) + node.end_col_offset
    return start, end


def _python_literal(value: str, original: str) -> str:
    if original.startswith('"'):
        return json.dumps(value, ensure_ascii=False)
    if original.startswith("'"):
        return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"
    raise RepairEditError("Python repair target is not a simple quoted string.")


def _python_protected_structure(tree: ast.AST) -> dict[str, Any]:
    tasks = []
    dependencies = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            variable = node.targets[0].id if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) else None
            tasks.append({
                "variable": variable,
                "operator": _ast_call_name(node.value.func),
                "task_id": _keyword_string(node.value, "task_id"),
            })
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.RShift):
            dependencies.append((_ast_name(node.left), _ast_name(node.right)))
    return {"tasks": sorted(tasks, key=str), "dependencies": sorted(dependencies, key=str)}


def _ast_name(node: ast.AST) -> str | None:
    return node.id if isinstance(node, ast.Name) else None


def _ast_call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return "UNKNOWN_OPERATOR"


def _strict_yaml(content: str, path: str) -> Any:
    if "{{" in content or "{%" in content or "{#" in content:
        raise RepairEditError("Dynamic Jinja is unsupported in structured repair targets.")

    class UniqueSafeLoader(yaml.SafeLoader):
        pass

    def construct_mapping(loader, node, deep=False):
        mapping = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node, deep=deep)
            if key in mapping:
                raise RepairEditError(f"Duplicate YAML key in {path}.")
            mapping[key] = loader.construct_object(value_node, deep=deep)
        return mapping

    UniqueSafeLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, construct_mapping
    )
    try:
        value = yaml.load(content, Loader=UniqueSafeLoader)
        safe_document(content, path)
    except (yaml.YAMLError, TypeError, ValueError) as exc:
        if isinstance(exc, RepairEditError):
            raise
        raise RepairEditError("Target YAML failed safe bounded parsing.") from exc
    if not isinstance(value, dict):
        raise RepairEditError("Structured repair target must have an object root.")
    return value


def _strict_json(content: str, path: str) -> dict[str, Any]:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise RepairEditError(f"Duplicate JSON key in {path}.")
            result[key] = value
        return result
    try:
        value = json.loads(content, object_pairs_hook=pairs)
    except json.JSONDecodeError as exc:
        raise RepairEditError("Target JSON does not parse.") from exc
    if not isinstance(value, dict):
        raise RepairEditError("Structured repair target must have an object root.")
    return value


def _location_tokens(location: str) -> tuple[str | int, ...]:
    tokens: list[str | int] = []
    for name, index in re.findall(r"(?:^|\.)([^.\[]+)|\[(\d+)\]", location):
        tokens.append(int(index) if index else name)
    if not tokens:
        raise RepairEditError("Structured target location is invalid.")
    return tuple(tokens)


def _value_at(value: Any, tokens: tuple[str | int, ...]) -> Any:
    current = value
    for token in tokens:
        try:
            current = current[token]
        except (KeyError, IndexError, TypeError) as exc:
            raise RepairEditError("Structured target location does not exist.") from exc
    return current


def _parent_at(value: Any, tokens: tuple[str | int, ...]) -> tuple[Any, str | int]:
    if not tokens:
        raise RepairEditError("Root replacement is forbidden.")
    return _value_at(value, tokens[:-1]) if len(tokens) > 1 else value, tokens[-1]


def _set_value(value: Any, tokens: tuple[str | int, ...], replacement: Any) -> None:
    parent, key = _parent_at(value, tokens)
    parent[key] = replacement


def _remove_value(value: Any, tokens: tuple[str | int, ...], current: Any) -> None:
    parent, key = _parent_at(value, tokens)
    target = parent[key]
    if isinstance(target, list) and current in target and target.count(current) == 1:
        target.remove(current)
    elif target == current:
        del parent[key]
    else:
        raise RepairEditError("Structured deletion target is ambiguous or stale.")


def _require_current(value, tokens, current, operation):
    observed = _value_at(value, tokens)
    if operation is EditOperation.REMOVE_STALE_STATIC_REFERENCE and isinstance(observed, list):
        if observed.count(current) != 1:
            raise RepairEditError("Structured deletion requires exactly one current value.")
    elif observed != current:
        raise RepairEditError("Structured current value does not match certified evidence.")


def _without_target(value, tokens, operation, target):
    result = copy.deepcopy(value)
    parent, key = _parent_at(result, tokens)
    observed = parent[key]
    if operation is EditOperation.REMOVE_STALE_STATIC_REFERENCE:
        if isinstance(observed, list):
            observed.remove(target)
        else:
            del parent[key]
    else:
        parent[key] = "__CHRONOS_REPAIR_TARGET__"
    return result


def _yaml_node_at(root: Node | None, tokens: tuple[str | int, ...]) -> Node:
    if root is None:
        raise RepairEditError("YAML target document is empty.")
    node = root
    for token in tokens:
        if isinstance(token, str) and isinstance(node, MappingNode):
            matches = [value for key, value in node.value if isinstance(key, ScalarNode) and key.value == token]
            if len(matches) != 1:
                raise RepairEditError("YAML mapping target is absent or duplicated.")
            node = matches[0]
        elif isinstance(token, int) and isinstance(node, SequenceNode):
            if token < 0 or token >= len(node.value):
                raise RepairEditError("YAML sequence target is out of range.")
            node = node.value[token]
        else:
            raise RepairEditError("YAML target path does not match the document structure.")
    return node


def _yaml_scalar(value: Any, original: str) -> str:
    if not isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if original.startswith("'"):
        return "'" + value.replace("'", "''") + "'"
    if original.startswith('"'):
        return json.dumps(value, ensure_ascii=False)
    return value if _SAFE_PLAIN_SCALAR.fullmatch(value) else json.dumps(value, ensure_ascii=False)


def _sql_targets(tree, target_kind, value):
    if target_kind == "column":
        return [node for node in tree.find_all(exp.Column) if node.name == value]
    if target_kind == "relation":
        return [node for node in tree.find_all(exp.Table) if node.name == value]
    if target_kind == "output_alias":
        return [node for node in tree.find_all(exp.Alias) if node.alias == value]
    raise RepairEditError("Unsupported SQL AST target kind.")


def _mutate_sql_target(node, target_kind, value):
    if target_kind in {"column", "relation"}:
        node.set("this", exp.to_identifier(value))
    else:
        node.set("alias", exp.to_identifier(value))


def _normalized_sql_dump(tree, target_kind, value):
    clone = tree.copy()
    matches = _sql_targets(clone, target_kind, value)
    if len(matches) != 1:
        raise RepairEditError("Protected SQL normalization requires one target.")
    _mutate_sql_target(matches[0], target_kind, "__chronos_repair_target__")
    return clone.dump()
