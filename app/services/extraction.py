"""Interfaces and errors for optional image-to-grid extraction."""

from typing import Protocol

from app.schemas.puzzle import ExtractedGrid


class GridExtractionError(Exception):
    """The configured provider failed or returned an unusable grid."""


class GridExtractionUnavailable(Exception):
    """Image extraction is not configured for this deployment."""


class GridExtractor(Protocol):
    """Provider-neutral asynchronous image-to-grid contract."""

    async def extract_grid(
        self,
        image_bytes: bytes,
        media_type: str,
    ) -> ExtractedGrid:
        """Extract a letter grid and its confidence from an image."""
