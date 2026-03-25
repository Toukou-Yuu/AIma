"""演示脚本：用 PIL 渲染麻将桌面并保存 PNG（不依赖终端内联图）。"""

import sys
from pathlib import Path

# 确保 src 在 Python 路径中
src_dir = Path(__file__).parent.parent
sys.path.insert(0, str(src_dir))

from kernel import (  # noqa: E402
    Action,
    ActionKind,
    apply,
    build_deck,
    initial_game_state,
    shuffle_deck,
)
from ui.render import TableRenderer  # noqa: E402


def _wall136(*, seed: int = 0) -> tuple:
    """Generate a shuffled wall of 136 tiles."""
    return tuple(shuffle_deck(build_deck(), seed=seed))


def main() -> None:
    g0 = initial_game_state()
    wall = _wall136(seed=42)

    g1 = apply(g0, Action(ActionKind.BEGIN_ROUND, wall=wall))
    state = g1.new_state
    board = state.board

    from ui.demo_fixtures import river_entries_from_sample, sample_melds

    all_river_entries = list(river_entries_from_sample())
    melds_raw = sample_melds()

    object.__setattr__(board, "river", tuple(all_river_entries))
    object.__setattr__(board, "melds", tuple(melds_raw[s] for s in range(4)))

    print(f"牌河总张数：{len(board.river)}")

    for s in range(4):
        print(f"  家 {s}: 副露 {len(board.melds[s])} 组")

    project_root = Path(__file__).parent.parent.parent
    renderer = TableRenderer(project_root / "assets" / "mahjong_tiles")
    image = renderer.render(state)

    output_path = Path(__file__).parent / "output.png"
    image.save(output_path, "PNG")
    print(f"已保存：{output_path}（{image.width}×{image.height}）")


if __name__ == "__main__":
    main()
