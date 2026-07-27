"""Fail-closed validation for the frozen CHRONOS-DEMO-001 snapshot baseline."""

from __future__ import annotations

from collections import Counter

from .models import (
    CurrentMetadataSnapshot,
    FieldMachineKey,
    RelationshipCategory,
    SnapshotValidationFinding,
    SnapshotValidationResult,
    SnapshotValidationState,
)
from .serialization import contains_secret, snapshot_to_dict


FROZEN_DEMONSTRATION_ID = "CHRONOS-DEMO-001"
FROZEN_SOURCE_SCHEMA_FIELD_COUNT = 15
FROZEN_DOWNSTREAM_FIELD_COUNT = 25
FROZEN_DOWNSTREAM_DATASET_COUNT = 20
FROZEN_MAXIMUM_FIELD_DEPTH = 5
FROZEN_SOURCE_FIELD_PATH = "order_total"
FROZEN_SOURCE_NATIVE_TYPE = "DOUBLE PRECISION"
FROZEN_SOURCE_NORMALIZED_TYPE = "Number"


def validate_snapshot(
    snapshot: CurrentMetadataSnapshot,
) -> SnapshotValidationResult:
    findings: list[SnapshotValidationFinding] = []
    checked: list[str] = []

    def check(
        invariant: str,
        condition: bool,
        *,
        expected: object,
        observed: object,
        evidence_ids: tuple[str, ...] = (),
        affected_key: str | None = None,
    ) -> None:
        checked.append(invariant)
        if not condition:
            findings.append(
                SnapshotValidationFinding(
                    invariant=invariant,
                    expected=str(expected),
                    observed=str(observed),
                    evidence_ids=tuple(sorted(set(evidence_ids))),
                    affected_key=affected_key,
                )
            )

    dataset_counts = Counter(item.dataset_urn for item in snapshot.datasets)
    field_counts = Counter(item.key for item in snapshot.fields)
    edge_counts = Counter(item.edge_id for item in snapshot.lineage_edges)
    group_counts = Counter(item.group_id for item in snapshot.mapping_groups)
    relationship_counts = Counter(
        item.relationship_id for item in snapshot.relationships
    )
    evidence_counts = Counter(item.evidence_id for item in snapshot.evidence)

    datasets = snapshot.dataset_by_urn()
    fields = snapshot.field_by_key()
    evidence = snapshot.evidence_by_id()
    source_dataset = datasets.get(snapshot.source_dataset_urn)
    source_field = fields.get(snapshot.source_field_key)
    schema_source_fields = [
        item
        for item in snapshot.source_schema.fields
        if item.field_path == FROZEN_SOURCE_FIELD_PATH
    ]

    check(
        "demonstration_id",
        snapshot.metadata.demonstration_id == FROZEN_DEMONSTRATION_ID,
        expected=FROZEN_DEMONSTRATION_ID,
        observed=snapshot.metadata.demonstration_id,
    )
    check(
        "source_dataset_exists",
        source_dataset is not None,
        expected="present",
        observed="present" if source_dataset else "missing",
        affected_key=snapshot.source_dataset_urn,
    )
    check(
        "source_field_exists",
        source_field is not None,
        expected="present exactly once",
        observed=field_counts[snapshot.source_field_key],
        affected_key=snapshot.source_field_key.text,
    )
    check(
        "source_field_belongs_to_source_dataset",
        snapshot.source_field_key.dataset_urn
        == snapshot.source_dataset_urn,
        expected=snapshot.source_dataset_urn,
        observed=snapshot.source_field_key.dataset_urn,
        affected_key=snapshot.source_field_key.text,
    )
    check(
        "source_schema_bound_to_source_dataset",
        snapshot.source_schema.dataset_urn == snapshot.source_dataset_urn,
        expected=snapshot.source_dataset_urn,
        observed=snapshot.source_schema.dataset_urn,
        evidence_ids=snapshot.source_schema.evidence_ids,
    )
    check(
        "source_schema_field_count",
        len(snapshot.source_schema.fields)
        == FROZEN_SOURCE_SCHEMA_FIELD_COUNT,
        expected=FROZEN_SOURCE_SCHEMA_FIELD_COUNT,
        observed=len(snapshot.source_schema.fields),
        evidence_ids=snapshot.source_schema.evidence_ids,
    )
    check(
        "source_schema_field_paths_unique",
        len({item.field_path for item in snapshot.source_schema.fields})
        == len(snapshot.source_schema.fields),
        expected="all unique",
        observed=len(
            snapshot.source_schema.fields
        )
        - len({item.field_path for item in snapshot.source_schema.fields}),
        evidence_ids=snapshot.source_schema.evidence_ids,
    )
    check(
        "order_total_in_source_schema",
        len(schema_source_fields) == 1,
        expected="present exactly once",
        observed=len(schema_source_fields),
        evidence_ids=snapshot.source_schema.evidence_ids,
    )
    if schema_source_fields:
        observed_source = schema_source_fields[0]
        check(
            "order_total_native_type",
            observed_source.native_type == FROZEN_SOURCE_NATIVE_TYPE,
            expected=FROZEN_SOURCE_NATIVE_TYPE,
            observed=observed_source.native_type,
            evidence_ids=observed_source.evidence_ids,
            affected_key=snapshot.source_field_key.text,
        )
        check(
            "order_total_normalized_type",
            observed_source.normalized_type
            == FROZEN_SOURCE_NORMALIZED_TYPE,
            expected=FROZEN_SOURCE_NORMALIZED_TYPE,
            observed=observed_source.normalized_type,
            evidence_ids=observed_source.evidence_ids,
            affected_key=snapshot.source_field_key.text,
        )

    check(
        "dataset_machine_keys_unique",
        all(count == 1 for count in dataset_counts.values()),
        expected="all unique",
        observed={
            key: count
            for key, count in dataset_counts.items()
            if count != 1
        },
    )
    check(
        "field_machine_keys_unique",
        all(count == 1 for count in field_counts.values()),
        expected="all unique",
        observed={
            key.text: count
            for key, count in field_counts.items()
            if count != 1
        },
    )
    check(
        "dataset_scope_count",
        len(snapshot.datasets) == 21,
        expected=21,
        observed=len(snapshot.datasets),
    )
    check(
        "lineage_field_node_count",
        len(snapshot.fields) == 26,
        expected=26,
        observed=len(snapshot.fields),
    )
    missing_context_states = sorted(
        item.dataset_urn
        for item in snapshot.datasets
        if not item.metadata_states
    )
    check(
        "all_scoped_datasets_have_context_state",
        not missing_context_states,
        expected="context state present for every scoped dataset",
        observed=missing_context_states,
    )
    downstream_fields = {
        item.key
        for item in snapshot.fields
        if item.key != snapshot.source_field_key
    }
    downstream_datasets = {
        item.dataset_urn
        for item in downstream_fields
        if item.dataset_urn != snapshot.source_dataset_urn
    }
    check(
        "downstream_field_count",
        len(downstream_fields) == FROZEN_DOWNSTREAM_FIELD_COUNT,
        expected=FROZEN_DOWNSTREAM_FIELD_COUNT,
        observed=len(downstream_fields),
    )
    check(
        "downstream_dataset_count",
        len(downstream_datasets) == FROZEN_DOWNSTREAM_DATASET_COUNT,
        expected=FROZEN_DOWNSTREAM_DATASET_COUNT,
        observed=len(downstream_datasets),
    )
    maximum_depth = max(
        (item.lineage_depth for item in snapshot.fields),
        default=0,
    )
    check(
        "maximum_field_depth",
        maximum_depth == FROZEN_MAXIMUM_FIELD_DEPTH,
        expected=FROZEN_MAXIMUM_FIELD_DEPTH,
        observed=maximum_depth,
    )

    unknown_parents = sorted(
        {
            item.key.dataset_urn
            for item in snapshot.fields
            if item.key.dataset_urn not in datasets
        }
    )
    check(
        "all_field_parents_known",
        not unknown_parents,
        expected="no unknown parent datasets",
        observed=unknown_parents,
    )
    dangling_edges = sorted(
        item.edge_id
        for item in snapshot.lineage_edges
        if item.upstream not in fields or item.downstream not in fields
    )
    check(
        "all_lineage_endpoints_known",
        not dangling_edges,
        expected="no dangling endpoints",
        observed=dangling_edges,
    )
    dangling_groups = sorted(
        item.group_id
        for item in snapshot.mapping_groups
        if any(key not in fields for key in item.upstream_fields)
        or any(key not in fields for key in item.downstream_fields)
    )
    check(
        "all_mapping_group_endpoints_known",
        not dangling_groups,
        expected="no dangling mapping-group endpoints",
        observed=dangling_groups,
    )
    check(
        "lineage_edge_ids_unique",
        all(count == 1 for count in edge_counts.values()),
        expected="all unique",
        observed={
            key: count for key, count in edge_counts.items() if count != 1
        },
    )
    check(
        "mapping_group_ids_unique",
        all(count == 1 for count in group_counts.values()),
        expected="all unique",
        observed={
            key: count for key, count in group_counts.items() if count != 1
        },
    )
    graph_evidence = next(
        (
            item
            for item in snapshot.evidence
            if item.source_phase == "1.4"
            and item.aspect_or_relationship == "field_lineage_graph"
        ),
        None,
    )
    graph_attributes = (
        {
            item.name: item.values[0] if len(item.values) == 1 else item.values
            for item in graph_evidence.attributes
        }
        if graph_evidence is not None
        else {}
    )
    declared_edge_count = graph_attributes.get("explicit_edge_count")
    declared_group_count = graph_attributes.get("mapping_group_count")
    check(
        "lineage_counts_match_phase_1_4_evidence",
        graph_evidence is not None
        and declared_edge_count == len(snapshot.lineage_edges)
        and declared_group_count == len(snapshot.mapping_groups),
        expected=(
            f"edges={declared_edge_count}; "
            f"mapping_groups={declared_group_count}"
        ),
        observed=(
            f"edges={len(snapshot.lineage_edges)}; "
            f"mapping_groups={len(snapshot.mapping_groups)}"
        ),
        evidence_ids=(
            (graph_evidence.evidence_id,)
            if graph_evidence is not None
            else ()
        ),
    )
    check(
        "relationship_ids_unique",
        all(count == 1 for count in relationship_counts.values()),
        expected="all unique",
        observed={
            key: count
            for key, count in relationship_counts.items()
            if count != 1
        },
    )
    check(
        "evidence_ids_unique",
        all(count == 1 for count in evidence_counts.values()),
        expected="all unique",
        observed={
            key: count
            for key, count in evidence_counts.items()
            if count != 1
        },
    )

    referenced_evidence: set[str] = set(snapshot.source_schema.evidence_ids)
    for collection in (
        snapshot.datasets,
        snapshot.fields,
        snapshot.lineage_edges,
        snapshot.mapping_groups,
        snapshot.structured_property_definitions,
        snapshot.relationships,
    ):
        for item in collection:
            referenced_evidence.update(item.evidence_ids)
    dangling_evidence = sorted(referenced_evidence - set(evidence))
    check(
        "no_dangling_evidence_references",
        not dangling_evidence,
        expected="no dangling evidence IDs",
        observed=dangling_evidence,
    )

    known_subjects = set(datasets) | {key.text for key in fields}
    dangling_context: list[str] = []
    for item in snapshot.relationships:
        if item.category in {
            RelationshipCategory.OWNERSHIP,
            RelationshipCategory.DOMAIN_ASSIGNMENT,
            RelationshipCategory.TAG_ASSIGNMENT,
            RelationshipCategory.GLOSSARY_ASSIGNMENT,
            RelationshipCategory.STRUCTURED_PROPERTY_ASSIGNMENT,
            RelationshipCategory.DATA_PRODUCT_MEMBERSHIP,
            RelationshipCategory.DOCUMENT_RELATIONSHIP,
        } and item.source_key not in known_subjects:
            dangling_context.append(item.relationship_id)
        if (
            item.category is RelationshipCategory.PIPELINE_CONTEXT
            and item.target_key not in known_subjects
        ):
            dangling_context.append(item.relationship_id)
        if (
            item.category is RelationshipCategory.BI_REACHABLE_CONTEXT
            and not item.relationship_path
        ):
            dangling_context.append(item.relationship_id)
    check(
        "all_context_relationships_typed_and_bound",
        not dangling_context,
        expected="known scoped subject or explicitly typed context entity",
        observed=sorted(set(dangling_context)),
    )
    check(
        "no_credentials_or_secrets",
        not contains_secret(
            snapshot_to_dict(snapshot, include_volatile=True)
        ),
        expected="no credential-shaped keys or values",
        observed="credential-shaped content detected",
    )

    findings_tuple = tuple(
        sorted(
            findings,
            key=lambda item: (
                item.invariant,
                item.affected_key or "",
                item.expected,
                item.observed,
            ),
        )
    )
    return SnapshotValidationResult(
        state=(
            SnapshotValidationState.INVALID
            if findings_tuple
            else SnapshotValidationState.VALID
        ),
        checked_invariants=tuple(sorted(set(checked))),
        findings=findings_tuple,
    )
