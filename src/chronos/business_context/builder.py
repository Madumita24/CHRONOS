"""Deterministic CHRONOS Phase 4.2 business-context propagation."""

from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

from chronos.change_semantics import ChangeSemanticContract, load_contract
from chronos.compatibility_evaluation import (
    CompatibilityEvaluationResult,
    load_compatibility_evaluation,
    validate_compatibility_evaluation,
)
from chronos.counterfactual_source import (
    CounterfactualSourceState,
    InputArtifactHash,
    load_source_state,
    validate_counterfactual_source_state,
)
from chronos.dependency_propagation import (
    DependencyPropagationResult,
    load_dependency_propagation,
    validate_dependency_propagation,
)
from chronos.explanations import (
    ExplanationBundle,
    load_explanation_bundle,
    validate_explanation_bundle,
)
from chronos.future_graph import (
    FutureContextRelationship,
    FutureMetadataGraph,
    load_future_graph,
    validate_future_metadata_graph,
)
from chronos.phase2_certification import (
    Phase2CertificationResult,
    Phase2CertificationState,
    load_certification,
)
from chronos.phase3_certification import (
    Phase3CertificationResult,
    Phase3CertificationStatus,
    load_phase3_certification,
    phase3_certification_semantic_fingerprint,
    validate_phase3_certification,
)
from chronos.proposal import (
    CANONICAL_DATASET_URN,
    ChangeProposal,
    ChangeType,
    load_proposal,
)
from chronos.proposal_validation import (
    ProposalValidationResult,
    load_validation_result,
)
from chronos.snapshot import (
    CurrentMetadataSnapshot,
    FieldMachineKey,
    RelationshipCategory,
    SnapshotValidationState,
    load_snapshot,
)
from chronos.technical_impact import (
    FieldTechnicalImpact,
    TechnicalImpactAnalysis,
    TechnicalImpactState,
    load_technical_impact,
    validate_technical_impact,
)

from .errors import (
    BusinessContextEntryError,
    BusinessContextValidationError,
)
from .models import (
    BUSINESS_CONTEXT_SCHEMA_VERSION,
    BusinessContextAggregateMetrics,
    BusinessContextPropagation,
    BusinessContextValidationState,
    ContextAssetRecord,
    ContextAssetReverseIndex,
    ContextAssetType,
    ContextAttribute,
    ContextCategory,
    ContextExposureCause,
    ContextExposureType,
    ContextLinkageState,
    ContextLinkRecord,
    ContextResolutionState,
    ContextReverseIndexes,
    DatasetContextReverseIndex,
    DatasetContextSummary,
    FieldContextReverseIndex,
    TechnicalSubjectType,
    TechnicalToContextMapping,
    UnresolvedContextReference,
)


Clock = Callable[[], datetime]
_CURRENT = FieldMachineKey(CANONICAL_DATASET_URN, "order_total")
_CANDIDATE = FieldMachineKey(CANONICAL_DATASET_URN, "order_amount")
_PROPOSAL_ID = "CHRONOS-DEMO-001-PROPOSAL-001"
_CAUSE_ID = "technical-impact-cause-source-rename-semantics"
_NAMES = (
    "current_metadata_snapshot.json",
    "change_proposal.json",
    "change_proposal_validation.json",
    "change_semantic_contract.json",
    "phase_2_certification.json",
    "counterfactual_source_state.json",
    "future_metadata_graph.json",
    "dependency_propagation.json",
    "compatibility_evaluation.json",
    "explanation_bundle.json",
    "phase_3_certification.json",
    "technical_impact_analysis.json",
)
_CATEGORY = {
    RelationshipCategory.OWNERSHIP: ContextCategory.OWNERSHIP,
    RelationshipCategory.DOMAIN_ASSIGNMENT: ContextCategory.DOMAIN,
    RelationshipCategory.TAG_ASSIGNMENT: ContextCategory.TAG,
    RelationshipCategory.GLOSSARY_ASSIGNMENT: ContextCategory.GLOSSARY,
    RelationshipCategory.STRUCTURED_PROPERTY_ASSIGNMENT: (
        ContextCategory.STRUCTURED_PROPERTY
    ),
    RelationshipCategory.DATA_PRODUCT_MEMBERSHIP: (
        ContextCategory.DATA_PRODUCT
    ),
    RelationshipCategory.DOCUMENT_RELATIONSHIP: ContextCategory.DOCUMENT,
    RelationshipCategory.PIPELINE_CONTEXT: ContextCategory.PIPELINE,
    RelationshipCategory.BI_REACHABLE_CONTEXT: ContextCategory.BI,
}


def propagate_business_context(
    snapshot: CurrentMetadataSnapshot,
    proposal: ChangeProposal,
    proposal_validation: ProposalValidationResult,
    contract: ChangeSemanticContract,
    phase2: Phase2CertificationResult,
    source_state: CounterfactualSourceState,
    graph: FutureMetadataGraph,
    propagation: DependencyPropagationResult,
    compatibility: CompatibilityEvaluationResult,
    explanations: ExplanationBundle,
    phase3: Phase3CertificationResult,
    technical_impact: TechnicalImpactAnalysis,
    *,
    input_artifact_hashes: tuple[InputArtifactHash, ...],
    clock: Clock | None = None,
) -> BusinessContextPropagation:
    """Propagate only certified context connected to Phase 4.1 subjects."""
    _require_entry(
        snapshot,
        proposal,
        proposal_validation,
        contract,
        phase2,
        source_state,
        graph,
        propagation,
        compatibility,
        explanations,
        phase3,
        technical_impact,
        input_artifact_hashes,
    )
    links = _context_links(graph, technical_impact, phase3)
    mappings = _technical_mappings(links, technical_impact)
    assets = _context_assets(links, mappings)
    reverse_indexes = _reverse_indexes(
        mappings,
        technical_impact,
        assets,
    )
    summaries = _dataset_summaries(
        links,
        mappings,
        technical_impact,
    )
    causes = _context_causes(
        technical_impact,
        mappings,
    )
    unresolved = tuple(
        UnresolvedContextReference(
            context_asset_id=item.asset_id,
            context_category=item.category,
            context_relationship_ids=item.certified_relationship_ids,
            preserved_state=item.resolution_state,
        )
        for item in assets
        if item.resolution_state is ContextResolutionState.UNRESOLVED
    )
    metrics = _aggregate(
        graph,
        links,
        assets,
        mappings,
        reverse_indexes,
    )
    result = BusinessContextPropagation(
        schema_version=BUSINESS_CONTEXT_SCHEMA_VERSION,
        demonstration_id=technical_impact.demonstration_id,
        proposal_id=technical_impact.proposal_id,
        phase_3_certification_fingerprint=phase3.semantic_fingerprint,
        technical_impact_fingerprint=technical_impact.semantic_fingerprint,
        technical_root_causes=causes,
        context_asset_registry=assets,
        context_link_registry=links,
        technical_to_context_mappings=mappings,
        dataset_context_summaries=summaries,
        reverse_indexes=reverse_indexes,
        aggregate_metrics=metrics,
        unresolved_context_references=unresolved,
        canonical_narrative=_canonical_narrative(metrics, technical_impact),
        warnings=(),
        input_artifact_hashes=input_artifact_hashes,
        created_at=_timestamp(clock),
        validation_state=BusinessContextValidationState.VALID,
    )
    validate_business_context(
        result,
        snapshot,
        graph,
        technical_impact,
        phase3,
    )
    return result


def propagate_business_context_from_artifacts(
    snapshot_path: str | Path,
    proposal_path: str | Path,
    validation_path: str | Path,
    contract_path: str | Path,
    phase2_path: str | Path,
    source_state_path: str | Path,
    graph_path: str | Path,
    propagation_path: str | Path,
    compatibility_path: str | Path,
    explanations_path: str | Path,
    phase3_path: str | Path,
    technical_impact_path: str | Path,
    *,
    clock: Clock | None = None,
) -> BusinessContextPropagation:
    paths = tuple(
        (name, Path(path))
        for name, path in zip(
            _NAMES,
            (
                snapshot_path,
                proposal_path,
                validation_path,
                contract_path,
                phase2_path,
                source_state_path,
                graph_path,
                propagation_path,
                compatibility_path,
                explanations_path,
                phase3_path,
                technical_impact_path,
            ),
        )
    )
    before = {name: _file_hash(path) for name, path in paths}
    snapshot = load_snapshot(snapshot_path)
    proposal = load_proposal(proposal_path)
    proposal_validation = load_validation_result(validation_path)
    contract = load_contract(contract_path)
    phase2 = load_certification(phase2_path)
    source_state = load_source_state(source_state_path)
    graph = load_future_graph(graph_path)
    propagation = load_dependency_propagation(propagation_path)
    compatibility = load_compatibility_evaluation(compatibility_path)
    explanations = load_explanation_bundle(explanations_path)
    phase3 = load_phase3_certification(phase3_path)
    technical_impact = load_technical_impact(technical_impact_path)
    after_load = {name: _file_hash(path) for name, path in paths}
    hashes = tuple(
        InputArtifactHash(name, before[name], after_load[name])
        for name, _ in paths
    )
    result = propagate_business_context(
        snapshot,
        proposal,
        proposal_validation,
        contract,
        phase2,
        source_state,
        graph,
        propagation,
        compatibility,
        explanations,
        phase3,
        technical_impact,
        input_artifact_hashes=hashes,
        clock=clock,
    )
    if {name: _file_hash(path) for name, path in paths} != before:
        raise BusinessContextValidationError(
            "An authoritative input changed during context propagation."
        )
    return result


def validate_business_context(
    result: BusinessContextPropagation,
    snapshot: CurrentMetadataSnapshot,
    graph: FutureMetadataGraph,
    technical_impact: TechnicalImpactAnalysis,
    phase3: Phase3CertificationResult,
) -> None:
    issues: list[str] = []

    def require(condition: bool, message: str) -> None:
        if not condition:
            issues.append(message)

    require(
        result.phase_3_certification_fingerprint
        == phase3.semantic_fingerprint,
        "Phase 3 certification reference mismatch",
    )
    require(
        result.technical_impact_fingerprint
        == technical_impact.semantic_fingerprint,
        "Phase 4.1 technical-impact reference mismatch",
    )
    require(
        result.demonstration_id == technical_impact.demonstration_id
        and result.proposal_id == technical_impact.proposal_id,
        "Demonstration or proposal scope mismatch",
    )
    expected_links = _context_links(graph, technical_impact, phase3)
    expected_mappings = _technical_mappings(
        expected_links,
        technical_impact,
    )
    expected_assets = _context_assets(expected_links, expected_mappings)
    expected_reverse = _reverse_indexes(
        expected_mappings,
        technical_impact,
        expected_assets,
    )
    expected_summaries = _dataset_summaries(
        expected_links,
        expected_mappings,
        technical_impact,
    )
    expected_causes = _context_causes(
        technical_impact,
        expected_mappings,
    )
    expected_unresolved = tuple(
        UnresolvedContextReference(
            context_asset_id=item.asset_id,
            context_category=item.category,
            context_relationship_ids=item.certified_relationship_ids,
            preserved_state=item.resolution_state,
        )
        for item in expected_assets
        if item.resolution_state is ContextResolutionState.UNRESOLVED
    )
    expected_metrics = _aggregate(
        graph,
        expected_links,
        expected_assets,
        expected_mappings,
        expected_reverse,
    )
    require(
        result.context_link_registry == expected_links,
        "Context relationship scope or content mismatch",
    )
    require(
        result.technical_to_context_mappings == expected_mappings,
        "Technical-to-context mapping mismatch",
    )
    require(
        result.context_asset_registry == expected_assets,
        "Context asset registry mismatch",
    )
    require(
        result.reverse_indexes == expected_reverse,
        "Context reverse indexes mismatch",
    )
    require(
        result.dataset_context_summaries == expected_summaries,
        "Dataset context summaries mismatch",
    )
    require(
        result.technical_root_causes == expected_causes,
        "Technical root-cause consolidation mismatch",
    )
    require(
        result.unresolved_context_references == expected_unresolved,
        "Unresolved context references mismatch",
    )
    require(
        result.aggregate_metrics == expected_metrics,
        "Aggregate context metrics mismatch",
    )
    technical_fields = {
        item.field_key: item for item in technical_impact.field_impacts
    }
    for mapping in result.technical_to_context_mappings:
        technical = technical_fields.get(mapping.technical_field_key)
        require(
            technical is not None,
            f"Dangling technical field: {mapping.technical_subject_id}",
        )
        if technical is not None:
            require(
                mapping.technical_impact_state
                is technical.technical_impact_state,
                f"Technical state mutation: {mapping.mapping_id}",
            )
            require(
                mapping.root_technical_cause_ids == technical.cause_ids,
                f"Technical cause mutation: {mapping.mapping_id}",
            )
    require(
        tuple(result.context_asset_registry)
        == tuple(sorted(result.context_asset_registry, key=lambda x: x.asset_id)),
        "Context assets are not deterministically ordered",
    )
    require(
        tuple(result.context_link_registry)
        == tuple(
            sorted(
                result.context_link_registry,
                key=lambda x: x.context_relationship_id,
            )
        ),
        "Context links are not deterministically ordered",
    )
    require(
        tuple(result.technical_to_context_mappings)
        == tuple(
            sorted(
                result.technical_to_context_mappings,
                key=lambda x: x.mapping_id,
            )
        ),
        "Context mappings are not deterministically ordered",
    )
    structured = {
        item.property_urn for item in graph.structured_property_registry
    }
    require(
        all(
            item.context_category
            is not ContextCategory.STRUCTURED_PROPERTY
            or item.target_key in structured
            for item in result.context_link_registry
        ),
        "Unknown structured-property definition",
    )
    serialized = result.to_json().lower()
    for phrase in (
        "dashboard is broken",
        "dashboard is impacted",
        "chart is broken",
        "chart is impacted",
        "high risk",
        "notification priority",
        "repair priority",
        "deployment recommendation",
    ):
        require(phrase not in serialized, f"Unsupported conclusion: {phrase}")
    require(
        result.canonical_narrative
        == _canonical_narrative(result.aggregate_metrics, technical_impact),
        "Canonical narrative is not derived from typed evidence",
    )
    require(
        len(result.input_artifact_hashes) == len(_NAMES)
        and tuple(
            item.artifact_name for item in result.input_artifact_hashes
        )
        == _NAMES
        and all(item.unchanged for item in result.input_artifact_hashes),
        "Phase 4.2 input immutability evidence is invalid",
    )
    snapshot_relationship_ids = {
        item.relationship_id for item in snapshot.relationships
    }
    require(
        all(
            item.context_relationship_id in snapshot_relationship_ids
            for item in result.context_link_registry
        ),
        "A context link lacks current snapshot evidence",
    )
    if issues:
        raise BusinessContextValidationError("; ".join(issues))


def _require_entry(
    snapshot: CurrentMetadataSnapshot,
    proposal: ChangeProposal,
    proposal_validation: ProposalValidationResult,
    contract: ChangeSemanticContract,
    phase2: Phase2CertificationResult,
    source_state: CounterfactualSourceState,
    graph: FutureMetadataGraph,
    propagation: DependencyPropagationResult,
    compatibility: CompatibilityEvaluationResult,
    explanations: ExplanationBundle,
    phase3: Phase3CertificationResult,
    technical_impact: TechnicalImpactAnalysis,
    hashes: tuple[InputArtifactHash, ...],
) -> None:
    try:
        validate_phase3_certification(phase3)
        validate_counterfactual_source_state(
            source_state,
            snapshot,
            proposal,
            proposal_validation,
            contract,
            phase2,
        )
        validate_future_metadata_graph(
            graph,
            snapshot,
            proposal,
            proposal_validation,
            contract,
            phase2,
            source_state,
        )
        validate_dependency_propagation(propagation, graph)
        validate_compatibility_evaluation(
            compatibility,
            graph,
            propagation,
        )
        validate_explanation_bundle(
            explanations,
            snapshot,
            source_state,
            graph,
            propagation,
            compatibility,
        )
        validate_technical_impact(
            technical_impact,
            source_state,
            graph,
            propagation,
            compatibility,
            explanations,
            phase3,
        )
    except ValueError as exc:
        raise BusinessContextEntryError(
            "Certified Phase 4.2 entry validation failed."
        ) from exc
    if (
        snapshot.validation_result.state is not SnapshotValidationState.VALID
        or phase2.certification_state
        is not Phase2CertificationState.CERTIFIED
        or phase3.certification_status
        is not Phase3CertificationStatus.CERTIFIED
        or phase3_certification_semantic_fingerprint(phase3)
        != phase3.semantic_fingerprint
        or proposal.change_type is not ChangeType.FIELD_RENAME
        or proposal.demonstration_id != "CHRONOS-DEMO-001"
        or proposal.proposal_id != _PROPOSAL_ID
        or proposal.change.target.dataset_urn != CANONICAL_DATASET_URN
        or proposal.change.before.field_path != _CURRENT.field_path
        or proposal.change.requested_after.field_path
        != _CANDIDATE.field_path
        or technical_impact.source_change.current_field != _CURRENT
        or technical_impact.source_change.candidate_field != _CANDIDATE
        or technical_impact.phase_3_certification_fingerprint
        != phase3.semantic_fingerprint
    ):
        raise BusinessContextEntryError(
            "A required certification, identity, or source transition "
            "is invalid."
        )
    if (
        len(technical_impact.relationship_impacts) != 27
        or len(technical_impact.path_impacts) != 48
        or len(technical_impact.field_impacts) != 25
        or len(technical_impact.dataset_summaries) != 20
        or {item.cause_id for item in technical_impact.technical_impact_causes}
        != {_CAUSE_ID}
    ):
        raise BusinessContextEntryError(
            "The certified Phase 4.1 technical scope is invalid."
        )
    if (
        len(hashes) != len(_NAMES)
        or tuple(item.artifact_name for item in hashes) != _NAMES
        or any(not item.unchanged for item in hashes)
    ):
        raise BusinessContextEntryError(
            "All twelve Phase 4.2 inputs must remain unchanged."
        )
    semantic_objects = (
        snapshot,
        proposal,
        proposal_validation,
        contract,
        phase2,
        source_state,
        graph,
        propagation,
        compatibility,
        explanations,
    )
    hash_by_name = {item.artifact_name: item for item in hashes}
    for identity, obj in zip(
        phase3.input_artifact_identities,
        semantic_objects,
    ):
        observed = hash_by_name.get(identity.artifact_name)
        if (
            identity.semantic_fingerprint != obj.semantic_fingerprint
            or observed is None
            or identity.physical_sha256 != observed.before_sha256
        ):
            raise BusinessContextEntryError(
                "Phase 3 predecessor identity or hash mismatch."
            )
    technical_hashes = {
        item.artifact_name: item
        for item in technical_impact.input_artifact_hashes
    }
    for name in _NAMES[:11]:
        recorded = technical_hashes.get(name)
        observed = hash_by_name[name]
        if (
            recorded is None
            or not recorded.unchanged
            or recorded.before_sha256 != observed.before_sha256
        ):
            raise BusinessContextEntryError(
                "Phase 4.1 predecessor physical hash mismatch."
            )


def _context_links(
    graph: FutureMetadataGraph,
    technical_impact: TechnicalImpactAnalysis,
    phase3: Phase3CertificationResult,
) -> tuple[ContextLinkRecord, ...]:
    dataset_scope = {
        item.dataset_urn for item in technical_impact.dataset_summaries
    }
    field_scope = {
        item.field_key.text: item.field_key
        for item in technical_impact.field_impacts
    }
    links: list[ContextLinkRecord] = []
    for relationship in graph.context_relationship_registry:
        anchor = _anchor(relationship, dataset_scope, field_scope)
        if anchor is None:
            continue
        dataset_urn, field_key = anchor
        asset_ids = _asset_ids(
            relationship,
            dataset_scope,
            dataset_urn,
        )
        if not asset_ids:
            raise BusinessContextValidationError(
                "A scoped context relationship has no certified asset."
            )
        links.append(
            ContextLinkRecord(
                context_relationship_id=(
                    relationship.current_relationship_id
                ),
                relationship_category=relationship.category,
                context_category=_CATEGORY[relationship.category],
                source_key=relationship.source_key,
                target_key=relationship.target_key,
                relationship_path=relationship.relationship_path,
                anchor_dataset_urn=dataset_urn,
                anchor_field_key=field_key,
                context_asset_ids=asset_ids,
                context_exposure_type=(
                    ContextExposureType.REACHABLE_CONTEXT
                    if relationship.category
                    is RelationshipCategory.BI_REACHABLE_CONTEXT
                    else ContextExposureType.DIRECT_CONTEXT
                ),
                certified_current_state=relationship.current_state,
                attributes=_attributes(relationship.current_attributes),
                current_evidence_ids=relationship.current_evidence_ids,
                future_graph_provenance_ids=relationship.provenance_ids,
                phase_3_certification_fingerprint=(
                    phase3.semantic_fingerprint
                ),
            )
        )
    return tuple(
        sorted(links, key=lambda item: item.context_relationship_id)
    )


def _anchor(
    relationship: FutureContextRelationship,
    dataset_scope: set[str],
    field_scope: dict[str, FieldMachineKey],
) -> tuple[str, FieldMachineKey | None] | None:
    if relationship.source_key in dataset_scope:
        return relationship.source_key, None
    if (
        relationship.category is RelationshipCategory.PIPELINE_CONTEXT
        and relationship.target_key in field_scope
    ):
        field_key = field_scope[relationship.target_key]
        return field_key.dataset_urn, field_key
    return None


def _asset_ids(
    relationship: FutureContextRelationship,
    dataset_scope: set[str],
    anchor_dataset_urn: str,
) -> tuple[str, ...]:
    if relationship.category is RelationshipCategory.PIPELINE_CONTEXT:
        candidates = (
            relationship.relationship_path + (relationship.source_key,)
        )
        return _ordered_unique(
            value
            for value in candidates
            if value.startswith("urn:li:dataFlow:")
            or value.startswith("urn:li:dataJob:")
        )
    if relationship.category is RelationshipCategory.BI_REACHABLE_CONTEXT:
        path = relationship.relationship_path or (
            anchor_dataset_urn,
            relationship.target_key,
        )
        return _ordered_unique(
            value
            for value in path + (relationship.target_key,)
            if value != anchor_dataset_urn
            and not (
                value.startswith("urn:li:dataset:")
                and value in dataset_scope
            )
        )
    return (relationship.target_key,)


def _technical_mappings(
    links: tuple[ContextLinkRecord, ...],
    technical_impact: TechnicalImpactAnalysis,
) -> tuple[TechnicalToContextMapping, ...]:
    fields_by_dataset: dict[str, list[FieldTechnicalImpact]] = defaultdict(
        list
    )
    for field in technical_impact.field_impacts:
        fields_by_dataset[field.dataset_urn].append(field)
    mappings: list[TechnicalToContextMapping] = []
    for link in links:
        fields = fields_by_dataset[link.anchor_dataset_urn]
        if link.anchor_field_key is not None:
            fields = [
                item
                for item in fields
                if item.field_key == link.anchor_field_key
            ]
        for technical in sorted(fields, key=lambda item: item.field_key.text):
            for asset_id in link.context_asset_ids:
                mapping_id = _mapping_id(
                    link.context_relationship_id,
                    technical.field_key,
                    asset_id,
                )
                mappings.append(
                    TechnicalToContextMapping(
                        mapping_id=mapping_id,
                        technical_subject_type=TechnicalSubjectType.FIELD,
                        technical_subject_id=technical.field_key.text,
                        technical_field_key=technical.field_key,
                        technical_impact_state=(
                            technical.technical_impact_state
                        ),
                        dataset_urn=technical.dataset_urn,
                        context_relationship_id=(
                            link.context_relationship_id
                        ),
                        context_category=link.context_category,
                        context_asset_id=asset_id,
                        context_exposure_type=(
                            link.context_exposure_type
                        ),
                        context_linkage_state=_linkage_state(
                            technical.technical_impact_state
                        ),
                        root_technical_cause_ids=technical.cause_ids,
                        supporting_field_keys=(technical.field_key,),
                        supporting_path_ids=technical.supporting_path_ids,
                        technical_provenance_ids=_ordered_unique(
                            technical.current_provenance_ids
                            + technical.counterfactual_provenance_ids
                        ),
                        context_provenance_ids=_ordered_unique(
                            link.current_evidence_ids
                            + link.future_graph_provenance_ids
                        ),
                        human_explanation=_mapping_explanation(
                            technical,
                            link,
                            asset_id,
                        ),
                    )
                )
    return tuple(sorted(mappings, key=lambda item: item.mapping_id))


def _context_assets(
    links: tuple[ContextLinkRecord, ...],
    mappings: tuple[TechnicalToContextMapping, ...],
) -> tuple[ContextAssetRecord, ...]:
    link_by_id = {
        item.context_relationship_id: item for item in links
    }
    mappings_by_asset: dict[
        str,
        list[TechnicalToContextMapping],
    ] = defaultdict(list)
    for mapping in mappings:
        mappings_by_asset[mapping.context_asset_id].append(mapping)
    assets: list[ContextAssetRecord] = []
    for asset_id, supported in mappings_by_asset.items():
        related_links = tuple(
            sorted(
                {
                    link_by_id[item.context_relationship_id]
                    for item in supported
                },
                key=lambda item: item.context_relationship_id,
            )
        )
        categories = {item.context_category for item in related_links}
        if len(categories) != 1:
            raise BusinessContextValidationError(
                "A certified context identity has conflicting categories."
            )
        category = next(iter(categories))
        resolution = (
            ContextResolutionState.UNRESOLVED
            if any(
                item.certified_current_state == "unresolved"
                and item.target_key == asset_id
                for item in related_links
            )
            else ContextResolutionState.RESOLVED
        )
        attributes = tuple(
            sorted(
                {
                    attribute
                    for link in related_links
                    for attribute in _asset_attributes(link, asset_id)
                },
                key=_attribute_sort_key,
            )
        )
        assets.append(
            ContextAssetRecord(
                asset_id=asset_id,
                category=category,
                asset_type=_asset_type(asset_id, category, attributes),
                display_name=_display_name(attributes),
                resolution_state=resolution,
                certified_relationship_ids=tuple(
                    item.context_relationship_id for item in related_links
                ),
                supporting_dataset_urns=tuple(
                    sorted({item.dataset_urn for item in supported})
                ),
                supporting_field_keys=tuple(
                    sorted(
                        {item.technical_field_key for item in supported},
                        key=lambda item: item.text,
                    )
                ),
                supporting_path_ids=tuple(
                    sorted(
                        {
                            value
                            for item in supported
                            for value in item.supporting_path_ids
                        }
                    )
                ),
                root_technical_cause_ids=tuple(
                    sorted(
                        {
                            value
                            for item in supported
                            for value in item.root_technical_cause_ids
                        }
                    )
                ),
                attributes=attributes,
                current_evidence_ids=tuple(
                    sorted(
                        {
                            value
                            for item in related_links
                            for value in item.current_evidence_ids
                        }
                    )
                ),
                future_graph_provenance_ids=tuple(
                    sorted(
                        {
                            value
                            for item in related_links
                            for value in item.future_graph_provenance_ids
                        }
                    )
                ),
            )
        )
    return tuple(sorted(assets, key=lambda item: item.asset_id))


def _asset_attributes(
    link: ContextLinkRecord,
    asset_id: str,
) -> tuple[ContextAttribute, ...]:
    if asset_id in (link.source_key, link.target_key):
        return link.attributes
    if asset_id.startswith("urn:li:dataFlow:"):
        return tuple(
            item
            for item in link.attributes
            if item.name in ("flow_name", "flow_platform", "flow_urn")
        )
    if asset_id.startswith("urn:li:dataJob:"):
        return tuple(
            item
            for item in link.attributes
            if item.name in ("job_name", "job_platform")
        )
    return ()


def _dataset_summaries(
    links: tuple[ContextLinkRecord, ...],
    mappings: tuple[TechnicalToContextMapping, ...],
    technical_impact: TechnicalImpactAnalysis,
) -> tuple[DatasetContextSummary, ...]:
    links_by_dataset: dict[str, list[ContextLinkRecord]] = defaultdict(list)
    for link in links:
        links_by_dataset[link.anchor_dataset_urn].append(link)
    mappings_by_dataset: dict[
        str,
        list[TechnicalToContextMapping],
    ] = defaultdict(list)
    for mapping in mappings:
        mappings_by_dataset[mapping.dataset_urn].append(mapping)
    fields_by_dataset: dict[str, list[FieldTechnicalImpact]] = defaultdict(
        list
    )
    for item in technical_impact.field_impacts:
        fields_by_dataset[item.dataset_urn].append(item)
    summaries: list[DatasetContextSummary] = []
    for dataset in sorted(
        technical_impact.dataset_summaries,
        key=lambda item: item.dataset_urn,
    ):
        dataset_links = links_by_dataset[dataset.dataset_urn]
        dataset_mappings = mappings_by_dataset[dataset.dataset_urn]
        fields = fields_by_dataset[dataset.dataset_urn]
        counts = Counter(item.technical_impact_state for item in fields)
        asset_ids = {
            item.context_asset_id for item in dataset_mappings
        }
        summaries.append(
            DatasetContextSummary(
                dataset_urn=dataset.dataset_urn,
                technical_field_keys=tuple(
                    sorted(
                        (item.field_key for item in fields),
                        key=lambda item: item.text,
                    )
                ),
                confirmed_technical_fields=counts[
                    TechnicalImpactState.CONFIRMED_IMPACT
                ],
                potential_technical_fields=counts[
                    TechnicalImpactState.POTENTIAL_IMPACT
                ],
                unresolved_technical_fields=counts[
                    TechnicalImpactState.UNRESOLVED_IMPACT
                ],
                no_demonstrated_technical_fields=counts[
                    TechnicalImpactState.NO_DEMONSTRATED_IMPACT
                ],
                owner_count=_unique_assets(
                    dataset_mappings,
                    ContextCategory.OWNERSHIP,
                ),
                domain_count=_unique_assets(
                    dataset_mappings,
                    ContextCategory.DOMAIN,
                ),
                tag_count=_unique_assets(
                    dataset_mappings,
                    ContextCategory.TAG,
                ),
                glossary_assignment_count=_link_count(
                    dataset_links,
                    ContextCategory.GLOSSARY,
                ),
                structured_property_assignment_count=_link_count(
                    dataset_links,
                    ContextCategory.STRUCTURED_PROPERTY,
                ),
                data_product_count=_unique_assets(
                    dataset_mappings,
                    ContextCategory.DATA_PRODUCT,
                ),
                document_count=_unique_assets(
                    dataset_mappings,
                    ContextCategory.DOCUMENT,
                ),
                pipeline_context_link_count=_link_count(
                    dataset_links,
                    ContextCategory.PIPELINE,
                ),
                bi_context_link_count=_link_count(
                    dataset_links,
                    ContextCategory.BI,
                ),
                unique_context_asset_count=len(asset_ids),
                context_asset_ids=tuple(sorted(asset_ids)),
                context_relationship_ids=tuple(
                    sorted(
                        item.context_relationship_id
                        for item in dataset_links
                    )
                ),
                root_technical_cause_ids=tuple(
                    sorted(
                        {
                            value
                            for item in fields
                            for value in item.cause_ids
                        }
                    )
                ),
            )
        )
    return tuple(summaries)


def _reverse_indexes(
    mappings: tuple[TechnicalToContextMapping, ...],
    technical_impact: TechnicalImpactAnalysis,
    assets: tuple[ContextAssetRecord, ...],
) -> ContextReverseIndexes:
    by_field_values: list[FieldContextReverseIndex] = []
    for field in sorted(
        technical_impact.field_impacts,
        key=lambda item: item.field_key.text,
    ):
        supported = [
            item
            for item in mappings
            if item.technical_field_key == field.field_key
        ]
        by_field_values.append(
            FieldContextReverseIndex(
                field_key=field.field_key,
                context_asset_ids=tuple(
                    sorted({item.context_asset_id for item in supported})
                ),
                context_relationship_ids=tuple(
                    sorted(
                        {
                            item.context_relationship_id
                            for item in supported
                        }
                    )
                ),
                mapping_ids=tuple(
                    sorted(item.mapping_id for item in supported)
                ),
            )
        )
    by_dataset_values: list[DatasetContextReverseIndex] = []
    for dataset in sorted(
        technical_impact.dataset_summaries,
        key=lambda item: item.dataset_urn,
    ):
        supported = [
            item
            for item in mappings
            if item.dataset_urn == dataset.dataset_urn
        ]
        by_dataset_values.append(
            DatasetContextReverseIndex(
                dataset_urn=dataset.dataset_urn,
                technical_field_keys=tuple(
                    sorted(
                        {
                            item.technical_field_key
                            for item in supported
                        },
                        key=lambda item: item.text,
                    )
                ),
                context_asset_ids=tuple(
                    sorted({item.context_asset_id for item in supported})
                ),
                context_relationship_ids=tuple(
                    sorted(
                        {
                            item.context_relationship_id
                            for item in supported
                        }
                    )
                ),
                mapping_ids=tuple(
                    sorted(item.mapping_id for item in supported)
                ),
            )
        )
    by_asset_values: list[ContextAssetReverseIndex] = []
    for asset in assets:
        supported = [
            item
            for item in mappings
            if item.context_asset_id == asset.asset_id
        ]
        by_asset_values.append(
            ContextAssetReverseIndex(
                context_asset_id=asset.asset_id,
                linked_dataset_urns=tuple(
                    sorted({item.dataset_urn for item in supported})
                ),
                linked_field_keys=tuple(
                    sorted(
                        {
                            item.technical_field_key
                            for item in supported
                        },
                        key=lambda item: item.text,
                    )
                ),
                supporting_path_ids=tuple(
                    sorted(
                        {
                            value
                            for item in supported
                            for value in item.supporting_path_ids
                        }
                    )
                ),
                root_technical_cause_ids=tuple(
                    sorted(
                        {
                            value
                            for item in supported
                            for value in item.root_technical_cause_ids
                        }
                    )
                ),
                mapping_ids=tuple(
                    sorted(item.mapping_id for item in supported)
                ),
            )
        )
    return ContextReverseIndexes(
        by_field=tuple(by_field_values),
        by_dataset=tuple(by_dataset_values),
        by_context_asset=tuple(by_asset_values),
    )


def _context_causes(
    technical_impact: TechnicalImpactAnalysis,
    mappings: tuple[TechnicalToContextMapping, ...],
) -> tuple[ContextExposureCause, ...]:
    values: list[ContextExposureCause] = []
    for cause in sorted(
        technical_impact.technical_impact_causes,
        key=lambda item: item.cause_id,
    ):
        supported = [
            item
            for item in mappings
            if cause.cause_id in item.root_technical_cause_ids
        ]
        values.append(
            ContextExposureCause(
                cause_id=cause.cause_id,
                root_relationship_id=cause.root_relationship_id,
                technical_impact_state=cause.impact_state,
                linked_context_asset_ids=tuple(
                    sorted({item.context_asset_id for item in supported})
                ),
                linked_dataset_urns=tuple(
                    sorted({item.dataset_urn for item in supported})
                ),
                linked_field_keys=tuple(
                    sorted(
                        {
                            item.technical_field_key
                            for item in supported
                        },
                        key=lambda item: item.text,
                    )
                ),
                mapping_ids=tuple(
                    sorted(item.mapping_id for item in supported)
                ),
                phase_4_1_technical_impact_fingerprint=(
                    technical_impact.semantic_fingerprint
                ),
            )
        )
    return tuple(values)


def _aggregate(
    graph: FutureMetadataGraph,
    links: tuple[ContextLinkRecord, ...],
    assets: tuple[ContextAssetRecord, ...],
    mappings: tuple[TechnicalToContextMapping, ...],
    reverse_indexes: ContextReverseIndexes,
) -> BusinessContextAggregateMetrics:
    def category_count(category: ContextCategory) -> int:
        return sum(item.category is category for item in assets)

    def asset_type_count(asset_type: ContextAssetType) -> int:
        return sum(item.asset_type is asset_type for item in assets)

    return BusinessContextAggregateMetrics(
        certified_graph_context_relationships=len(
            graph.context_relationship_registry
        ),
        scoped_context_relationships=len(links),
        excluded_context_relationships=(
            len(graph.context_relationship_registry) - len(links)
        ),
        unique_owners=category_count(ContextCategory.OWNERSHIP),
        unique_domains=category_count(ContextCategory.DOMAIN),
        unique_tags=category_count(ContextCategory.TAG),
        unique_glossary_terms=category_count(ContextCategory.GLOSSARY),
        structured_property_assignments=sum(
            item.context_category is ContextCategory.STRUCTURED_PROPERTY
            for item in links
        ),
        structured_property_definitions=category_count(
            ContextCategory.STRUCTURED_PROPERTY
        ),
        unique_data_products=category_count(
            ContextCategory.DATA_PRODUCT
        ),
        unique_documents=category_count(ContextCategory.DOCUMENT),
        pipeline_context_assets=category_count(ContextCategory.PIPELINE),
        bi_context_assets=category_count(ContextCategory.BI),
        charts=asset_type_count(ContextAssetType.CHART),
        dashboards=asset_type_count(ContextAssetType.DASHBOARD),
        total_unique_context_assets=len(assets),
        total_technical_to_context_mappings=len(mappings),
        context_assets_linked_to_multiple_datasets=sum(
            len(item.linked_dataset_urns) > 1
            for item in reverse_indexes.by_context_asset
        ),
        context_assets_linked_through_multiple_technical_fields=sum(
            len(item.linked_field_keys) > 1
            for item in reverse_indexes.by_context_asset
        ),
    )


def _asset_type(
    asset_id: str,
    category: ContextCategory,
    attributes: tuple[ContextAttribute, ...],
) -> ContextAssetType:
    if asset_id.startswith("urn:li:corpuser:"):
        return ContextAssetType.OWNER_USER
    if asset_id.startswith("urn:li:corpGroup:"):
        return ContextAssetType.OWNER_GROUP
    if asset_id.startswith("urn:li:domain:"):
        return ContextAssetType.DOMAIN
    if asset_id.startswith("urn:li:tag:"):
        return ContextAssetType.TAG
    if asset_id.startswith("urn:li:glossaryTerm:"):
        return ContextAssetType.GLOSSARY_TERM
    if asset_id.startswith("urn:li:structuredProperty:"):
        return ContextAssetType.STRUCTURED_PROPERTY_DEFINITION
    if asset_id.startswith("urn:li:dataProduct:"):
        return ContextAssetType.DATA_PRODUCT
    if asset_id.startswith("urn:li:document:"):
        return ContextAssetType.DOCUMENT
    if asset_id.startswith("urn:li:dataFlow:"):
        return ContextAssetType.DATA_FLOW
    if asset_id.startswith("urn:li:dataJob:"):
        return ContextAssetType.DATA_JOB
    if asset_id.startswith("urn:li:chart:"):
        return ContextAssetType.CHART
    if asset_id.startswith("urn:li:dashboard:"):
        return ContextAssetType.DASHBOARD
    if (
        category is ContextCategory.BI
        and asset_id.startswith("urn:li:dataset:")
    ):
        return ContextAssetType.BI_DATASET
    entity_type = _attribute_value(attributes, "entity_type")
    if entity_type == "CHART":
        return ContextAssetType.CHART
    if entity_type == "DASHBOARD":
        return ContextAssetType.DASHBOARD
    return ContextAssetType.CERTIFIED_CONTEXT


def _linkage_state(
    state: TechnicalImpactState,
) -> ContextLinkageState:
    return {
        TechnicalImpactState.CONFIRMED_IMPACT: (
            ContextLinkageState.CONTEXT_LINKED_TO_CONFIRMED_TECHNICAL_STATE
        ),
        TechnicalImpactState.POTENTIAL_IMPACT: (
            ContextLinkageState.CONTEXT_LINKED_TO_POTENTIAL_TECHNICAL_STATE
        ),
        TechnicalImpactState.UNRESOLVED_IMPACT: (
            ContextLinkageState.CONTEXT_LINKED_TO_UNRESOLVED_TECHNICAL_STATE
        ),
        TechnicalImpactState.NO_DEMONSTRATED_IMPACT: (
            ContextLinkageState
            .CONTEXT_LINKED_TO_NO_DEMONSTRATED_TECHNICAL_STATE
        ),
    }[state]


def _mapping_explanation(
    technical: FieldTechnicalImpact,
    link: ContextLinkRecord,
    asset_id: str,
) -> str:
    reachability = (
        "reachable"
        if link.context_exposure_type
        is ContextExposureType.REACHABLE_CONTEXT
        else "direct"
    )
    return (
        f"{asset_id} is {reachability} certified "
        f"{link.context_category.value} context for "
        f"{technical.dataset_urn}. The Dataset contains technically exposed "
        f"field {technical.field_key.field_path}, whose Phase 4.1 state "
        f"remains {technical.technical_impact_state.value}."
    )


def _canonical_narrative(
    metrics: BusinessContextAggregateMetrics,
    technical_impact: TechnicalImpactAnalysis,
) -> str:
    return (
        f"CHRONOS linked {metrics.total_unique_context_assets} unique "
        f"certified context assets through "
        f"{metrics.scoped_context_relationships} scoped relationships to "
        f"{len(technical_impact.field_impacts)} downstream technical fields "
        f"across {len(technical_impact.dataset_summaries)} datasets. These "
        "records preserve organizational, governance, pipeline, and consumer "
        "context alongside the unchanged Phase 4.1 technical states; they "
        "make no severity, risk, repair, notification, or deployment "
        "conclusion."
    )


def _attributes(values: Iterable[object]) -> tuple[ContextAttribute, ...]:
    return tuple(
        ContextAttribute(item.name, tuple(item.values))
        for item in values
    )


def _display_name(
    attributes: tuple[ContextAttribute, ...],
) -> str | None:
    for name in (
        "display_name",
        "name",
        "title",
        "qualified_name",
        "job_name",
        "flow_name",
    ):
        value = _attribute_value(attributes, name)
        if isinstance(value, str) and value:
            return value
    return None


def _attribute_value(
    attributes: tuple[ContextAttribute, ...],
    name: str,
) -> object:
    for item in attributes:
        if item.name == name and item.values:
            return item.values[0]
    return None


def _attribute_sort_key(
    attribute: ContextAttribute,
) -> tuple[str, str]:
    return attribute.name, repr(attribute.values)


def _unique_assets(
    mappings: list[TechnicalToContextMapping],
    category: ContextCategory,
) -> int:
    return len(
        {
            item.context_asset_id
            for item in mappings
            if item.context_category is category
        }
    )


def _link_count(
    links: list[ContextLinkRecord],
    category: ContextCategory,
) -> int:
    return sum(item.context_category is category for item in links)


def _mapping_id(
    relationship_id: str,
    field_key: FieldMachineKey,
    asset_id: str,
) -> str:
    payload = "\x1f".join(
        (relationship_id, field_key.text, asset_id)
    ).encode("utf-8")
    return "context-mapping-" + hashlib.sha256(payload).hexdigest()[:24]


def _ordered_unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _timestamp(clock: Clock | None) -> str:
    value = clock() if clock is not None else datetime.now(timezone.utc)
    if value.tzinfo is None:
        raise BusinessContextValidationError(
            "Phase 4.2 clock must return a timezone-aware datetime."
        )
    return value.isoformat()
