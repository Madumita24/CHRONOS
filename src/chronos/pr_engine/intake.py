"""Safe local-Git and portable-bundle intake without repository execution."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from dataclasses import replace
from pathlib import Path, PurePosixPath
from typing import Any

from chronos.snapshot import contains_secret
from chronos.structural_engine.serialization import semantic_fingerprint, stable_id

from .errors import FileSafetyError, RepositoryIntakeError
from .models import (
    MAX_CHANGED_FILES,
    MAX_FILE_BYTES,
    ChangedFile,
    FileCategory,
    FilePayload,
    FileStatus,
    PullRequestAnalysisProposal,
    PullRequestInput,
)


_REVISION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,127}$")
_GENERATED = {
    ".git", ".hg", ".svn", "node_modules", "vendor", "dist", "build",
    "target", "__pycache__", ".pytest_cache", ".mypy_cache", ".next",
}
_CREDENTIAL_NAMES = {
    ".env", ".env.local", ".npmrc", ".pypirc", "credentials", "credentials.json",
    "id_rsa", "id_ed25519", "secrets.yml", "secrets.yaml", "secrets.json",
}
_PRIVATE_KEY = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")
_TOKEN_VALUE = re.compile(
    r"(?im)^\s*(?:token|password|secret|authorization|api[_-]?key)\s*[:=]\s*\S+"
)
_BUNDLE_KEYS = {
    "schema_version", "repository_identity", "base_revision", "head_revision", "files",
    "pull_request_metadata",
}
_BUNDLE_FILE_KEYS = {
    "status", "base_path", "head_path", "base_fingerprint", "head_fingerprint",
}


def load_git_range(
    repository: str | Path,
    proposal: PullRequestAnalysisProposal,
) -> PullRequestInput:
    root = Path(repository).resolve()
    if not root.is_dir() or not (root / ".git").exists():
        raise RepositoryIntakeError("Local intake requires an existing Git repository root.")
    observed_root = Path(_git_text(root, "rev-parse", "--show-toplevel").strip()).resolve()
    if observed_root != root:
        raise RepositoryIntakeError("Repository path must be the exact Git root.")
    base = _resolve_revision(root, proposal.base_revision)
    head = _resolve_revision(root, proposal.head_revision)
    if base == head:
        raise RepositoryIntakeError("Resolved base and head commits must differ.")
    raw = _git_bytes(root, "diff", "--name-status", "-z", "-M", "-C", base, head)
    changes = _parse_git_name_status(raw)
    if len(changes) > MAX_CHANGED_FILES:
        raise RepositoryIntakeError("Changed-file count exceeds the certified limit.")
    payloads = []
    seen = set()
    for status, base_path, head_path in changes:
        identity = (base_path, head_path, status.value)
        if identity in seen:
            raise RepositoryIntakeError("Duplicate changed-file identity from Git.")
        seen.add(identity)
        base_bytes = _git_blob(root, base, base_path) if base_path else None
        head_bytes = _git_blob(root, head, head_path) if head_path else None
        payloads.append(_payload(status, base_path, head_path, base_bytes, head_bytes))
    return PullRequestInput(
        repository_identity=_repository_identity(proposal, base, head),
        base_commit=base,
        head_commit=head,
        files=tuple(sorted(payloads, key=lambda item: item.record.file_change_id)),
        intake_warnings=(),
    )


def load_exported_bundle(
    bundle: str | Path,
    proposal: PullRequestAnalysisProposal,
) -> PullRequestInput:
    root = Path(bundle).resolve()
    manifest_path = root / "bundle.json"
    if not root.is_dir() or not manifest_path.is_file() or manifest_path.is_symlink():
        raise RepositoryIntakeError("Bundle requires a regular bundle.json file.")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RepositoryIntakeError("Bundle manifest is not valid UTF-8 JSON.") from exc
    _validate_bundle_manifest(manifest, proposal)
    files = manifest["files"]
    if len(files) > MAX_CHANGED_FILES:
        raise RepositoryIntakeError("Changed-file count exceeds the certified limit.")
    payloads = []
    seen = set()
    for raw in files:
        status = _bundle_status(raw)
        base_path = raw.get("base_path")
        head_path = raw.get("head_path")
        identity = (base_path, head_path, status.value)
        if identity in seen:
            raise RepositoryIntakeError("Duplicate changed-file identity in bundle.")
        seen.add(identity)
        base_bytes = _bundle_file(root, "base", base_path) if base_path else None
        head_bytes = _bundle_file(root, "head", head_path) if head_path else None
        _check_manifest_fingerprint(raw.get("base_fingerprint"), base_bytes, "base")
        _check_manifest_fingerprint(raw.get("head_fingerprint"), head_bytes, "head")
        payloads.append(_payload(status, base_path, head_path, base_bytes, head_bytes))
    base = manifest["base_revision"]
    head = manifest["head_revision"]
    return PullRequestInput(
        repository_identity=_repository_identity(proposal, base, head),
        base_commit=base,
        head_commit=head,
        files=tuple(sorted(payloads, key=lambda item: item.record.file_change_id)),
        intake_warnings=(),
    )


def with_classification(
    value: PullRequestInput,
    classifications: dict[str, tuple[FileCategory, str, tuple[str, ...]]],
) -> PullRequestInput:
    files = []
    for payload in value.files:
        category, parser, warnings = classifications[payload.record.file_change_id]
        files.append(
            replace(
                payload,
                record=replace(
                    payload.record,
                    category=category,
                    parser_assignment=parser,
                    warnings=tuple(sorted(set(payload.record.warnings + warnings))),
                ),
            )
        )
    return replace(value, files=tuple(files))


def _git_bytes(root: Path, *args: str) -> bytes:
    command = ["git", "--no-pager", *args]
    environment = dict(os.environ)
    environment.update({"GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0"})
    try:
        completed = subprocess.run(
            command,
            cwd=root,
            env=environment,
            shell=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RepositoryIntakeError("Bounded Git command failed to run.") from exc
    if completed.returncode != 0:
        diagnostic = completed.stderr.decode("utf-8", errors="replace").strip()[:240]
        raise RepositoryIntakeError(f"Bounded Git command failed: {diagnostic}")
    return completed.stdout


def _git_text(root: Path, *args: str) -> str:
    try:
        return _git_bytes(root, *args).decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise RepositoryIntakeError("Git metadata is not valid UTF-8.") from exc


def _resolve_revision(root: Path, revision: str) -> str:
    if not _REVISION.fullmatch(revision) or revision.startswith("-") or ".." in revision:
        raise RepositoryIntakeError("Git revision is outside the bounded syntax.")
    value = _git_text(root, "rev-parse", "--verify", f"{revision}^{{commit}}").strip()
    if not re.fullmatch(r"[0-9a-fA-F]{40,64}", value):
        raise RepositoryIntakeError("Git revision did not resolve to one commit.")
    return value.lower()


def _parse_git_name_status(raw: bytes):
    try:
        tokens = raw.decode("utf-8", errors="strict").split("\0")
    except UnicodeDecodeError as exc:
        raise RepositoryIntakeError("Git changed paths are not valid UTF-8.") from exc
    tokens = [item for item in tokens if item]
    result = []
    index = 0
    while index < len(tokens):
        code = tokens[index]
        index += 1
        letter = code[0]
        if letter in {"R", "C"}:
            if index + 1 >= len(tokens):
                raise RepositoryIntakeError("Git rename/copy record is incomplete.")
            old, new = tokens[index], tokens[index + 1]
            index += 2
            status = FileStatus.RENAMED if letter == "R" else FileStatus.COPIED
            _safe_repo_path(old)
            _safe_repo_path(new)
            result.append((status, old, new))
        elif letter in {"A", "M", "D"}:
            if index >= len(tokens):
                raise RepositoryIntakeError("Git file record is incomplete.")
            path = tokens[index]
            index += 1
            _safe_repo_path(path)
            status = {"A": FileStatus.ADDED, "M": FileStatus.MODIFIED, "D": FileStatus.DELETED}[letter]
            result.append((status, None if letter == "A" else path, None if letter == "D" else path))
        else:
            raise RepositoryIntakeError(f"Unsupported Git change status {code!r}.")
    return result


def _git_blob(root: Path, commit: str, path: str) -> bytes:
    _safe_repo_path(path)
    tree = _git_bytes(root, "ls-tree", "-z", commit, "--", path)
    if not tree:
        raise RepositoryIntakeError("Git object path is missing from the declared commit.")
    mode = tree.split(b" ", 1)[0]
    if mode not in {b"100644", b"100755"}:
        raise FileSafetyError("Symlinks and non-regular Git objects are not analyzable.")
    size_text = _git_text(root, "cat-file", "-s", f"{commit}:{path}").strip()
    if not size_text.isdigit() or int(size_text) > MAX_FILE_BYTES:
        raise FileSafetyError("Changed file exceeds the certified byte limit.")
    return _git_bytes(root, "show", f"{commit}:{path}")


def _bundle_file(root: Path, side: str, path: str) -> bytes:
    _safe_repo_path(path)
    target = (root / side / Path(*PurePosixPath(path).parts)).resolve()
    expected_root = (root / side).resolve()
    try:
        target.relative_to(expected_root)
    except ValueError as exc:
        raise FileSafetyError("Bundle file escapes its side directory.") from exc
    if target.is_symlink() or not target.is_file():
        raise FileSafetyError("Bundle evidence must be a regular non-symlink file.")
    if target.stat().st_size > MAX_FILE_BYTES:
        raise FileSafetyError("Changed file exceeds the certified byte limit.")
    return target.read_bytes()


def _payload(status, base_path, head_path, base_bytes, head_bytes) -> FilePayload:
    for path in (base_path, head_path):
        if path:
            _safe_repo_path(path)
            _reject_credential_path(path)
    binary = any(content is not None and b"\0" in content for content in (base_bytes, head_bytes))
    base_text = _decode_content(base_bytes) if base_bytes is not None and not binary else None
    head_text = _decode_content(head_bytes) if head_bytes is not None and not binary else None
    for content in (base_text, head_text):
        if content is not None:
            _reject_credentials(content)
    identity_path = head_path or base_path or "unknown"
    record = ChangedFile(
        file_change_id=stable_id("pr-file", status.value, base_path or "", head_path or ""),
        base_path=base_path,
        head_path=head_path,
        status=status,
        category=FileCategory.UNSUPPORTED,
        base_content_fingerprint=_content_fingerprint(base_bytes),
        head_content_fingerprint=_content_fingerprint(head_bytes),
        base_size=len(base_bytes or b""),
        head_size=len(head_bytes or b""),
        binary=binary,
        parser_assignment="unassigned",
        warnings=("binary_file_not_semantically_parsed",) if binary else (),
    )
    if not identity_path:
        raise RepositoryIntakeError("Changed file has no identity path.")
    return FilePayload(record, base_text, head_text)


def _decode_content(value: bytes) -> str:
    try:
        return value.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise FileSafetyError("Supported text evidence must use UTF-8.") from exc


def _content_fingerprint(value: bytes | None) -> str | None:
    if value is None:
        return None
    normalized = value.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return "sha256:" + hashlib.sha256(normalized).hexdigest()


def _validate_bundle_manifest(manifest: Any, proposal: PullRequestAnalysisProposal) -> None:
    if not isinstance(manifest, dict) or set(manifest) - _BUNDLE_KEYS:
        raise RepositoryIntakeError("Bundle manifest has an invalid root shape.")
    required = _BUNDLE_KEYS - {"pull_request_metadata"}
    if required - set(manifest) or manifest.get("schema_version") != "1.0":
        raise RepositoryIntakeError("Bundle manifest is incomplete or has an unsupported version.")
    if manifest["base_revision"] != proposal.base_revision or manifest["head_revision"] != proposal.head_revision:
        raise RepositoryIntakeError("Bundle base/head identity does not match the proposal.")
    expected_repo = {
        "repository_name": proposal.repository_identity.repository_name,
        **(
            {"repository_namespace": proposal.repository_identity.repository_namespace}
            if proposal.repository_identity.repository_namespace else {}
        ),
    }
    if manifest["repository_identity"] != expected_repo:
        raise RepositoryIntakeError("Bundle repository identity does not match the proposal.")
    if not isinstance(manifest["files"], list):
        raise RepositoryIntakeError("Bundle files must be an array.")
    if contains_secret(manifest) or _PRIVATE_KEY.search(json.dumps(manifest)):
        raise RepositoryIntakeError("Credential-shaped data is forbidden in bundle metadata.")
    for raw in manifest["files"]:
        if not isinstance(raw, dict) or set(raw) != _BUNDLE_FILE_KEYS:
            raise RepositoryIntakeError("Bundle changed-file record has an invalid shape.")


def _bundle_status(raw: dict[str, Any]) -> FileStatus:
    try:
        status = FileStatus(raw["status"])
    except (ValueError, TypeError) as exc:
        raise RepositoryIntakeError("Bundle file status is unsupported.") from exc
    base_path, head_path = raw.get("base_path"), raw.get("head_path")
    expected = {
        FileStatus.ADDED: (False, True), FileStatus.DELETED: (True, False),
        FileStatus.MODIFIED: (True, True), FileStatus.RENAMED: (True, True),
        FileStatus.COPIED: (True, True),
    }
    if status not in expected or (bool(base_path), bool(head_path)) != expected[status]:
        raise RepositoryIntakeError("Bundle file paths do not match the declared status.")
    return status


def _check_manifest_fingerprint(expected: str | None, content: bytes | None, side: str) -> None:
    observed = _content_fingerprint(content)
    if expected != observed:
        raise RepositoryIntakeError(f"Bundle {side} content fingerprint mismatch.")


def _safe_repo_path(value: str) -> None:
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        raise FileSafetyError("Repository paths must be non-empty portable POSIX paths.")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise FileSafetyError("Repository path traversal is forbidden.")
    if any(part.lower() in _GENERATED for part in path.parts):
        raise FileSafetyError("Generated, dependency, VCS, and vendor paths are isolated.")


def _reject_credential_path(value: str) -> None:
    name = PurePosixPath(value).name.lower()
    if name in _CREDENTIAL_NAMES or name.endswith((".pem", ".key", ".p12", ".pfx")):
        raise FileSafetyError("Hidden credential and private-key files are forbidden.")


def _reject_credentials(value: str) -> None:
    if _PRIVATE_KEY.search(value) or _TOKEN_VALUE.search(value):
        raise FileSafetyError("Credential-shaped file content is forbidden.")


def _repository_identity(proposal, base, head):
    public = {
        "repository_name": proposal.repository_identity.repository_name,
        **(
            {"repository_namespace": proposal.repository_identity.repository_namespace}
            if proposal.repository_identity.repository_namespace else {}
        ),
        "analysis_root": ".",
        "base_commit": base,
        "head_commit": head,
    }
    return {
        **public,
        "repository_fingerprint": semantic_fingerprint(public),
    }
