"""Command-line entry point for independent Phase 6 certification."""

from __future__ import annotations

import argparse
import json
import sys

from .certifier import certify_phase6


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m chronos.phase6_certification")
    parser.add_argument("--repository", default=".", help="CHRONOS repository root.")
    parser.add_argument("--output", required=True, help="Dedicated certification output directory.")
    parser.add_argument("--test-summary", required=True, help="Machine-readable test execution summary JSON.")
    parser.add_argument("--overwrite", action="store_true", help="Replace only a recognized Phase 6 certification package.")
    args = parser.parse_args(argv)
    try:
        result = certify_phase6(
            args.repository,
            args.output,
            test_summary=args.test_summary,
            overwrite=args.overwrite,
        )
    except Exception as exc:
        print(
            json.dumps(
                {
                    "error": {"message": str(exc), "type": type(exc).__name__},
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
                "artifact_count": len(result.artifact_paths),
                "certification_state": result.certification_state,
                "manifest_fingerprint": result.manifest_fingerprint,
                "output_dir": str(result.output_dir),
                "release_id": result.release_id,
                "runtime_verified": False,
                "status": "succeeded",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
