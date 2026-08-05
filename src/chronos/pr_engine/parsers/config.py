"""Safe bounded dbt-schema, contract, pipeline, and quality parsers."""

from __future__ import annotations

import json
from typing import Any

import yaml

from chronos.structural_engine.serialization import canonicalize, stable_id

from ..errors import FileParseError
from ..models import FileCategory
from .common import delta, file_result


def safe_document(content: str | None, path: str) -> Any:
    if content is None:
        return None
    if "{{" in content or "{%" in content or "{#" in content:
        raise FileParseError(f"Dynamic Jinja is unsupported in {path!r}.")
    try:
        value = json.loads(content) if path.lower().endswith(".json") else yaml.safe_load(content)
    except (json.JSONDecodeError, yaml.YAMLError) as exc:
        raise FileParseError(f"Invalid bounded YAML/JSON in {path!r}.") from exc
    if value is not None and not isinstance(value, dict):
        raise FileParseError(f"Bounded YAML/JSON root must be an object in {path!r}.")
    return value or {}


class DbtSchemaParser:
    name = "bounded_dbt_schema"
    version = "6.3.0/pyyaml-6.0.3"
    categories = {FileCategory.DBT_SCHEMA}

    def parse(self, payload, **_):
        path = payload.record.head_path or payload.record.base_path
        before = _dbt_representation(safe_document(payload.base_content, path)) if payload.base_content is not None else None
        after = _dbt_representation(safe_document(payload.head_content, path)) if payload.head_content is not None else None
        deltas = _diff_dbt(before or {"models": {}}, after or {"models": {}}, path)
        evidence = [{
            "evidence_id": stable_id("pr-evidence", payload.record.file_change_id, "dbt-schema"),
            "evidence_class": "CODE_DERIVED_EVIDENCE",
            "parser": self.version,
        }]
        return file_result(payload, self.name, self.version, before, after, deltas, evidence=evidence)


class BoundedConfigParser:
    name = "bounded_contract_pipeline_config"
    version = "6.3.0/pyyaml-6.0.3"
    categories = {
        FileCategory.SCHEMA_CONTRACT, FileCategory.PIPELINE_CONFIG,
        FileCategory.QUALITY_CONFIG, FileCategory.DOCUMENTATION_ONLY,
    }
    _REFERENCE_KEYS = {
        "source_dataset", "target_dataset", "input_dataset", "output_dataset",
        "dataset", "relation", "model", "model_file", "contract_file",
        "source_field", "target_field", "field", "expected_field_name",
        "validation_target", "expected_type", "dependency", "output_field",
        "input_field",
    }
    _CONTRACT_KEYS = {
        "dataset", "model", "fields", "type", "nullable", "unique",
        "accepted_values", "semantic_definition", "owner", "criticality",
        "compatibility_guarantees", "description", "enforced",
    }

    def parse(self, payload, **_):
        path = payload.record.head_path or payload.record.base_path
        if payload.record.category is FileCategory.DOCUMENTATION_ONLY:
            before = {"documentation_fingerprint": _documentation_value(payload.base_content)} if payload.base_content is not None else None
            after = {"documentation_fingerprint": _documentation_value(payload.head_content)} if payload.head_content is not None else None
            deltas = [] if before == after else [delta(
                "DocumentationOnlyDelta", "DOCUMENTATION_CHANGED", path,
                before, after, scope="FILE", material=False,
                explanation="Documentation changed without a supported technical claim.",
            )]
        else:
            before_doc = safe_document(payload.base_content, path) if payload.base_content is not None else None
            after_doc = safe_document(payload.head_content, path) if payload.head_content is not None else None
        if payload.record.category is FileCategory.SCHEMA_CONTRACT:
            before = _contract(before_doc or {}, self._CONTRACT_KEYS)
            after = _contract(after_doc or {}, self._CONTRACT_KEYS)
            deltas = _diff_contract(before, after, path)
        elif payload.record.category not in {FileCategory.DOCUMENTATION_ONLY}:
            before = {"references": _references(before_doc or {}, self._REFERENCE_KEYS)}
            after = {"references": _references(after_doc or {}, self._REFERENCE_KEYS)}
            deltas = _diff_references(before["references"], after["references"], path, payload.record.category)
            if not deltas and canonicalize(before_doc) != canonicalize(after_doc):
                deltas = [delta(
                    "DocumentationOnlyDelta", "CONFIG_DOCUMENTATION_CHANGED", path,
                    before, after, scope="FILE", material=False,
                    explanation="Configuration text changed without changing an allowlisted static reference.",
                )]
        return file_result(
            payload, self.name, self.version, before, after, deltas,
            evidence=[{
                "evidence_id": stable_id("pr-evidence", payload.record.file_change_id, "bounded-config"),
                "evidence_class": "CODE_DERIVED_EVIDENCE", "parser": self.version,
            }],
        )


def _dbt_representation(value: dict[str, Any]) -> dict[str, Any]:
    allowed_root = {"version", "models"}
    if set(value) - allowed_root or not isinstance(value.get("models", []), list):
        raise FileParseError("dbt schema supports only version and models at the root.")
    models = {}
    for raw_model in value.get("models", []):
        if not isinstance(raw_model, dict) or not isinstance(raw_model.get("name"), str):
            raise FileParseError("Each dbt schema model requires a static name.")
        columns = {}
        for raw_column in raw_model.get("columns", []) or []:
            if not isinstance(raw_column, dict) or not isinstance(raw_column.get("name"), str):
                raise FileParseError("Each dbt schema column requires a static name.")
            tests = raw_column.get("data_tests", raw_column.get("tests", [])) or []
            columns[raw_column["name"]] = {
                "name": raw_column["name"],
                "data_type": raw_column.get("data_type"),
                "description": raw_column.get("description"),
                "tests": canonicalize(tests),
                "constraints": canonicalize(raw_column.get("constraints", [])),
                "meta": canonicalize(raw_column.get("meta", {})),
                "tags": sorted(raw_column.get("tags", []) or []),
            }
        config = raw_model.get("config", {}) or {}
        contract = config.get("contract", {}) if isinstance(config, dict) else {}
        models[raw_model["name"]] = {
            "name": raw_model["name"],
            "description": raw_model.get("description"),
            "columns": columns,
            "contract_enforced": contract.get("enforced") if isinstance(contract, dict) else None,
            "constraints": canonicalize(raw_model.get("constraints", [])),
            "tests": canonicalize(raw_model.get("data_tests", raw_model.get("tests", [])) or []),
            "meta": canonicalize(raw_model.get("meta", {})),
            "tags": sorted(raw_model.get("tags", []) or []),
        }
    return {"models": models}


def _diff_dbt(before, after, path):
    result = []
    old_models, new_models = before["models"], after["models"]
    for name in sorted(set(old_models) | set(new_models)):
        old, new = old_models.get(name), new_models.get(name)
        if old is None or new is None:
            result.append(delta(
                "ModelContractDelta", "MODEL_ADDED" if old is None else "MODEL_REMOVED",
                path, old, new, scope=f"model:{name}", references=(name,),
                explanation="A dbt schema model declaration was added or removed.",
            ))
            continue
        old_columns, new_columns = old["columns"], new["columns"]
        for column in sorted(set(old_columns) | set(new_columns)):
            left, right = old_columns.get(column), new_columns.get(column)
            if left is None or right is None:
                result.append(delta(
                    "ModelContractDelta", "COLUMN_ADDED" if left is None else "COLUMN_REMOVED",
                    path, left, right, scope=f"model:{name}:column:{column}",
                    references=(name, column),
                    explanation="A dbt schema column declaration was added or removed.",
                ))
                continue
            if left.get("data_type") != right.get("data_type"):
                result.append(delta(
                    "ModelContractDelta", "DECLARED_TYPE_CHANGED", path,
                    left.get("data_type"), right.get("data_type"),
                    scope=f"model:{name}:column:{column}", references=(name, column),
                    explanation="The declared dbt column type changed.",
                ))
            for key in ("tests", "constraints"):
                if left[key] != right[key]:
                    result.append(delta(
                        "QualityExpectationDelta", f"COLUMN_{key.upper()}_CHANGED", path,
                        left[key], right[key], scope=f"model:{name}:column:{column}",
                        references=(name, column),
                        explanation="A dbt quality expectation or constraint changed.",
                    ))
            non_doc = {key: value for key, value in left.items() if key != "description"}
            new_non_doc = {key: value for key, value in right.items() if key != "description"}
            if non_doc == new_non_doc and left.get("description") != right.get("description"):
                result.append(delta(
                    "DocumentationOnlyDelta", "COLUMN_DESCRIPTION_CHANGED", path,
                    left.get("description"), right.get("description"),
                    scope=f"model:{name}:column:{column}", references=(name, column), material=False,
                    explanation="Only the dbt column description changed.",
                ))
        if old["contract_enforced"] != new["contract_enforced"]:
            result.append(delta(
                "ModelContractDelta", "CONTRACT_ENFORCEMENT_CHANGED", path,
                old["contract_enforced"], new["contract_enforced"], scope=f"model:{name}",
                references=(name,), explanation="dbt model contract enforcement changed.",
            ))
        if old["tests"] != new["tests"] or old["constraints"] != new["constraints"]:
            result.append(delta(
                "QualityExpectationDelta", "MODEL_QUALITY_EXPECTATION_CHANGED", path,
                {"tests": old["tests"], "constraints": old["constraints"]},
                {"tests": new["tests"], "constraints": new["constraints"]},
                scope=f"model:{name}", references=(name,),
                explanation="dbt model-level tests or constraints changed.",
            ))
    return result


def _contract(value, allowed):
    if set(value) != {"contract"} or not isinstance(value["contract"], dict):
        raise FileParseError("Generic contract requires exactly one contract root object.")
    contract = value["contract"]
    if set(contract) - allowed:
        raise FileParseError("Generic contract contains unsupported properties.")
    if not any(key in contract for key in ("dataset", "model")):
        raise FileParseError("Generic contract requires dataset or model identity.")
    return canonicalize(contract)


def _diff_contract(before, after, path):
    if before == after:
        return []
    result = []
    keys = sorted(set(before) | set(after))
    technical = [key for key in keys if key not in {"description", "owner"} and before.get(key) != after.get(key)]
    documentation = [key for key in keys if key in {"description", "owner"} and before.get(key) != after.get(key)]
    if technical:
        result.append(delta(
            "ModelContractDelta", "CONTRACT_CHANGED", path,
            {key: before.get(key) for key in technical},
            {key: after.get(key) for key in technical},
            scope="CONTRACT", references=tuple(str(before.get(key) or after.get(key)) for key in ("dataset", "model") if before.get(key) or after.get(key)),
            explanation="A bounded contract guarantee changed.",
        ))
    if documentation:
        result.append(delta(
            "DocumentationOnlyDelta", "CONTRACT_DOCUMENTATION_CHANGED", path,
            {key: before.get(key) for key in documentation},
            {key: after.get(key) for key in documentation},
            scope="CONTRACT", material=False,
            explanation="Only contract documentation or ownership text changed.",
        ))
    return result


def _references(value, allowed, prefix=""):
    result = []
    if isinstance(value, dict):
        for key in sorted(value):
            item = value[key]
            current = f"{prefix}.{key}" if prefix else key
            if key in allowed:
                if isinstance(item, str):
                    result.append({"kind": key, "value": item, "location": current})
                elif isinstance(item, list) and all(isinstance(entry, str) for entry in item):
                    result.extend({"kind": key, "value": entry, "location": current} for entry in item)
                else:
                    result.append({"kind": key, "value": None, "location": current, "dynamic": True})
            else:
                result.extend(_references(item, allowed, current))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            result.extend(_references(item, allowed, f"{prefix}[{index}]"))
    return sorted(result, key=lambda item: (item["kind"], str(item["value"]), item["location"]))


def _diff_references(before, after, path, category):
    old = {(item["kind"], item.get("value"), item["location"]) for item in before}
    new = {(item["kind"], item.get("value"), item["location"]) for item in after}
    result = []
    for item in sorted(old - new, key=str):
        kind, value, location = item
        klass = _reference_class(kind, category)
        result.append(delta(
            klass, "STATIC_REFERENCE_REMOVED", path, value, None,
            scope=location, references=tuple(filter(None, (value,))),
            explanation="An allowlisted static configuration reference was removed.",
        ))
    for item in sorted(new - old, key=str):
        kind, value, location = item
        klass = _reference_class(kind, category)
        result.append(delta(
            klass, "STATIC_REFERENCE_ADDED", path, None, value,
            scope=location, references=tuple(filter(None, (value,))),
            explanation="An allowlisted static configuration reference was added.",
        ))
    return result


def _reference_class(kind, category):
    if category is FileCategory.QUALITY_CONFIG:
        return "QualityExpectationDelta"
    if "field" in kind or kind == "validation_target":
        return "FieldReferenceDelta"
    if kind in {"dependency", "model_file", "contract_file"}:
        return "ConfigurationDelta"
    return "DatasetReferenceDelta"


def _documentation_value(content):
    if content is None:
        return None
    lines = [line.strip() for line in content.replace("\r\n", "\n").split("\n")]
    return "\n".join(line for line in lines if line)
