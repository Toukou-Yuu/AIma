"""CLI entry point for metrics aggregation.

Usage:
    python -m experiments.aggregate --run runs/smoke
    python -m experiments.aggregate --run runs/smoke --output runs/smoke/aggregate
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from metrics.loader import load_run_data
from metrics.pipeline import create_default_pipeline
from metrics.report import ReportGenerator


def main() -> int:
    """Main entry point for aggregate CLI.

    Returns:
        Exit code: 0 for success, non-zero for failure.
    """
    parser = argparse.ArgumentParser(
        description="Aggregate metrics from experiment runs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python -m experiments.aggregate --run runs/smoke
    python -m experiments.aggregate --run runs/smoke --output runs/smoke/aggregate
        """,
    )
    parser.add_argument(
        "--run",
        "-r",
        type=Path,
        required=True,
        help="Run directory path (e.g., runs/smoke)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("aggregate"),
        help="Output directory for reports (default: aggregate)",
    )

    args = parser.parse_args()

    run_dir = args.run
    output_dir = args.output

    # Validate run directory
    if not run_dir.exists():
        print(f"Error: Run directory not found: {run_dir}", file=sys.stderr)
        return 1

    if not run_dir.is_dir():
        print(f"Error: Not a directory: {run_dir}", file=sys.stderr)
        return 1

    # Load data
    print(f"Loading data from {run_dir}...")
    run_data = load_run_data(run_dir)

    if not run_data:
        print(f"Warning: No job data found in {run_dir}", file=sys.stderr)
        # Still create empty reports
        run_data = []

    print(f"Loaded {len(run_data)} jobs")

    # Run pipeline
    print("Running metrics pipeline...")
    pipeline = create_default_pipeline()
    results = pipeline.run(run_data)

    # Print summary
    match_count = len(results.get("match", []))
    decision_count = len(results.get("decision", []))
    player_count = len(results.get("player", []))
    print(f"Generated metrics: {match_count} matches, {decision_count} decisions, {player_count} players")

    # Generate reports
    print(f"Writing reports to {output_dir}...")
    generator = ReportGenerator(results)
    generator.write_all(output_dir)

    print(f"Reports written to {output_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())