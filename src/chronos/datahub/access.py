"""Fail-closed readiness gate for CHRONOS-DEMO-001."""

from __future__ import annotations

import logging
from typing import Callable, Mapping
from urllib.parse import urlparse

from ._transport import (
    AuthenticationEnforcement,
    DataHubSdkReadOnlyTransport,
    DatasetIdentity,
    ReadOnlyTransport,
)
from .config import DataHubConfig, ProfileLoader
from .errors import (
    AuthenticationError,
    AuthorizationError,
    CanonicalDatasetAmbiguous,
    CanonicalDatasetNotFound,
    CanonicalFieldNotFound,
    CanonicalFieldTypeMismatch,
    ConfigurationError,
    DataHubAccessError,
    FailureCode,
    redact_secrets,
)
from .logging_utils import log_event
from .models import (
    AuthenticationResult,
    AuthenticationState,
    CanonicalSourceResult,
    CapabilityCheck,
    CapabilityReport,
    CapabilityState,
    ConfigurationSource,
    ConnectivityResult,
    EnvironmentInformation,
    FailureDetail,
    ReadinessResult,
    ReadinessState,
)


_CAPABILITY_REQUIREMENTS: Mapping[str, Mapping[str, frozenset[str]]] = {
    "dataset_read": {
        "Query": frozenset({"dataset", "entities"}),
        "Dataset": frozenset({"urn", "properties"}),
    },
    "schema_read": {
        "Dataset": frozenset({"schemaMetadata"}),
        "SchemaMetadata": frozenset({"fields"}),
    },
    "field_read": {
        "SchemaMetadata": frozenset({"fields"}),
    },
    "lineage_read": {
        "Query": frozenset({"scrollAcrossLineage"}),
        "Dataset": frozenset({"lineage"}),
    },
    "fine_grained_lineage_read": {
        "Dataset": frozenset({"fineGrainedLineages"}),
    },
    "governance_read": {
        "Dataset": frozenset(
            {
                "ownership",
                "tags",
                "glossaryTerms",
                "domain",
                "structuredProperties",
            }
        ),
    },
    "bi_context_read": {
        "Query": frozenset({"dashboard", "chart"}),
        "Dashboard": frozenset({"properties", "inputFields", "relationships"}),
    },
    "pipeline_context_read": {
        "Query": frozenset({"dataFlow", "dataJob"}),
        "DataFlow": frozenset({"properties", "lineage"}),
        "DataJob": frozenset({"inputOutput", "lineage"}),
    },
}


class ChronosDataHubAccess:
    """Public Phase 1.1 boundary.

    The only public operation is ``check_readiness``. The class exposes no
    mutation primitive and never returns the underlying SDK client.
    """

    def __init__(
        self,
        config: DataHubConfig,
        transport: ReadOnlyTransport | None = None,
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        self._config = config
        self._transport = transport or DataHubSdkReadOnlyTransport(config)
        self._logger = logger or logging.getLogger("chronos.datahub")

    def check_readiness(self) -> ReadinessResult:
        failures: list[FailureDetail] = []
        secrets = (self._config._credential,)
        log_event(
            self._logger,
            logging.INFO,
            "readiness_started",
            secrets=secrets,
            endpoint=self._config.gms_url,
            configuration_source=self._config.configuration_source.value,
        )

        connectivity = self._check_connectivity(failures)
        if not connectivity.reachable or not connectivity.healthy:
            return self._finish(
                connectivity,
                _unverified_authentication("Connectivity did not pass."),
                _unknown_environment(self._config, "Connectivity did not pass."),
                _unverified_capabilities("Connectivity did not pass."),
                _missing_canonical(self._config, "Connectivity did not pass."),
                failures,
            )

        authentication = self._check_authentication(failures)
        if authentication.state in {
            AuthenticationState.FAILED,
            AuthenticationState.FORBIDDEN,
            AuthenticationState.UNVERIFIED,
        }:
            return self._finish(
                connectivity,
                authentication,
                _unknown_environment(
                    self._config, "Authentication did not pass."
                ),
                _unverified_capabilities("Authentication did not pass."),
                _missing_canonical(
                    self._config, "Authentication did not pass."
                ),
                failures,
            )

        environment = self._check_environment()
        capabilities = self._check_capabilities(failures)
        canonical = self._check_canonical_source(failures)

        return self._finish(
            connectivity,
            authentication,
            environment,
            capabilities,
            canonical,
            failures,
        )

    def _check_connectivity(
        self, failures: list[FailureDetail]
    ) -> ConnectivityResult:
        try:
            observation = self._transport.health()
            result = ConnectivityResult(
                reachable=observation.reachable,
                healthy=observation.healthy,
                endpoint=self._config.gms_url,
                latency_ms=observation.latency_ms,
                http_status=observation.http_status,
                diagnostic=observation.diagnostic,
            )
            if not result.reachable or not result.healthy:
                failures.append(
                    FailureDetail(
                        code=FailureCode.CONNECTION_ERROR,
                        message="DataHub GMS did not pass its health check.",
                        diagnostic=result.diagnostic,
                    )
                )
            log_event(
                self._logger,
                logging.INFO,
                "connectivity_checked",
                secrets=(self._config._credential,),
                endpoint=self._config.gms_url,
                reachable=result.reachable,
                healthy=result.healthy,
                latency_ms=result.latency_ms,
                http_status=result.http_status,
            )
            return result
        except DataHubAccessError as exc:
            failures.append(_failure_from_error(exc, self._config._credential))
            log_event(
                self._logger,
                logging.ERROR,
                "connectivity_failed",
                secrets=(self._config._credential,),
                endpoint=self._config.gms_url,
                code=exc.code.value,
                diagnostic=exc.diagnostic or exc.safe_message,
            )
            return ConnectivityResult(
                reachable=False,
                healthy=False,
                endpoint=self._config.gms_url,
                latency_ms=None,
                http_status=exc.status_code,
                diagnostic=exc.safe_message,
            )

    def _check_authentication(
        self, failures: list[FailureDetail]
    ) -> AuthenticationResult:
        try:
            observation = self._transport.authentication()
            state = (
                AuthenticationState.AUTHENTICATED
                if observation.enforcement
                is AuthenticationEnforcement.ENFORCED
                else AuthenticationState.NOT_ENFORCED
            )
            log_event(
                self._logger,
                logging.INFO,
                "authentication_checked",
                secrets=(self._config._credential,),
                endpoint=self._config.gms_url,
                state=state.value,
                principal=observation.principal,
            )
            return AuthenticationResult(
                state=state,
                principal=observation.principal,
                diagnostic=observation.diagnostic,
            )
        except AuthenticationError as exc:
            failures.append(_failure_from_error(exc, self._config._credential))
            return AuthenticationResult(
                state=AuthenticationState.FAILED,
                principal=None,
                diagnostic=exc.safe_message,
            )
        except AuthorizationError as exc:
            failures.append(_failure_from_error(exc, self._config._credential))
            return AuthenticationResult(
                state=AuthenticationState.FORBIDDEN,
                principal=None,
                diagnostic=exc.safe_message,
            )
        except DataHubAccessError as exc:
            failures.append(_failure_from_error(exc, self._config._credential))
            return AuthenticationResult(
                state=AuthenticationState.UNVERIFIED,
                principal=None,
                diagnostic=exc.safe_message,
            )

    def _check_environment(self) -> EnvironmentInformation:
        observation = self._transport.environment_information()
        notes: list[str] = []
        if observation.gms_version is None:
            notes.append("GMS version was not available.")
        elif observation.gms_version != self._config.expected_gms_version:
            notes.append(
                "Observed GMS version differs from the frozen Phase 0 "
                "expectation; capability checks determine readiness."
            )
        if observation.sdk_version is None:
            notes.append("SDK version was not available.")
        elif observation.sdk_version != self._config.expected_sdk_version:
            notes.append(
                "Observed SDK version differs from the frozen Phase 0 "
                "expectation; capability checks determine readiness."
            )
        log_event(
            self._logger,
            logging.INFO,
            "environment_observed",
            secrets=(self._config._credential,),
            endpoint=self._config.gms_url,
            observed_gms_version=observation.gms_version,
            observed_sdk_version=observation.sdk_version,
            server_type=observation.server_type,
            server_environment=observation.server_environment,
        )
        return EnvironmentInformation(
            endpoint=self._config.gms_url,
            observed_gms_version=observation.gms_version,
            expected_gms_version=self._config.expected_gms_version,
            observed_sdk_version=observation.sdk_version,
            expected_sdk_version=self._config.expected_sdk_version,
            server_type=observation.server_type,
            server_environment=observation.server_environment,
            version_notes=tuple(notes),
            diagnostic=observation.diagnostic,
        )

    def _check_capabilities(
        self, failures: list[FailureDetail]
    ) -> CapabilityReport:
        try:
            available_fields = self._transport.graphql_type_fields()
        except DataHubAccessError as exc:
            failures.append(_failure_from_error(exc, self._config._credential))
            return _unverified_capabilities(exc.safe_message)

        checks: list[CapabilityCheck] = []
        for capability_name, requirements in _CAPABILITY_REQUIREMENTS.items():
            expected = tuple(
                sorted(
                    f"{type_name}.{field_name}"
                    for type_name, field_names in requirements.items()
                    for field_name in field_names
                )
            )
            missing = tuple(
                item
                for item in expected
                if item.split(".", 1)[1]
                not in available_fields.get(item.split(".", 1)[0], frozenset())
            )
            if missing:
                check = CapabilityCheck(
                    name=capability_name,
                    required=True,
                    state=CapabilityState.UNAVAILABLE,
                    evidence=expected,
                    diagnostic=f"Missing GraphQL fields: {', '.join(missing)}",
                )
                failures.append(
                    FailureDetail(
                        code=FailureCode.CAPABILITY_ERROR,
                        message=f"Required capability is unavailable: {capability_name}",
                        diagnostic=check.diagnostic,
                    )
                )
            else:
                check = CapabilityCheck(
                    name=capability_name,
                    required=True,
                    state=CapabilityState.AVAILABLE,
                    evidence=expected,
                    diagnostic="All required GraphQL fields are available.",
                )
            checks.append(check)
            log_event(
                self._logger,
                logging.INFO,
                "capability_checked",
                secrets=(self._config._credential,),
                endpoint=self._config.gms_url,
                capability=capability_name,
                state=check.state.value,
            )
        return CapabilityReport(checks=tuple(checks))

    def _check_canonical_source(
        self, failures: list[FailureDetail]
    ) -> CanonicalSourceResult:
        identity: DatasetIdentity | None = None
        observed_type: str | None = None
        native_type: str | None = None
        field_found = False
        try:
            urns = self._transport.search_dataset_urns(
                platform=self._config.canonical_platform,
                environment=self._config.canonical_environment,
                query="orders",
            )
            matches: list[DatasetIdentity] = []
            suffix = f".{self._config.canonical_dataset_suffix}".lower()
            for urn in urns:
                identity = self._transport.dataset_identity(urn)
                if (
                    identity.platform.lower()
                    == self._config.canonical_platform.lower()
                    and identity.environment.upper()
                    == self._config.canonical_environment.upper()
                    and (
                        identity.name.lower()
                        == self._config.canonical_dataset_suffix.lower()
                        or identity.name.lower().endswith(suffix)
                    )
                ):
                    matches.append(identity)

            if not matches:
                raise CanonicalDatasetNotFound(
                    "The canonical PostgreSQL orders dataset was not found."
                )
            if len(matches) != 1:
                raise CanonicalDatasetAmbiguous(
                    "The canonical PostgreSQL orders dataset did not resolve uniquely.",
                    diagnostic=f"Matching dataset count: {len(matches)}",
                )

            identity = matches[0]
            schema_fields = self._transport.schema_fields(identity.urn)
            matching_fields = tuple(
                field
                for field in schema_fields
                if field.name == self._config.canonical_field
            )
            if not matching_fields:
                raise CanonicalFieldNotFound(
                    f"The canonical field {self._config.canonical_field} was not found."
                )
            field = matching_fields[0]
            field_found = True
            observed_type = field.normalized_type
            native_type = field.native_type
            if field.normalized_type != self._config.canonical_type:
                raise CanonicalFieldTypeMismatch(
                    "The canonical field type does not match the frozen baseline.",
                    diagnostic=(
                        f"Expected {self._config.canonical_type}; "
                        f"observed {field.normalized_type}."
                    ),
                )

            log_event(
                self._logger,
                logging.INFO,
                "canonical_source_checked",
                secrets=(self._config._credential,),
                endpoint=self._config.gms_url,
                resolved_dataset_urn=identity.urn,
                field=field.name,
                observed_type=field.normalized_type,
                success=True,
            )
            return CanonicalSourceResult(
                dataset_found=True,
                resolved_dataset_urn=identity.urn,
                canonical_display_identity=self._config.canonical_display_identity,
                field_found=True,
                field_name=field.name,
                observed_field_type=field.normalized_type,
                expected_field_type=self._config.canonical_type,
                native_field_type=field.native_type,
                satisfies_frozen_baseline=True,
                diagnostic="Canonical source satisfies the Phase 1.1 baseline.",
            )
        except DataHubAccessError as exc:
            failures.append(_failure_from_error(exc, self._config._credential))
            log_event(
                self._logger,
                logging.ERROR,
                "canonical_source_failed",
                secrets=(self._config._credential,),
                endpoint=self._config.gms_url,
                code=exc.code.value,
                diagnostic=exc.diagnostic or exc.safe_message,
                success=False,
            )
            return CanonicalSourceResult(
                dataset_found=identity is not None,
                resolved_dataset_urn=identity.urn if identity else None,
                canonical_display_identity=self._config.canonical_display_identity,
                field_found=field_found,
                field_name=self._config.canonical_field,
                observed_field_type=observed_type,
                expected_field_type=self._config.canonical_type,
                native_field_type=native_type,
                satisfies_frozen_baseline=False,
                diagnostic=exc.safe_message,
            )

    def _finish(
        self,
        connectivity: ConnectivityResult,
        authentication: AuthenticationResult,
        environment: EnvironmentInformation,
        capabilities: CapabilityReport,
        canonical: CanonicalSourceResult,
        failures: list[FailureDetail],
    ) -> ReadinessResult:
        final_failures = list(failures)
        security_warning: str | None = None
        authentication_acceptable = (
            authentication.state is AuthenticationState.AUTHENTICATED
        )
        if authentication.state is AuthenticationState.NOT_ENFORCED:
            if _is_expected_local_quickstart(self._config, environment):
                authentication_acceptable = True
                security_warning = (
                    "GMS authentication enforcement is disabled in this "
                    "local Quickstart environment."
                )
            else:
                final_failures.append(
                    FailureDetail(
                        code=FailureCode.AUTHENTICATION_ERROR,
                        message=(
                            "Authentication is not enforced outside the "
                            "expected local Quickstart environment."
                        ),
                        diagnostic=(
                            "Unauthenticated metadata access is blocking "
                            "because the server was not positively identified "
                            "as the frozen local Quickstart."
                        ),
                    )
                )
        ready = (
            connectivity.reachable
            and connectivity.healthy
            and authentication_acceptable
            and capabilities.required_capabilities_available
            and canonical.satisfies_frozen_baseline
            and not any(item.blocking for item in final_failures)
        )
        result = ReadinessResult(
            state=ReadinessState.READY if ready else ReadinessState.NOT_READY,
            can_continue=ready,
            configuration_source=self._config.configuration_source,
            security_warning=security_warning,
            connectivity=connectivity,
            authentication=authentication,
            environment=environment,
            capabilities=capabilities,
            canonical_source=canonical,
            failures=tuple(final_failures),
        )
        log_event(
            self._logger,
            logging.INFO if ready else logging.ERROR,
            "readiness_finished",
            secrets=(self._config._credential,),
            endpoint=self._config.gms_url,
            state=result.state.value,
            can_continue=result.can_continue,
            failure_count=len(result.failures),
        )
        return result


def check_readiness(
    *,
    environ: Mapping[str, str] | None = None,
    profile_loader: ProfileLoader | None = None,
    transport_factory: Callable[[DataHubConfig], ReadOnlyTransport] | None = None,
    logger: logging.Logger | None = None,
) -> ReadinessResult:
    """Create configuration and return a structured fail-closed result."""

    try:
        config = DataHubConfig.from_environment(
            environ,
            profile_loader=profile_loader,
        )
    except ConfigurationError as exc:
        safe_diagnostic = redact_secrets(exc.diagnostic or exc.safe_message)
        failure = FailureDetail(
            code=exc.code,
            message=exc.safe_message,
            diagnostic=safe_diagnostic,
        )
        return _configuration_failure_result(exc, failure)

    transport = (
        transport_factory(config)
        if transport_factory is not None
        else DataHubSdkReadOnlyTransport(config)
    )
    return ChronosDataHubAccess(
        config,
        transport,
        logger=logger,
    ).check_readiness()


def _failure_from_error(
    exc: DataHubAccessError, token: str
) -> FailureDetail:
    return FailureDetail(
        code=exc.code,
        message=redact_secrets(exc.safe_message, (token,)),
        diagnostic=(
            redact_secrets(exc.diagnostic, (token,))
            if exc.diagnostic is not None
            else None
        ),
    )


def _configuration_failure_result(
    exc: ConfigurationError, failure: FailureDetail
) -> ReadinessResult:
    empty_config = DataHubConfig(
        gms_url="<unconfigured>",
        _credential="<redacted>",
        configuration_source=ConfigurationSource.ENVIRONMENT,
    )
    return ReadinessResult(
        state=ReadinessState.NOT_READY,
        can_continue=False,
        configuration_source=None,
        security_warning=None,
        connectivity=ConnectivityResult(
            reachable=False,
            healthy=False,
            endpoint="<unconfigured>",
            latency_ms=None,
            http_status=None,
            diagnostic=exc.safe_message,
        ),
        authentication=_unverified_authentication("Configuration failed."),
        environment=_unknown_environment(empty_config, "Configuration failed."),
        capabilities=_unverified_capabilities("Configuration failed."),
        canonical_source=_missing_canonical(
            empty_config, "Configuration failed."
        ),
        failures=(failure,),
    )


def _unverified_authentication(reason: str) -> AuthenticationResult:
    return AuthenticationResult(
        state=AuthenticationState.UNVERIFIED,
        principal=None,
        diagnostic=reason,
    )


def _unknown_environment(
    config: DataHubConfig, reason: str
) -> EnvironmentInformation:
    return EnvironmentInformation(
        endpoint=config.gms_url,
        observed_gms_version=None,
        expected_gms_version=config.expected_gms_version,
        observed_sdk_version=None,
        expected_sdk_version=config.expected_sdk_version,
        server_type=None,
        server_environment=None,
        version_notes=("Environment information was not observed.",),
        diagnostic=reason,
    )


def _unverified_capabilities(reason: str) -> CapabilityReport:
    return CapabilityReport(
        checks=tuple(
            CapabilityCheck(
                name=name,
                required=True,
                state=CapabilityState.UNVERIFIED,
                evidence=(),
                diagnostic=reason,
            )
            for name in _CAPABILITY_REQUIREMENTS
        )
    )


def _missing_canonical(
    config: DataHubConfig, reason: str
) -> CanonicalSourceResult:
    return CanonicalSourceResult(
        dataset_found=False,
        resolved_dataset_urn=None,
        canonical_display_identity=config.canonical_display_identity,
        field_found=False,
        field_name=config.canonical_field,
        observed_field_type=None,
        expected_field_type=config.canonical_type,
        native_field_type=None,
        satisfies_frozen_baseline=False,
        diagnostic=reason,
    )


def _is_expected_local_quickstart(
    config: DataHubConfig,
    environment: EnvironmentInformation,
) -> bool:
    hostname = (urlparse(config.gms_url).hostname or "").lower()
    return (
        hostname in {"localhost", "127.0.0.1", "::1"}
        and (environment.server_type or "").lower() == "quickstart"
        and (environment.server_environment or "").lower() == "core"
    )
