"""Top-level experiments CLI help wrapper."""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    """Show the supported experiment entry points."""
    parser = argparse.ArgumentParser(
        prog="python -m experiments",
        description="AIma experiment command group",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Entry points:
  python -m experiments.run --config examples/smoke.yaml --output runs
  python -m experiments.aggregate --run runs/smoke
  python -m experiments.index --rebuild runs
        """,
    )
    parser.parse_args(argv)
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
