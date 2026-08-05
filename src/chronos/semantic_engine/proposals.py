"""Strict semantic proposal parsing and serialization."""

from __future__ import annotations

from dataclasses import fields
from enum import Enum
from typing import Any, Mapping

from .errors import SemanticProposalError
from .models import MetadataItem, SemanticCodeChangeProposal, SemanticOperation


_ALLOWED = {
    "proposal_id",
    "analysis_id",
    "operation",
    "model_dataset_urn",
    "sql_dialect",
    "before_code_reference",
    "after_code_reference",
    "source_snapshot_fingerprint",
    "source_snapshot_id",
    "dbt_manifest_reference",
    "scenario_id",
    "model_relation",
    "description",
    "created_at",
    "proposal_metadata",
}
_REQUIRED = {
    "proposal_id",
    "analysis_id",
    "operation",
    "model_dataset_urn",
    "sql_dialect",
    "before_code_reference",
    "after_code_reference",
    "source_snapshot_fingerprint",
}


def parse_semantic_proposal(value: Mapping[str, Any]) -> SemanticCodeChangeProposal:
    if not isinstance(value, Mapping):
        raise SemanticProposalError("Semantic proposal must be a JSON object.")
    unknown = sorted(set(value) - _ALLOWED)
    missing = sorted(_REQUIRED - set(value))
    if unknown:
        raise SemanticProposalError(
            f"Unknown semantic proposal properties: {', '.join(unknown)}."
        )
    if missing:
        raise SemanticProposalError(
            f"Missing semantic proposal properties: {', '.join(missing)}."
        )
    try:
        operation = SemanticOperation(value["operation"])
    except (TypeError, ValueError) as exc:
        raise SemanticProposalError(
            "operation must be SEMANTIC_CODE_CHANGE."
        ) from exc
    kwargs = dict(value)
    kwargs["operation"] = operation
    kwargs["proposal_metadata"] = _metadata(kwargs.get("proposal_metadata", {}))
    proposal = SemanticCodeChangeProposal(**kwargs)
    _validate(proposal)
    return proposal


def semantic_proposal_to_dict(
    proposal: SemanticCodeChangeProposal,
    *,
    semantic: bool = False,
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for item in fields(proposal):
        if semantic and item.name == "created_at":
            continue
        value = getattr(proposal, item.name)
        if isinstance(value, Enum):
            value = value.value
        elif item.name == "proposal_metadata":
            value = {entry.key: entry.value for entry in value}
        if value is not None:
            result[item.name] = value
    return result


def _metadata(value: Any) -> tuple[MetadataItem, ...]:
    if not isinstance(value, Mapping):
        raise SemanticProposalError("proposal_metadata must be a JSON object.")
    if not all(isinstance(key, str) and isinstance(item, str) for key, item in value.items()):
        raise SemanticProposalError(
            "proposal_metadata keys and values must be strings."
        )
    return tuple(MetadataItem(key=key, value=value[key]) for key in sorted(value))


def _validate(proposal: SemanticCodeChangeProposal) -> None:
    required = (
        proposal.proposal_id,
        proposal.analysis_id,
        proposal.model_dataset_urn,
        proposal.sql_dialect,
        proposal.before_code_reference,
        proposal.after_code_reference,
        proposal.source_snapshot_fingerprint,
    )
    if any(not isinstance(item, str) or not item.strip() for item in required):
        raise SemanticProposalError("Required semantic proposal strings must be non-empty.")
    if not (
        proposal.model_dataset_urn.startswith("urn:li:dataset:(")
        and proposal.model_dataset_urn.endswith(")")
    ):
        raise SemanticProposalError("model_dataset_urn must be a DataHub Dataset URN.")
    optional = (
        proposal.source_snapshot_id,
        proposal.dbt_manifest_reference,
        proposal.scenario_id,
        proposal.model_relation,
        proposal.description,
        proposal.created_at,
    )
    if any(item is not None and not isinstance(item, str) for item in optional):
        raise SemanticProposalError("Optional semantic proposal text must be strings.")
