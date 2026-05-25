"""CLI entry point for experiments module (backward-compatible wrapper).

Usage:
    python -m experiments --config examples/smoke.yaml
    python -m experiments --rebuild-index --output-root runs
    python -m experiments --aggregate --run runs/smoke
"""

from __future__ import annotations

import sys

from experiments.cli import main

if __name__ == "__main__":
    sys.exit(main())