"""Strict parsing for the Phase 6.3 pull-request proposal."""

from __future__ import annotations

from dataclasses import fields
from enum import Enum
from pathlib import PurePosixPath
from typing import Any, Mapping

from .errors import PullRequestProposalError
from .models import (
    FileModelMapping,
    IntakeMode,
    ProposalMetadataItem,
    PullRequestAnalysisProposal,
    PullRequestOperation,
    RepositoryIdentityInput,
)


_ALLOWED = {
    "proposal_id", "analysis_id", "operation", "source_snapshot_fingerprint",
    "repository_identity", "base_revision", "head_revision", "intake_mode",
    "source_snapshot_id", "pull_request_number", "scenario_id", "title",
    "description", "created_at", "proposal_metadata", "file_model_mappings",
}
_REQUIRED = {
    "proposal_id", "analysis_id", "operation", "source_snapshot_fingerprint",
    "repository_identity", "base_revision", "head_revision", "intake_mode",
}
_REPOSITORY_KEYS = {"repository_name", "repository_namespace"}
_MAPPING_KEYS = {
    "path", "model_dataset_urn", "model_relation", "sql_dialect",
    "dbt_manifest_path",
}


def parse_pr_proposal(value: Mapping[str, Any]) -> PullRequestAnalysisProposal:
    if not isinstance(value, Mapping):
        raise PullRequestProposalError("PR proposal must be a JSON object.")
    unknown = sorted(set(value) - _ALLOWED)
    missing = sorted(_REQUIRED - set(value))
    if unknown or missing:
        detail = f"unknown={unknown}" if unknown else f"missing={missing}"
        raise PullRequestProposalError(f"Invalid PR proposal properties: {detail}.")
    try:
        operation = PullRequestOperation(value["operation"])
        intake_mode = IntakeMode(value["intake_mode"])
    except (TypeError, ValueError) as exc:
        raise PullRequestProposalError("Invalid PR operation or intake_mode.") from exc
    repository = _repository(value["repository_identity"])
    kwargs = dict(value)
    kwargs["operation"] = operation
    kwargs["intake_mode"] = intake_mode
    kwargs["repository_identity"] = repository
    kwargs["proposal_metadata"] = _metadata(value.get("proposal_metadata", {}))
    kwargs["file_model_mappings"] = _mappings(value.get("file_model_mappings", []))
    proposal = PullRequestAnalysisProposal(**kwargs)
    _validate(proposal)
    return proposal


def pr_proposal_to_dict(
    proposal: PullRequestAnalysisProposal, *, semantic: bool = False
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for item in fields(proposal):
        if semantic and item.name == "created_at":
            continue
        value = getattr(proposal, item.name)
        if isinstance(value, Enum):
            value = value.value
        elif item.name == "repository_identity":
            value = {
                "repository_name": value.repository_name,
                **(
                    {"repository_namespace": value.repository_namespace}
                    if value.repository_namespace else {}
                ),
            }
        elif item.name == "proposal_metadata":
            value = {entry.key: entry.value for entry in value}
        elif item.name == "file_model_mappings":
            value = [
                {
                    "path": entry.path,
                    "model_dataset_urn": entry.model_dataset_urn,
                    "model_relation": entry.model_relation,
                    "sql_dialect": entry.sql_dialect,
                    **(
                        {"dbt_manifest_path": entry.dbt_manifest_path}
                        if entry.dbt_manifest_path else {}
                    ),
                }
                for entry in value
            ]
        if value is not None:
            result[item.name] = value
    return result


def _repository(value: Any) -> RepositoryIdentityInput:
    if not isinstance(value, Mapping) or set(value) - _REPOSITORY_KEYS:
        raise PullRequestProposalError("repository_identity has unknown properties.")
    name = value.get("repository_name")
    namespace = value.get("repository_namespace")
    if not isinstance(name, str) or not name.strip():
        raise PullRequestProposalError("repository_name must be non-empty.")
    if namespace is not None and (not isinstance(namespace, str) or not namespace.strip()):
        raise PullRequestProposalError("repository_namespace must be non-empty when supplied.")
    return RepositoryIdentityInput(name, namespace)


def _metadata(value: Any) -> tuple[ProposalMetadataItem, ...]:
    if not isinstance(value, Mapping) or not all(
        isinstance(key, str) and isinstance(item, str) for key, item in value.items()
    ):
        raise PullRequestProposalError("proposal_metadata must contain string pairs.")
    return tuple(ProposalMetadataItem(key, value[key]) for key in sorted(value))


def _mappings(value: Any) -> tuple[FileModelMapping, ...]:
    if not isinstance(value, list):
        raise PullRequestProposalError("file_model_mappings must be an array.")
    result = []
    for raw in value:
        if not isinstance(raw, Mapping) or set(raw) != (
            {"path", "model_dataset_urn", "model_relation", "sql_dialect"}
            | ({"dbt_manifest_path"} if "dbt_manifest_path" in raw else set())
        ):
            raise PullRequestProposalError("Each file model mapping has an invalid shape.")
        mapping = FileModelMapping(**raw)
        _safe_path(mapping.path)
        if mapping.dbt_manifest_path:
            _safe_path(mapping.dbt_manifest_path)
        if not mapping.model_dataset_urn.startswith("urn:li:dataset:("):
            raise PullRequestProposalError("Model mappings require a DataHub Dataset URN.")
        result.append(mapping)
    paths = [item.path for item in result]
    if len(paths) != len(set(paths)):
        raise PullRequestProposalError("Duplicate file model mapping path.")
    return tuple(sorted(result, key=lambda item: item.path))


def _validate(proposal: PullRequestAnalysisProposal) -> None:
    strings = (
        proposal.proposal_id, proposal.analysis_id, proposal.source_snapshot_fingerprint,
        proposal.base_revision, proposal.head_revision,
    )
    if any(not isinstance(item, str) or not item.strip() for item in strings):
        raise PullRequestProposalError("Required PR proposal strings must be non-empty.")
    if proposal.base_revision == proposal.head_revision:
        raise PullRequestProposalError("base_revision and head_revision must differ.")
    optional = (
        proposal.source_snapshot_id, proposal.scenario_id, proposal.title,
        proposal.description, proposal.created_at,
    )
    if any(item is not None and not isinstance(item, str) for item in optional):
        raise PullRequestProposalError("Optional PR proposal text must be strings.")
    if proposal.pull_request_number is not None and (
        not isinstance(proposal.pull_request_number, int)
        or isinstance(proposal.pull_request_number, bool)
        or proposal.pull_request_number <= 0
    ):
        raise PullRequestProposalError("pull_request_number must be a positive integer.")


def _safe_path(value: str) -> None:
    if not isinstance(value, str) or not value or "\\" in value:
        raise PullRequestProposalError("Mapping paths must be non-empty POSIX paths.")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise PullRequestProposalError("Mapping path escapes the repository.")
