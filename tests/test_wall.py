"""Tests for wall split."""

from kernel import (
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
    assert len(s.dead.indicators) == INDICATOR_COUNT
    assert RINSHAN_COUNT + INDICATOR_COUNT == DEAD_WALL_SIZE
    assert LIVE_WALL_SIZE + DEAD_WALL_SIZE == WALL_SIZE


def test_split_wall_concat_roundtrip() -> None:
    wall = tuple(shuffle_deck(build_deck(), seed=7))
    s = split_wall(wall)
    back = s.live + s.dead.rinshan + s.dead.indicators
    assert back == wall


def test_split_wall_rejects_bad_length() -> None:
    try:
        split_wall(build_deck()[:135])
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")
