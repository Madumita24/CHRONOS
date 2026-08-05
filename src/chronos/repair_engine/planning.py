"""Evidence-backed repairability classification and immutable plan construction."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import replace
from typing import Any

from chronos.pr_engine.parsers.config import safe_document
from chronos.structural_engine.serialization import stable_id

from .errors import RepairPlanningError, RepairSelectionError
from .models import (
    MAX_REPAIR_ACTIONS,
    EditOperation,
    RepairAction,
    RepairCompleteness,
    RepairDisposition,
    RepairGenerationProposal,
    RepairMode,
    RepairPlan,
    RepairabilityClassification,
    RepairabilityState,
)
from .proposals import proposal_metadata
from .rules import RepairRuleRegistry
from .trust import TrustedPredecessor


_CATEGORY_ORDER = {
    "SQL_MODEL": 10,
    "DBT_MODEL": 10,
    "DBT_SCHEMA": 20,
    "SCHEMA_CONTRACT": 20,
    "PIPELINE_CONFIG": 30,
    "PIPELINE_DAG": 30,
    "QUALITY_CONFIG": 40,
}
_SEMANTIC_ROOTS = {
    "SEMANTIC_DEFINITION_CHANGED",
}


def build_repair_plan(
    predecessor: TrustedPredecessor,
    proposal: RepairGenerationProposal,
    registry: RepairRuleRegistry,
) -> tuple[RepairPlan, RepairCompleteness, RepairDisposition]:
    roots = predecessor.artifacts["technical_impact_analysis.json"]["root_causes"]
    groups = predecessor.artifacts["logical_change_groups.json"]["groups"]
    selected = _select_roots(roots, groups, proposal)
    inventory = {
        item["file_change_id"]: item
        for item in predecessor.artifacts["changed_file_inventory.json"]["files"]
    }
    results = {
        item["file_change_id"]: item
        for item in predecessor.artifacts["file_analysis_results.json"]["results"]
    }
    classifications: list[RepairabilityClassification] = []
    actions: list[RepairAction] = []
    for root in selected:
        classification, root_actions = _classify_root(
            predecessor, proposal, registry, root, groups, inventory, results
        )
        classifications.append(classification)
        actions.extend(root_actions)
    if len(actions) > MAX_REPAIR_ACTIONS:
        raise RepairPlanningError("Repair action count exceeds the certified limit.")
    actions = _with_dependencies(actions)
    order = _topological_order(actions)
    action_by_id = {item.repair_action_id: item for item in actions}
    actions = [action_by_id[item] for item in order]
    addressed = {
        item.root_cause_id for item in actions
    }
    repairable_selected = {
        item.root_cause_id for item in classifications
        if item.repairability in {
            RepairabilityState.AUTO_REPAIRABLE,
            RepairabilityState.CONDITIONALLY_REPAIRABLE,
        }
    }
    has_non_repairable_selected = any(
        item.repairability not in {
            RepairabilityState.AUTO_REPAIRABLE,
            RepairabilityState.CONDITIONALLY_REPAIRABLE,
        }
        for item in classifications
    )
    if not actions:
        completeness = RepairCompleteness.NO_SUPPORTED_REPAIR
    elif repairable_selected <= addressed and not has_non_repairable_selected:
        completeness = RepairCompleteness.FULLY_ADDRESSED_SELECTED_ROOTS
    else:
        completeness = RepairCompleteness.PARTIALLY_ADDRESSED_SELECTED_ROOTS
    conflict_blocked = any(
        item.repairability is RepairabilityState.BLOCKED_BY_CONFLICT
        for item in classifications
    )
    non_actionable = any(
        item.repairability not in {
            RepairabilityState.AUTO_REPAIRABLE,
            RepairabilityState.CONDITIONALLY_REPAIRABLE,
        }
        for item in classifications
    )
    if conflict_blocked and not actions:
        disposition = RepairDisposition.REPAIR_BLOCKED_BY_CONFLICT
    elif not actions:
        disposition = RepairDisposition.NO_SUPPORTED_AUTOMATIC_REPAIR
    elif non_actionable or completeness is RepairCompleteness.PARTIALLY_ADDRESSED_SELECTED_ROOTS:
        disposition = RepairDisposition.PARTIAL_REPAIR_CANDIDATE
    else:
        disposition = RepairDisposition.REPAIR_CANDIDATE_READY_FOR_REVIEW
    blocked_states = {
        RepairabilityState.BLOCKED_BY_CONFLICT,
        RepairabilityState.BLOCKED_BY_MISSING_EVIDENCE,
        RepairabilityState.UNSUPPORTED,
    }
    manual = tuple(
        sorted(
            item.root_cause_id for item in classifications
            if item.repairability is RepairabilityState.MANUAL_DECISION_REQUIRED
        )
    )
    blocked = tuple(
        sorted(
            item.root_cause_id for item in classifications
            if item.repairability in blocked_states
        )
    )
    limitations = {
        uncertainty
        for item in classifications
        for uncertainty in item.remaining_uncertainty
    }
    phase7 = {
        requirement
        for action in actions
        for requirement in action.remaining_evidence_requirements
    } | {
        "apply_candidate_patch_in_disposable_checkout",
        "execute_affected_project_validation",
        "verify_runtime_and_data_semantics",
        "obtain_human_review_and_owner_approval",
    }
    plan = RepairPlan(
        repair_analysis_id=proposal.repair_analysis_id,
        predecessor_analysis_id=proposal.predecessor_analysis_id,
        selected_root_cause_ids=tuple(item["root_cause_id"] for item in selected),
        classifications=tuple(classifications),
        repair_actions=tuple(actions),
        non_repairable_root_ids=manual,
        blocked_root_ids=blocked,
        affected_files=tuple(sorted({item.target_path for item in actions})),
        edit_dependencies=tuple(
            {"action_id": action.repair_action_id, "depends_on": dependency}
            for action in actions for dependency in action.dependency_actions
        ),
        application_order=tuple(order),
        expected_repository_coherence_improvement=(
            "deterministic_projected_reanalysis_required" if actions else "none"
        ),
        expected_compatibility_limitations=tuple(sorted(limitations)),
        required_human_decisions=manual,
        required_phase_7_validations=tuple(sorted(phase7)),
        warnings=(
            "candidate_repairs_are_unapplied",
            "runtime_correctness_unverified",
            "human_review_required",
        ),
    )
    return plan, completeness, disposition


def _select_roots(roots, groups, proposal):
    root_by_id = {item["root_cause_id"]: item for item in roots}
    group_by_id = {item["logical_change_id"]: item for item in groups}
    if proposal.repair_mode is RepairMode.ALL_SUPPORTED:
        return sorted(roots, key=lambda item: item["root_cause_id"])
    if proposal.repair_mode is RepairMode.SELECTED_ROOTS:
        unknown = set(proposal.target_root_cause_ids) - set(root_by_id)
        if unknown:
            raise RepairSelectionError(f"Unknown predecessor root IDs: {sorted(unknown)}")
        return [root_by_id[item] for item in proposal.target_root_cause_ids]
    unknown = set(proposal.target_logical_change_group_ids) - set(group_by_id)
    if unknown:
        raise RepairSelectionError(f"Unknown predecessor logical group IDs: {sorted(unknown)}")
    selected_groups = [group_by_id[item] for item in proposal.target_logical_change_group_ids]
    selected = []
    for root in roots:
        if any(_root_matches_group(root, group) for group in selected_groups):
            selected.append(root)
    return sorted(selected, key=lambda item: item["root_cause_id"])


def _classify_root(predecessor, proposal, registry, root, groups, inventory, results):
    root_id = root["root_cause_id"]
    root_type = root["root_type"]
    group = _group_for_root(root, groups)
    group_id = group.get("logical_change_id") if group else root.get("logical_change_id")
    evidence = [root_id, *root.get("delta_ids", []), *root.get("contributing_file_ids", [])]
    if root_type == "CONFLICTING_FUTURE_FIELD_IDENTITIES" or (
        group and len(group.get("future_fields", [])) > 1
    ):
        return _classification(
            root, RepairabilityState.BLOCKED_BY_CONFLICT,
            "repair.blocked.explicit-conflict.v1", evidence,
            ("one_separately_validated_authoritative_future_identity",),
            "The certified predecessor preserves competing future identities; Phase 6.4 cannot choose one.",
            (), ("authoritative_future_identity",), group_id,
        ), []
    if _root_has_dynamic_target(root, results):
        return _classification(
            root, RepairabilityState.UNSUPPORTED,
            "repair.unsupported.dynamic-reference.v1", evidence,
            ("static_parser_confirmed_target",),
            "The contributing file contains an unresolved dynamic expression.",
            (), ("runtime_generated_reference",), group_id,
        ), []
    if root_type in _SEMANTIC_ROOTS:
        return _classification(
            root, RepairabilityState.MANUAL_DECISION_REQUIRED,
            "repair.manual.semantic-intent.v1", evidence,
            ("certified_expected_semantic_definition", "owner_approval"),
            "Aggregation, filter, join, expression, or metric intent is not repaired automatically.",
            (), ("product_or_model_owner_intent", "runtime_semantic_validation"), group_id,
        ), []
    if root_type == "STALE_PIPELINE_OR_QUALITY_REFERENCE":
        return _classify_stale(
            predecessor, registry, root, group, inventory, results
        )
    delete = _delete_transition(predecessor, root)
    if delete is not None:
        return _classify_delete(
            predecessor, proposal, registry, root, group, inventory, results, delete
        )
    type_transition = _declared_type_transition(predecessor, root)
    if type_transition is not None:
        return _classify_type(
            predecessor, proposal, registry, root, group, inventory, results,
            type_transition,
        )
    if root_type in {
        "STRUCTURAL_CHANGE", "CONTRACT_CHANGE", "QUALITY_EXPECTATION_CHANGED",
        "FIELD_REFERENCE_CHANGED", "DATASET_REFERENCE_CHANGED", "CONFIGURATION_CHANGED",
        "PIPELINE_TASK_CHANGED", "PIPELINE_DEPENDENCY_CHANGED",
    }:
        return _classification(
            root, RepairabilityState.MANUAL_DECISION_REQUIRED,
            "repair.manual.change-source-or-intent.v1", evidence,
            ("one_exact_stale_target_or_approved_intent",),
            "This root records a proposed change or unresolved intent, not an independently proven stale target.",
            tuple(sorted({inventory[item]["category"] for item in root.get("contributing_file_ids", []) if item in inventory})),
            ("repair_target_not_established", "runtime_validation"), group_id,
        ), []
    return _classification(
        root, RepairabilityState.UNSUPPORTED,
        "repair.unsupported.root-type.v1", evidence, (),
        "The predecessor root type has no registered deterministic repair rule.",
        (), ("unsupported_root_type",), group_id,
    ), []


def _classify_stale(predecessor, registry, root, group, inventory, results):
    root_id = root["root_cause_id"]
    if not group or len(group.get("future_fields", [])) != 1 or not group.get("current_field"):
        return _classification(
            root, RepairabilityState.BLOCKED_BY_MISSING_EVIDENCE,
            "repair.blocked.missing-coherent-identity.v1", (root_id,),
            ("one_coherent_future_identity",),
            "The stale root cannot be bound to one coherent current/future identity.",
            (), ("coherent_future_identity",), root.get("logical_change_id"),
        ), []
    current = group["current_field"]
    future = group["future_fields"][0]
    file_ids = root.get("contributing_file_ids", [])
    if len(file_ids) != 1 or file_ids[0] not in inventory:
        return _ambiguous_target(root, group, "Stale root does not identify exactly one changed file.")
    file_id = file_ids[0]
    record = inventory[file_id]
    parsed = results[file_id]
    matches = _parsed_reference_matches(parsed.get("parsed_head"), current)
    if len(matches) != 1:
        return _ambiguous_target(
            root, group, "Stale repair requires exactly one parser-confirmed current reference."
        )
    match = matches[0]
    dataset_kinds = {
        "source_dataset", "target_dataset", "input_dataset", "output_dataset",
        "dataset", "relation", "model", "model_file", "contract_file",
    }
    rule_prefix = (
        "repair.stale-dataset."
        if match.get("kind") in dataset_kinds
        else "repair.stale-field."
    )
    rules = tuple(
        item for item in registry.for_target(root["root_type"], record["category"])
        if item.repair_rule_id.startswith(rule_prefix)
    )
    if len(rules) != 1:
        return _ambiguous_target(
            root, group, "No unique repair rule supports the stale file category."
        )
    rule = rules[0]
    action = _action(
        predecessor, root, group, record, parsed, rule,
        current=current, future=future, match=match,
    )
    classification = _classification(
        root, RepairabilityState.AUTO_REPAIRABLE, rule.repair_rule_id,
        (
            root_id, group["logical_change_id"], record["file_change_id"],
            record["head_content_fingerprint"],
            *group.get("evidence_references", []),
        ),
        rule.preconditions,
        "One exact static stale reference maps to one certified coherent future identity.",
        rule.supported_file_categories,
        rule.remaining_evidence_requirements,
        group["logical_change_id"],
    )
    return classification, [action]


def _classify_delete(predecessor, proposal, registry, root, group, inventory, results, transition):
    current = transition["current"]
    metadata = {
        **{
            item.key: item.value
            for item in predecessor.proposal.proposal_metadata
        },
        **proposal_metadata(proposal),
    }
    approved = metadata.get("approved_delete_field") == current
    matches = _all_reference_targets(results, inventory, current, exclude=set(root.get("contributing_file_ids", [])))
    if not approved:
        return _classification(
            root, RepairabilityState.BLOCKED_BY_MISSING_EVIDENCE,
            "repair.delete.requires-approved-intent.v1", tuple(root.get("delta_ids", [])),
            ("approved_delete_field",),
            "The structural removal exists, but explicit no-replacement deletion intent is absent.",
            (), ("approved_delete_without_replacement",), group.get("logical_change_id") if group else None,
        ), []
    rule = registry.get("repair.delete.structured-stale-reference.v1")
    eligible = [item for item in matches if item[1]["category"] in rule.supported_file_categories]
    if not eligible:
        return _classification(
            root, RepairabilityState.BLOCKED_BY_MISSING_EVIDENCE,
            rule.repair_rule_id, tuple(root.get("delta_ids", [])), rule.preconditions,
            "No exact supported stale structured reference was found for the explicit deletion.",
            rule.supported_file_categories, ("supported_stale_delete_target",),
            group.get("logical_change_id") if group else None,
        ), []
    actions = [
        _action(
            predecessor, root, group, record, parsed, rule,
            current=current, future=None, match=match,
        )
        for parsed, record, match in eligible
    ]
    return _classification(
        root, RepairabilityState.CONDITIONALLY_REPAIRABLE, rule.repair_rule_id,
        tuple(root.get("delta_ids", [])) + tuple(item[1]["file_change_id"] for item in eligible),
        rule.preconditions,
        "Explicit certified deletion intent and exact structured stale targets satisfy the conditional rule.",
        rule.supported_file_categories, rule.remaining_evidence_requirements,
        group.get("logical_change_id") if group else None,
    ), actions


def _classify_type(predecessor, proposal, registry, root, group, inventory, results, transition):
    current, future = transition["current"], transition["future"]
    metadata = {
        **{item.key: item.value for item in predecessor.proposal.proposal_metadata},
        **proposal_metadata(proposal),
    }
    approved = metadata.get("approved_type_transition") == f"{current}->{future}"
    rule = registry.get("repair.type.declaration-alignment.v1")
    if not approved:
        return _classification(
            root, RepairabilityState.BLOCKED_BY_MISSING_EVIDENCE,
            rule.repair_rule_id, tuple(root.get("delta_ids", [])), rule.preconditions,
            "A declared type changed, but an approved unambiguous declaration transition is absent.",
            rule.supported_file_categories, ("approved_type_transition", "conversion_policy"),
            group.get("logical_change_id") if group else None,
        ), []
    targets = _all_reference_targets(
        results, inventory, current,
        exclude=set(root.get("contributing_file_ids", [])),
        kinds={"type", "expected_type", "data_type"},
    )
    eligible = [item for item in targets if item[1]["category"] in rule.supported_file_categories]
    if not eligible:
        return _classification(
            root, RepairabilityState.BLOCKED_BY_MISSING_EVIDENCE,
            rule.repair_rule_id, tuple(root.get("delta_ids", [])), rule.preconditions,
            "No exact supported stale declaration target was found.",
            rule.supported_file_categories, ("supported_stale_type_declaration",),
            group.get("logical_change_id") if group else None,
        ), []
    actions = [
        _action(
            predecessor, root, group, record, parsed, rule,
            current=current, future=future, match=match,
        )
        for parsed, record, match in eligible
    ]
    return _classification(
        root, RepairabilityState.CONDITIONALLY_REPAIRABLE, rule.repair_rule_id,
        tuple(root.get("delta_ids", [])) + tuple(item[1]["file_change_id"] for item in eligible),
        rule.preconditions,
        "The approved explicit type transition supports declaration alignment only; no runtime cast is generated.",
        rule.supported_file_categories, rule.remaining_evidence_requirements,
        group.get("logical_change_id") if group else None,
    ), actions


def _action(predecessor, root, group, record, parsed, rule, *, current, future, match):
    group_id = group.get("logical_change_id") if group else root.get("logical_change_id")
    path = record.get("head_path") or record.get("base_path")
    if not path:
        raise RepairPlanningError("Repair action target lacks a HEAD path.")
    match = dict(match)
    if (
        record["category"] == "SCHEMA_CONTRACT"
        and isinstance(match.get("location"), str)
        and not match["location"].startswith("contract.")
    ):
        match["location"] = f"contract.{match['location']}"
    action_id = stable_id(
        "repair-action", root["root_cause_id"], record["file_change_id"],
        rule.repair_rule_id, str(match.get("location")), str(current), str(future),
    )
    future_entities = group.get("counterfactual_entities", []) if group else []
    current_entities = group.get("resolved_current_entities", []) if group else []
    return RepairAction(
        repair_action_id=action_id,
        repair_rule_id=rule.repair_rule_id,
        root_cause_id=root["root_cause_id"],
        logical_change_group_id=group_id,
        target_file_change_id=record["file_change_id"],
        target_path=path,
        file_category=record["category"],
        current_evidence={
            **match,
            "value": current,
            "editor_name": rule.editor_name,
            "parser": parsed.get("parser"),
            "head_content_fingerprint": record.get("head_content_fingerprint"),
            "predecessor_root_cause_id": root["root_cause_id"],
            "datahub_or_current_entities": current_entities,
        },
        intended_future_evidence={
            "value": future,
            "counterfactual_entities": future_entities,
            "identity_claim_evidence": group.get("evidence_references", []) if group else root.get("delta_ids", []),
        },
        edit_operation=rule.edit_operation,
        expected_changed_identities=tuple(
            item for item in (str(current) if current is not None else None, str(future) if future is not None else None)
            if item is not None
        ),
        dependency_actions=(),
        confidence="CERTIFIED_STATIC_EXACT",
        preconditions=rule.preconditions,
        static_validation_requirements=rule.post_generation_static_checks,
        remaining_evidence_requirements=rule.remaining_evidence_requirements,
        human_explanation=rule.explanation_template.format(current=current, future=future),
        target_location=match.get("location"),
    )


def _classification(root, state, rule_id, evidence, preconditions, reason, categories, uncertainty, group_id):
    return RepairabilityClassification(
        root_cause_id=root["root_cause_id"], root_type=root["root_type"],
        repairability=state, repairability_rule_id=rule_id,
        supporting_evidence=tuple(sorted(set(str(item) for item in evidence if item))),
        required_preconditions=tuple(preconditions), reason=reason,
        eligible_file_categories=tuple(categories),
        remaining_uncertainty=tuple(uncertainty),
        logical_change_group_id=group_id,
    )


def _ambiguous_target(root, group, reason):
    return _classification(
        root, RepairabilityState.BLOCKED_BY_MISSING_EVIDENCE,
        "repair.blocked.ambiguous-static-target.v1", (root["root_cause_id"],),
        ("one_parser_confirmed_target",), reason, (),
        ("exact_static_target",), group.get("logical_change_id") if group else None,
    ), []


def _group_for_root(root, groups):
    if root.get("logical_change_id"):
        for group in groups:
            if group["logical_change_id"] == root["logical_change_id"]:
                return group
    for group in groups:
        if _root_matches_group(root, group):
            return group
    return None


def _root_matches_group(root, group):
    if root.get("logical_change_id") == group.get("logical_change_id"):
        return True
    entities = set(root.get("resolved_entities", []))
    identity_match = group.get("current_field") in entities or bool(
        entities & set(group.get("future_fields", []))
    )
    return identity_match and bool(
        set(root.get("contributing_file_ids", []))
        & set(group.get("contributing_file_ids", []))
    )


def _root_has_dynamic_target(root, results):
    return any(
        any(
            item.get("reason") == "dynamic_python_expression"
            or str(item.get("code_reference", "")).startswith("dynamic_")
            for item in results.get(file_id, {}).get("unresolved_references", [])
        )
        for file_id in root.get("contributing_file_ids", [])
    )


def _parsed_reference_matches(parsed, current):
    if not isinstance(parsed, dict):
        return []
    matches = []
    for item in parsed.get("references", []):
        if item.get("value") == current:
            matches.append(dict(item))
    if matches:
        return matches
    return _structured_matches(parsed, current)


def _structured_matches(value, current, prefix=""):
    matches = []
    if isinstance(value, dict):
        for key, item in value.items():
            location = f"{prefix}.{key}" if prefix else str(key)
            if item == current and key in {
                "name", "type", "data_type", "expected_type", "field",
                "source_field", "target_field", "input_field", "output_field",
                "dataset", "model", "model_file", "contract_file",
            }:
                matches.append({"kind": key, "value": current, "location": location})
            else:
                matches.extend(_structured_matches(item, current, location))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            matches.extend(_structured_matches(item, current, f"{prefix}[{index}]"))
    return matches


def _all_reference_targets(results, inventory, current, *, exclude=frozenset(), kinds=None):
    found = []
    for file_id, parsed in results.items():
        if file_id in exclude or file_id not in inventory:
            continue
        matches = _parsed_reference_matches(parsed.get("parsed_head"), current)
        for match in matches:
            if kinds is None or match.get("kind") in kinds:
                found.append((parsed, inventory[file_id], match))
    return found


def _delete_transition(predecessor, root):
    deltas = predecessor.artifacts["structural_change_set.json"]["deltas"]
    relevant = [item for item in deltas if item["delta_id"] in root.get("delta_ids", [])]
    if len(relevant) == 1 and relevant[0].get("delta_type") == "OUTPUT_COLUMN_REMOVED":
        return {"current": relevant[0].get("affected_output_field"), "future": None}
    return None


def _declared_type_transition(predecessor, root):
    deltas = predecessor.artifacts["contract_quality_change_set.json"]["deltas"]
    relevant = [item for item in deltas if item["delta_id"] in root.get("delta_ids", [])]
    if len(relevant) == 1 and relevant[0].get("delta_type") == "DECLARED_TYPE_CHANGED":
        return {
            "current": relevant[0].get("before_representation", relevant[0].get("before")),
            "future": relevant[0].get("after_representation", relevant[0].get("after")),
        }
    return None


def _with_dependencies(actions):
    grouped = defaultdict(list)
    for action in actions:
        grouped[action.logical_change_group_id or action.root_cause_id].append(action)
    result = []
    for _, group_actions in sorted(grouped.items()):
        ordered = sorted(
            group_actions,
            key=lambda item: (
                _CATEGORY_ORDER.get(item.file_category, 99),
                item.target_path, item.target_location or "", item.repair_action_id,
            ),
        )
        previous = None
        for action in ordered:
            dependencies = (previous.repair_action_id,) if previous is not None else ()
            updated = replace(action, dependency_actions=dependencies)
            result.append(updated)
            previous = updated
    return sorted(result, key=lambda item: item.repair_action_id)


def _topological_order(actions):
    by_id = {item.repair_action_id: item for item in actions}
    indegree = {item: 0 for item in by_id}
    outgoing = defaultdict(set)
    for action in actions:
        for dependency in action.dependency_actions:
            if dependency not in by_id:
                raise RepairPlanningError("Repair action has an unknown dependency.")
            outgoing[dependency].add(action.repair_action_id)
            indegree[action.repair_action_id] += 1
    queue = deque(sorted(item for item, count in indegree.items() if count == 0))
    ordered = []
    while queue:
        current = queue.popleft()
        ordered.append(current)
        for target in sorted(outgoing[current]):
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    if len(ordered) != len(actions):
        raise RepairPlanningError("Repair action dependencies contain a cycle.")
    return ordered
