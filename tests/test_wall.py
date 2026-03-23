"""Tests for wall split."""

from kernel import (
    DEAD_INDICATOR_STOCK,
    DEAD_WALL_SIZE,
    INDICATOR_COUNT,
    LIVE_WALL_SIZE,
    RINSHAN_COUNT,
    WALL_SIZE,
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
        t
        for i in range(INDICATOR_COUNT)
        for t in (s.dead.ura_bases[i], s.dead.indicators[i])
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
