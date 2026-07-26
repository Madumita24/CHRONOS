from __future__ import annotations

import os
import unittest

from chronos.datahub import (
    AuthenticationState,
    CapabilityState,
    ConfigurationSource,
    ReadinessState,
    check_readiness,
)


@unittest.skipUnless(
    os.environ.get("CHRONOS_RUN_INTEGRATION") == "1",
    "Set CHRONOS_RUN_INTEGRATION=1 to test the live DataHub instance.",
)
class DataHubReadinessIntegrationTests(unittest.TestCase):
    def test_live_showcase_environment_is_ready(self) -> None:
        result = check_readiness()

        self.assertEqual(result.state, ReadinessState.READY, result.to_dict())
        self.assertEqual(
            result.configuration_source,
            ConfigurationSource.DATAHUB_CLI_PROFILE,
        )
        self.assertTrue(result.connectivity.reachable)
        self.assertTrue(result.connectivity.healthy)
        self.assertEqual(
            result.authentication.state,
            AuthenticationState.NOT_ENFORCED,
        )
        self.assertIsNotNone(result.security_warning)
        self.assertTrue(result.capabilities.required_capabilities_available)
        self.assertTrue(
            all(
                check.state is CapabilityState.AVAILABLE
                for check in result.capabilities.checks
                if check.required
            )
        )
        self.assertTrue(result.canonical_source.dataset_found)
        self.assertTrue(result.canonical_source.field_found)
        self.assertEqual(
            result.canonical_source.observed_field_type,
            result.canonical_source.expected_field_type,
        )
        self.assertTrue(result.canonical_source.satisfies_frozen_baseline)


if __name__ == "__main__":
    unittest.main()
