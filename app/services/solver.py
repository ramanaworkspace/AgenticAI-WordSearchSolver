"""Provider-independent word-search solver."""

from app.schemas.puzzle import Coordinate, Direction, Grid, GridSize, SolveResponse, WordMatch

DIRECTIONS: tuple[tuple[Direction, int, int], ...] = (
    ("north", -1, 0),
    ("northeast", -1, 1),
    ("east", 0, 1),
    ("southeast", 1, 1),
    ("south", 1, 0),
    ("southwest", 1, -1),
    ("west", 0, -1),
    ("northwest", -1, -1),
)


def _find_word(grid: Grid, word: str) -> WordMatch | None:
    rows = len(grid)
    columns = len(grid[0])
    for start_row in range(rows):
        for start_column in range(columns):
            if grid[start_row][start_column] != word[0]:
                continue
            for direction, row_step, column_step in DIRECTIONS:
                end_row = start_row + (len(word) - 1) * row_step
                end_column = start_column + (len(word) - 1) * column_step
                if not (0 <= end_row < rows and 0 <= end_column < columns):
                    continue
                if all(
                    grid[start_row + index * row_step][start_column + index * column_step] == letter
                    for index, letter in enumerate(word)
                ):
                    return WordMatch(
                        word=word,
                        start=Coordinate(row=start_row, column=start_column),
                        end=Coordinate(row=end_row, column=end_column),
                        direction=direction,
                    )
    return None


def solve(grid: Grid, words: list[str]) -> SolveResponse:
    """Search a non-empty, validated grid for distinct normalized words.

    Search order is row-major start position, then north, northeast, east,
    southeast, south, southwest, west, and northwest. Searching every
    direction naturally includes forward and backward spellings.
    """
    rows = len(grid)
    columns = len(grid[0])
    matches: list[WordMatch] = []
    not_found: list[str] = []
    for word in words:
        match = _find_word(grid, word)
        if match is None:
            not_found.append(word)
        else:
            matches.append(match)
    return SolveResponse(
        grid_size=GridSize(rows=rows, columns=columns),
        results=matches,
        not_found=not_found,
    )
