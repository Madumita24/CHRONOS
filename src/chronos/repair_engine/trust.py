"""Fail-closed trust gate for certified Phase 6.3 predecessor packages."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from chronos.pr_engine.analysis import _file_record
from chronos.pr_engine.certification import (
    PRE_CERTIFICATION_ARTIFACTS,
    certify_pr_artifacts,
    validate_completed_package,
)
from chronos.pr_engine.engine import PR_ARTIFACT_FILENAMES
from chronos.pr_engine.intake import load_exported_bundle, with_classification
from chronos.pr_engine.models import PullRequestAnalysisIdentity
from chronos.pr_engine.proposals import parse_pr_proposal
from chronos.pr_engine.registry import ParserRegistry
from chronos.snapshot import CurrentMetadataSnapshot, contains_secret
from chronos.structural_engine.serialization import canonicalize, semantic_fingerprint

from .errors import PredecessorTrustError
from .models import MAX_PREDECESSOR_ARTIFACT_BYTES, RepairGenerationProposal


_ABSOLUTE_WINDOWS = re.compile(r"[A-Za-z]:[\\/]")


@dataclass(frozen=True)
class TrustedPredecessor:
    root: Path
    artifacts: dict[str, dict[str, Any]]
    manifest: dict[str, Any]
    manifest_fingerprint: str
    proposal: Any
    identity: PullRequestAnalysisIdentity
    pr_input: Any
    bundle_root: Path
    file_results: tuple[dict[str, Any], ...]
    trust_checks: tuple[dict[str, str], ...]


def load_trusted_predecessor(
    analysis_dir: str | Path,
    repository_bundle: str | Path,
    repair_proposal: RepairGenerationProposal,
    snapshot: CurrentMetadataSnapshot,
) -> TrustedPredecessor:
    repository_root = Path(__file__).resolve().parents[3]
    root_input = Path(analysis_dir)
    if root_input.is_symlink():
        raise PredecessorTrustError("Predecessor package root cannot be a symlink.")
    root = root_input.resolve()
    _contained(root, repository_root, "Predecessor package")
    if not root.is_dir():
        raise PredecessorTrustError("Predecessor package directory is missing.")
    expected = set(PR_ARTIFACT_FILENAMES)
    observed = {item.name for item in root.iterdir()}
    if observed != expected:
        raise PredecessorTrustError("Predecessor package does not match the 26-artifact contract.")
    artifacts: dict[str, dict[str, Any]] = {}
    for name in PR_ARTIFACT_FILENAMES:
        path = root / name
        if path.is_symlink() or not path.is_file():
            raise PredecessorTrustError("Predecessor artifacts must be regular non-symlink files.")
        if path.stat().st_size > MAX_PREDECESSOR_ARTIFACT_BYTES:
            raise PredecessorTrustError("Predecessor artifact exceeds the repair trust limit.")
        artifacts[name] = _strict_json(path)
    if contains_secret(artifacts) or _ABSOLUTE_WINDOWS.search(json.dumps(artifacts)):
        raise PredecessorTrustError("Predecessor package contains secret-shaped or absolute-path data.")

    manifest = artifacts["manifest.json"]
    manifest_fingerprint = semantic_fingerprint(manifest)
    _require(
        manifest_fingerprint == repair_proposal.predecessor_manifest_fingerprint,
        "Predecessor manifest fingerprint does not match the repair proposal.",
    )
    _require(
        manifest.get("analysis_id") == repair_proposal.predecessor_analysis_id,
        "Predecessor analysis identity does not match the repair proposal.",
    )
    _require(
        manifest.get("certification_status") == "certified",
        "Predecessor manifest is not certified.",
    )
    _require(
        manifest.get("artifact_names") == list(PR_ARTIFACT_FILENAMES),
        "Predecessor manifest artifact list is invalid.",
    )

    predecessor_proposal_artifact = artifacts["pr_analysis_proposal.json"]
    predecessor_proposal = parse_pr_proposal(predecessor_proposal_artifact.get("proposal"))
    identity = PullRequestAnalysisIdentity(
        analysis_id=predecessor_proposal.analysis_id,
        proposal_id=predecessor_proposal.proposal_id,
        operation=predecessor_proposal.operation,
        intake_mode=predecessor_proposal.intake_mode,
        repository_fingerprint=manifest.get("repository_identity", {}).get(
            "repository_fingerprint", ""
        ),
        base_commit=manifest.get("base_commit", ""),
        head_commit=manifest.get("head_commit", ""),
        source_snapshot_id=predecessor_proposal_artifact.get("source_snapshot_id", ""),
        source_snapshot_fingerprint=manifest.get("source_snapshot_fingerprint", ""),
        proposal_fingerprint=manifest.get("proposal_fingerprint", ""),
        engine_version=manifest.get("engine_version", ""),
        scenario_id=predecessor_proposal.scenario_id,
        created_at=predecessor_proposal.created_at,
    )
    pre_certification = {
        name: artifacts[name] for name in PRE_CERTIFICATION_ARTIFACTS
    }
    recertification, pre_fingerprints, analysis_fingerprint = certify_pr_artifacts(
        identity, pre_certification
    )
    _require(
        recertification == artifacts["analysis_certification.json"],
        "Predecessor certification cannot be reproduced.",
    )
    all_fingerprints = {
        **pre_fingerprints,
        "analysis_certification.json": semantic_fingerprint(recertification),
    }
    _require(
        all_fingerprints == manifest.get("artifact_fingerprints"),
        "Predecessor artifact fingerprints do not match the manifest.",
    )
    _require(
        analysis_fingerprint == manifest.get("analysis_semantic_fingerprint"),
        "Predecessor analysis fingerprint is inconsistent.",
    )
    validate_completed_package(
        artifacts, manifest, PR_ARTIFACT_FILENAMES, all_fingerprints
    )

    _validate_proposal_identity(repair_proposal, manifest)
    _require(
        identity.source_snapshot_fingerprint == snapshot.semantic_fingerprint
        and identity.source_snapshot_id == snapshot.metadata.snapshot_id,
        "Current frozen snapshot does not match the predecessor snapshot identity.",
    )

    bundle_input = Path(repository_bundle)
    if bundle_input.is_symlink():
        raise PredecessorTrustError("Repository bundle root cannot be a symlink.")
    bundle_root = bundle_input.resolve()
    _contained(bundle_root, repository_root, "Repository bundle")
    try:
        pr_input = load_exported_bundle(bundle_root, predecessor_proposal)
    except Exception as exc:
        raise PredecessorTrustError("Repository bundle failed Phase 6.3 intake validation.") from exc
    _require(
        pr_input.repository_identity == manifest.get("repository_identity"),
        "Repository bundle identity does not match the predecessor.",
    )
    expected_inventory = artifacts["changed_file_inventory.json"]["files"]
    observed_inventory = [_file_record(item.record) for item in pr_input.files]
    # Classification is assigned below; compare immutable intake evidence first.
    for item in observed_inventory:
        item["category"] = "UNSUPPORTED"
        item["parser_assignment"] = "unassigned"
        item["warnings"] = (
            ["binary_file_not_semantically_parsed"] if item["binary"] else []
        )
    expected_intake = []
    for item in expected_inventory:
        value = dict(item)
        value["category"] = "UNSUPPORTED"
        value["parser_assignment"] = "unassigned"
        value["warnings"] = (
            ["binary_file_not_semantically_parsed"] if value["binary"] else []
        )
        expected_intake.append(value)
    _require(
        canonicalize(observed_inventory) == canonicalize(expected_intake),
        "Repository bundle file identity or HEAD content fingerprint mismatch.",
    )

    registry = ParserRegistry()
    classifications = {
        item.record.file_change_id: registry.classify(item) for item in pr_input.files
    }
    pr_input = with_classification(pr_input, classifications)
    observed_classified = [_file_record(item.record) for item in pr_input.files]
    _require(
        canonicalize(observed_classified) == canonicalize(expected_inventory),
        "Repository bundle parser assignment differs from the predecessor.",
    )
    observed_results = tuple(
        registry.analyze(
            item,
            snapshot=snapshot,
            proposal=predecessor_proposal,
            all_payloads=pr_input.files,
        )
        for item in pr_input.files
    )
    _require(
        canonicalize(list(observed_results))
        == canonicalize(artifacts["file_analysis_results.json"]["results"]),
        "Repository bundle parsed evidence differs from the certified predecessor.",
    )
    checks = tuple(
        {"check_id": check_id, "status": "passed"}
        for check_id in (
            "package_contract",
            "manifest_fingerprint",
            "artifact_fingerprints",
            "reproduced_predecessor_certification",
            "analysis_snapshot_repository_base_head_identity",
            "root_group_conflict_and_coherence_integrity",
            "bundle_manifest_and_head_content_fingerprints",
            "parser_assignment_and_parsed_evidence",
            "path_secret_and_output_boundary",
        )
    )
    return TrustedPredecessor(
        root=root,
        artifacts=artifacts,
        manifest=manifest,
        manifest_fingerprint=manifest_fingerprint,
        proposal=predecessor_proposal,
        identity=identity,
        pr_input=pr_input,
        bundle_root=bundle_root,
        file_results=observed_results,
        trust_checks=checks,
    )


def _validate_proposal_identity(proposal, manifest):
    repository = manifest.get("repository_identity", {})
    expected = proposal.repository_identity
    _require(
        repository.get("repository_name") == expected.repository_name,
        "Repair proposal repository name mismatch.",
    )
    _require(
        repository.get("repository_namespace") == expected.repository_namespace,
        "Repair proposal repository namespace mismatch.",
    )
    if expected.repository_fingerprint is not None:
        _require(
            repository.get("repository_fingerprint") == expected.repository_fingerprint,
            "Repair proposal repository fingerprint mismatch.",
        )
    _require(
        manifest.get("base_commit") == proposal.base_revision
        and manifest.get("head_commit") == proposal.head_revision,
        "Repair proposal BASE/HEAD identity mismatch.",
    )


def _strict_json(path: Path) -> dict[str, Any]:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise PredecessorTrustError(
                    f"Duplicate JSON key in predecessor artifact {path.name}."
                )
            result[key] = value
        return result

    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PredecessorTrustError(
            f"Unable to load predecessor artifact {path.name}."
        ) from exc
    if not isinstance(value, dict):
        raise PredecessorTrustError("Predecessor artifacts must contain JSON objects.")
    return value


def _contained(path: Path, root: Path, label: str) -> None:
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise PredecessorTrustError(f"{label} must remain inside the CHRONOS repository.") from exc


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PredecessorTrustError(message)
