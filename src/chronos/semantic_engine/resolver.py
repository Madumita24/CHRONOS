"""Certified snapshot resolution for SQL model, relations, columns, and outputs."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from chronos.snapshot import CurrentMetadataSnapshot, FieldMachineKey

from .errors import SemanticProposalError, SemanticResolutionError
from .models import (
    OutputMappingState,
    ParsedModel,
    ResolutionState,
    SemanticCodeChangeProposal,
)


_DIALECT_PLATFORMS = {
    "postgres": "postgres",
    "postgresql": "postgres",
    "snowflake": "snowflake",
    "bigquery": "bigquery",
    "mysql": "mysql",
    "redshift": "redshift",
    "spark": "spark",
    "databricks": "databricks",
}


def resolve_semantic_entities(
    snapshot: CurrentMetadataSnapshot,
    proposal: SemanticCodeChangeProposal,
    before: ParsedModel,
    after: ParsedModel,
    *,
    changed_output_names: set[str],
) -> dict[str, Any]:
    _validate_snapshot(snapshot, proposal)
    model_matches = [
        item
        for item in snapshot.datasets
        if item.dataset_urn == proposal.model_dataset_urn
    ]
    if len(model_matches) != 1:
        raise SemanticResolutionError(
            "Target model Dataset must resolve exactly once in the supplied snapshot."
        )
    model = model_matches[0]
    if proposal.model_relation is not None and not _dataset_matches_relation(
        model, proposal.model_relation
    ):
        raise SemanticResolutionError(
            "Proposal model_relation does not match the target Dataset identity."
        )
    before_relations = _resolve_relations(snapshot, before, proposal.sql_dialect)
    after_relations = _resolve_relations(snapshot, after, proposal.sql_dialect)
    before_columns = _resolve_columns(snapshot, before, before_relations)
    after_columns = _resolve_columns(snapshot, after, after_relations)
    star_expansions = _resolve_stars(snapshot, before, before_relations) + _resolve_stars(
        snapshot, after, after_relations
    )
    target_fields = _dataset_field_paths(snapshot, model.dataset_urn)
    output_names = sorted(
        {
            item.output_name
            for item in before.output_columns + after.output_columns
        }
    )
    output_mappings = []
    before_names = {item.output_name for item in before.output_columns}
    after_names = {item.output_name for item in after.output_columns}
    for name in output_names:
        if name in before_names and name not in after_names:
            state = OutputMappingState.REMOVED_OUTPUT
        elif name not in before_names and name in after_names:
            state = OutputMappingState.NEW_OUTPUT
        elif name in target_fields and name in changed_output_names:
            state = OutputMappingState.IDENTITY_PRESERVED_SEMANTICS_CHANGED
        elif name in target_fields:
            state = OutputMappingState.RESOLVED_CURRENT_OUTPUT
        else:
            state = OutputMappingState.UNRESOLVED_OUTPUT
        output_mappings.append(
            {
                "datahub_field_key": (
                    f"{model.dataset_urn}|{name}" if name in target_fields else None
                ),
                "evidence_class": (
                    "OBSERVED_DATAHUB_EVIDENCE"
                    if name in target_fields
                    else "CODE_DERIVED_EVIDENCE"
                ),
                "mapping_state": state.value,
                "output_name": name,
            }
        )
    return {
        "model": {
            "dataset_urn": model.dataset_urn,
            "environment": model.environment,
            "logical_name": model.logical_name,
            "platform": model.platform,
            "resolution_state": ResolutionState.RESOLVED.value,
        },
        "before_relations": before_relations,
        "after_relations": after_relations,
        "before_input_columns": before_columns,
        "after_input_columns": after_columns,
        "output_mappings": output_mappings,
        "star_expansions": star_expansions,
        "unresolved_references": [
            item
            for item in before_columns + after_columns + output_mappings
            if item.get("resolution_state")
            in {
                ResolutionState.NOT_FOUND.value,
                ResolutionState.INSUFFICIENT_METADATA.value,
            }
            or item.get("mapping_state") == OutputMappingState.UNRESOLVED_OUTPUT.value
        ],
    }


def _validate_snapshot(snapshot, proposal):
    if snapshot.semantic_fingerprint != proposal.source_snapshot_fingerprint:
        raise SemanticProposalError(
            "Proposal source_snapshot_fingerprint does not match the supplied snapshot."
        )
    if (
        proposal.source_snapshot_id is not None
        and proposal.source_snapshot_id != snapshot.metadata.snapshot_id
    ):
        raise SemanticProposalError(
            "Proposal source_snapshot_id does not match the supplied snapshot."
        )


def _resolve_relations(snapshot, model, dialect):
    platform = _DIALECT_PLATFORMS.get(dialect.lower())
    if platform is None:
        raise SemanticResolutionError(
            f"Dialect {dialect!r} has no certified DataHub platform mapping."
        )
    result = []
    for relation in model.source_relations:
        if relation.is_cte:
            result.append(
                {
                    "alias": relation.alias,
                    "code_relation": relation.qualified_name,
                    "dataset_urn": None,
                    "evidence_class": "CODE_DERIVED_EVIDENCE",
                    "resolution_state": ResolutionState.RESOLVED.value,
                    "resolution_type": "CTE_SCOPE",
                }
            )
            continue
        candidates = [
            item
            for item in snapshot.datasets
            if item.platform.lower() == platform
            and _dataset_matches_relation(item, relation.qualified_name)
        ]
        if len(candidates) != 1:
            state = (
                ResolutionState.AMBIGUOUS
                if len(candidates) > 1
                else ResolutionState.NOT_FOUND
            )
            raise SemanticResolutionError(
                f"Relation {relation.qualified_name!r} resolved as {state.value} for platform {platform}."
            )
        result.append(
            {
                "alias": relation.alias,
                "code_relation": relation.qualified_name,
                "dataset_urn": candidates[0].dataset_urn,
                "evidence_class": "OBSERVED_DATAHUB_EVIDENCE",
                "resolution_state": ResolutionState.RESOLVED.value,
                "resolution_type": "EXACT_PLATFORM_RELATION",
            }
        )
    return result


def _resolve_columns(snapshot, model, relations):
    aliases = {item["alias"]: item for item in relations}
    observed_relations = [item for item in relations if item["dataset_urn"]]
    references = {
        (item.name, item.qualifier, item.normalized)
        for output in model.output_columns
        for item in output.input_columns
    }
    references.update(
        (item.name, item.qualifier, item.normalized)
        for item in model.filter_columns
    )
    for join in model.joins:
        references.update(
            (item.name, item.qualifier, item.normalized)
            for item in join.predicate_columns
        )
    result = []
    for name, qualifier, normalized in sorted(
        references, key=lambda item: (item[1] or "", item[0], item[2])
    ):
        if qualifier:
            relation = aliases.get(qualifier)
            if relation is None:
                raise SemanticResolutionError(
                    f"Column {normalized!r} uses unknown relation alias {qualifier!r}."
                )
            candidates = [relation] if relation["dataset_urn"] else []
        else:
            if len(observed_relations) != 1:
                raise SemanticResolutionError(
                    f"Unqualified column {name!r} is ambiguous across {len(observed_relations)} relations."
                )
            candidates = observed_relations
        if not candidates:
            result.append(
                {
                    "code_reference": normalized,
                    "datahub_field_key": None,
                    "dataset_urn": None,
                    "evidence_class": "CODE_DERIVED_EVIDENCE",
                    "resolution_state": ResolutionState.INSUFFICIENT_METADATA.value,
                }
            )
            continue
        dataset_urn = candidates[0]["dataset_urn"]
        fields = _dataset_field_paths(snapshot, dataset_urn)
        found = name.lower() in fields
        result.append(
            {
                "code_reference": normalized,
                "datahub_field_key": (
                    f"{dataset_urn}|{name.lower()}" if found else None
                ),
                "dataset_urn": dataset_urn,
                "evidence_class": (
                    "OBSERVED_DATAHUB_EVIDENCE"
                    if found
                    else "CODE_DERIVED_EVIDENCE"
                ),
                "resolution_state": (
                    ResolutionState.RESOLVED.value
                    if found
                    else ResolutionState.INSUFFICIENT_METADATA.value
                ),
            }
        )
    return result


def _resolve_stars(snapshot, model, relations):
    if not model.unresolved_stars:
        return []
    observed = [item for item in relations if item["dataset_urn"]]
    if len(observed) != 1:
        raise SemanticResolutionError(
            "SELECT * expansion requires exactly one resolved source relation."
        )
    fields = sorted(_dataset_field_paths(snapshot, observed[0]["dataset_urn"]))
    if not fields:
        raise SemanticResolutionError(
            "SELECT * cannot be expanded because the certified snapshot has no source schema."
        )
    return [
        {
            "dataset_urn": observed[0]["dataset_urn"],
            "evidence_class": "COUNTERFACTUAL_DERIVATION",
            "expanded_field_paths": fields,
            "star": star,
        }
        for star in model.unresolved_stars
    ]


def _dataset_field_paths(snapshot, dataset_urn):
    values = {
        item.key.field_path.lower()
        for item in snapshot.fields
        if item.key.dataset_urn == dataset_urn
    }
    dataset = next(
        (item for item in snapshot.datasets if item.dataset_urn == dataset_urn),
        None,
    )
    if dataset:
        values.update(item.lower() for item in dataset.schema_field_paths)
        values.update(item.field_path.lower() for item in dataset.lineage_field_keys)
    if snapshot.source_schema.dataset_urn == dataset_urn:
        values.update(item.field_path.lower() for item in snapshot.source_schema.fields)
    return values


def _dataset_matches_relation(dataset, relation):
    relation = relation.strip('"`[]').lower()
    candidates = {
        value.lower()
        for value in (dataset.qualified_name, dataset.logical_name)
        if isinstance(value, str) and value
    }
    urn_name = _urn_dataset_name(dataset.dataset_urn)
    if urn_name:
        candidates.add(urn_name.lower())
    expanded = set(candidates)
    for candidate in candidates:
        parts = candidate.split(".")
        if parts and parts[0].startswith("b2fd91"):
            expanded.add(".".join(parts[1:]))
        expanded.add(parts[-1])
    return relation in expanded


def _urn_dataset_name(urn):
    try:
        body = urn[len("urn:li:dataset:(") : -1]
        return body.split(",", 2)[1]
    except (IndexError, AttributeError):
        return None
