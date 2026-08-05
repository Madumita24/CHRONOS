"""Repository-contained SQL and bounded raw-dbt intake."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import UnsafeCodeInputError, UnsupportedDbtError
from .serialization import semantic_fingerprint


_JINJA_BLOCK = re.compile(r"\{%|\{#")
_JINJA_EXPRESSION = re.compile(r"\{\{(.*?)\}\}", re.DOTALL)
_REF = re.compile(r"^\s*ref\(\s*['\"]([^'\"]+)['\"]\s*\)\s*$")
_SOURCE = re.compile(
    r"^\s*source\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)\s*$"
)


@dataclass(frozen=True)
class CodeInput:
    reference: str
    raw_content: str
    compiled_content: str
    content_fingerprint: str
    compiled_fingerprint: str
    input_kind: str
    dbt_references: tuple[str, ...]


def load_code_input(
    reference: str,
    *,
    repository_root: Path,
    manifest_reference: str | None = None,
) -> CodeInput:
    path = safe_repository_path(reference, repository_root=repository_root)
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise UnsafeCodeInputError(f"Unable to read SQL input {reference!r}.") from exc
    manifest = None
    if manifest_reference is not None:
        manifest_path = safe_repository_path(
            manifest_reference, repository_root=repository_root
        )
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise UnsupportedDbtError("Unable to load supplied dbt manifest JSON.") from exc
    compiled, refs, kind = _compile_bounded_dbt(raw, manifest)
    return CodeInput(
        reference=Path(reference).as_posix(),
        raw_content=raw,
        compiled_content=compiled,
        content_fingerprint=semantic_fingerprint({"content": _line_endings(raw)}),
        compiled_fingerprint=semantic_fingerprint({"content": _line_endings(compiled)}),
        input_kind=kind,
        dbt_references=refs,
    )


def safe_repository_path(reference: str, *, repository_root: Path) -> Path:
    if not isinstance(reference, str) or not reference.strip():
        raise UnsafeCodeInputError("Code reference must be a non-empty relative path.")
    lowered = reference.lower()
    if (
        "://" in lowered
        or "$(" in reference
        or "`" in reference
        or Path(reference).is_absolute()
    ):
        raise UnsafeCodeInputError("Code references must be repository-contained files.")
    root = repository_root.resolve()
    path = (root / reference).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise UnsafeCodeInputError("Code reference escapes the repository.") from exc
    if not path.is_file():
        raise UnsafeCodeInputError(f"Code reference does not exist: {reference!r}.")
    return path


def _compile_bounded_dbt(
    raw: str,
    manifest: dict[str, Any] | None,
) -> tuple[str, tuple[str, ...], str]:
    if not ("{{" in raw or "{%" in raw or "{#" in raw):
        return raw, (), "plain_or_compiled_sql"
    if _JINJA_BLOCK.search(raw):
        raise UnsupportedDbtError(
            "Jinja statements, comments, and macros are unsupported; provide compiled SQL."
        )
    if manifest is None:
        raise UnsupportedDbtError(
            "Raw dbt ref/source input requires a supplied manifest; Jinja is never executed."
        )
    references: list[str] = []

    def replace(match: re.Match[str]) -> str:
        body = match.group(1)
        ref = _REF.fullmatch(body)
        if ref:
            name = ref.group(1)
            references.append(f"ref:{name}")
            return _manifest_ref(manifest, name)
        source = _SOURCE.fullmatch(body)
        if source:
            source_name, table_name = source.groups()
            references.append(f"source:{source_name}.{table_name}")
            return _manifest_source(manifest, source_name, table_name)
        raise UnsupportedDbtError(
            "Only static dbt ref() and source() expressions are supported."
        )

    compiled = _JINJA_EXPRESSION.sub(replace, raw)
    if "{{" in compiled or "}}" in compiled:
        raise UnsupportedDbtError("Unresolved Jinja remains after bounded dbt resolution.")
    return compiled, tuple(sorted(references)), "raw_dbt_resolved_from_manifest"


def _manifest_ref(manifest: dict[str, Any], name: str) -> str:
    matches = [
        node
        for node in manifest.get("nodes", {}).values()
        if node.get("resource_type") == "model"
        and name in {node.get("name"), node.get("alias")}
    ]
    return _one_relation(matches, f"dbt ref({name!r})")


def _manifest_source(
    manifest: dict[str, Any], source_name: str, table_name: str
) -> str:
    matches = [
        source
        for source in manifest.get("sources", {}).values()
        if source.get("source_name") == source_name
        and table_name in {source.get("name"), source.get("identifier")}
    ]
    return _one_relation(matches, f"dbt source({source_name!r}, {table_name!r})")


def _one_relation(matches: list[dict[str, Any]], label: str) -> str:
    if len(matches) != 1:
        raise UnsupportedDbtError(f"{label} must resolve exactly once in the manifest.")
    node = matches[0]
    relation = node.get("relation_name")
    if not relation:
        parts = [node.get("database"), node.get("schema"), node.get("alias") or node.get("identifier") or node.get("name")]
        if not all(isinstance(part, str) and part for part in parts):
            raise UnsupportedDbtError(f"{label} has no static compiled relation identity.")
        relation = ".".join(parts)
    if not isinstance(relation, str) or any(token in relation for token in ("{{", "}}", ";")):
        raise UnsupportedDbtError(f"{label} relation identity is unsafe.")
    return relation


def _line_endings(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n")
