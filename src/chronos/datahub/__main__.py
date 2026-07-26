"""Command-line entry point for the Phase 1.1 readiness gate."""

from __future__ import annotations

import json
import logging
import os

from .access import check_readiness


def main() -> int:
    level_name = os.environ.get("CHRONOS_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(level=level, format="%(message)s")

    result = check_readiness()
    print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    return 0 if result.can_continue else 1


if __name__ == "__main__":
    raise SystemExit(main())
