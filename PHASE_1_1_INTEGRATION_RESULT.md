# CHRONOS Phase 1.1 — Integration Verification Record

**Demonstration:** `CHRONOS-DEMO-001`<br>
**Verification date:** 2026-07-25<br>
**Scope:** Read-only local DataHub readiness only

## Final gate result

The following command was executed without manually setting
`DATAHUB_GMS_URL` or `DATAHUB_TOKEN`:

```powershell
.\.venv-datahub-310\Scripts\python.exe -m chronos.datahub
```

| Check | Observed result |
|---|---|
| Configuration source | `datahub_cli_profile` |
| GMS endpoint | `http://localhost:8080` |
| Connectivity | Reachable and healthy; HTTP `200` |
| Authentication | `authentication_not_enforced` |
| Principal | `urn:li:corpuser:__datahub_system` |
| Security warning | GMS authentication enforcement is disabled in this local Quickstart environment |
| GMS version | `v1.5.0.6` |
| Python SDK version | `1.6.0.15` |
| Server type / environment | `quickstart` / `core` |
| Readiness | `ready` |
| `can_continue` | `true` |
| Failures | None |

The configuration was loaded through DataHub's official
`datahub.cli.config_utils.load_client_config()` implementation. CHRONOS did
not parse `.datahubenv`, generate a token, copy a token into the process
environment, or expose the stored credential.

The configured, anonymous, and generated-invalid-credential GraphQL metadata
reads all succeeded. Because the endpoint is loopback and server metadata
positively identifies `quickstart` / `core`, this state is non-blocking for
the frozen local demonstration only. The security warning remains visible in
the authoritative readiness result.

## Required capability report

| Capability | State |
|---|---|
| Dataset read | `available` |
| Schema read | `available` |
| Schema-field read | `available` |
| Lineage read | `available` |
| Fine-grained lineage read | `available` |
| Governance read | `available` |
| Dashboard/chart read | `available` |
| Data flow/job read | `available` |

Capability evidence came from read-only GraphQL schema introspection.

## Canonical source verification

| Item | Observed result |
|---|---|
| Dataset | PostgreSQL `order_entry_db.order_entry.orders` |
| Resolved dataset URN | `urn:li:dataset:(urn:li:dataPlatform:postgres,b2fd91.order_entry_db.order_entry.orders,PROD)` |
| Field | `order_total` |
| Normalized type | `Number` |
| Native type | `DOUBLE PRECISION` |
| Frozen baseline satisfied | `true` |

The dataset was resolved through DataHub search and its schema was read using
the official Python SDK. The URN was not fabricated.

## Automated verification

- Unit suite: **23 passed**.
- Python compilation check: **passed**.
- Exact no-manual-token CLI readiness check: **passed**, exit code `0`.
- Readiness credential serialization/logging: no credential observed.
- No DataHub configuration or metadata was altered.
- Phase 1.2 was not started.
