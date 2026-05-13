"""Tests for wall split."""

from kernel import (
    DEAD_INDICATOR_STOCK,
    DEAD_WALL_SIZE,
    INDICATOR_COUNT,
    LIVE_WALL_SIZE,
    RINSHAN_COUNT,
    WALL_SIZE,
    Suit,
    Tile,
    build_deck,
    shuffle_deck,
    split_wall,
)


def test_split_wall_sizes() -> None:
    wall = tuple(build_deck())
    s = split_wall(wall)
    assert len(s.live) == LIVE_WALL_SIZE
    assert len(s.dead.rinshan) == RINSHAN_COUNT
    assert len(s.dead.ura_bases) == INDICATOR_COUNT
    assert len(s.dead.indicators) == INDICATOR_COUNT
    assert RINSHAN_COUNT + DEAD_INDICATOR_STOCK == DEAD_WALL_SIZE
    assert LIVE_WALL_SIZE + DEAD_WALL_SIZE == WALL_SIZE


def test_split_wall_concat_roundtrip() -> None:
    wall = tuple(shuffle_deck(build_deck(), seed=7))
    s = split_wall(wall)
    dead_pairs = tuple(
        t for i in range(INDICATOR_COUNT) for t in (s.dead.ura_bases[i], s.dead.indicators[i])
    )
    back = s.live + s.dead.rinshan + dead_pairs
    assert back == wall


def test_split_wall_rejects_bad_length() -> None:
    try:
        split_wall(build_deck()[:135])
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")


def test_dead_wall_rejects_wrong_rinshan_length() -> None:
    from kernel.wall.split import DeadWall
    try:
        DeadWall(
            rinshan=(Tile(Suit.MAN, 1),) * 5,  # 应该是 4
            ura_bases=(Tile(Suit.MAN, 2),) * 4,
            indicators=(Tile(Suit.MAN, 3),) * 4,
        )
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")


def test_dead_wall_rejects_wrong_ura_length() -> None:
    from kernel.wall.split import DeadWall
    try:
        DeadWall(
            rinshan=(Tile(Suit.MAN, 1),) * 4,
            ura_bases=(Tile(Suit.MAN, 2),) * 3,  # 应该是 4
            indicators=(Tile(Suit.MAN, 3),) * 4,
        )
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")


def test_dead_wall_rejects_wrong_indicator_length() -> None:
    from kernel.wall.split import DeadWall
    try:
        DeadWall(
            rinshan=(Tile(Suit.MAN, 1),) * 4,
            ura_bases=(Tile(Suit.MAN, 2),) * 4,
            indicators=(Tile(Suit.MAN, 3),) * 5,  # 应该是 4
        )
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")


def test_wall_split_rejects_wrong_live_length() -> None:
    from kernel.wall.split import WallSplit, DeadWall
    try:
        WallSplit(
            live=(Tile(Suit.MAN, 1),) * 71,  # 应该是 LIVE_WALL_SIZE
            dead=DeadWall(
                rinshan=(Tile(Suit.MAN, 1),) * 4,
                ura_bases=(Tile(Suit.MAN, 2),) * 4,
                indicators=(Tile(Suit.MAN, 3),) * 4,
            ),
        )
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")
