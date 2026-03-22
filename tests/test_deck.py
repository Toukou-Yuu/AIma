"""Tests for tile deck construction and shuffling."""

from collections import Counter

from kernel import Suit, Tile, build_deck, shuffle_deck


def test_build_deck_length() -> None:
    assert len(build_deck()) == 136
    assert len(build_deck(red_fives=False)) == 136


def test_build_deck_red_fives_counts() -> None:
    deck = build_deck(red_fives=True)
    codes = [t.to_code() for t in deck]
    c = Counter(codes)
    assert c["5mr"] == c["5pr"] == c["5sr"] == 1
    for suit in "mps":
        assert c[f"5{suit}"] == 3
    for rank in range(1, 10):
        if rank == 5:
            continue
        for suit in "mps":
            assert c[f"{rank}{suit}"] == 4
    for z in range(1, 8):
        assert c[f"{z}z"] == 4


def test_build_deck_no_red_fives() -> None:
    deck = build_deck(red_fives=False)
    assert not any(t.is_red for t in deck)
    codes = [t.to_code() for t in deck]
    assert "5mr" not in codes
    c = Counter(codes)
    for suit in "mps":
        assert c[f"5{suit}"] == 4


def test_shuffle_deterministic() -> None:
    deck = build_deck()
    a = shuffle_deck(deck, seed=42)
    b = shuffle_deck(deck, seed=42)
    assert a == b
    assert a != list(deck)


def test_tile_immutable_and_hashable() -> None:
    t = Tile(Suit.MAN, 5, True)
    assert hash(t) == hash(t)
    assert len({t, t}) == 1


def test_tile_invalid_red() -> None:
    try:
        Tile(Suit.MAN, 4, True)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")


def test_tile_honor_rank_bounds() -> None:
    try:
        Tile(Suit.HONOR, 8, False)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")
