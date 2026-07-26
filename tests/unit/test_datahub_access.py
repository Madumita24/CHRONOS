from __future__ import annotations

import inspect
import io
import json
import logging
import unittest
from types import SimpleNamespace

from chronos.datahub import ChronosDataHubAccess, check_readiness
from chronos.datahub._transport import (
    AuthenticationEnforcement,
    AuthenticationObservation,
    DatasetIdentity,
    EnvironmentObservation,
    HealthObservation,
    ReadOnlyTransport,
    SchemaFieldObservation,
)
from chronos.datahub.config import DataHubConfig
from chronos.datahub.errors import (
    AuthenticationError,
    AuthorizationError,
    ConnectionError,
    FailureCode,
    UnexpectedDataHubError,
)
from chronos.datahub.models import (
    AuthenticationState,
    CapabilityState,
    ConfigurationSource,
    ReadinessState,
)


def capability_schema() -> dict[str, frozenset[str]]:
    return {
        "Query": frozenset(
            {
                "dataset",
                "entities",
                "scrollAcrossLineage",
                "dashboard",
                "chart",
                "dataFlow",
                "dataJob",
            }
        ),
        "Dataset": frozenset(
            {
                "urn",
                "properties",
                "schemaMetadata",
                "lineage",
                "fineGrainedLineages",
                "ownership",
                "tags",
                "glossaryTerms",
                "domain",
                "structuredProperties",
            }
        ),
        "SchemaMetadata": frozenset({"fields"}),
        "Dashboard": frozenset({"properties", "inputFields", "relationships"}),
        "DataFlow": frozenset({"properties", "lineage"}),
        "DataJob": frozenset({"inputOutput", "lineage"}),
    }


class FakeTransport:
    def __init__(self) -> None:
        self.health_value = HealthObservation(
            reachable=True,
            healthy=True,
            latency_ms=1.25,
            http_status=200,
            diagnostic="ok",
        )
        self.auth_value: AuthenticationObservation | Exception = (
            AuthenticationObservation(
                principal="urn:li:corpuser:test",
                enforcement=AuthenticationEnforcement.ENFORCED,
                diagnostic="Configured metadata read succeeded.",
            )
        )
        self.environment_value = EnvironmentObservation(
            gms_version="v1.5.0.6",
            sdk_version="1.6.0.15",
            server_type="quickstart",
            server_environment="core",
        )
        self.capabilities_value = capability_schema()
        self.search_results = (
            "urn:li:dataset:(urn:li:dataPlatform:postgres,"
            "b2fd91.order_entry_db.order_entry.orders,PROD)",
        )
        self.fields = (
            SchemaFieldObservation(
                name="order_total",
                normalized_type="Number",
                native_type="DOUBLE PRECISION",
            ),
        )

    def health(self) -> HealthObservation:
        if isinstance(self.health_value, Exception):
            raise self.health_value
        return self.health_value

    def authentication(self) -> AuthenticationObservation:
        if isinstance(self.auth_value, Exception):
            raise self.auth_value
        return self.auth_value

    def environment_information(self) -> EnvironmentObservation:
        return self.environment_value

    def graphql_type_fields(self) -> dict[str, frozenset[str]]:
        return self.capabilities_value

    def search_dataset_urns(self, **_: str) -> tuple[str, ...]:
        return self.search_results

    def dataset_identity(self, urn: str) -> DatasetIdentity:
        return DatasetIdentity(
            urn=urn,
            platform="postgres",
            name="b2fd91.order_entry_db.order_entry.orders",
            environment="PROD",
        )

    def schema_fields(self, _: str) -> tuple[SchemaFieldObservation, ...]:
        return self.fields


def config(token: str = "unit-test-secret-token") -> DataHubConfig:
    return DataHubConfig(
        gms_url="http://datahub.test:8080",
        _credential=token,
        configuration_source=ConfigurationSource.ENVIRONMENT,
    )


def local_quickstart_config(
    token: str = "unit-test-secret-token",
) -> DataHubConfig:
    return DataHubConfig(
        gms_url="http://localhost:8080",
        _credential=token,
        configuration_source=ConfigurationSource.DATAHUB_CLI_PROFILE,
    )


def unavailable_profile() -> object:
    raise FileNotFoundError("profile missing")


class DataHubReadinessTests(unittest.TestCase):
    def test_missing_configuration_is_not_ready(self) -> None:
        result = check_readiness(
            environ={},
            profile_loader=unavailable_profile,
        )
        self.assertEqual(result.state, ReadinessState.NOT_READY)
        self.assertFalse(result.can_continue)
        self.assertEqual(result.failures[0].code, FailureCode.CONFIGURATION_ERROR)

    def test_unreachable_gms_is_not_ready(self) -> None:
        fake = FakeTransport()
        fake.health_value = ConnectionError("unreachable")
        result = ChronosDataHubAccess(config(), fake).check_readiness()
        self.assertFalse(result.can_continue)
        self.assertFalse(result.connectivity.reachable)
        self.assertEqual(result.failures[0].code, FailureCode.CONNECTION_ERROR)

    def test_invalid_authentication_is_not_ready(self) -> None:
        fake = FakeTransport()
        fake.auth_value = AuthenticationError("invalid credential")
        result = ChronosDataHubAccess(config(), fake).check_readiness()
        self.assertFalse(result.can_continue)
        self.assertEqual(
            result.authentication.state, AuthenticationState.FAILED
        )
        self.assertEqual(
            result.failures[0].code, FailureCode.AUTHENTICATION_ERROR
        )

    def test_unverified_authentication_state_is_not_ready(self) -> None:
        fake = FakeTransport()
        fake.auth_value = UnexpectedDataHubError(
            "DataHub authentication state could not be verified.",
            diagnostic="Authentication probes produced inconsistent results.",
        )
        result = ChronosDataHubAccess(config(), fake).check_readiness()
        self.assertFalse(result.can_continue)
        self.assertEqual(
            result.authentication.state,
            AuthenticationState.UNVERIFIED,
        )
        self.assertEqual(
            result.failures[0].code, FailureCode.UNEXPECTED_DATAHUB_ERROR
        )

    def test_authorization_failure_is_not_ready(self) -> None:
        fake = FakeTransport()
        fake.auth_value = AuthorizationError("metadata read forbidden")
        result = ChronosDataHubAccess(config(), fake).check_readiness()
        self.assertFalse(result.can_continue)
        self.assertEqual(
            result.authentication.state, AuthenticationState.FORBIDDEN
        )
        self.assertEqual(
            result.failures[0].code, FailureCode.AUTHORIZATION_ERROR
        )

    def test_required_capability_unavailable_is_not_ready(self) -> None:
        fake = FakeTransport()
        fake.capabilities_value["Dataset"] = frozenset(
            fake.capabilities_value["Dataset"] - {"fineGrainedLineages"}
        )
        result = ChronosDataHubAccess(config(), fake).check_readiness()
        check = result.capabilities.by_name()["fine_grained_lineage_read"]
        self.assertFalse(result.can_continue)
        self.assertEqual(check.state, CapabilityState.UNAVAILABLE)

    def test_dataset_not_found_is_not_ready(self) -> None:
        fake = FakeTransport()
        fake.search_results = ()
        result = ChronosDataHubAccess(config(), fake).check_readiness()
        self.assertFalse(result.can_continue)
        self.assertFalse(result.canonical_source.dataset_found)
        self.assertEqual(
            result.failures[-1].code,
            FailureCode.CANONICAL_DATASET_NOT_FOUND,
        )

    def test_canonical_field_not_found_is_not_ready(self) -> None:
        fake = FakeTransport()
        fake.fields = (
            SchemaFieldObservation("order_id", "Number", "INTEGER"),
        )
        result = ChronosDataHubAccess(config(), fake).check_readiness()
        self.assertFalse(result.can_continue)
        self.assertFalse(result.canonical_source.field_found)
        self.assertEqual(
            result.failures[-1].code,
            FailureCode.CANONICAL_FIELD_NOT_FOUND,
        )

    def test_canonical_type_mismatch_is_not_ready(self) -> None:
        fake = FakeTransport()
        fake.fields = (
            SchemaFieldObservation("order_total", "String", "VARCHAR"),
        )
        result = ChronosDataHubAccess(config(), fake).check_readiness()
        self.assertFalse(result.can_continue)
        self.assertTrue(result.canonical_source.dataset_found)
        self.assertIsNotNone(result.canonical_source.resolved_dataset_urn)
        self.assertTrue(result.canonical_source.field_found)
        self.assertEqual(result.canonical_source.observed_field_type, "String")
        self.assertEqual(
            result.failures[-1].code,
            FailureCode.CANONICAL_FIELD_TYPE_MISMATCH,
        )

    def test_successful_readiness_is_structured_and_ready(self) -> None:
        result = ChronosDataHubAccess(config(), FakeTransport()).check_readiness()
        self.assertTrue(result.can_continue)
        self.assertEqual(result.state, ReadinessState.READY)
        self.assertEqual(
            result.authentication.state,
            AuthenticationState.AUTHENTICATED,
        )
        self.assertIsNone(result.security_warning)
        self.assertTrue(result.capabilities.required_capabilities_available)
        self.assertTrue(result.canonical_source.satisfies_frozen_baseline)
        self.assertEqual(
            result.canonical_source.observed_field_type, "Number"
        )
        self.assertEqual(result.failures, ())
        serialized = result.to_dict()
        self.assertIsInstance(serialized["capabilities"]["checks"], list)
        self.assertEqual(serialized["state"], "ready")

    def test_local_quickstart_without_auth_enforcement_is_ready_with_warning(
        self,
    ) -> None:
        fake = FakeTransport()
        fake.auth_value = AuthenticationObservation(
            principal="urn:li:corpuser:__datahub_system",
            enforcement=AuthenticationEnforcement.NOT_ENFORCED,
            diagnostic="Authentication enforcement is disabled.",
        )

        result = ChronosDataHubAccess(
            local_quickstart_config(),
            fake,
        ).check_readiness()

        self.assertTrue(result.can_continue)
        self.assertEqual(result.state, ReadinessState.READY)
        self.assertEqual(
            result.authentication.state,
            AuthenticationState.NOT_ENFORCED,
        )
        self.assertIsNotNone(result.security_warning)
        self.assertEqual(result.failures, ())

    def test_non_quickstart_without_auth_enforcement_is_not_ready(self) -> None:
        fake = FakeTransport()
        fake.auth_value = AuthenticationObservation(
            principal="urn:li:corpuser:test",
            enforcement=AuthenticationEnforcement.NOT_ENFORCED,
            diagnostic="Authentication enforcement is disabled.",
        )
        fake.environment_value = EnvironmentObservation(
            gms_version="v1.5.0.6",
            sdk_version="1.6.0.15",
            server_type="production",
            server_environment="prod",
        )

        result = ChronosDataHubAccess(
            local_quickstart_config(),
            fake,
        ).check_readiness()

        self.assertFalse(result.can_continue)
        self.assertEqual(result.state, ReadinessState.NOT_READY)
        self.assertIsNone(result.security_warning)
        self.assertEqual(
            result.failures[-1].code,
            FailureCode.AUTHENTICATION_ERROR,
        )

    def test_authentication_security_warning_never_contains_credential(
        self,
    ) -> None:
        secret = "quickstart-profile-secret"
        fake = FakeTransport()
        fake.auth_value = AuthenticationObservation(
            principal="urn:li:corpuser:__datahub_system",
            enforcement=AuthenticationEnforcement.NOT_ENFORCED,
            diagnostic="Authentication enforcement is disabled.",
        )

        result = ChronosDataHubAccess(
            local_quickstart_config(secret),
            fake,
        ).check_readiness()
        serialized = json.dumps(result.to_dict())

        self.assertNotIn(secret, serialized)
        self.assertIn(
            "authentication enforcement is disabled",
            (result.security_warning or "").lower(),
        )

    def test_version_mismatch_is_informational_when_capabilities_pass(self) -> None:
        fake = FakeTransport()
        fake.environment_value = EnvironmentObservation(
            gms_version="v9.9.9",
            sdk_version="9.9.9",
            server_type="quickstart",
            server_environment="core",
        )
        result = ChronosDataHubAccess(config(), fake).check_readiness()
        self.assertTrue(result.can_continue)
        self.assertEqual(len(result.environment.version_notes), 2)

    def test_secret_is_redacted_from_results_logs_and_repr(self) -> None:
        token = "do-not-leak-this-token"
        fake = FakeTransport()
        fake.health_value = ConnectionError(
            "unreachable",
            diagnostic=f"Authorization: Bearer {token}",
        )
        stream = io.StringIO()
        logger = logging.getLogger("chronos.test.redaction")
        logger.handlers.clear()
        logger.propagate = False
        logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler(stream)
        logger.addHandler(handler)

        cfg = config(token)
        result = ChronosDataHubAccess(cfg, fake, logger=logger).check_readiness()
        combined = json.dumps(result.to_dict()) + stream.getvalue() + repr(cfg)
        self.assertNotIn(token, combined)
        self.assertIn("<redacted>", combined)

    def test_public_boundary_is_read_only(self) -> None:
        public_methods = {
            name
            for name, value in inspect.getmembers(
                ChronosDataHubAccess, predicate=callable
            )
            if not name.startswith("_")
        }
        self.assertEqual(public_methods, {"check_readiness"})

        transport_methods = {
            name
            for name, value in ReadOnlyTransport.__dict__.items()
            if callable(value) and not name.startswith("_")
        }
        forbidden = {
            "emit",
            "write",
            "create",
            "update",
            "delete",
            "patch",
            "upsert",
            "mutate",
            "rollback",
        }
        self.assertFalse(
            any(
                marker in method.lower()
                for method in transport_methods
                for marker in forbidden
            )
        )


class DataHubConfigurationResolutionTests(unittest.TestCase):
    def test_complete_environment_configuration_is_selected(self) -> None:
        profile_called = False

        def loader() -> object:
            nonlocal profile_called
            profile_called = True
            return SimpleNamespace(
                server="http://profile.test:8080",
                token="profile-secret",
            )

        result = check_readiness(
            environ={
                "DATAHUB_GMS_URL": "http://environment.test:8080",
                "DATAHUB_TOKEN": "environment-secret",
            },
            profile_loader=loader,
            transport_factory=lambda _: FakeTransport(),
        )

        self.assertTrue(result.can_continue)
        self.assertFalse(profile_called)
        self.assertEqual(
            result.configuration_source,
            ConfigurationSource.ENVIRONMENT,
        )
        self.assertEqual(
            result.connectivity.endpoint,
            "http://environment.test:8080",
        )

    def test_cli_profile_is_selected_when_environment_is_absent(self) -> None:
        result = check_readiness(
            environ={},
            profile_loader=lambda: SimpleNamespace(
                server="http://profile.test:8080",
                token="profile-secret",
            ),
            transport_factory=lambda _: FakeTransport(),
        )

        self.assertTrue(result.can_continue)
        self.assertEqual(
            result.configuration_source,
            ConfigurationSource.DATAHUB_CLI_PROFILE,
        )
        self.assertEqual(
            result.connectivity.endpoint,
            "http://profile.test:8080",
        )

    def test_environment_value_overrides_corresponding_profile_value(self) -> None:
        result = check_readiness(
            environ={"DATAHUB_GMS_URL": "http://override.test:8080"},
            profile_loader=lambda: SimpleNamespace(
                server="http://profile.test:8080",
                token="profile-secret",
            ),
            transport_factory=lambda _: FakeTransport(),
        )

        self.assertTrue(result.can_continue)
        self.assertEqual(
            result.configuration_source,
            ConfigurationSource.DATAHUB_CLI_PROFILE,
        )
        self.assertEqual(
            result.connectivity.endpoint,
            "http://override.test:8080",
        )

    def test_missing_profile_returns_configuration_error(self) -> None:
        result = check_readiness(
            environ={},
            profile_loader=unavailable_profile,
        )

        self.assertFalse(result.can_continue)
        self.assertIsNone(result.configuration_source)
        self.assertEqual(
            result.failures[0].code,
            FailureCode.CONFIGURATION_ERROR,
        )

    def test_malformed_profile_returns_safe_configuration_error(self) -> None:
        secret = "malformed-profile-secret"

        def malformed_profile() -> object:
            raise ValueError(f"token={secret}")

        result = check_readiness(
            environ={},
            profile_loader=malformed_profile,
        )
        serialized = json.dumps(result.to_dict())

        self.assertFalse(result.can_continue)
        self.assertEqual(
            result.failures[0].code,
            FailureCode.CONFIGURATION_ERROR,
        )
        self.assertNotIn(secret, serialized)

    def test_profile_credential_is_absent_from_results_logs_and_repr(self) -> None:
        secret = "profile-secret-must-not-leak"
        stream = io.StringIO()
        logger = logging.getLogger("chronos.test.profile-redaction")
        logger.handlers.clear()
        logger.propagate = False
        logger.setLevel(logging.DEBUG)
        logger.addHandler(logging.StreamHandler(stream))

        def transport_factory(cfg: DataHubConfig) -> FakeTransport:
            fake = FakeTransport()
            fake.health_value = ConnectionError(
                "unreachable",
                diagnostic=f"Authorization: Bearer {secret}",
            )
            self.assertNotIn(secret, repr(cfg))
            return fake

        result = check_readiness(
            environ={},
            profile_loader=lambda: SimpleNamespace(
                server="http://profile.test:8080",
                token=secret,
            ),
            transport_factory=transport_factory,
            logger=logger,
        )
        combined = json.dumps(result.to_dict()) + stream.getvalue()

        self.assertNotIn(secret, combined)
        self.assertIn("<redacted>", combined)

    def test_successful_readiness_uses_profile_derived_configuration(self) -> None:
        result = check_readiness(
            environ={},
            profile_loader=lambda: SimpleNamespace(
                server="http://profile.test:8080",
                token="profile-secret",
            ),
            transport_factory=lambda _: FakeTransport(),
        )

        self.assertEqual(result.state, ReadinessState.READY)
        self.assertTrue(result.can_continue)
        self.assertEqual(
            result.to_dict()["configuration_source"],
            "datahub_cli_profile",
        )


if __name__ == "__main__":
    unittest.main()
