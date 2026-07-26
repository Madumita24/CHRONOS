"""Deterministic, read-only canonical entity resolution."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Callable

from chronos.datahub._transport import (
    DatasetMetadataObservation,
    ReadOnlyTransport,
    SchemaFieldObservation,
)
from chronos.datahub.errors import (
    DataHubAccessError,
    EntityAmbiguous,
    EntityNotFound,
    FieldNotFound,
    InvalidCanonicalIdentity,
    ResolutionUnavailable,
    UnexpectedResolutionError,
    redact_secrets,
)
from chronos.datahub.logging_utils import log_event

from .models import (
    CanonicalDatasetIdentity,
    CanonicalSchemaFieldIdentity,
    DatasetResolutionResult,
    EvidenceAttribute,
    FieldResolutionResult,
    ResolutionEvidence,
    ResolutionFailure,
    ResolutionState,
    ResolvedDatasetIdentity,
    ResolvedSchemaFieldIdentity,
)


Clock = Callable[[], datetime]

_PLATFORM_ALIASES = {
    "postgres": "postgres",
    "postgresql": "postgres",
    "snowflake": "snowflake",
}


class CanonicalEntityResolver:
    """Phase 1.2 resolver over the existing read-only DataHub transport."""

    def __init__(
        self,
        transport: ReadOnlyTransport,
        *,
        logger: logging.Logger | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._transport = transport
        self._logger = logger or logging.getLogger("chronos.resolution")
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def resolve_dataset(
        self,
        requested: CanonicalDatasetIdentity,
    ) -> DatasetResolutionResult:
        validation_error = _validate_dataset_identity(requested)
        if validation_error is not None:
            return _invalid_dataset_result(requested, validation_error)

        log_event(
            self._logger,
            logging.INFO,
            "dataset_resolution_started",
            platform=requested.platform,
            qualified_name=requested.qualified_name,
            environment=requested.environment,
        )

        try:
            discovered_urns = tuple(
                dict.fromkeys(
                    self._transport.search_dataset_urns(
                        platform=_normalized_platform(requested.platform),
                        environment=requested.environment.upper(),
                        query=requested.logical_name,
                    )
                )
            )
            observations = tuple(
                self._transport.dataset_metadata(urn)
                for urn in discovered_urns
            )
        except DataHubAccessError as exc:
            return _unavailable_dataset_result(requested, exc)
        except Exception as exc:
            return _unexpected_dataset_result(requested, exc)

        verified = tuple(
            _resolved_dataset(observation)
            for observation in observations
            if _dataset_matches(requested, observation)
        )

        if not verified:
            error = EntityNotFound(
                "No DataHub dataset exactly matched the canonical identity.",
                diagnostic=(
                    f"Discovered {len(discovered_urns)} candidates; "
                    "verified 0 exact matches."
                ),
            )
            return DatasetResolutionResult(
                state=ResolutionState.NOT_FOUND,
                requested=requested,
                discovered_candidate_count=len(discovered_urns),
                verified_candidate_count=0,
                resolved=None,
                candidates=(),
                evidence=None,
                failure=_failure(error),
            )

        if len(verified) > 1:
            error = EntityAmbiguous(
                "More than one DataHub dataset exactly matched the canonical identity.",
                diagnostic=f"Verified exact match count: {len(verified)}.",
            )
            return DatasetResolutionResult(
                state=ResolutionState.AMBIGUOUS,
                requested=requested,
                discovered_candidate_count=len(discovered_urns),
                verified_candidate_count=len(verified),
                resolved=None,
                candidates=verified,
                evidence=None,
                failure=_failure(error),
            )

        resolved = verified[0]
        evidence = self._dataset_evidence(requested, resolved)
        log_event(
            self._logger,
            logging.INFO,
            "dataset_resolution_finished",
            platform=resolved.platform,
            resolved_urn=resolved.urn,
            state=ResolutionState.RESOLVED.value,
            discovered_candidate_count=len(discovered_urns),
            verified_candidate_count=1,
        )
        return DatasetResolutionResult(
            state=ResolutionState.RESOLVED,
            requested=requested,
            discovered_candidate_count=len(discovered_urns),
            verified_candidate_count=1,
            resolved=resolved,
            candidates=(resolved,),
            evidence=evidence,
            failure=None,
        )

    def resolve_field(
        self,
        requested: CanonicalSchemaFieldIdentity,
        parent_dataset: ResolvedDatasetIdentity,
    ) -> FieldResolutionResult:
        validation_error = _validate_field_identity(
            requested,
            parent_dataset,
        )
        if validation_error is not None:
            error = InvalidCanonicalIdentity(
                validation_error,
            )
            return FieldResolutionResult(
                state=ResolutionState.INVALID_IDENTITY,
                requested=requested,
                parent_dataset=parent_dataset,
                verified_candidate_count=0,
                resolved=None,
                candidates=(),
                evidence=None,
                failure=_failure(error),
            )

        try:
            schema_fields = tuple(
                self._transport.schema_fields(parent_dataset.urn)
            )
        except DataHubAccessError as exc:
            return _unavailable_field_result(requested, parent_dataset, exc)
        except Exception as exc:
            return _unexpected_field_result(requested, parent_dataset, exc)

        exact_fields = tuple(
            field
            for field in schema_fields
            if field.name == requested.field_path
            and _field_leaf_name(field.name) == requested.field_name
        )
        resolved_candidates = tuple(
            _resolved_field(parent_dataset.urn, field)
            for field in exact_fields
        )

        if not resolved_candidates:
            error = FieldNotFound(
                "The field was not found inside the resolved parent dataset.",
                diagnostic=(
                    f"Requested exact field path: {requested.field_path}."
                ),
            )
            return FieldResolutionResult(
                state=ResolutionState.NOT_FOUND,
                requested=requested,
                parent_dataset=parent_dataset,
                verified_candidate_count=0,
                resolved=None,
                candidates=(),
                evidence=None,
                failure=_failure(error),
            )

        if len(resolved_candidates) > 1:
            error = EntityAmbiguous(
                "The parent schema contains multiple exact field matches.",
                diagnostic=(
                    f"Verified exact field count: {len(resolved_candidates)}."
                ),
            )
            return FieldResolutionResult(
                state=ResolutionState.AMBIGUOUS,
                requested=requested,
                parent_dataset=parent_dataset,
                verified_candidate_count=len(resolved_candidates),
                resolved=None,
                candidates=resolved_candidates,
                evidence=None,
                failure=_failure(error),
            )

        resolved = resolved_candidates[0]
        evidence = self._field_evidence(requested, resolved)
        log_event(
            self._logger,
            logging.INFO,
            "field_resolution_finished",
            parent_dataset_urn=resolved.parent_dataset_urn,
            field_path=resolved.field_path,
            state=ResolutionState.RESOLVED.value,
        )
        return FieldResolutionResult(
            state=ResolutionState.RESOLVED,
            requested=requested,
            parent_dataset=parent_dataset,
            verified_candidate_count=1,
            resolved=resolved,
            candidates=(resolved,),
            evidence=evidence,
            failure=None,
        )

    def _dataset_evidence(
        self,
        requested: CanonicalDatasetIdentity,
        resolved: ResolvedDatasetIdentity,
    ) -> ResolutionEvidence:
        return ResolutionEvidence(
            method="candidate_search_then_exact_aspect_verification",
            interfaces=(
                "DataHubGraph.get_urns_by_filter",
                "DatasetProperties",
                "DataPlatformInstance",
                "SchemaMetadata",
            ),
            canonical_request=_dataset_request_text(requested),
            resolved_urn=resolved.urn,
            verified_attributes=(
                _attribute(
                    "platform",
                    _normalized_platform(requested.platform),
                    resolved.platform,
                    case_sensitive=False,
                ),
                _attribute(
                    "environment",
                    requested.environment,
                    resolved.environment,
                    case_sensitive=False,
                ),
                _attribute(
                    "qualified_name",
                    requested.qualified_name,
                    resolved.qualified_name,
                    case_sensitive=False,
                ),
                _attribute(
                    "logical_name",
                    requested.logical_name,
                    resolved.logical_name,
                    case_sensitive=False,
                ),
            ),
            observed_at=_timestamp(self._clock),
            snapshot_context="Live DataHub aspect reads during Phase 1.2.",
        )

    def _field_evidence(
        self,
        requested: CanonicalSchemaFieldIdentity,
        resolved: ResolvedSchemaFieldIdentity,
    ) -> ResolutionEvidence:
        return ResolutionEvidence(
            method="exact_parent_schema_field_verification",
            interfaces=("SchemaMetadata.fields",),
            canonical_request=_field_request_text(requested),
            resolved_urn=(
                resolved.schema_field_urn or resolved.parent_dataset_urn
            ),
            verified_attributes=(
                _attribute(
                    "parent_dataset_urn",
                    resolved.parent_dataset_urn,
                    resolved.parent_dataset_urn,
                    case_sensitive=True,
                ),
                _attribute(
                    "field_path",
                    requested.field_path,
                    resolved.field_path,
                    case_sensitive=True,
                ),
                _attribute(
                    "field_name",
                    requested.field_name,
                    resolved.field_name,
                    case_sensitive=True,
                ),
            ),
            observed_at=_timestamp(self._clock),
            snapshot_context="Parent-scoped SchemaMetadata read during Phase 1.2.",
        )


def _validate_dataset_identity(
    requested: CanonicalDatasetIdentity,
) -> str | None:
    required = {
        "platform": requested.platform,
        "qualified_name": requested.qualified_name,
        "environment": requested.environment,
        "logical_name": requested.logical_name,
    }
    for name, value in required.items():
        if not value or value != value.strip():
            return (
                f"Canonical dataset {name} must be non-empty and must not "
                "contain surrounding whitespace."
            )
    parts = requested.qualified_name.split(".")
    if any(not part for part in parts):
        return "Canonical dataset qualified_name contains an empty segment."
    if _casefold(parts[-1]) != _casefold(requested.logical_name):
        return (
            "Canonical dataset logical_name must match the final "
            "qualified_name segment."
        )
    if requested.database is not None:
        if len(parts) < 3 or _casefold(parts[-3]) != _casefold(
            requested.database
        ):
            return "Canonical dataset database conflicts with qualified_name."
    if requested.schema is not None:
        if len(parts) < 2 or _casefold(parts[-2]) != _casefold(
            requested.schema
        ):
            return "Canonical dataset schema conflicts with qualified_name."
    return None


def _validate_field_identity(
    requested: CanonicalSchemaFieldIdentity,
    parent: ResolvedDatasetIdentity,
) -> str | None:
    dataset_error = _validate_dataset_identity(requested.parent_dataset)
    if dataset_error is not None:
        return dataset_error
    if (
        not requested.field_path
        or requested.field_path != requested.field_path.strip()
        or not requested.field_name
        or requested.field_name != requested.field_name.strip()
    ):
        return (
            "Canonical field path and name must be non-empty and must not "
            "contain surrounding whitespace."
        )
    if _field_leaf_name(requested.field_path) != requested.field_name:
        return "Canonical field name must match the field_path leaf exactly."
    if not _resolved_parent_matches(requested.parent_dataset, parent):
        return (
            "Resolved parent dataset does not match the canonical field's "
            "parent identity."
        )
    return None


def _dataset_matches(
    requested: CanonicalDatasetIdentity,
    observed: DatasetMetadataObservation,
) -> bool:
    return (
        _casefold(_normalized_platform(requested.platform))
        == _casefold(observed.platform)
        and _casefold(requested.environment)
        == _casefold(observed.environment)
        and _casefold(requested.qualified_name)
        == _casefold(observed.schema_name)
        and _casefold(requested.logical_name)
        == _casefold(observed.logical_name)
    )


def _resolved_parent_matches(
    requested: CanonicalDatasetIdentity,
    observed: ResolvedDatasetIdentity,
) -> bool:
    return (
        _casefold(_normalized_platform(requested.platform))
        == _casefold(observed.platform)
        and _casefold(requested.environment)
        == _casefold(observed.environment)
        and _casefold(requested.qualified_name)
        == _casefold(observed.qualified_name)
        and _casefold(requested.logical_name)
        == _casefold(observed.logical_name)
    )


def _resolved_dataset(
    observation: DatasetMetadataObservation,
) -> ResolvedDatasetIdentity:
    return ResolvedDatasetIdentity(
        urn=observation.urn,
        urn_name=observation.urn_name,
        platform=observation.platform,
        environment=observation.environment,
        qualified_name=observation.schema_name,
        logical_name=observation.logical_name,
        platform_instance=observation.platform_instance,
        properties_qualified_name=observation.properties_qualified_name,
    )


def _resolved_field(
    parent_urn: str,
    field: SchemaFieldObservation,
) -> ResolvedSchemaFieldIdentity:
    return ResolvedSchemaFieldIdentity(
        parent_dataset_urn=parent_urn,
        field_path=field.name,
        field_name=_field_leaf_name(field.name),
        native_type=field.native_type,
        normalized_type=field.normalized_type,
        description=field.description,
        schema_field_urn=field.schema_field_urn,
    )


def _invalid_dataset_result(
    requested: CanonicalDatasetIdentity,
    message: str,
) -> DatasetResolutionResult:
    return DatasetResolutionResult(
        state=ResolutionState.INVALID_IDENTITY,
        requested=requested,
        discovered_candidate_count=0,
        verified_candidate_count=0,
        resolved=None,
        candidates=(),
        evidence=None,
        failure=_failure(InvalidCanonicalIdentity(message)),
    )


def _unavailable_dataset_result(
    requested: CanonicalDatasetIdentity,
    exc: DataHubAccessError,
) -> DatasetResolutionResult:
    error = ResolutionUnavailable(
        "DataHub was unavailable during dataset resolution.",
        diagnostic=f"{exc.code.value}: {exc.diagnostic or exc.safe_message}",
    )
    return DatasetResolutionResult(
        state=ResolutionState.UNAVAILABLE,
        requested=requested,
        discovered_candidate_count=0,
        verified_candidate_count=0,
        resolved=None,
        candidates=(),
        evidence=None,
        failure=_failure(error),
    )


def _unexpected_dataset_result(
    requested: CanonicalDatasetIdentity,
    exc: Exception,
) -> DatasetResolutionResult:
    error = UnexpectedResolutionError(
        "Dataset resolution failed unexpectedly.",
        diagnostic=redact_secrets(type(exc).__name__),
    )
    return DatasetResolutionResult(
        state=ResolutionState.UNAVAILABLE,
        requested=requested,
        discovered_candidate_count=0,
        verified_candidate_count=0,
        resolved=None,
        candidates=(),
        evidence=None,
        failure=_failure(error),
    )


def _unavailable_field_result(
    requested: CanonicalSchemaFieldIdentity,
    parent: ResolvedDatasetIdentity,
    exc: DataHubAccessError,
) -> FieldResolutionResult:
    error = ResolutionUnavailable(
        "DataHub was unavailable during field resolution.",
        diagnostic=f"{exc.code.value}: {exc.diagnostic or exc.safe_message}",
    )
    return FieldResolutionResult(
        state=ResolutionState.UNAVAILABLE,
        requested=requested,
        parent_dataset=parent,
        verified_candidate_count=0,
        resolved=None,
        candidates=(),
        evidence=None,
        failure=_failure(error),
    )


def _unexpected_field_result(
    requested: CanonicalSchemaFieldIdentity,
    parent: ResolvedDatasetIdentity,
    exc: Exception,
) -> FieldResolutionResult:
    error = UnexpectedResolutionError(
        "Field resolution failed unexpectedly.",
        diagnostic=redact_secrets(type(exc).__name__),
    )
    return FieldResolutionResult(
        state=ResolutionState.UNAVAILABLE,
        requested=requested,
        parent_dataset=parent,
        verified_candidate_count=0,
        resolved=None,
        candidates=(),
        evidence=None,
        failure=_failure(error),
    )


def _failure(exc: DataHubAccessError) -> ResolutionFailure:
    return ResolutionFailure(
        code=exc.code,
        message=redact_secrets(exc.safe_message),
        diagnostic=(
            redact_secrets(exc.diagnostic)
            if exc.diagnostic is not None
            else None
        ),
    )


def _normalized_platform(value: str) -> str:
    normalized = _casefold(value)
    return _PLATFORM_ALIASES.get(normalized, normalized)


def _casefold(value: str) -> str:
    return value.casefold()


def _field_leaf_name(field_path: str) -> str:
    return field_path.rsplit(".", 1)[-1]


def _dataset_request_text(requested: CanonicalDatasetIdentity) -> str:
    return (
        requested.display_identity
        or f"{requested.platform} / {requested.qualified_name}"
    )


def _field_request_text(requested: CanonicalSchemaFieldIdentity) -> str:
    return (
        requested.display_identity
        or f"{_dataset_request_text(requested.parent_dataset)} / "
        f"{requested.field_path}"
    )


def _attribute(
    name: str,
    requested: str,
    observed: str,
    *,
    case_sensitive: bool,
) -> EvidenceAttribute:
    matched = (
        requested == observed
        if case_sensitive
        else _casefold(requested) == _casefold(observed)
    )
    return EvidenceAttribute(
        attribute=name,
        requested=requested,
        observed=observed,
        matched=matched,
    )


def _timestamp(clock: Clock) -> str:
    value = clock()
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()
