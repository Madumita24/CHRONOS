"""Typed, secret-safe errors for the CHRONOS DataHub boundary."""

from __future__ import annotations

import re
from enum import Enum
from typing import Iterable


class FailureCode(str, Enum):
    CONFIGURATION_ERROR = "configuration_error"
    CONNECTION_ERROR = "connection_error"
    AUTHENTICATION_ERROR = "authentication_error"
    AUTHORIZATION_ERROR = "authorization_error"
    CAPABILITY_ERROR = "capability_error"
    CANONICAL_DATASET_NOT_FOUND = "canonical_dataset_not_found"
    CANONICAL_DATASET_AMBIGUOUS = "canonical_dataset_ambiguous"
    CANONICAL_FIELD_NOT_FOUND = "canonical_field_not_found"
    CANONICAL_FIELD_TYPE_MISMATCH = "canonical_field_type_mismatch"
    UNEXPECTED_DATAHUB_ERROR = "unexpected_datahub_error"


_BEARER_PATTERN = re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,;]+")
_TOKEN_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)\b(datahub_(?:gms_)?token|token|access_token)\s*[:=]\s*[^\s,;]+"
)


def redact_secrets(value: object, secrets: Iterable[str] = ()) -> str:
    """Return a diagnostic string with known and token-shaped secrets removed."""

    text = str(value)
    for secret in secrets:
        if secret:
            text = text.replace(secret, "<redacted>")
    text = _BEARER_PATTERN.sub(r"\1<redacted>", text)
    text = _TOKEN_ASSIGNMENT_PATTERN.sub(lambda m: f"{m.group(1)}=<redacted>", text)
    return text


class DataHubAccessError(Exception):
    """Base class carrying a stable machine-readable failure category."""

    code = FailureCode.UNEXPECTED_DATAHUB_ERROR

    def __init__(
        self,
        safe_message: str,
        *,
        diagnostic: str | None = None,
        status_code: int | None = None,
    ) -> None:
        super().__init__(safe_message)
        self.safe_message = safe_message
        self.diagnostic = diagnostic
        self.status_code = status_code


class ConfigurationError(DataHubAccessError):
    code = FailureCode.CONFIGURATION_ERROR


class ConnectionError(DataHubAccessError):
    code = FailureCode.CONNECTION_ERROR


class AuthenticationError(DataHubAccessError):
    code = FailureCode.AUTHENTICATION_ERROR


class AuthorizationError(DataHubAccessError):
    code = FailureCode.AUTHORIZATION_ERROR


class CapabilityError(DataHubAccessError):
    code = FailureCode.CAPABILITY_ERROR


class CanonicalDatasetNotFound(DataHubAccessError):
    code = FailureCode.CANONICAL_DATASET_NOT_FOUND


class CanonicalDatasetAmbiguous(DataHubAccessError):
    code = FailureCode.CANONICAL_DATASET_AMBIGUOUS


class CanonicalFieldNotFound(DataHubAccessError):
    code = FailureCode.CANONICAL_FIELD_NOT_FOUND


class CanonicalFieldTypeMismatch(DataHubAccessError):
    code = FailureCode.CANONICAL_FIELD_TYPE_MISMATCH


class UnexpectedDataHubError(DataHubAccessError):
    code = FailureCode.UNEXPECTED_DATAHUB_ERROR
