"""Shared Phase 4 certification gate for presentation artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, TypeVar

from chronos.phase4_certification import (
    CertificationCheckStatus,
    Phase4CertificationResult,
    Phase4CertificationStatus,
    load_phase4_certification,
    validate_phase4_certification,
)

from .errors import CertifiedReviewNotFound, PresentationIntegrityError


EXPECTED_PHASE4_CERTIFICATION_FINGERPRINT = (
    "sha256:3e8444ec904e0ba1c55c5ae22d69edfa"
    "8e722310f51ab30fc783b8175a87ac4a"
)
SUPPORTED_REVIEW_ID = "CHRONOS-DEMO-001"
_T = TypeVar("_T")


class CertifiedArtifactLoader:
    """Load only artifacts whose identities are frozen by Phase 4."""

    def __init__(
        self,
        artifact_dir: str | Path,
        *,
        expected_fingerprint: str = (
            EXPECTED_PHASE4_CERTIFICATION_FINGERPRINT
        ),
    ) -> None:
        self._artifact_dir = Path(artifact_dir)
        self._expected_fingerprint = expected_fingerprint

    def certification(
        self,
        review_id: str,
    ) -> Phase4CertificationResult:
        if review_id != SUPPORTED_REVIEW_ID:
            raise CertifiedReviewNotFound(
                f"Certified review {review_id!r} was not found."
            )
        try:
            certification = load_phase4_certification(
                self._artifact_dir / "phase_4_certification.json"
            )
            validate_phase4_certification(certification)
        except Exception as exc:
            raise PresentationIntegrityError(
                "Phase 4 certification validation failed."
            ) from exc
        if (
            certification.certification_status
            is not Phase4CertificationStatus.CERTIFIED
            or certification.semantic_fingerprint
            != self._expected_fingerprint
            or any(
                check.status is not CertificationCheckStatus.PASS
                for check in certification.certification_checks
            )
        ):
            raise PresentationIntegrityError(
                "Phase 4 certification gate rejected the artifact."
            )
        return certification

    def load(
        self,
        certification: Phase4CertificationResult,
        name: str,
        loader: Callable[[Path], _T],
    ) -> _T:
        identities = {
            item.artifact_name: item.semantic_fingerprint
            for item in certification.input_artifact_identities
        }
        try:
            result = loader(self._artifact_dir / name)
        except Exception as exc:
            raise PresentationIntegrityError(
                f"Certified artifact {name} could not be loaded."
            ) from exc
        actual = getattr(result, "semantic_fingerprint", None)
        if identities.get(name) != actual:
            raise PresentationIntegrityError(
                f"Certified identity mismatch for {name}."
            )
        return result
