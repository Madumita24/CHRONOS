"""Strict parsing and serialization for repair-generation proposals."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .errors import RepairProposalError
from .models import (
    ProposalMetadataItem,
    RepairGenerationProposal,
    RepairMode,
    RepairOperation,
    RepairRepositoryIdentity,
)


_ROOT_KEYS = {
    "proposal_id", "repair_analysis_id", "operation", "predecessor_analysis_id",
    "predecessor_manifest_fingerprint", "repository_identity", "base_revision",
    "head_revision", "repair_mode", "target_root_cause_ids",
    "target_logical_change_group_ids", "scenario_id", "description",
    "proposal_metadata",
}
_REQUIRED_KEYS = {
    "proposal_id", "repair_analysis_id", "operation", "predecessor_analysis_id",
    "predecessor_manifest_fingerprint", "repository_identity", "base_revision",
    "head_revision", "repair_mode",
}
_REPOSITORY_KEYS = {
    "repository_name", "repository_namespace", "repository_fingerprint",
}


def parse_repair_proposal(value: Mapping[str, Any]) -> RepairGenerationProposal:
    if not isinstance(value, Mapping):
        raise RepairProposalError("Repair proposal must be a JSON object.")
    unknown = set(value) - _ROOT_KEYS
    missing = _REQUIRED_KEYS - set(value)
    if unknown or missing:
        raise RepairProposalError(
            f"Repair proposal has unknown {sorted(unknown)} or missing {sorted(missing)} properties."
        )
    operation = _enum(RepairOperation, value["operation"], "operation")
    mode = _enum(RepairMode, value["repair_mode"], "repair_mode")
    repository = _repository(value["repository_identity"])
    roots = _identifier_list(value.get("target_root_cause_ids", []), "target_root_cause_ids")
    groups = _identifier_list(
        value.get("target_logical_change_group_ids", []),
        "target_logical_change_group_ids",
    )
    if mode is RepairMode.ALL_SUPPORTED and (roots or groups):
        raise RepairProposalError("ALL_SUPPORTED does not accept selected roots or groups.")
    if mode is RepairMode.SELECTED_ROOTS and (not roots or groups):
        raise RepairProposalError("SELECTED_ROOTS requires only target_root_cause_ids.")
    if mode is RepairMode.SELECTED_GROUPS and (not groups or roots):
        raise RepairProposalError("SELECTED_GROUPS requires only target_logical_change_group_ids.")
    proposal = RepairGenerationProposal(
        proposal_id=_text(value["proposal_id"], "proposal_id"),
        repair_analysis_id=_text(value["repair_analysis_id"], "repair_analysis_id"),
        operation=operation,
        predecessor_analysis_id=_text(
            value["predecessor_analysis_id"], "predecessor_analysis_id"
        ),
        predecessor_manifest_fingerprint=_fingerprint(
            value["predecessor_manifest_fingerprint"]
        ),
        repository_identity=repository,
        base_revision=_text(value["base_revision"], "base_revision"),
        head_revision=_text(value["head_revision"], "head_revision"),
        repair_mode=mode,
        target_root_cause_ids=roots,
        target_logical_change_group_ids=groups,
        scenario_id=_optional_text(value.get("scenario_id"), "scenario_id"),
        description=_optional_text(value.get("description"), "description", maximum=2000),
        proposal_metadata=_metadata(value.get("proposal_metadata", {})),
    )
    if proposal.repair_analysis_id == proposal.predecessor_analysis_id:
        raise RepairProposalError("Repair and predecessor analysis identities must differ.")
    return proposal


def repair_proposal_to_dict(
    proposal: RepairGenerationProposal, *, semantic: bool = False
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "proposal_id": proposal.proposal_id,
        "repair_analysis_id": proposal.repair_analysis_id,
        "operation": proposal.operation.value,
        "predecessor_analysis_id": proposal.predecessor_analysis_id,
        "predecessor_manifest_fingerprint": proposal.predecessor_manifest_fingerprint,
        "repository_identity": {
            "repository_name": proposal.repository_identity.repository_name,
            **(
                {"repository_namespace": proposal.repository_identity.repository_namespace}
                if proposal.repository_identity.repository_namespace else {}
            ),
            **(
                {"repository_fingerprint": proposal.repository_identity.repository_fingerprint}
                if proposal.repository_identity.repository_fingerprint else {}
            ),
        },
        "base_revision": proposal.base_revision,
        "head_revision": proposal.head_revision,
        "repair_mode": proposal.repair_mode.value,
        "target_root_cause_ids": list(proposal.target_root_cause_ids),
        "target_logical_change_group_ids": list(
            proposal.target_logical_change_group_ids
        ),
        "proposal_metadata": {
            item.key: item.value for item in proposal.proposal_metadata
        },
    }
    if proposal.scenario_id is not None:
        result["scenario_id"] = proposal.scenario_id
    if proposal.description is not None and not semantic:
        result["description"] = proposal.description
    return result


def proposal_metadata(proposal: RepairGenerationProposal) -> dict[str, str]:
    return {item.key: item.value for item in proposal.proposal_metadata}


def _repository(value: Any) -> RepairRepositoryIdentity:
    if not isinstance(value, Mapping) or set(value) - _REPOSITORY_KEYS:
        raise RepairProposalError("repository_identity has an invalid shape.")
    if "repository_name" not in value:
        raise RepairProposalError("repository_identity requires repository_name.")
    fingerprint = value.get("repository_fingerprint")
    if fingerprint is not None:
        fingerprint = _fingerprint(fingerprint)
    return RepairRepositoryIdentity(
        repository_name=_text(value["repository_name"], "repository_name"),
        repository_namespace=_optional_text(
            value.get("repository_namespace"), "repository_namespace"
        ),
        repository_fingerprint=fingerprint,
    )


def _metadata(value: Any) -> tuple[ProposalMetadataItem, ...]:
    if not isinstance(value, Mapping):
        raise RepairProposalError("proposal_metadata must be an object of string values.")
    if len(value) > 32:
        raise RepairProposalError("proposal_metadata exceeds the 32-item limit.")
    items = []
    for key, item in sorted(value.items()):
        items.append(
            ProposalMetadataItem(
                _text(key, "proposal_metadata key", maximum=100),
                _text(item, f"proposal_metadata.{key}", maximum=1000),
            )
        )
    return tuple(items)


def _identifier_list(value: Any, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) > 500:
        raise RepairProposalError(f"{label} must be an array of at most 500 IDs.")
    result = tuple(_text(item, label, maximum=200) for item in value)
    if len(result) != len(set(result)):
        raise RepairProposalError(f"{label} contains duplicate IDs.")
    return tuple(sorted(result))


def _enum(enum_type, value: Any, label: str):
    try:
        return enum_type(value)
    except (TypeError, ValueError) as exc:
        raise RepairProposalError(f"Unsupported {label}.") from exc


def _fingerprint(value: Any) -> str:
    text = _text(value, "fingerprint", maximum=100)
    if not text.startswith("sha256:") or len(text) != 71:
        raise RepairProposalError("Fingerprint must be a sha256 value.")
    try:
        int(text[7:], 16)
    except ValueError as exc:
        raise RepairProposalError("Fingerprint must contain hexadecimal sha256 bytes.") from exc
    return text


def _text(value: Any, label: str, *, maximum: int = 300) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise RepairProposalError(f"{label} must be a non-empty bounded string.")
    if "\x00" in value:
        raise RepairProposalError(f"{label} contains a forbidden null byte.")
    return value


def _optional_text(value: Any, label: str, *, maximum: int = 300) -> str | None:
    return None if value is None else _text(value, label, maximum=maximum)
