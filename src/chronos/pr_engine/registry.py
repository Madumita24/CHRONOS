"""Explicit isolated file-parser registry and deterministic classification."""

from __future__ import annotations

from pathlib import PurePosixPath

from .models import FileCategory
from .parsers import BoundedConfigParser, DbtSchemaParser, PythonDagParser, SqlModelParser
from .parsers.common import delta, file_result
from .parsers.config import safe_document


class ParserRegistry:
    def __init__(self) -> None:
        self.parsers = (
            SqlModelParser(), DbtSchemaParser(), PythonDagParser(), BoundedConfigParser()
        )

    def classify(self, payload):
        record = payload.record
        path = (record.head_path or record.base_path or "").lower()
        name = PurePosixPath(path).name
        if record.binary:
            return FileCategory.UNSUPPORTED, "unsupported", ("binary_file_isolated",)
        if path.endswith(".sql"):
            content = (payload.head_content or payload.base_content or "")
            return (
                FileCategory.DBT_MODEL if "{{" in content else FileCategory.SQL_MODEL,
                SqlModelParser.name,
                (),
            )
        if path.endswith(".py") and any(part in path.split("/") for part in ("dag", "dags", "pipelines")):
            return FileCategory.PIPELINE_DAG, PythonDagParser.name, ()
        if path.endswith((".md", ".rst", ".txt")):
            return FileCategory.DOCUMENTATION_ONLY, BoundedConfigParser.name, ()
        if path.endswith((".yml", ".yaml", ".json")):
            if name in {"schema.yml", "schema.yaml"}:
                return FileCategory.DBT_SCHEMA, DbtSchemaParser.name, ()
            if "contract" in path:
                return FileCategory.SCHEMA_CONTRACT, BoundedConfigParser.name, ()
            if "quality" in path or "check" in name:
                return FileCategory.QUALITY_CONFIG, BoundedConfigParser.name, ()
            if any(part in path.split("/") for part in ("dag", "dags", "pipeline", "pipelines")):
                return FileCategory.PIPELINE_CONFIG, BoundedConfigParser.name, ()
            # Content may establish a bounded adapter only after safe structural parsing.
            try:
                document = safe_document(payload.head_content or payload.base_content, path)
            except Exception:
                return FileCategory.UNSUPPORTED, "unsupported", ("unclassified_invalid_yaml_json",)
            if isinstance(document, dict) and "models" in document:
                return FileCategory.DBT_SCHEMA, DbtSchemaParser.name, ()
            if isinstance(document, dict) and set(document) == {"contract"}:
                return FileCategory.SCHEMA_CONTRACT, BoundedConfigParser.name, ()
            if isinstance(document, dict) and any(key in document for key in ("pipeline", "tasks")):
                return FileCategory.PIPELINE_CONFIG, BoundedConfigParser.name, ()
        return FileCategory.UNSUPPORTED, "unsupported", ("unsupported_file_retained",)

    def analyze(self, payload, **context):
        for parser in self.parsers:
            if payload.record.category in parser.categories:
                return parser.parse(payload, **context)
        return file_result(
            payload, "unsupported", "6.3.0", None, None,
            [delta(
                "UnsupportedFileDelta", "UNSUPPORTED_FILE", payload.record.head_path or payload.record.base_path,
                None, None, scope="FILE", material=False,
                explanation="The changed file is retained in inventory but has no certified parser.",
            )],
            warnings=["unsupported_file_not_interpreted"], status="UNSUPPORTED",
        )
