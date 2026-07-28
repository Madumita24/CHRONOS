"""Read-only queries over a materialized Phase 4.2 artifact."""

from __future__ import annotations

from chronos.snapshot import FieldMachineKey

from .models import (
    BusinessContextPropagation,
    ContextAssetRecord,
    ContextCategory,
    TechnicalToContextMapping,
)


def get_context_for_field(
    result: BusinessContextPropagation,
    field_key: FieldMachineKey,
) -> tuple[ContextAssetRecord, ...]:
    index = next(
        (
            item
            for item in result.reverse_indexes.by_field
            if item.field_key == field_key
        ),
        None,
    )
    if index is None:
        return ()
    wanted = set(index.context_asset_ids)
    return tuple(
        item
        for item in result.context_asset_registry
        if item.asset_id in wanted
    )


def get_context_for_dataset(
    result: BusinessContextPropagation,
    dataset_urn: str,
) -> tuple[ContextAssetRecord, ...]:
    index = next(
        (
            item
            for item in result.reverse_indexes.by_dataset
            if item.dataset_urn == dataset_urn
        ),
        None,
    )
    if index is None:
        return ()
    wanted = set(index.context_asset_ids)
    return tuple(
        item
        for item in result.context_asset_registry
        if item.asset_id in wanted
    )


def get_owners_for_technical_scope(
    result: BusinessContextPropagation,
) -> tuple[ContextAssetRecord, ...]:
    return _category(result, ContextCategory.OWNERSHIP)


def get_domains_for_technical_scope(
    result: BusinessContextPropagation,
) -> tuple[ContextAssetRecord, ...]:
    return _category(result, ContextCategory.DOMAIN)


def get_data_products_for_technical_scope(
    result: BusinessContextPropagation,
) -> tuple[ContextAssetRecord, ...]:
    return _category(result, ContextCategory.DATA_PRODUCT)


def get_documents_for_technical_scope(
    result: BusinessContextPropagation,
) -> tuple[ContextAssetRecord, ...]:
    return _category(result, ContextCategory.DOCUMENT)


def get_pipeline_context_for_technical_scope(
    result: BusinessContextPropagation,
) -> tuple[ContextAssetRecord, ...]:
    return _category(result, ContextCategory.PIPELINE)


def get_bi_context_for_technical_scope(
    result: BusinessContextPropagation,
) -> tuple[ContextAssetRecord, ...]:
    return _category(result, ContextCategory.BI)


def get_technical_sources_for_context_asset(
    result: BusinessContextPropagation,
    asset_id: str,
) -> tuple[TechnicalToContextMapping, ...]:
    return tuple(
        item
        for item in result.technical_to_context_mappings
        if item.context_asset_id == asset_id
    )


def _category(
    result: BusinessContextPropagation,
    category: ContextCategory,
) -> tuple[ContextAssetRecord, ...]:
    return tuple(
        item
        for item in result.context_asset_registry
        if item.category is category
    )
