"""Adapter that reuses the Phase 6.2 SQL/dbt parser, deltas, and resolver."""

from __future__ import annotations

import json

from chronos.semantic_engine.deltas import delta_to_dict, detect_deltas
from chronos.semantic_engine.intake import resolve_bounded_dbt_sql
from chronos.semantic_engine.models import SemanticCodeChangeProposal, SemanticOperation
from chronos.semantic_engine.parser import parse_model, parsed_model_to_dict
from chronos.semantic_engine.resolver import resolve_semantic_entities
from chronos.structural_engine.serialization import stable_id

from ..errors import FileParseError, PullRequestResolutionError
from ..models import FileCategory
from .common import delta, file_result


class SqlModelParser:
    name = "phase_6_2_sql_adapter"
    version = "6.3.0/sqlglot-30.13.0"
    categories = {FileCategory.SQL_MODEL, FileCategory.DBT_MODEL}

    def parse(self, payload, *, snapshot, proposal, all_payloads):
        path = payload.record.head_path or payload.record.base_path
        mappings = {item.path: item for item in proposal.file_model_mappings}
        mapping = mappings.get(path)
        manifest_base = manifest_head = None
        if mapping and mapping.dbt_manifest_path:
            manifest_payload = next(
                (
                    item for item in all_payloads
                    if mapping.dbt_manifest_path in {item.record.base_path, item.record.head_path}
                ),
                None,
            )
            if manifest_payload is None:
                raise FileParseError("Mapped dbt manifest is absent from the bounded change set.")
            try:
                manifest_base = json.loads(manifest_payload.base_content) if manifest_payload.base_content else None
                manifest_head = json.loads(manifest_payload.head_content) if manifest_payload.head_content else None
            except json.JSONDecodeError as exc:
                raise FileParseError("Mapped dbt manifest is invalid JSON.") from exc
        try:
            before_sql, before_refs, _ = resolve_bounded_dbt_sql(payload.base_content or "", manifest_base)
            after_sql, after_refs, _ = resolve_bounded_dbt_sql(payload.head_content or "", manifest_head)
            before = parse_model(before_sql, dialect=mapping.sql_dialect if mapping else "postgres") if payload.base_content is not None else None
            after = parse_model(after_sql, dialect=mapping.sql_dialect if mapping else "postgres") if payload.head_content is not None else None
        except Exception as exc:
            if isinstance(exc, FileParseError):
                raise
            raise FileParseError(f"SQL/dbt file {path!r} failed bounded parsing: {exc}") from exc
        detected = []
        structural = semantic = ()
        model_urn = mapping.model_dataset_urn if mapping else "UNRESOLVED_MODEL"
        if before and after:
            structural, semantic = detect_deltas(before, after, model_dataset_urn=model_urn)
            for item in structural:
                value = delta_to_dict(item)
                value["delta_class"] = "StructuralFieldDelta"
                value["material"] = item.delta_type.value != "OUTPUT_ORDER_CHANGE"
                value["file_path"] = path
                detected.append(value)
            for item in semantic:
                value = delta_to_dict(item)
                value["delta_class"] = "SemanticSqlDelta"
                value["material"] = True
                value["file_path"] = path
                detected.append(value)
        else:
            active = after or before
            action = "MODEL_ADDED" if after else "MODEL_REMOVED"
            for output in active.output_columns:
                detected.append(
                    delta(
                        "StructuralFieldDelta", action, path,
                        None if after else output.output_name,
                        output.output_name if after else None,
                        scope="MODEL", references=(model_urn, output.output_name),
                        explanation=f"SQL model output participates in a {action.lower().replace('_', ' ')}.",
                    )
                )
        resolved = []
        unresolved = []
        if mapping and before and after:
            semantic_proposal = SemanticCodeChangeProposal(
                proposal_id=proposal.proposal_id,
                analysis_id=proposal.analysis_id,
                operation=SemanticOperation.SEMANTIC_CODE_CHANGE,
                model_dataset_urn=mapping.model_dataset_urn,
                sql_dialect=mapping.sql_dialect,
                before_code_reference=path,
                after_code_reference=path,
                source_snapshot_fingerprint=proposal.source_snapshot_fingerprint,
                source_snapshot_id=proposal.source_snapshot_id,
                model_relation=mapping.model_relation,
            )
            changed = {
                item.get("affected_output_field")
                for item in detected
                if item.get("affected_output_field")
            }
            try:
                resolution = resolve_semantic_entities(
                    snapshot, semantic_proposal, before, after,
                    changed_output_names=changed,
                )
            except Exception as exc:
                raise PullRequestResolutionError(
                    f"SQL file {path!r} could not resolve certified model identity: {exc}"
                ) from exc
            resolved = [resolution["model"], *resolution["before_relations"], *resolution["after_relations"], *resolution["output_mappings"]]
            unresolved = resolution["unresolved_references"]
        elif mapping:
            resolved = [{
                "dataset_urn": mapping.model_dataset_urn,
                "model_relation": mapping.model_relation,
                "resolution_state": "RESOLVED",
                "evidence_class": "OBSERVED_DATAHUB_EVIDENCE",
            }]
        else:
            unresolved = [{
                "code_reference": path,
                "resolution_state": "INSUFFICIENT_METADATA",
                "reason": "No exact file_model_mapping was supplied.",
            }]
        evidence = [{
            "evidence_id": stable_id("pr-evidence", payload.record.file_change_id, "sql-ast"),
            "evidence_class": "CODE_DERIVED_EVIDENCE",
            "parser": self.version,
            "dbt_references": sorted(set(before_refs + after_refs)),
        }]
        return file_result(
            payload, self.name, self.version,
            parsed_model_to_dict(before) if before else None,
            parsed_model_to_dict(after) if after else None,
            detected, resolved_entities=resolved, unresolved_references=unresolved,
            evidence=evidence,
        )
