"""Readiness-gated Phase 1.4 session over one read-only DataHub client."""

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
from chronos.schema.models import (
    DatasetSchemaSnapshot,
    SchemaFailure,
    SchemaRetrievalResult,
    SchemaRetrievalState,
)
from chronos.schema.retriever import DatasetSchemaRetriever

from .models import (
    LineageFailure,
    LineageRetrievalResult,
    LineageRetrievalState,
)
from .retriever import FieldLineageRetriever


class LineageRetrievalSession:
    """Share one client across readiness, identity, schema, and lineage reads."""

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
        self._schema = DatasetSchemaRetriever(
            transport,
            logger=logger,
        )
        self._lineage = FieldLineageRetriever(
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
        return self._schema.retrieve(requested, dataset)

    def retrieve_direct_lineage(
        self,
        source_snapshot: DatasetSchemaSnapshot,
        field_path: str,
    ) -> LineageRetrievalResult:
        if not self.check_readiness().can_continue:
            return _lineage_readiness_failure()
        return self._lineage.retrieve_direct(source_snapshot, field_path)

    def traverse_downstream_lineage(
        self,
        source_snapshot: DatasetSchemaSnapshot,
        field_path: str,
    ) -> LineageRetrievalResult:
        if not self.check_readiness().can_continue:
            return _lineage_readiness_failure()
        return self._lineage.traverse_downstream(
            source_snapshot,
            field_path,
        )


def create_lineage_retrieval_session(
    *,
    environ: Mapping[str, str] | None = None,
    profile_loader: ProfileLoader | None = None,
    logger: logging.Logger | None = None,
) -> LineageRetrievalSession:
    config = DataHubConfig.from_environment(
        environ,
        profile_loader=profile_loader,
    )
    return LineageRetrievalSession(config, logger=logger)


def _resolution_readiness_failure() -> ResolutionFailure:
    return ResolutionFailure(
        code=FailureCode.RESOLUTION_UNAVAILABLE,
        message="Phase 1.1 readiness did not pass.",
        diagnostic="Canonical resolution is blocked until DataHub is ready.",
    )


def _lineage_readiness_failure() -> LineageRetrievalResult:
    return LineageRetrievalResult(
        state=LineageRetrievalState.UNAVAILABLE,
        graph=None,
        findings=(),
        failure=LineageFailure(
            code=FailureCode.LINEAGE_TRAVERSAL_UNAVAILABLE,
            message="Phase 1.1 readiness did not pass.",
            diagnostic="Lineage retrieval is blocked until DataHub is ready.",
        ),
    )
