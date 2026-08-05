"""Python AST-only extraction for a deliberately small static DAG subset."""

from __future__ import annotations

import ast
from typing import Any

from chronos.structural_engine.serialization import stable_id

from ..errors import FileParseError
from ..models import FileCategory
from .common import delta, file_result


class PythonDagParser:
    name = "python_ast_static_dag"
    version = "6.3.0/python-ast"
    categories = {FileCategory.PIPELINE_DAG}
    reference_keys = {
        "source_table", "target_table", "input_dataset", "output_dataset",
        "sql", "source_field", "target_field", "input_field", "output_field",
        "model_file", "contract_file",
    }

    def parse(self, payload, **_):
        path = payload.record.head_path or payload.record.base_path
        before = self._parse(payload.base_content, path) if payload.base_content is not None else None
        after = self._parse(payload.head_content, path) if payload.head_content is not None else None
        deltas = self._diff(before or _empty(), after or _empty(), path)
        unresolved = [
            {"code_reference": item, "resolution_state": "INSUFFICIENT_METADATA", "reason": "dynamic_python_expression"}
            for item in sorted(set((before or _empty())["dynamic"] + (after or _empty())["dynamic"]))
        ]
        status = "PARTIAL" if unresolved else "ANALYZED"
        return file_result(
            payload, self.name, self.version, before, after, deltas,
            unresolved_references=unresolved,
            evidence=[{
                "evidence_id": stable_id("pr-evidence", payload.record.file_change_id, "python-ast"),
                "evidence_class": "CODE_DERIVED_EVIDENCE", "parser": self.version,
            }],
            warnings=["dynamic_dag_constructs_retained_unresolved"] if unresolved else [],
            status=status,
        )

    def _parse(self, content: str, path: str) -> dict[str, Any]:
        try:
            tree = ast.parse(content, filename=path, mode="exec")
        except SyntaxError as exc:
            raise FileParseError(f"Invalid Python syntax in {path!r}.") from exc
        tasks = {}
        dependencies = set()
        references = []
        dynamic = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.For, ast.While, ast.ListComp, ast.DictComp, ast.SetComp, ast.GeneratorExp)):
                dynamic.append(f"{type(node).__name__}@{getattr(node, 'lineno', 0)}")
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
                variable = node.targets[0].id if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) else None
                task = _task(node.value, variable, self.reference_keys, dynamic, references)
                if task:
                    tasks[task["task_id"]] = task
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.RShift):
                left, right = _name(node.left), _name(node.right)
                if left and right:
                    dependencies.add((left, right))
                else:
                    dynamic.append(f"dynamic_dependency@{getattr(node, 'lineno', 0)}")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.args:
                owner, argument = _name(node.func.value), _name(node.args[0])
                if node.func.attr == "set_downstream" and owner and argument:
                    dependencies.add((owner, argument))
                elif node.func.attr == "set_upstream" and owner and argument:
                    dependencies.add((argument, owner))
        return {
            "tasks": [tasks[key] for key in sorted(tasks)],
            "dependencies": [{"upstream": left, "downstream": right} for left, right in sorted(dependencies)],
            "references": sorted(references, key=lambda item: (item["kind"], item["value"], item["task_id"])),
            "dynamic": sorted(set(dynamic)),
        }

    def _diff(self, before, after, path):
        result = []
        old_tasks = {item["task_id"]: item for item in before["tasks"]}
        new_tasks = {item["task_id"]: item for item in after["tasks"]}
        for task_id in sorted(set(old_tasks) | set(new_tasks)):
            old, new = old_tasks.get(task_id), new_tasks.get(task_id)
            if old != new:
                result.append(delta(
                    "PipelineTaskDelta", "TASK_ADDED" if old is None else "TASK_REMOVED" if new is None else "TASK_CHANGED",
                    path, old, new, scope=f"task:{task_id}", references=(task_id,),
                    explanation="A statically declared pipeline task changed.",
                ))
        old_deps = {(item["upstream"], item["downstream"]) for item in before["dependencies"]}
        new_deps = {(item["upstream"], item["downstream"]) for item in after["dependencies"]}
        for item in sorted(old_deps - new_deps):
            result.append(delta(
                "PipelineDependencyDelta", "TASK_DEPENDENCY_REMOVED", path, item, None,
                scope="PIPELINE", references=item,
                explanation="A static DAG task dependency was removed.",
            ))
        for item in sorted(new_deps - old_deps):
            result.append(delta(
                "PipelineDependencyDelta", "TASK_DEPENDENCY_ADDED", path, None, item,
                scope="PIPELINE", references=item,
                explanation="A static DAG task dependency was added.",
            ))
        old_refs = {(item["kind"], item["value"], item["task_id"]) for item in before["references"]}
        new_refs = {(item["kind"], item["value"], item["task_id"]) for item in after["references"]}
        for item in sorted(old_refs - new_refs):
            result.append(delta(
                "FieldReferenceDelta" if "field" in item[0] else "DatasetReferenceDelta",
                "DAG_REFERENCE_REMOVED", path, item[1], None,
                scope=f"task:{item[2]}", references=(item[1], item[2]),
                explanation="A static DAG dataset, field, or file reference was removed.",
            ))
        for item in sorted(new_refs - old_refs):
            result.append(delta(
                "FieldReferenceDelta" if "field" in item[0] else "DatasetReferenceDelta",
                "DAG_REFERENCE_ADDED", path, None, item[1],
                scope=f"task:{item[2]}", references=(item[1], item[2]),
                explanation="A static DAG dataset, field, or file reference was added.",
            ))
        return result


def _task(call, variable, reference_keys, dynamic, references):
    operator = _call_name(call.func)
    task_id = None
    static = {}
    for keyword in call.keywords:
        if keyword.arg == "task_id":
            task_id = _literal_string(keyword.value)
            if task_id is None:
                dynamic.append(f"dynamic_task_id@{getattr(keyword.value, 'lineno', 0)}")
        if keyword.arg in reference_keys:
            value = _literal_string(keyword.value)
            if value is None:
                dynamic.append(f"dynamic_{keyword.arg}@{getattr(keyword.value, 'lineno', 0)}")
            else:
                static[keyword.arg] = value
    if task_id is None:
        task_id = variable
    if not task_id:
        return None
    for kind, value in static.items():
        references.append({"kind": kind, "value": value, "task_id": task_id})
    return {"task_id": task_id, "variable": variable, "operator_type": operator, "static_arguments": static}


def _literal_string(node):
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _name(node):
    return node.id if isinstance(node, ast.Name) else None


def _call_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return "UNKNOWN_OPERATOR"


def _empty():
    return {"tasks": [], "dependencies": [], "references": [], "dynamic": []}
