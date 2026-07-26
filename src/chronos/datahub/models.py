"""Typed readiness and capability models."""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
from typing import Any, Mapping

from .errors import FailureCode


class ReadinessState(str, Enum):
    READY = "ready"
    NOT_READY = "not_ready"


class ConfigurationSource(str, Enum):
    ENVIRONMENT = "environment"
    DATAHUB_CLI_PROFILE = "datahub_cli_profile"


class AuthenticationState(str, Enum):
    AUTHENTICATED = "authenticated"
    NOT_ENFORCED = "authentication_not_enforced"
    FAILED = "authentication_failed"
    FORBIDDEN = "authorization_failed"
    UNVERIFIED = "unverified"


class CapabilityState(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    UNVERIFIED = "unverified"


@dataclass(frozen=True)
class FailureDetail:
    code: FailureCode
    message: str
    blocking: bool = True
    diagnostic: str | None = None


@dataclass(frozen=True)
class ConnectivityResult:
    reachable: bool
    healthy: bool
    endpoint: str
    latency_ms: float | None
    http_status: int | None
    diagnostic: str


@dataclass(frozen=True)
class AuthenticationResult:
    state: AuthenticationState
    principal: str | None
    diagnostic: str


@dataclass(frozen=True)
class EnvironmentInformation:
    endpoint: str
    observed_gms_version: str | None
    expected_gms_version: str
    observed_sdk_version: str | None
    expected_sdk_version: str
    server_type: str | None
    server_environment: str | None
    version_notes: tuple[str, ...]
    diagnostic: str | None = None


@dataclass(frozen=True)
class CapabilityCheck:
    name: str
    required: bool
    state: CapabilityState
    evidence: tuple[str, ...]
    diagnostic: str


@dataclass(frozen=True)
class CapabilityReport:
    checks: tuple[CapabilityCheck, ...]

    @property
    def required_capabilities_available(self) -> bool:
        return all(
            not check.required or check.state is CapabilityState.AVAILABLE
            for check in self.checks
        )

    def by_name(self) -> Mapping[str, CapabilityCheck]:
        return {check.name: check for check in self.checks}


@dataclass(frozen=True)
class CanonicalSourceResult:
    dataset_found: bool
    resolved_dataset_urn: str | None
    canonical_display_identity: str
    field_found: bool
    field_name: str
    observed_field_type: str | None
    expected_field_type: str
    native_field_type: str | None
    satisfies_frozen_baseline: bool
    diagnostic: str


@dataclass(frozen=True)
class ReadinessResult:
    state: ReadinessState
    can_continue: bool
    configuration_source: ConfigurationSource | None
    security_warning: str | None
    connectivity: ConnectivityResult
    authentication: AuthenticationResult
    environment: EnvironmentInformation
    capabilities: CapabilityReport
    canonical_source: CanonicalSourceResult
    failures: tuple[FailureDetail, ...]

    def to_dict(self) -> dict[str, Any]:
        return _to_primitive(self)


def _to_primitive(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {
            item.name: _to_primitive(getattr(value, item.name))
            for item in fields(value)
        }
    if isinstance(value, tuple):
        return [_to_primitive(item) for item in value]
    if isinstance(value, list):
        return [_to_primitive(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _to_primitive(item) for key, item in value.items()}
    return value
