"""Readiness-gated Phase 1.3 session over one read-only transport."""

from __future__ import annotations

import logging
from typing import Mapping

from chronos.datahub._transport import DataHubSdkReadOnlyTransport
from chronos.datahub.access import ChronosDataHubAccess
from chronos.datahub.config import DataHubConfig, ProfileLoader
from chronos.datahub.errors import FailureCode
from chronos.datahub.models import ReadinessResult
from chronos.resolution.models import (
    CanonicalDatasetIdentity,
    CanonicalSchemaFieldIdentity,
    DatasetResolutionResult,
    FieldResolutionResult,
    ResolutionFailure,
    ResolutionState,
    ResolvedDatasetIdentity,
)
from chronos.resolution.resolver import CanonicalEntityResolver

from .models import (
    SchemaFailure,
    SchemaRetrievalResult,
    SchemaRetrievalState,
)
from .retriever import DatasetSchemaRetriever


class SchemaRetrievalSession:
    """Run readiness, resolution, and schema reads through one SDK client."""

    def __init__(
        self,
        config: DataHubConfig,
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        transport = DataHubSdkReadOnlyTransport(config)
        self._readiness = ChronosDataHubAccess(
            config,
            transport,
            logger=logger,
        )
        self._resolver = CanonicalEntityResolver(
            transport,
            logger=logger,
        )
        self._retriever = DatasetSchemaRetriever(
            transport,
            logger=logger,
        )
        self._readiness_result: ReadinessResult | None = None

    def check_readiness(self) -> ReadinessResult:
        if self._readiness_result is None:
            self._readiness_result = self._readiness.check_readiness()
        return self._readiness_result

    def resolve_dataset(
        self,
        requested: CanonicalDatasetIdentity,
    ) -> DatasetResolutionResult:
        if not self.check_readiness().can_continue:
            return DatasetResolutionResult(
                state=ResolutionState.UNAVAILABLE,
                requested=requested,
                discovered_candidate_count=0,
                verified_candidate_count=0,
                resolved=None,
                candidates=(),
                evidence=None,
                failure=_resolution_readiness_failure(),
            )
        return self._resolver.resolve_dataset(requested)

    def resolve_field(
        self,
        requested: CanonicalSchemaFieldIdentity,
        parent_dataset: ResolvedDatasetIdentity,
    ) -> FieldResolutionResult:
        if not self.check_readiness().can_continue:
            return FieldResolutionResult(
                state=ResolutionState.UNAVAILABLE,
                requested=requested,
                parent_dataset=parent_dataset,
                verified_candidate_count=0,
                resolved=None,
                candidates=(),
                evidence=None,
                failure=_resolution_readiness_failure(),
            )
        return self._resolver.resolve_field(requested, parent_dataset)

    def retrieve_schema(
        self,
        requested: CanonicalDatasetIdentity,
        dataset: ResolvedDatasetIdentity,
    ) -> SchemaRetrievalResult:
        if not self.check_readiness().can_continue:
            return SchemaRetrievalResult(
                state=SchemaRetrievalState.UNAVAILABLE,
                requested=requested,
                dataset=dataset,
                snapshot=None,
                findings=(),
                failure=SchemaFailure(
                    code=FailureCode.SCHEMA_RETRIEVAL_UNAVAILABLE,
                    message="Phase 1.1 readiness did not pass.",
                    diagnostic=(
                        "Schema retrieval is blocked until DataHub is ready."
                    ),
                ),
            )
        return self._retriever.retrieve(requested, dataset)


def create_schema_retrieval_session(
    *,
    environ: Mapping[str, str] | None = None,
    profile_loader: ProfileLoader | None = None,
    logger: logging.Logger | None = None,
) -> SchemaRetrievalSession:
    config = DataHubConfig.from_environment(
        environ,
        profile_loader=profile_loader,
    )
    return SchemaRetrievalSession(config, logger=logger)


def _resolution_readiness_failure() -> ResolutionFailure:
    return ResolutionFailure(
        code=FailureCode.RESOLUTION_UNAVAILABLE,
        message="Phase 1.1 readiness did not pass.",
        diagnostic="Canonical resolution is blocked until DataHub is ready.",
    )
