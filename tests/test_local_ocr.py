"""Local grid detection and OCR tests; no remote service is used."""

import asyncio
import io
import subprocess
import time
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.core.config import Settings
from app.main import app
from app.services.extraction import GridExtractionError, GridExtractionUnavailable
from app.services.local_ocr import LocalGridExtractor, _find_tesseract, _locate_grid, _run_ocr


@pytest.mark.parametrize(
    ("output", "expected"),
    [
        (b"level\tconf\ttext\n5\t95\tA\n", ("A", 0.95)),
        (b"level\tconf\ttext\n5\t95\tAB\n", None),
        (b"level\tconf\ttext\n5\t0\t\n", None),
        (b"level\tconf\ttext\n5\tnan\tA\n", None),
    ],
)
def test_local_engine_result_validation(
    monkeypatch: pytest.MonkeyPatch,
    output: bytes,
    expected: tuple[str, float] | None,
) -> None:
    def run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(args=[], returncode=0, stdout=output, stderr=b"")

    monkeypatch.setattr("app.services.local_ocr.subprocess.run", run)
    result = _run_ocr(
        "tesseract", np.full((20, 20), 255, dtype=np.uint8), 10, time.monotonic() + 10
    )
    assert result == expected


def test_local_engine_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    def run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        raise subprocess.TimeoutExpired("tesseract", 1)

    monkeypatch.setattr("app.services.local_ocr.subprocess.run", run)
    with pytest.raises(GridExtractionError, match="timed out"):
        _run_ocr("tesseract", np.full((20, 20), 255, dtype=np.uint8), 10, time.monotonic() + 10)


def test_blank_image_reports_no_grid() -> None:
    with pytest.raises(GridExtractionError, match="No clear bordered"):
        _locate_grid(np.full((200, 200), 255, dtype=np.uint8))


def test_configured_missing_tesseract_is_explicit() -> None:
    with pytest.raises(GridExtractionUnavailable, match="TESSERACT_CMD"):
        _find_tesseract("nonexistent-tesseract-test-command")


def test_missing_local_engine_maps_to_503(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TESSERACT_CMD", "nonexistent-tesseract-test-command")
    with io.BytesIO() as buffer:
        Image.new("RGB", (2, 2), "white").save(buffer, format="PNG")
        image = buffer.getvalue()
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/solve/image",
            files={"image": ("puzzle.png", image, "image/png")},
            data={"words": '["CAT"]'},
        )
    assert response.status_code == 503
    assert "TESSERACT_CMD" in response.json()["detail"]


@pytest.mark.parametrize(
    ("provider", "expected_status"),
    [("disabled", 503), ("bad-provider", 503)],
)
def test_provider_selection_errors(
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
    expected_status: int,
) -> None:
    monkeypatch.setenv("IMAGE_EXTRACTION_PROVIDER", provider)
    with io.BytesIO() as buffer:
        Image.new("RGB", (2, 2), "white").save(buffer, format="PNG")
        image = buffer.getvalue()
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/solve/image",
            files={"image": ("puzzle.png", image, "image/png")},
            data={"words": '["CAT"]'},
        )
    assert response.status_code == expected_status


def test_default_provider_does_not_select_remote_gateway(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ROUTE_LLM_API_KEY", "test-placeholder")
    monkeypatch.setenv("ROUTE_LLM_MODEL", "test-model")
    monkeypatch.setenv("TESSERACT_CMD", "nonexistent-tesseract-test-command")
    with io.BytesIO() as buffer:
        Image.new("RGB", (2, 2), "white").save(buffer, format="PNG")
        image = buffer.getvalue()
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/solve/image",
            files={"image": ("puzzle.png", image, "image/png")},
            data={"words": '["CAT"]'},
        )
    assert response.status_code == 503
    assert "TESSERACT_CMD" in response.json()["detail"]


@pytest.mark.local_ocr
def test_recognizes_all_worksheet_cells() -> None:
    try:
        executable = _find_tesseract("")
    except GridExtractionUnavailable:
        pytest.skip("Tesseract is not installed; run local_ocr tests on a configured host.")
    root = Path(__file__).resolve().parents[1]
    image = root / "Animal Image.jpeg"
    if not image.is_file():
        pytest.skip("Worksheet photo fixture is not available.")
    settings = Settings.from_environment()
    result = asyncio.run(
        LocalGridExtractor(settings).extract_grid(image.read_bytes(), "image/jpeg")
    )
    assert ["".join(row) for row in result.grid] == [
        "JFROGJYI",
        "DGOATYWM",
        "MUXCBVOL",
        "LSCIEJLI",
        "BEAKASFO",
        "QAEDRWDN",
        "SLYCRABD",
        "FISHZNJH",
    ]
    assert result.confidence >= settings.extraction_confidence_threshold
    assert executable
