"""Small deterministic structured-logging helper."""

from __future__ import annotations

import json
import logging
from typing import Any, Iterable

from .errors import redact_secrets


def log_event(
    logger: logging.Logger,
    level: int,
    event: str,
    *,
    secrets: Iterable[str] = (),
    **fields: Any,
) -> None:
    safe_fields = {
        key: (
            redact_secrets(value, secrets)
            if isinstance(value, str)
            else value
        )
        for key, value in fields.items()
        if value is not None
    }
    payload = {"event": event, **safe_fields}
    logger.log(
        level,
        json.dumps(payload, sort_keys=True, separators=(",", ":")),
    )
