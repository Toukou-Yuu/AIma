"""交互式会话运行器。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from llm.cli import main as llm_main


@dataclass(frozen=True, slots=True)
class SessionRunResult:
    """交互式会话运行结果。"""

    returncode: int


def run_llm_session(
    args: Sequence[str],
) -> SessionRunResult:
    """在当前进程内运行 ``python -m llm`` 对应逻辑。"""
    def _invoke(argv: list[str]) -> int:
        try:
            return llm_main(argv)
        except SystemExit as exc:
            code = exc.code
            return int(code) if isinstance(code, int) else 1

    argv = list(args)
    return SessionRunResult(returncode=_invoke(argv))
