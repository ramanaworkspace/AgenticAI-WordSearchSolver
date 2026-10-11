"""FastAPI routes for solving word-search puzzles."""

import json
import warnings
from io import BytesIO
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from PIL import Image, UnidentifiedImageError
from PIL.Image import DecompressionBombError, DecompressionBombWarning
from pydantic import WithJsonSchema
from starlette.datastructures import UploadFile as StarletteUploadFile

from app.core.config import Settings, get_settings
from app.schemas.puzzle import (
    ExtractedGrid,
    HealthResponse,
    ImageSolveResponse,
    SolveRequest,
    SolveResponse,
    normalize_words,
)
from app.services.extraction import (
    GridExtractionError,
    GridExtractionUnavailable,
    GridExtractor,
)
from app.services.local_ocr import LocalGridExtractor
from app.services.route_llm import RouteLLMGridExtractor
from app.services.solver import solve

router = APIRouter()
ALLOWED_IMAGE_TYPES = {
    "image/jpeg": "JPEG",
    "image/png": "PNG",
    "image/webp": "WEBP",
    "image/gif": "GIF",
}


def get_image_settings() -> Settings:
    try:
        return get_settings()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Image extraction settings are invalid; contact the service administrator.",
        ) from exc


def get_grid_extractor(
    settings: Annotated[Settings, Depends(get_image_settings)],
) -> GridExtractor | None:
    """Select an explicit local or remote image extraction provider."""
    if settings.image_extraction_provider == "local":
        return LocalGridExtractor(settings)
    if settings.image_extraction_provider == "disabled":
        return None
    if settings.image_extraction_provider != "route_llm":
        raise HTTPException(status_code=503, detail="IMAGE_EXTRACTION_PROVIDER is invalid.")
    if not settings.route_llm_api_key or not settings.route_llm_model:
        return None
    return RouteLLMGridExtractor(settings)


@router.get("/health", response_model=HealthResponse, tags=["health"])
async def health() -> HealthResponse:
    """Report process health without disclosing configuration or secrets."""
    return HealthResponse(status="ok")


@router.post("/api/v1/solve", response_model=SolveResponse, tags=["puzzles"])
async def solve_puzzle(request: SolveRequest) -> SolveResponse:
    """Find each requested word in a rectangular letter grid."""
    return await run_in_threadpool(solve, request.grid, request.words)


def _validate_image(image_bytes: bytes, expected_format: str, settings: Settings) -> None:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", DecompressionBombWarning)
            with Image.open(BytesIO(image_bytes)) as image:
                if image.format != expected_format:
                    raise HTTPException(
                        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                        detail="The file content does not match its declared image type.",
                    )
                width, height = image.size
                if width > settings.image_max_width or height > settings.image_max_height:
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail=(
                            "Image dimensions exceed the configured limit of "
                            f"{settings.image_max_width}x{settings.image_max_height} pixels."
                        ),
                    )
                if getattr(image, "n_frames", 1) != 1:
                    raise HTTPException(
                        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                        detail="Animated images are not supported; upload a single frame.",
                    )
                image.verify()
            with Image.open(BytesIO(image_bytes)) as image:
                image.load()
    except (DecompressionBombError, DecompressionBombWarning) as exc:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="Image decoded size exceeds the safe processing limit.",
        ) from exc
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is not a valid, supported image.",
        ) from exc


async def _read_and_validate_image(
    upload: UploadFile,
    settings: Settings,
) -> tuple[bytes, str]:
    media_type = (upload.content_type or "").lower()
    expected_format = ALLOWED_IMAGE_TYPES.get(media_type)
    if expected_format is None:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Upload a JPEG, PNG, WebP, or GIF image.",
        )

    image_bytes = await upload.read(settings.image_max_bytes + 1)
    if len(image_bytes) > settings.image_max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"Image exceeds the {settings.image_max_bytes}-byte upload limit.",
        )
    if not image_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded image is empty.",
        )

    await run_in_threadpool(_validate_image, image_bytes, expected_format, settings)
    return image_bytes, media_type


@router.post(
    "/api/v1/solve/image",
    response_model=ImageSolveResponse,
    tags=["puzzles"],
    openapi_extra={
        "requestBody": {
            "content": {
                "multipart/form-data": {
                    "encoding": {"words": {"contentType": "application/json"}},
                },
            },
        },
    },
)
async def solve_image(
    image: Annotated[UploadFile, File(description="Puzzle image file.")],
    words: Annotated[
        str | UploadFile,
        WithJsonSchema({"type": "string"}),
        Form(description='JSON array of target words, for example ["BEAR", "FROG"].'),
    ],
    settings: Annotated[Settings, Depends(get_image_settings)],
    extractor: Annotated[GridExtractor | None, Depends(get_grid_extractor)],
) -> ImageSolveResponse:
    """Extract a grid from an image, then solve it using the deterministic solver."""
    raw_words: str | bytes
    if isinstance(words, StarletteUploadFile):
        if words.content_type != "application/json":
            raise HTTPException(status_code=415, detail="The words part must use application/json.")
        raw_words = await words.read(65537)
        if len(raw_words) > 65536:
            raise HTTPException(status_code=413, detail="The words part exceeds 64 KiB.")
    else:
        raw_words = words
    try:
        target_words = normalize_words(json.loads(raw_words))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail='words must be a JSON array of strings, for example ["BEAR", "FROG"].',
        ) from exc
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    image_bytes, media_type = await _read_and_validate_image(image, settings)
    if extractor is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Image extraction is not configured or is disabled.",
        )
    try:
        extraction = ExtractedGrid.model_validate(
            await extractor.extract_grid(image_bytes, media_type)
        )
        if extraction.confidence < settings.extraction_confidence_threshold:
            raise GridExtractionError(
                "Grid recognition confidence is below the configured threshold."
            )
        puzzle = SolveRequest(grid=extraction.grid, words=target_words)
    except GridExtractionUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except GridExtractionError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The image extractor returned an invalid puzzle grid.",
        ) from exc

    return ImageSolveResponse(
        grid=puzzle.grid,
        confidence=extraction.confidence,
        solution=await run_in_threadpool(solve, puzzle.grid, puzzle.words),
    )
