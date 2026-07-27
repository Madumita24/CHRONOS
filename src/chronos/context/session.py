"""Readiness-gated Phase 1.5 session over one read-only DataHub client."""

from __future__ import annotations

import logging
from typing import Mapping

from chronos.datahub.config import DataHubConfig, ProfileLoader
from chronos.datahub.errors import FailureCode
from chronos.lineage.models import FieldLineageGraph
from chronos.lineage.session import LineageRetrievalSession

from .models import (
    ContextFailure,
    ContextRetrievalResult,
    ContextRetrievalState,
)
from .retriever import AssetContextRetriever


class ContextRetrievalSession(LineageRetrievalSession):
    """Share one client across readiness, identity, schema, lineage, and context."""

    def __init__(
        self,
        config: DataHubConfig,
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        super().__init__(config, logger=logger)
        self._context = AssetContextRetriever(self._transport)

    def retrieve_context(
        self,
        graph: FieldLineageGraph,
    ) -> ContextRetrievalResult:
        if not self.check_readiness().can_continue:
            return ContextRetrievalResult(
                state=ContextRetrievalState.UNAVAILABLE,
                snapshot=None,
                findings=(),
                failure=ContextFailure(
                    code=FailureCode.GOVERNANCE_RETRIEVAL_UNAVAILABLE,
                    message="Phase 1.1 readiness did not pass.",
                    diagnostic=(
                        "Context retrieval is blocked until DataHub is ready."
                    ),
                ),
            )
        return self._context.retrieve(graph)


def create_context_retrieval_session(
    *,
    environ: Mapping[str, str] | None = None,
    profile_loader: ProfileLoader | None = None,
    logger: logging.Logger | None = None,
) -> ContextRetrievalSession:
    config = DataHubConfig.from_environment(
        environ,
        profile_loader=profile_loader,
    )
    return ContextRetrievalSession(config, logger=logger)
