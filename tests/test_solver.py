"""Unit tests for the provider-independent search algorithm."""

import pytest

from app.schemas.puzzle import SolveRequest
from app.services.solver import solve


@pytest.mark.parametrize(
    ("grid", "word", "start", "end", "direction"),
    [
        ([list("ABC")], "ABC", (0, 0), (0, 2), "east"),
        ([list("CBA")], "ABC", (0, 2), (0, 0), "west"),
        ([list("A"), list("B"), list("C")], "ABC", (0, 0), (2, 0), "south"),
        ([list("C"), list("B"), list("A")], "ABC", (2, 0), (0, 0), "north"),
        ([list("AXX"), list("XBX"), list("XXC")], "ABC", (0, 0), (2, 2), "southeast"),
        ([list("XXA"), list("XBX"), list("CXX")], "ABC", (0, 2), (2, 0), "southwest"),
        ([list("XXC"), list("XBX"), list("AXX")], "ABC", (2, 0), (0, 2), "northeast"),
        ([list("CXX"), list("XBX"), list("XXA")], "ABC", (2, 2), (0, 0), "northwest"),
    ],
)
def test_finds_word_in_each_direction(
    grid: list[list[str]],
    word: str,
    start: tuple[int, int],
    end: tuple[int, int],
    direction: str,
) -> None:
    result = solve(grid, [word])

    assert result.not_found == []
    match = result.results[0]
    assert (match.start.row, match.start.column) == start
    assert (match.end.row, match.end.column) == end
    assert match.direction == direction


def test_reports_missing_words_and_grid_size() -> None:
    result = solve([list("CAT")], ["CAT", "DOG"])

    assert result.grid_size.model_dump() == {"rows": 1, "columns": 3}
    assert [match.word for match in result.results] == ["CAT"]
    assert result.not_found == ["DOG"]


def test_normalizes_and_deduplicates_input() -> None:
    request = SolveRequest(grid=[[" c ", "a", "t"]], words=[" cat ", "CAT"])

    assert request.grid == [["C", "A", "T"]]
    assert request.words == ["CAT"]
    assert len(solve(request.grid, request.words).results) == 1


def test_one_letter_word_is_found() -> None:
    result = solve([list("ABC")], ["B"])

    assert result.results[0].word == "B"
    assert result.results[0].start == result.results[0].end
    assert result.results[0].direction == "north"


@pytest.mark.parametrize(
    ("grid", "words"),
    [
        ([["A"], ["B", "C"]], ["A"]),
        ([["AB"]], ["A"]),
        ([["A"], [""]], ["A"]),
        ([["A"]], [""]),
        ([["A"]], ["A1"]),
        ([["A"]], []),
        ([], ["A"]),
        ([[]], ["A"]),
        ([["A"]], ["\u00df"]),
        ([["\u00e9"]], ["A"]),
        ([["A"]], ["A"] * 201),
        ([["A"]], ["A" * 101]),
        ([["A"]] * 101, ["A"]),
        ([["A"] * 101], ["A"]),
    ],
)
def test_rejects_malformed_puzzle_data(
    grid: list[list[str]],
    words: list[str],
) -> None:
    with pytest.raises(ValueError):
        SolveRequest(grid=grid, words=words)


def test_solves_the_worksheet_grid() -> None:
    grid = [
        list("JFROGJYI"),
        list("DGOATYWM"),
        list("MUXCBVOL"),
        list("LSCIEJLI"),
        list("BEAKASFO"),
        list("QAEDRWDN"),
        list("SLYCRABD"),
        list("FISHZNJH"),
    ]
    words = ["BEAR", "CRAB", "DUCK", "FISH", "FROG", "GOAT", "LION", "SEAL", "SWAN", "WOLF"]

    result = solve(grid, words)

    assert result.not_found == []
    assert {match.word for match in result.results} == set(words)
    expected = {
        "BEAR": ((2, 4), (5, 4), "south"),
        "CRAB": ((6, 3), (6, 6), "east"),
        "DUCK": ((1, 0), (4, 3), "southeast"),
        "FISH": ((7, 0), (7, 3), "east"),
        "FROG": ((0, 1), (0, 4), "east"),
        "GOAT": ((1, 1), (1, 4), "east"),
        "LION": ((2, 7), (5, 7), "south"),
        "SEAL": ((3, 1), (6, 1), "south"),
        "SWAN": ((4, 5), (7, 5), "south"),
        "WOLF": ((1, 6), (4, 6), "south"),
    }
    for match in result.results:
        assert (
            (match.start.row, match.start.column),
            (match.end.row, match.end.column),
            match.direction,
        ) == expected[match.word]


def test_repeated_occurrences_have_stable_selection() -> None:
    result = solve([list("CATCAT")], ["CAT"])
    assert len(result.results) == 1
    assert result.results[0].start.column == 0
