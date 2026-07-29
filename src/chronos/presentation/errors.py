"""Errors exposed by the certified presentation boundary."""


class PresentationBoundaryError(RuntimeError):
    """Base error for the read-only presentation boundary."""


class CertifiedReviewNotFound(PresentationBoundaryError):
    """The requested certified demonstration is not available."""


class PresentationIntegrityError(PresentationBoundaryError):
    """A certified input is missing, invalid, or inconsistent."""
