"""Command-line interface for CHRONOS analysis workflows."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from .structural_engine import StructuralEngineError, analyze_structural_change


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="chronos")
    commands = parser.add_subparsers(dest="command", required=True)
    analyze = commands.add_parser(
        "analyze-structural-change",
        help="Analyze a supported structural change from a frozen snapshot.",
    )
    analyze.add_argument("--proposal", required=True, help="Proposal JSON path.")
    analyze.add_argument("--snapshot", required=True, help="Snapshot JSON path.")
    analyze.add_argument("--output", required=True, help="Isolated output directory.")
    analyze.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace only a prior generalized artifact directory.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = analyze_structural_change(
            args.proposal,
            args.snapshot,
            args.output,
            overwrite=args.overwrite,
        )
    except Exception as exc:
        print(
            json.dumps(
                {
                    "error": {
                        "message": str(exc),
                        "type": type(exc).__name__,
                    },
                    "status": "failed",
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    print(
        json.dumps(
            {
                "analysis_id": result.identity.analysis_id,
                "certification_status": result.certification_status,
                "disposition": result.disposition,
                "operation": result.identity.operation.value,
                "output_dir": str(result.output_dir),
                "semantic_fingerprint": result.semantic_fingerprint,
                "status": "succeeded",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
