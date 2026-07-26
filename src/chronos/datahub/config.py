"""Secret-safe configuration resolution for the read-only DataHub boundary."""

from __future__ import annotations

import contextlib
import io
import os
from dataclasses import dataclass, field
from typing import Callable, Mapping
from urllib.parse import urlparse

from .errors import ConfigurationError
from .models import ConfigurationSource


ProfileLoader = Callable[[], object]


@dataclass(frozen=True)
class DataHubConfig:
    """Internal resolved configuration.

    The credential is intentionally private, excluded from ``repr``, and the
    type is not exported from the public ``chronos.datahub`` package.
    """

    gms_url: str
    _credential: str = field(repr=False)
    configuration_source: ConfigurationSource
    timeout_seconds: float = 10.0
    expected_gms_version: str = "v1.5.0.6"
    expected_sdk_version: str = "1.6.0.15"

    canonical_platform: str = "postgres"
    canonical_environment: str = "PROD"
    canonical_dataset_suffix: str = "order_entry_db.order_entry.orders"
    canonical_field: str = "order_total"
    canonical_type: str = "Number"
    canonical_display_identity: str = (
        "PostgreSQL / order_entry_db / order_entry / orders"
    )

    @classmethod
    def from_environment(
        cls,
        environ: Mapping[str, str] | None = None,
        *,
        profile_loader: ProfileLoader | None = None,
    ) -> "DataHubConfig":
        """Resolve CHRONOS environment values, then the DataHub CLI profile.

        Explicit CHRONOS environment values win field by field. The official
        DataHub CLI loader supplies any missing URL or credential.
        """

        values = os.environ if environ is None else environ
        environment_url = values.get("DATAHUB_GMS_URL", "").strip()
        environment_token = values.get("DATAHUB_TOKEN", "").strip()

        profile_url = ""
        profile_token = ""
        profile_was_used = not (environment_url and environment_token)
        if profile_was_used:
            profile = _load_profile_safely(profile_loader)
            try:
                raw_profile_url = getattr(profile, "server")
                raw_profile_token = getattr(profile, "token")
            except Exception:
                raise ConfigurationError(
                    "The DataHub CLI profile is malformed or unreadable.",
                    diagnostic=(
                        "The official profile loader did not return the "
                        "required server and token fields."
                    ),
                ) from None
            profile_url = (
                raw_profile_url.strip()
                if isinstance(raw_profile_url, str)
                else ""
            )
            profile_token = (
                raw_profile_token.strip()
                if isinstance(raw_profile_token, str)
                else ""
            )

        gms_url = environment_url or profile_url
        credential = environment_token or profile_token
        missing = []
        if not gms_url:
            missing.append("DataHub GMS URL")
        if not credential:
            missing.append("DataHub authentication credential")
        if missing:
            raise ConfigurationError(
                "Required DataHub configuration is missing.",
                diagnostic=f"Missing: {', '.join(missing)}.",
            )

        _validate_gms_url(gms_url)
        timeout_seconds = _resolve_timeout(values)
        source = (
            ConfigurationSource.DATAHUB_CLI_PROFILE
            if profile_was_used
            else ConfigurationSource.ENVIRONMENT
        )
        return cls(
            gms_url=gms_url.rstrip("/"),
            _credential=credential,
            configuration_source=source,
            timeout_seconds=timeout_seconds,
        )


def _load_profile_safely(profile_loader: ProfileLoader | None) -> object:
    loader = profile_loader or _official_profile_loader
    try:
        return loader()
    except ConfigurationError:
        raise
    except BaseException as exc:
        if isinstance(exc, (KeyboardInterrupt, GeneratorExit)):
            raise
        raise ConfigurationError(
            "The DataHub CLI profile is unavailable or invalid.",
            diagnostic=(
                "The official DataHub profile loader failed safely "
                f"({type(exc).__name__})."
            ),
        ) from None


def _official_profile_loader() -> object:
    """Use DataHub's supported CLI configuration resolution implementation."""

    from datahub.cli.config_utils import load_client_config

    # DataHub 1.6.0.15 writes validation failures through Click before raising
    # SystemExit. Suppress those implementation diagnostics so a malformed
    # profile can never echo credential material through CHRONOS.
    with contextlib.redirect_stdout(io.StringIO()):
        with contextlib.redirect_stderr(io.StringIO()):
            return load_client_config()


def _validate_gms_url(gms_url: str) -> None:
    parsed = urlparse(gms_url)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ConfigurationError(
            "The resolved DataHub GMS URL must be a plain HTTP(S) service URL "
            "without embedded credentials, query parameters, or fragments."
        )


def _resolve_timeout(values: Mapping[str, str]) -> float:
    timeout_text = values.get("DATAHUB_TIMEOUT_SECONDS", "10").strip()
    try:
        timeout_seconds = float(timeout_text)
    except ValueError as exc:
        raise ConfigurationError(
            "DATAHUB_TIMEOUT_SECONDS must be numeric."
        ) from exc
    if timeout_seconds <= 0:
        raise ConfigurationError(
            "DATAHUB_TIMEOUT_SECONDS must be greater than zero."
        )
    return timeout_seconds
