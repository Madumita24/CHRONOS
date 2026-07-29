"""FastAPI application for the certified CHRONOS review contract."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .errors import CertifiedReviewNotFound, PresentationIntegrityError
from .explorer_models import CertifiedImpactExplorer
from .explorer_service import CertifiedImpactExplorerService
from .graph_models import CertifiedGraphReview
from .graph_service import CertifiedGraphService
from .models import CertifiedChangeReview, HealthDTO
from .service import (
    EXPECTED_PHASE4_CERTIFICATION_FINGERPRINT,
    SUPPORTED_REVIEW_ID,
    CertifiedReviewService,
)


def _default_artifact_dir() -> Path:
    configured = os.environ.get("CHRONOS_ARTIFACT_DIR")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[3] / "artifacts"


def create_app(
    *,
    artifact_dir: str | Path | None = None,
    allowed_origins: tuple[str, ...] = (
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ),
) -> FastAPI:
    service = CertifiedReviewService(
        artifact_dir or _default_artifact_dir()
    )
    graph_service = CertifiedGraphService(
        artifact_dir or _default_artifact_dir()
    )
    explorer_service = CertifiedImpactExplorerService(
        artifact_dir or _default_artifact_dir()
    )
    app = FastAPI(
        title="CHRONOS Certified Presentation API",
        version="5.3.0",
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(allowed_origins),
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["Accept", "Content-Type"],
    )

    @app.get("/health", response_model=HealthDTO)
    def health() -> HealthDTO:
        _get_review_or_http(service, SUPPORTED_REVIEW_ID)
        return HealthDTO(
            status="ready",
            review_id=SUPPORTED_REVIEW_ID,
            certification_fingerprint=(
                EXPECTED_PHASE4_CERTIFICATION_FINGERPRINT
            ),
        )

    @app.get(
        "/api/reviews/{review_id}",
        response_model=CertifiedChangeReview,
        response_model_by_alias=True,
    )
    def get_review(review_id: str) -> CertifiedChangeReview:
        return _get_review_or_http(service, review_id)

    @app.get(
        "/api/reviews/{review_id}/graph",
        response_model=CertifiedGraphReview,
        response_model_by_alias=True,
    )
    def get_graph(review_id: str) -> CertifiedGraphReview:
        return _get_graph_or_http(graph_service, review_id)

    @app.get(
        "/api/reviews/{review_id}/explorer",
        response_model=CertifiedImpactExplorer,
        response_model_by_alias=True,
    )
    def get_explorer(review_id: str) -> CertifiedImpactExplorer:
        return _get_explorer_or_http(explorer_service, review_id)

    return app


def _get_review_or_http(
    service: CertifiedReviewService,
    review_id: str,
) -> CertifiedChangeReview:
    try:
        return service.get_review(review_id)
    except CertifiedReviewNotFound as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "certified_review_not_found",
                "message": "The requested certified review was not found.",
            },
        ) from exc
    except PresentationIntegrityError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "certification_integrity_error",
                "message": (
                    "The certified review is unavailable because its "
                    "integrity checks failed."
                ),
            },
        ) from exc


def _get_graph_or_http(
    service: CertifiedGraphService,
    review_id: str,
) -> CertifiedGraphReview:
    try:
        return service.get_graph(review_id)
    except CertifiedReviewNotFound as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "certified_review_not_found",
                "message": "The requested certified review was not found.",
            },
        ) from exc
    except PresentationIntegrityError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "certification_integrity_error",
                "message": (
                    "The certified graph is unavailable because its "
                    "integrity checks failed."
                ),
            },
        ) from exc


def _get_explorer_or_http(
    service: CertifiedImpactExplorerService,
    review_id: str,
) -> CertifiedImpactExplorer:
    try:
        return service.get_explorer(review_id)
    except CertifiedReviewNotFound as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "certified_review_not_found",
                "message": "The requested certified review was not found.",
            },
        ) from exc
    except PresentationIntegrityError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "certification_integrity_error",
                "message": (
                    "The certified impact explorer is unavailable because "
                    "its integrity checks failed."
                ),
            },
        ) from exc


app = create_app()
