# CHRONOS Phase 1.1 — DataHub Readiness Gate

This package implements only the read-only connection and capability gate for
`CHRONOS-DEMO-001`. It does not traverse lineage, calculate the 25-field
blast radius, construct a Future Graph, analyze impact, recommend repairs, or
write metadata.

## Setup

Use Python 3.10 and the pinned DataHub SDK:

```powershell
.\.venv-datahub-310\Scripts\python.exe -m pip install -e . --no-build-isolation
```

Configuration is resolved in this order:

1. Explicit `DATAHUB_GMS_URL` and `DATAHUB_TOKEN` values.
2. Missing values are filled from the standard DataHub CLI profile created
   by `datahub init`.
3. If the combined configuration is unusable, the gate returns
   `configuration_error`.

Environment values override corresponding profile values. When the profile
contributes either required value, the reported source is
`datahub_cli_profile`; when both explicit values are supplied, it is
`environment`.

The implementation uses DataHub 1.6.0.15's official
`datahub.cli.config_utils.load_client_config()` mechanism. It does not parse
`.datahubenv` itself. The profile credential remains private and is excluded
from readiness JSON, logs, errors, and configuration representations.

Copy `.env.example` only when explicit overrides are needed. The package does
not load `.env` files automatically.

## Run the readiness check

```powershell
.\.venv-datahub-310\Scripts\python.exe -m chronos.datahub
```

Exit code `0` means Ready. Exit code `1` means Not Ready. Output is structured
JSON; program logic uses typed states and failure codes rather than parsing
diagnostic messages.

A successful result includes:

- healthy GMS connectivity and measured latency;
- a successful configured metadata read and resolved principal;
- an explicit authentication state;
- `configuration_source` set to `environment` or `datahub_cli_profile`;
- observed and expected GMS/SDK version information;
- eight required capabilities marked `available`;
- the runtime-resolved PostgreSQL `orders` dataset URN;
- field `order_total`;
- observed normalized type `Number`;
- `can_continue: true`.

A version difference is reported but is not independently blocking. Missing
required capabilities or frozen canonical metadata is blocking.

## Authentication semantics

The gate distinguishes:

- `authenticated`: enforcement is active, unauthenticated probes are rejected,
  and the configured credential succeeds;
- `authentication_not_enforced`: configured, anonymous, and generated-invalid
  credential probes all succeed;
- `authentication_failed`: the configured credential is rejected;
- `authorization_failed`: the required metadata read is denied;
- `unverified`: enforcement or metadata access cannot be determined safely.

`authentication_not_enforced` is non-blocking only for the frozen local
Quickstart: the endpoint must be loopback and server metadata must report
`quickstart` / `core`. In that case the result includes a visible
`security_warning`. The same state is blocking for every other environment.

## Unit tests

Unit tests use a fake read-only transport and do not require Docker:

```powershell
.\.venv-datahub-310\Scripts\python.exe -m unittest discover -s tests\unit -v
```

They cover environment/profile precedence, missing and malformed profiles,
profile and environment secret redaction, connectivity, authentication,
authorization, missing capabilities and canonical metadata, type mismatch,
success, Quickstart-only no-auth semantics, security-warning redaction,
version handling, and the read-only public boundary.

## Optional integration test

With the local CLI profile already configured, set only the integration-test
switch:

```powershell
$env:CHRONOS_RUN_INTEGRATION = "1"
.\.venv-datahub-310\Scripts\python.exe -m unittest discover -s tests\integration -v
```

The integration test is skipped unless explicitly enabled. Ordinary unit
tests never require DataHub.

## Common failures

| Failure code | Meaning | Expected action |
|---|---|---|
| `configuration_error` | Neither environment nor CLI profile supplies usable configuration | Run `datahub init` or correct explicit overrides |
| `connection_error` | GMS is unreachable or unhealthy | Restore local DataHub connectivity |
| `authentication_error` | Credential was rejected | Supply a valid token |
| `authorization_error` | Required metadata read was denied | Grant the necessary read permission |
| `capability_error` | Required GraphQL capability is absent | Use a compatible DataHub environment |
| `canonical_dataset_not_found` | Canonical PostgreSQL `orders` did not resolve | Restore the official showcase datapack |
| `canonical_dataset_ambiguous` | More than one canonical candidate matched | Correct the environment; do not select arbitrarily |
| `canonical_field_not_found` | `order_total` is absent | Restore the frozen source schema |
| `canonical_field_type_mismatch` | Observed type is not `Number` | Treat as baseline drift |
| `unexpected_datahub_error` | Unexpected API/response failure | Inspect sanitized diagnostics and retry after correction |

## Read-only guarantee

The public `ChronosDataHubAccess` boundary exposes only
`check_readiness()`. Its private transport protocol contains only health,
authentication, environment, capability, dataset-search, identity, and
schema-read operations.

Phase 1.1 contains no emitter, GraphQL mutation, REST write, MCP/MCE
publication, create, update, delete, patch, upsert, or rollback path.

## Current local integration status

The verification record is maintained in
`PHASE_1_1_INTEGRATION_RESULT.md`. On 2026-07-25 the no-manual-token CLI
check resolved the existing DataHub CLI profile and returned `ready`.
