"""Deterministic read-only schema retrieval and structural validation."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Callable

from chronos.datahub._transport import (
    ReadOnlyTransport,
    SchemaFieldMetadataObservation,
    SchemaMetadataObservation,
)
from chronos.datahub.errors import (
    DataHubAccessError,
    DuplicateFieldPath,
    SchemaEmpty,
    SchemaMalformed,
    SchemaNotFound,
    SchemaRetrievalUnavailable,
    UnsupportedFieldMetadata,
    redact_secrets,
)
from chronos.datahub.logging_utils import log_event
from chronos.datahub.schema_types import normalize_datahub_type
from chronos.resolution.models import (
    CanonicalDatasetIdentity,
    ResolvedDatasetIdentity,
)

from .models import (
    DatasetSchemaSnapshot,
    SchemaEvidence,
    SchemaFailure,
    SchemaFieldRecord,
    SchemaRetrievalResult,
    SchemaRetrievalState,
    SchemaValidationFinding,
    SchemaValidationState,
)


Clock = Callable[[], datetime]


class DatasetSchemaRetriever:
    """Retrieve one complete schema for an already-resolved dataset."""

    def __init__(
        self,
        transport: ReadOnlyTransport,
        *,
        logger: logging.Logger | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._transport = transport
        self._logger = logger or logging.getLogger("chronos.schema")
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def retrieve(
        self,
        requested: CanonicalDatasetIdentity,
        dataset: ResolvedDatasetIdentity,
    ) -> SchemaRetrievalResult:
        log_event(
            self._logger,
            logging.INFO,
            "schema_retrieval_started",
            dataset_urn=dataset.urn,
        )
        try:
            identity_error = _validate_identity_binding(requested, dataset)
            if identity_error is not None:
                return _invalid_result(
                    requested,
                    dataset,
                    SchemaMalformed(identity_error),
                )

            observation = self._transport.schema_metadata(dataset.urn)
            if observation is None:
                return _not_found_result(
                    requested,
                    dataset,
                    SchemaNotFound(
                        "SchemaMetadata is absent for the resolved dataset.",
                    ),
                )

            structural_error = _validate_schema(observation, dataset)
            if structural_error is not None:
                return _invalid_result(
                    requested,
                    dataset,
                    structural_error,
                )

            observed_at = _timestamp(self._clock)
            fields = tuple(
                _field_record(position, field)
                for position, field in enumerate(observation.fields)
            )
            evidence = SchemaEvidence(
                dataset_urn=dataset.urn,
                aspect="SchemaMetadata",
                interface="DataHubGraph.get_aspect(SchemaMetadataClass)",
                observed_at=observed_at,
                schema_name=observation.schema_name,
                schema_version=observation.version,
                schema_hash=observation.schema_hash,
                field_count=len(fields),
                validation_state=SchemaValidationState.VALID,
            )
            snapshot = DatasetSchemaSnapshot(
                dataset=dataset,
                canonical_identity=requested,
                schema_name=observation.schema_name,
                platform=dataset.platform,
                source_platform=observation.platform,
                environment=dataset.environment,
                schema_version=observation.version,
                schema_hash=observation.schema_hash,
                fields=fields,
                observed_at=observed_at,
                evidence=evidence,
                created_time=observation.created_time,
                last_modified_time=observation.last_modified_time,
                dataset_reference=observation.dataset_reference,
                cluster=observation.cluster,
                primary_keys=observation.primary_keys,
            )
        except DataHubAccessError as exc:
            return _unavailable_result(requested, dataset, exc)
        except Exception as exc:
            return _unavailable_result(
                requested,
                dataset,
                SchemaRetrievalUnavailable(
                    "Schema retrieval failed unexpectedly.",
                    diagnostic=redact_secrets(exc),
                ),
            )

        log_event(
            self._logger,
            logging.INFO,
            "schema_retrieval_finished",
            dataset_urn=dataset.urn,
            field_count=snapshot.field_count,
            state=SchemaRetrievalState.RETRIEVED.value,
        )
        return SchemaRetrievalResult(
            state=SchemaRetrievalState.RETRIEVED,
            requested=requested,
            dataset=dataset,
            snapshot=snapshot,
            findings=(),
            failure=None,
        )


def _validate_identity_binding(
    requested: CanonicalDatasetIdentity,
    dataset: ResolvedDatasetIdentity,
) -> str | None:
    expected_platform = _platform_name(requested.platform)
    if (
        expected_platform.casefold() != dataset.platform.casefold()
        or requested.environment.casefold() != dataset.environment.casefold()
        or requested.qualified_name.casefold()
        != dataset.qualified_name.casefold()
        or requested.logical_name.casefold() != dataset.logical_name.casefold()
    ):
        return (
            "Resolved dataset identity does not match the supplied canonical "
            "dataset identity."
        )
    return None


def _validate_schema(
    observation: SchemaMetadataObservation,
    dataset: ResolvedDatasetIdentity,
) -> DataHubAccessError | None:
    if observation.dataset_urn != dataset.urn:
        return SchemaMalformed(
            "SchemaMetadata was returned for a different dataset URN.",
        )
    if (
        not isinstance(observation.schema_name, str)
        or not observation.schema_name
        or observation.schema_name != observation.schema_name.strip()
    ):
        return SchemaMalformed(
            "SchemaMetadata schema name is missing or malformed.",
        )
    if observation.schema_name.casefold() != dataset.qualified_name.casefold():
        return SchemaMalformed(
            "SchemaMetadata schema name conflicts with the resolved dataset.",
        )
    if (
        not isinstance(observation.platform, str)
        or not observation.platform
        or _platform_name(observation.platform).casefold()
        != dataset.platform.casefold()
    ):
        return SchemaMalformed(
            "SchemaMetadata platform is missing or conflicts with the dataset.",
        )
    if not observation.fields:
        return SchemaEmpty(
            "SchemaMetadata contains zero fields.",
        )
    if observation.version is not None and not isinstance(
        observation.version,
        int,
    ):
        return SchemaMalformed(
            "SchemaMetadata version is not an integer.",
        )
    if observation.schema_hash is not None and not isinstance(
        observation.schema_hash,
        str,
    ):
        return SchemaMalformed(
            "SchemaMetadata hash is not text.",
        )

    seen: set[str] = set()
    for field in observation.fields:
        field_error = _validate_field(field)
        if field_error is not None:
            return field_error
        assert isinstance(field.field_path, str)
        if field.field_path in seen:
            return DuplicateFieldPath(
                "SchemaMetadata contains a duplicate field path.",
                diagnostic=f"Duplicate exact field path: {field.field_path}.",
            )
        seen.add(field.field_path)
    return None


def _validate_field(
    field: SchemaFieldMetadataObservation,
) -> DataHubAccessError | None:
    if (
        not isinstance(field.field_path, str)
        or not field.field_path
        or field.field_path != field.field_path.strip()
    ):
        return SchemaMalformed(
            "SchemaMetadata contains an empty or malformed field path.",
        )
    text_values = {
        "datahub type": field.datahub_type,
        "native type": field.native_type,
        "description": field.description,
        "JSON path": field.json_path,
        "label": field.label,
        "schema-field URN": field.schema_field_urn,
    }
    for name, value in text_values.items():
        if value is not None and not isinstance(value, str):
            return UnsupportedFieldMetadata(
                f"Schema field {name} has an unsupported representation.",
                diagnostic=f"Field path: {field.field_path}.",
            )
    boolean_values = {
        "nullable": field.nullable,
        "key indicator": field.is_part_of_key,
        "partitioning-key indicator": field.is_partitioning_key,
        "recursive indicator": field.recursive,
    }
    for name, value in boolean_values.items():
        if value is not None and not isinstance(value, bool):
            return UnsupportedFieldMetadata(
                f"Schema field {name} has an unsupported representation.",
                diagnostic=f"Field path: {field.field_path}.",
            )
    return None


def _field_record(
    position: int,
    field: SchemaFieldMetadataObservation,
) -> SchemaFieldRecord:
    assert isinstance(field.field_path, str)
    return SchemaFieldRecord(
        position=position,
        field_path=field.field_path,
        field_name=_field_leaf_name(field.field_path),
        native_type=field.native_type,
        normalized_type=normalize_datahub_type(field.datahub_type),
        datahub_type=field.datahub_type,
        description=field.description,
        nullable=field.nullable,
        is_part_of_key=field.is_part_of_key,
        is_partitioning_key=field.is_partitioning_key,
        json_path=field.json_path,
        label=field.label,
        recursive=field.recursive,
        schema_field_urn=field.schema_field_urn,
    )


def _field_leaf_name(field_path: str) -> str:
    return field_path.rsplit(".", 1)[-1]


def _platform_name(value: str) -> str:
    name = value.rsplit(":", 1)[-1]
    aliases = {
        "postgresql": "postgres",
        "postgres": "postgres",
        "snowflake": "snowflake",
    }
    return aliases.get(name.casefold(), name)


def _not_found_result(
    requested: CanonicalDatasetIdentity,
    dataset: ResolvedDatasetIdentity,
    error: DataHubAccessError,
) -> SchemaRetrievalResult:
    return SchemaRetrievalResult(
        state=SchemaRetrievalState.NOT_FOUND,
        requested=requested,
        dataset=dataset,
        snapshot=None,
        findings=(
            SchemaValidationFinding(
                code=error.code,
                message=error.safe_message,
            ),
        ),
        failure=_failure(error),
    )


def _invalid_result(
    requested: CanonicalDatasetIdentity,
    dataset: ResolvedDatasetIdentity,
    error: DataHubAccessError,
) -> SchemaRetrievalResult:
    return SchemaRetrievalResult(
        state=SchemaRetrievalState.INVALID_SCHEMA,
        requested=requested,
        dataset=dataset,
        snapshot=None,
        findings=(
            SchemaValidationFinding(
                code=error.code,
                message=error.safe_message,
                field_path=_diagnostic_field_path(error.diagnostic),
            ),
        ),
        failure=_failure(error),
    )


def _unavailable_result(
    requested: CanonicalDatasetIdentity,
    dataset: ResolvedDatasetIdentity,
    error: DataHubAccessError,
) -> SchemaRetrievalResult:
    return SchemaRetrievalResult(
        state=SchemaRetrievalState.UNAVAILABLE,
        requested=requested,
        dataset=dataset,
        snapshot=None,
        findings=(),
        failure=_failure(error),
    )


def _failure(error: DataHubAccessError) -> SchemaFailure:
    return SchemaFailure(
        code=error.code,
        message=redact_secrets(error.safe_message),
        diagnostic=(
            redact_secrets(error.diagnostic)
            if error.diagnostic is not None
            else None
        ),
    )


def _diagnostic_field_path(diagnostic: str | None) -> str | None:
    if not diagnostic or not diagnostic.startswith("Field path: "):
        return None
    return diagnostic.removeprefix("Field path: ").removesuffix(".")


def _timestamp(clock: Clock) -> str:
    value = clock()
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()
