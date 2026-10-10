"""Validated request and response models for puzzles."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Grid = list[list[str]]
Direction = Annotated[
    Literal[
        "north",
        "northeast",
        "east",
        "southeast",
        "south",
        "southwest",
        "west",
        "northwest",
    ],
    Field(
        description=(
            "Direction of the match: north, northeast, east, southeast, "
            "south, southwest, west, or northwest."
        )
    ),
]


def normalize_words(value: object) -> list[str]:
    """Normalize a non-empty list of alphabetic words and remove duplicates."""
    if not isinstance(value, list) or not value:
        raise ValueError("At least one target word is required.")
    if len(value) > 200:
        raise ValueError("At most 200 target words may be requested.")

    normalized: list[str] = []
    seen: set[str] = set()
    for word in value:
        if not isinstance(word, str):
            raise ValueError("Every target word must be a string.")
        normalized_word = word.strip().upper()
        stripped_word = word.strip()
        if not stripped_word or not stripped_word.isascii() or not stripped_word.isalpha():
            raise ValueError("Target words must contain A-Z letters only.")
        if len(normalized_word) > 100:
            raise ValueError("Target words may contain at most 100 letters.")
        if normalized_word not in seen:
            normalized.append(normalized_word)
            seen.add(normalized_word)
    return normalized


class SolveRequest(BaseModel):
    """A rectangular grid and the words to search for."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid", strict=True)

    grid: Grid = Field(
        min_length=1,
        max_length=100,
        description="Rectangular array of rows containing one alphabetic character per cell.",
    )
    words: list[str] = Field(
        min_length=1,
        max_length=200,
        description="Target words; matching is case-insensitive and searches all eight directions.",
    )

    @field_validator("grid")
    @classmethod
    def validate_grid(cls, grid: Grid) -> Grid:
        if not grid or not grid[0]:
            raise ValueError("The grid must contain at least one row and one column.")
        width = len(grid[0])
        if width > 100:
            raise ValueError("The grid may contain at most 100 columns.")
        normalized_grid: Grid = []
        for row in grid:
            if len(row) != width:
                raise ValueError("Every grid row must have the same number of columns.")
            normalized_row: list[str] = []
            for cell in row:
                if not isinstance(cell, str):
                    raise ValueError("Every grid cell must be a single alphabetic character.")
                letter = cell.strip().upper()
                if len(letter) != 1 or not cell.isascii() or not letter.isalpha():
                    raise ValueError("Every grid cell must be a single A-Z letter.")
                normalized_row.append(letter)
            normalized_grid.append(normalized_row)
        return normalized_grid

    @field_validator("words", mode="before")
    @classmethod
    def validate_words(cls, words: object) -> list[str]:
        return normalize_words(words)


class Coordinate(BaseModel):
    """Zero-based row and column within the submitted grid."""

    row: int = Field(ge=0, description="Zero-based row index.")
    column: int = Field(ge=0, description="Zero-based column index.")


class WordMatch(BaseModel):
    """Location of one matched word."""

    word: str
    found: bool = True
    start: Coordinate
    end: Coordinate
    direction: Direction


class GridSize(BaseModel):
    """Dimensions of the puzzle grid."""

    rows: int = Field(ge=1)
    columns: int = Field(ge=1)


class SolveResponse(BaseModel):
    """Matches and target words not present in the grid."""

    grid_size: GridSize
    results: list[WordMatch]
    not_found: list[str]


class ExtractedGrid(BaseModel):
    """Grid and recognition score returned by an extraction provider."""

    model_config = ConfigDict(extra="forbid", strict=True)

    grid: Grid
    confidence: float = Field(ge=0, le=1)

    @field_validator("grid")
    @classmethod
    def validate_grid(cls, grid: Grid) -> Grid:
        return SolveRequest(grid=grid, words=["A"]).grid


class ImageSolveResponse(BaseModel):
    """Recognized grid and its deterministic solution."""

    grid: Grid
    confidence: float = Field(
        ge=0,
        le=1,
        description="Provider recognition score, not a calibrated probability or guarantee.",
    )
    solution: SolveResponse


class HealthResponse(BaseModel):
    """Non-sensitive service health result."""

    status: str
