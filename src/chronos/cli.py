"""Command-line interface for CHRONOS analysis workflows."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from .structural_engine import StructuralEngineError, analyze_structural_change
from .semantic_engine import analyze_semantic_code_change
from .pr_engine import analyze_pull_request


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
    semantic = commands.add_parser(
        "analyze-semantic-change",
        help="Analyze one SQL or safely resolved dbt model semantic change.",
    )
    semantic.add_argument("--proposal", required=True, help="Semantic proposal JSON path.")
    semantic.add_argument("--snapshot", required=True, help="Snapshot JSON path.")
    semantic.add_argument("--before", required=True, help="Repository-relative BEFORE SQL path.")
    semantic.add_argument("--after", required=True, help="Repository-relative AFTER SQL path.")
    semantic.add_argument("--output", required=True, help="Isolated output directory.")
    semantic.add_argument("--dialect", help="SQL dialect; must match the proposal.")
    semantic.add_argument("--dbt-manifest", help="Optional repository-relative dbt manifest.")
    semantic.add_argument(
        "--fixture",
        action="store_true",
        help="Declare a deterministic fixture run; analysis is deterministic in all modes.",
    )
    semantic.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace only a prior semantic analysis directory.",
    )
    pull_request = commands.add_parser(
        "analyze-pr",
        help="Analyze one bounded multi-file repository transition.",
    )
    pull_request.add_argument("--proposal", required=True, help="Strict PR proposal JSON path.")
    pull_request.add_argument("--snapshot", required=True, help="Snapshot JSON path.")
    intake = pull_request.add_mutually_exclusive_group(required=True)
    intake.add_argument("--repo", help="Local Git repository root.")
    intake.add_argument("--bundle", help="Exported PR bundle root.")
    pull_request.add_argument("--base", help="Base revision; must match the proposal.")
    pull_request.add_argument("--head", help="Head revision; must match the proposal.")
    pull_request.add_argument("--output", required=True, help="Isolated output directory.")
    pull_request.add_argument(
        "--overwrite", action="store_true",
        help="Replace only a recognized prior PR analysis package.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "analyze-pr":
            result = analyze_pull_request(
                snapshot=args.snapshot,
                proposal=args.proposal,
                output_dir=args.output,
                repository=args.repo,
                bundle=args.bundle,
                base_revision=args.base,
                head_revision=args.head,
                overwrite=args.overwrite,
            )
        elif args.command == "analyze-semantic-change":
            result = analyze_semantic_code_change(
                snapshot=args.snapshot,
                proposal=args.proposal,
                before_sql=args.before,
                after_sql=args.after,
                output_dir=args.output,
                dbt_manifest=args.dbt_manifest,
                sql_dialect=args.dialect,
                overwrite=args.overwrite,
            )
        else:
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
                **(
                    {
                        "delta_count": len(result.detected_deltas),
                        "semantic_compatibility": result.semantic_compatibility.value,
                    }
                    if args.command == "analyze-semantic-change"
                    else {}
                ),
                **(
                    {
                        "changed_file_count": result.changed_file_summary["changed_file_count"],
                        "coherence_state": result.coherence_state.value,
                        "conflict_count": len(result.conflicts),
                        "root_cause_count": len(result.root_causes),
                    }
                    if args.command == "analyze-pr"
                    else {}
                ),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
