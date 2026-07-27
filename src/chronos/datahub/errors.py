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
    ENTITY_NOT_FOUND = "entity_not_found"
    ENTITY_AMBIGUOUS = "entity_ambiguous"
    FIELD_NOT_FOUND = "field_not_found"
    INVALID_CANONICAL_IDENTITY = "invalid_canonical_identity"
    RESOLUTION_UNAVAILABLE = "resolution_unavailable"
    UNEXPECTED_RESOLUTION_ERROR = "unexpected_resolution_error"
    SCHEMA_NOT_FOUND = "schema_not_found"
    SCHEMA_EMPTY = "schema_empty"
    SCHEMA_MALFORMED = "schema_malformed"
    DUPLICATE_FIELD_PATH = "duplicate_field_path"
    UNSUPPORTED_FIELD_METADATA = "unsupported_field_metadata"
    SCHEMA_RETRIEVAL_UNAVAILABLE = "schema_retrieval_unavailable"
    FINE_GRAINED_LINEAGE_UNAVAILABLE = "fine_grained_lineage_unavailable"
    MALFORMED_LINEAGE_GROUP = "malformed_lineage_group"
    UNRESOLVED_FIELD_REFERENCE = "unresolved_field_reference"
    LINEAGE_TRAVERSAL_UNAVAILABLE = "lineage_traversal_unavailable"
    LINEAGE_EVIDENCE_CONFLICT = "lineage_evidence_conflict"
    UNEXPECTED_LINEAGE_ERROR = "unexpected_lineage_error"
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


class EntityNotFound(DataHubAccessError):
    code = FailureCode.ENTITY_NOT_FOUND


class EntityAmbiguous(DataHubAccessError):
    code = FailureCode.ENTITY_AMBIGUOUS


class FieldNotFound(DataHubAccessError):
    code = FailureCode.FIELD_NOT_FOUND


class InvalidCanonicalIdentity(DataHubAccessError):
    code = FailureCode.INVALID_CANONICAL_IDENTITY


class ResolutionUnavailable(DataHubAccessError):
    code = FailureCode.RESOLUTION_UNAVAILABLE


class UnexpectedResolutionError(DataHubAccessError):
    code = FailureCode.UNEXPECTED_RESOLUTION_ERROR


class SchemaNotFound(DataHubAccessError):
    code = FailureCode.SCHEMA_NOT_FOUND


class SchemaEmpty(DataHubAccessError):
    code = FailureCode.SCHEMA_EMPTY


class SchemaMalformed(DataHubAccessError):
    code = FailureCode.SCHEMA_MALFORMED


class DuplicateFieldPath(DataHubAccessError):
    code = FailureCode.DUPLICATE_FIELD_PATH


class UnsupportedFieldMetadata(DataHubAccessError):
    code = FailureCode.UNSUPPORTED_FIELD_METADATA


class SchemaRetrievalUnavailable(DataHubAccessError):
    code = FailureCode.SCHEMA_RETRIEVAL_UNAVAILABLE


class FineGrainedLineageUnavailable(DataHubAccessError):
    code = FailureCode.FINE_GRAINED_LINEAGE_UNAVAILABLE


class MalformedLineageGroup(DataHubAccessError):
    code = FailureCode.MALFORMED_LINEAGE_GROUP


class UnresolvedFieldReference(DataHubAccessError):
    code = FailureCode.UNRESOLVED_FIELD_REFERENCE


class LineageTraversalUnavailable(DataHubAccessError):
    code = FailureCode.LINEAGE_TRAVERSAL_UNAVAILABLE


class LineageEvidenceConflict(DataHubAccessError):
    code = FailureCode.LINEAGE_EVIDENCE_CONFLICT


class UnexpectedLineageError(DataHubAccessError):
    code = FailureCode.UNEXPECTED_LINEAGE_ERROR
