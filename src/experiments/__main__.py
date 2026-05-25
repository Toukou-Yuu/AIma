"""CLI entry point for experiments module.

Usage:
    python -m experiments --config examples/smoke.yaml
    python -m experiments --rebuild-index --output-root runs
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
        "--output-root",
        "-o",
        type=Path,
        default=None,
        help="Output root directory (default: from config or 'runs')",
    )

    args = parser.parse_args()

    # Handle rebuild-index mode
    if args.rebuild_index:
        if args.output_root is None:
            print("Error: --output-root is required for --rebuild-index", file=sys.stderr)
            return 1

        from experiments.index import rebuild_index

        rebuild_index(args.output_root)
        print(f"Index rebuilt for {args.output_root}")
        return 0

    # Handle experiment run mode
    if args.config is None:
        print("Error: --config is required (unless --rebuild-index is specified)", file=sys.stderr)
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
    if args.output_root is not None:
        spec.artifacts.output_root = str(args.output_root)

    # Run experiment
    runner = ExperimentRunner(spec)
    result = runner.run()

    # Print summary
    print(f"Experiment complete: {result['succeeded']} succeeded, {result['failed']} failed")

    return 0 if result["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())