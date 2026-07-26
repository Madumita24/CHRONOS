"""Readiness-gated Phase 1.2 resolution session."""

from __future__ import annotations

import logging
from typing import Mapping

from chronos.datahub._transport import DataHubSdkReadOnlyTransport
from chronos.datahub.access import ChronosDataHubAccess
from chronos.datahub.config import DataHubConfig, ProfileLoader
from chronos.datahub.errors import FailureCode
from chronos.datahub.models import ReadinessResult

from .models import (
    CanonicalDatasetIdentity,
    CanonicalSchemaFieldIdentity,
    DatasetResolutionResult,
    FieldResolutionResult,
    ResolutionFailure,
    ResolutionState,
    ResolvedDatasetIdentity,
)
from .resolver import CanonicalEntityResolver


class ResolutionSession:
    """Public read-only session that reuses the Phase 1.1 client boundary."""

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
        self._readiness_result: ReadinessResult | None = None

    def check_readiness(self) -> ReadinessResult:
        if self._readiness_result is None:
            self._readiness_result = self._readiness.check_readiness()
        return self._readiness_result

    def resolve_dataset(
        self,
        requested: CanonicalDatasetIdentity,
    ) -> DatasetResolutionResult:
        readiness = self.check_readiness()
        if not readiness.can_continue:
            return DatasetResolutionResult(
                state=ResolutionState.UNAVAILABLE,
                requested=requested,
                discovered_candidate_count=0,
                verified_candidate_count=0,
                resolved=None,
                candidates=(),
                evidence=None,
                failure=_readiness_failure(),
            )
        return self._resolver.resolve_dataset(requested)

    def resolve_field(
        self,
        requested: CanonicalSchemaFieldIdentity,
        parent_dataset: ResolvedDatasetIdentity,
    ) -> FieldResolutionResult:
        readiness = self.check_readiness()
        if not readiness.can_continue:
            return FieldResolutionResult(
                state=ResolutionState.UNAVAILABLE,
                requested=requested,
                parent_dataset=parent_dataset,
                verified_candidate_count=0,
                resolved=None,
                candidates=(),
                evidence=None,
                failure=_readiness_failure(),
            )
        return self._resolver.resolve_field(requested, parent_dataset)


def create_resolution_session(
    *,
    environ: Mapping[str, str] | None = None,
    profile_loader: ProfileLoader | None = None,
    logger: logging.Logger | None = None,
) -> ResolutionSession:
    config = DataHubConfig.from_environment(
        environ,
        profile_loader=profile_loader,
    )
    return ResolutionSession(config, logger=logger)


def _readiness_failure() -> ResolutionFailure:
    return ResolutionFailure(
        code=FailureCode.RESOLUTION_UNAVAILABLE,
        message="Phase 1.1 readiness did not pass.",
        diagnostic="Canonical resolution is blocked until DataHub is ready.",
    )
