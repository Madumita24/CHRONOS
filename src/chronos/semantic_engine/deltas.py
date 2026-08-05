"""Deterministic AST-contract semantic delta detection."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .models import (
    AggregationChange,
    Delta,
    DeltaScope,
    DeltaType,
    DerivedExpressionChange,
    FilterChange,
    JoinPredicateChange,
    JoinTypeChange,
    JoinedRelationChange,
    OutputColumnAdded,
    OutputColumnRemoved,
    OutputColumnRename,
    OutputOrderChange,
    ParsedModel,
    SemanticDelta,
)
from .serialization import stable_id


def detect_deltas(
    before: ParsedModel,
    after: ParsedModel,
    *,
    model_dataset_urn: str,
) -> tuple[tuple[Delta, ...], tuple[Delta, ...]]:
    semantic: list[Delta] = []
    structural: list[Delta] = []
    before_outputs = {item.output_name: item for item in before.output_columns}
    after_outputs = {item.output_name: item for item in after.output_columns}
    removed = sorted(set(before_outputs) - set(after_outputs))
    added = sorted(set(after_outputs) - set(before_outputs))

    # A one-for-one same-position name change is represented as a rename.
    renamed_removed: set[str] = set()
    renamed_added: set[str] = set()
    for old in removed:
        old_output = before_outputs[old]
        matches = [
            name
            for name in added
            if after_outputs[name].ordinal == old_output.ordinal
            and after_outputs[name].expression_fingerprint
            == old_output.expression_fingerprint
        ]
        if len(matches) == 1:
            new = matches[0]
            structural.append(
                _delta(
                    OutputColumnRename,
                    DeltaType.OUTPUT_COLUMN_RENAME,
                    DeltaScope.STRUCTURAL,
                    model_dataset_urn,
                    old,
                    old,
                    new,
                    (),
                    ("output_identity",),
                    f"Output column {old} was renamed to {new}.",
                )
            )
            renamed_removed.add(old)
            renamed_added.add(new)
    for name in removed:
        if name not in renamed_removed:
            structural.append(
                _delta(
                    OutputColumnRemoved,
                    DeltaType.OUTPUT_COLUMN_REMOVED,
                    DeltaScope.STRUCTURAL,
                    model_dataset_urn,
                    name,
                    asdict(before_outputs[name]),
                    None,
                    _inputs(before_outputs[name]),
                    ("output_identity",),
                    f"Output column {name} was removed.",
                )
            )
    for name in added:
        if name not in renamed_added:
            structural.append(
                _delta(
                    OutputColumnAdded,
                    DeltaType.OUTPUT_COLUMN_ADDED,
                    DeltaScope.STRUCTURAL,
                    model_dataset_urn,
                    name,
                    None,
                    asdict(after_outputs[name]),
                    _inputs(after_outputs[name]),
                    ("output_identity",),
                    f"Output column {name} was added.",
                )
            )

    common = sorted(set(before_outputs) & set(after_outputs))
    for name in common:
        previous = before_outputs[name]
        future = after_outputs[name]
        grouping_changed_for_aggregate = (
            bool(previous.aggregations or future.aggregations)
            and before.grouping != after.grouping
        )
        if (
            previous.expression_fingerprint == future.expression_fingerprint
            and not grouping_changed_for_aggregate
        ):
            continue
        if previous.aggregations != future.aggregations or before.grouping != after.grouping:
            components = _aggregation_components(previous, future, before, after)
            semantic.append(
                _delta(
                    AggregationChange,
                    DeltaType.AGGREGATION_CHANGE,
                    DeltaScope.OUTPUT_FIELD,
                    model_dataset_urn,
                    name,
                    [asdict(item) for item in previous.aggregations],
                    [asdict(item) for item in future.aggregations],
                    tuple(sorted(set(_inputs(previous) + _inputs(future)))),
                    ("before_parsed_model", "after_parsed_model"),
                    f"Aggregation semantics changed for output {name}: {', '.join(components)}.",
                    components=components,
                )
            )
        else:
            components = _expression_components(previous, future)
            semantic.append(
                _delta(
                    DerivedExpressionChange,
                    DeltaType.DERIVED_EXPRESSION_CHANGE,
                    DeltaScope.OUTPUT_FIELD,
                    model_dataset_urn,
                    name,
                    previous.normalized_expression,
                    future.normalized_expression,
                    tuple(sorted(set(_inputs(previous) + _inputs(future)))),
                    ("before_parsed_model", "after_parsed_model"),
                    f"Derived expression semantics changed for output {name}: {', '.join(components)}.",
                    components=components,
                )
            )

    if before.filter_predicate != after.filter_predicate:
        semantic.append(
            _delta(
                FilterChange,
                DeltaType.FILTER_CHANGE,
                DeltaScope.MODEL_WIDE,
                model_dataset_urn,
                None,
                before.filter_predicate,
                after.filter_predicate,
                tuple(
                    sorted(
                        {
                            item.normalized
                            for item in before.filter_columns + after.filter_columns
                        }
                    )
                ),
                ("before_parsed_model", "after_parsed_model"),
                _filter_explanation(before.filter_predicate, after.filter_predicate),
                components=_predicate_components(before, after),
            )
        )

    semantic.extend(_join_deltas(before, after, model_dataset_urn))

    before_order = tuple(item.output_name for item in before.output_columns)
    after_order = tuple(item.output_name for item in after.output_columns)
    if before_order != after_order and set(before_order) == set(after_order):
        structural.append(
            _delta(
                OutputOrderChange,
                DeltaType.OUTPUT_ORDER_CHANGE,
                DeltaScope.STRUCTURAL,
                model_dataset_urn,
                None,
                before_order,
                after_order,
                (),
                ("before_parsed_model", "after_parsed_model"),
                "Output order changed; positional consumer significance is unresolved.",
                certainty="REQUIRES_REVIEW",
            )
        )

    return (
        tuple(sorted(structural, key=lambda item: item.delta_id)),
        tuple(sorted(semantic, key=lambda item: item.delta_id)),
    )


def delta_to_dict(delta: Delta) -> dict[str, Any]:
    value = asdict(delta)
    value["delta_type"] = delta.delta_type.value
    value["scope"] = delta.scope.value
    return value


def _delta(
    cls,
    delta_type,
    scope,
    model_urn,
    output,
    before,
    after,
    inputs,
    evidence,
    explanation,
    *,
    components=(),
    certainty="DERIVED",
):
    delta_id = stable_id(
        "semantic-delta",
        delta_type.value,
        model_urn,
        output or "model",
        repr(before),
        repr(after),
    )
    return cls(
        delta_id=delta_id,
        delta_type=delta_type,
        scope=scope,
        affected_model_urn=model_urn,
        affected_output_field=output,
        before_representation=before,
        after_representation=after,
        input_references=tuple(inputs),
        evidence_references=tuple(evidence),
        certainty=certainty,
        change_components=tuple(components),
        explanation=explanation,
    )


def _inputs(output) -> tuple[str, ...]:
    return tuple(item.normalized for item in output.input_columns)


def _aggregation_components(previous, future, before, after):
    components = []
    before_aggs = previous.aggregations
    after_aggs = future.aggregations
    if not before_aggs and after_aggs:
        components.append("aggregate_added")
    elif before_aggs and not after_aggs:
        components.append("aggregate_removed")
    else:
        before_functions = tuple(item.function for item in before_aggs)
        after_functions = tuple(item.function for item in after_aggs)
        if before_functions != after_functions:
            components.append("function_changed")
        if tuple(item.distinct for item in before_aggs) != tuple(item.distinct for item in after_aggs):
            components.append("distinct_changed")
        if tuple(item.input_references for item in before_aggs) != tuple(item.input_references for item in after_aggs):
            components.append("input_changed")
    if before.grouping != after.grouping:
        components.append("grouping_changed")
    return tuple(components or ("aggregation_expression_changed",))


def _expression_components(previous, future):
    components = []
    if previous.operators != future.operators:
        components.append("operator_changed")
    if previous.functions != future.functions:
        components.append("function_changed")
    if previous.literals != future.literals:
        components.append("literal_changed")
    if previous.input_columns != future.input_columns:
        components.append("referenced_column_changed")
    if previous.has_case != future.has_case or (previous.has_case and previous.normalized_expression != future.normalized_expression):
        components.append("case_structure_changed")
    return tuple(components or ("expression_structure_changed",))


def _predicate_components(before, after):
    if before.filter_predicate is None:
        return ("filter_added",)
    if after.filter_predicate is None:
        return ("filter_removed",)
    components = []
    before_inputs = tuple(item.normalized for item in before.filter_columns)
    after_inputs = tuple(item.normalized for item in after.filter_columns)
    if before_inputs != after_inputs:
        components.append("referenced_column_changed")
    if before.filter_literals != after.filter_literals:
        components.append("literal_changed")
    if before.filter_operators != after.filter_operators:
        components.append("logical_or_comparison_operator_changed")
    components.append("predicate_modified")
    return tuple(components)


def _filter_explanation(before, after):
    if before is None:
        return f"A model-wide filter was added: {after}."
    if after is None:
        return f"The model-wide filter was removed: {before}."
    return f"The model-wide filter changed from {before} to {after}."


def _join_deltas(before, after, model_urn):
    result = []
    length = max(len(before.joins), len(after.joins))
    for ordinal in range(length):
        old = before.joins[ordinal] if ordinal < len(before.joins) else None
        new = after.joins[ordinal] if ordinal < len(after.joins) else None
        if old is None or new is None:
            result.append(
                _delta(
                    JoinTypeChange,
                    DeltaType.JOIN_TYPE_CHANGE,
                    DeltaScope.MODEL_WIDE,
                    model_urn,
                    None,
                    asdict(old) if old else None,
                    asdict(new) if new else None,
                    (),
                    ("before_parsed_model", "after_parsed_model"),
                    "A join was added or removed; row preservation and cardinality are unresolved.",
                    components=("join_added" if old is None else "join_removed",),
                )
            )
            continue
        if old.join_type != new.join_type:
            result.append(
                _delta(
                    JoinTypeChange,
                    DeltaType.JOIN_TYPE_CHANGE,
                    DeltaScope.MODEL_WIDE,
                    model_urn,
                    None,
                    old.join_type,
                    new.join_type,
                    (),
                    ("before_parsed_model", "after_parsed_model"),
                    f"Join type changed from {old.join_type} to {new.join_type}; row preservation may change.",
                    components=("join_type_changed",),
                )
            )
        if old.relation.qualified_name != new.relation.qualified_name:
            result.append(
                _delta(
                    JoinedRelationChange,
                    DeltaType.JOINED_RELATION_CHANGE,
                    DeltaScope.MODEL_WIDE,
                    model_urn,
                    None,
                    old.relation.qualified_name,
                    new.relation.qualified_name,
                    (),
                    ("before_parsed_model", "after_parsed_model"),
                    f"Joined relation changed from {old.relation.qualified_name} to {new.relation.qualified_name}; matching semantics are unresolved.",
                    components=("joined_relation_changed",),
                )
            )
        if old.normalized_predicate != new.normalized_predicate:
            inputs = tuple(
                sorted(
                    {
                        item.normalized
                        for item in old.predicate_columns + new.predicate_columns
                    }
                )
            )
            result.append(
                _delta(
                    JoinPredicateChange,
                    DeltaType.JOIN_PREDICATE_CHANGE,
                    DeltaScope.MODEL_WIDE,
                    model_urn,
                    None,
                    old.normalized_predicate,
                    new.normalized_predicate,
                    inputs,
                    ("before_parsed_model", "after_parsed_model"),
                    "Join matching predicate changed; cardinality and duplicate behavior are unresolved.",
                    components=("join_predicate_changed",),
                )
            )
    return result
