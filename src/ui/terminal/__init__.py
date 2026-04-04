"""Rich 终端实时观战.

用法::

    from ui.terminal import LiveMatchViewer, LiveMatchCallback

或命令行::

    python -m llm --dry-run --seed 0 --watch
"""

from .viewer import LiveMatchViewer, LiveMatchCallback, demo_dry_run

__all__ = ['LiveMatchViewer', 'LiveMatchCallback', 'demo_dry_run']
