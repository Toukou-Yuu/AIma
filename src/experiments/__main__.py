"""CLI entry point for experiments module.

Usage:
    python -m experiments --config examples/smoke.yaml
    python -m experiments --rebuild-index --output-root runs
    python -m experiments --aggregate --run runs/smoke
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    """Main entry point for experiments CLI.

    Returns:
        Exit code: 0 for success, non-zero for failure.
    """
    parser = argparse.ArgumentParser(
        description="Run AIma experiments",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python -m experiments --config examples/smoke.yaml
    python -m experiments --config examples/smoke.yaml --output-root runs
    python -m experiments --rebuild-index --output-root runs
    python -m experiments --aggregate --run runs/smoke
        """,
    )
    parser.add_argument(
        "--config",
        "-c",
        type=Path,
        help="Path to YAML configuration file",
    )
    parser.add_argument(
        "--rebuild-index",
        action="store_true",
        help="Rebuild SQLite index from existing run directories",
    )
    parser.add_argument(
        "--aggregate",
        action="store_true",
        help="Aggregate metrics from a run directory",
    )
    parser.add_argument(
        "--run",
        "-r",
        type=Path,
        help="Run directory path (for --aggregate)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Output root directory (default: from config or 'runs')\n"
        "For --aggregate: output directory for reports (default: aggregate)",
    )

    args = parser.parse_args()

    # Handle aggregate mode
    if args.aggregate:
        if args.run is None:
            print("Error: --run is required for --aggregate", file=sys.stderr)
            return 1

        from experiments.aggregate import main as aggregate_main

        # Reconstruct sys.argv for aggregate CLI
        agg_args = ["--run", str(args.run)]
        if args.output:
            agg_args.extend(["--output", str(args.output)])

        original_argv = sys.argv
        sys.argv = ["aggregate"] + agg_args
        try:
            return aggregate_main()
        finally:
            sys.argv = original_argv

    # Handle rebuild-index mode
    if args.rebuild_index:
        if args.output is None:
            print("Error: --output is required for --rebuild-index", file=sys.stderr)
            return 1

        from experiments.index import rebuild_index

        rebuild_index(args.output)
        print(f"Index rebuilt for {args.output}")
        return 0

    # Handle experiment run mode
    if args.config is None:
        print("Error: --config is required (unless --rebuild-index or --aggregate is specified)", file=sys.stderr)
        parser.print_help(sys.stderr)
        return 1

    if not args.config.exists():
        print(f"Error: Configuration file not found: {args.config}", file=sys.stderr)
        return 1

    # Import here to allow --help to work without dependencies
    from experiments import ExperimentSpec
    from experiments.runner import ExperimentRunner

    # Load configuration
    spec = ExperimentSpec.from_yaml(args.config)

    # Override output root if specified
    if args.output is not None:
        spec.artifacts.output_root = str(args.output)

    # Run experiment
    runner = ExperimentRunner(spec)
    result = runner.run()

    # Print summary
    print(f"Experiment complete: {result['succeeded']} succeeded, {result['failed']} failed")

    return 0 if result["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())