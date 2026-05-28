"""CLI entry point for running experiments.

Usage:
    python -m experiments.run --config examples/smoke.yaml
    python -m experiments.run --config examples/smoke.yaml --output runs
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    """Main entry point for experiments.run CLI.

    Returns:
        Exit code: 0 for success, non-zero for failure.
    """
    parser = argparse.ArgumentParser(
        description="Run AIma experiments",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python -m experiments.run --config examples/smoke.yaml
    python -m experiments.run --config examples/smoke.yaml --output runs
        """,
    )
    parser.add_argument(
        "--config",
        "-c",
        type=Path,
        required=True,
        help="Path to YAML configuration file",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Output root directory (default: from config or 'runs')",
    )

    args = parser.parse_args()

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
    runner = ExperimentRunner(spec, config_path=args.config)
    result = runner.run()

    # Print summary
    print(f"Experiment complete: {result['succeeded']} succeeded, {result['failed']} failed")

    return 0 if result["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())