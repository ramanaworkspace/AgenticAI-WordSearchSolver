"""Local recognition of a bordered, evenly spaced word-search grid."""

import csv
import io
import shutil
import subprocess
import time
from pathlib import Path

import cv2
import numpy as np
from fastapi.concurrency import run_in_threadpool
from numpy.typing import NDArray
from PIL import Image, ImageOps

from app.core.config import Settings
from app.schemas.puzzle import ExtractedGrid
from app.services.extraction import GridExtractionError, GridExtractionUnavailable

GrayImage = NDArray[np.uint8]
Box = tuple[int, int, int, int]


def _find_tesseract(configured_path: str) -> str:
    if configured_path:
        resolved = shutil.which(configured_path)
        if resolved:
            return resolved
        raise GridExtractionUnavailable("TESSERACT_CMD does not identify an executable.")
    resolved = shutil.which("tesseract")
    if resolved:
        return resolved
    for location in (
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ):
        if Path(location).is_file():
            return location
    raise GridExtractionUnavailable(
        "Local OCR requires Tesseract with English language data. "
        "Install it and set TESSERACT_CMD or add it to PATH."
    )


def _rectify(gray: GrayImage, corners: NDArray[np.float32]) -> GrayImage:
    points = corners.reshape(4, 2)
    sums = points.sum(axis=1)
    differences = np.diff(points, axis=1).reshape(4)
    ordered = np.array(
        [
            points[int(sums.argmin())],
            points[int(differences.argmin())],
            points[int(sums.argmax())],
            points[int(differences.argmax())],
        ],
        dtype=np.float32,
    )
    top_left, top_right, bottom_right, bottom_left = ordered
    width = max(np.linalg.norm(top_right - top_left), np.linalg.norm(bottom_right - bottom_left))
    height = max(np.linalg.norm(bottom_left - top_left), np.linalg.norm(bottom_right - top_right))
    scale = min(3.0, 1600 / max(width, height))
    output_width, output_height = int(width * scale), int(height * scale)
    destination = np.array(
        [
            [0, 0],
            [output_width - 1, 0],
            [output_width - 1, output_height - 1],
            [0, output_height - 1],
        ],
        dtype=np.float32,
    )
    transform = cv2.getPerspectiveTransform(ordered, destination)
    return np.asarray(
        cv2.warpPerspective(gray, transform, (output_width, output_height)),
        dtype=np.uint8,
    )


def _letter_rows(gray: GrayImage) -> tuple[GrayImage, list[list[Box]]] | None:
    height, width = gray.shape
    margin = max(4, int(min(width, height) * 0.02))
    inner = gray[margin : height - margin, margin : width - margin]
    _, binary = cv2.threshold(inner, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes: list[Box] = []
    for contour in contours:
        x, y, box_width, box_height = cv2.boundingRect(contour)
        if (
            height * 0.015 < box_height < height * 0.3
            and 2 < box_width < width * 0.3
            and cv2.contourArea(contour) > 8
        ):
            boxes.append((x, y, box_width, box_height))
    if len(boxes) < 4:
        return None
    median_height = float(np.median([box[3] for box in boxes]))
    boxes = [box for box in boxes if 0.65 * median_height <= box[3] <= 1.4 * median_height]
    boxes.sort(key=lambda box: box[1] + box[3] / 2)
    rows: list[list[Box]] = []
    centers: list[float] = []
    for box in boxes:
        center_y = box[1] + box[3] / 2
        if not rows or abs(center_y - centers[-1]) > median_height * 0.6:
            rows.append([box])
            centers.append(center_y)
        else:
            rows[-1].append(box)
    if not 2 <= len(rows) <= 100 or not 2 <= len(rows[0]) <= 100:
        return None
    if any(len(row) != len(rows[0]) for row in rows):
        return None
    for row in rows:
        row.sort(key=lambda box: box[0] + box[2] / 2)
    column_centers = np.array(
        [[box[0] + box[2] / 2 for box in row] for row in rows],
    )
    spacings = np.diff(column_centers, axis=1)
    spacing = float(np.median(spacings))
    if spacing <= 0 or np.any(abs(spacings - spacing) > spacing * 0.3):
        return None
    if np.any(np.ptp(column_centers, axis=0) > spacing * 0.3):
        return None
    row_spacings = np.diff(centers)
    row_spacing = float(np.median(row_spacings))
    if row_spacing <= 0 or np.any(abs(row_spacings - row_spacing) > row_spacing * 0.3):
        return None
    return np.asarray(inner, dtype=np.uint8), rows


def _locate_grid(gray: GrayImage) -> tuple[GrayImage, list[list[Box]]]:
    edges = cv2.Canny(gray, 50, 150)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    candidates = []
    image_area = gray.shape[0] * gray.shape[1]
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < image_area * 0.01:
            continue
        corners = cv2.approxPolyDP(contour, 0.02 * cv2.arcLength(contour, True), True)
        if len(corners) == 4 and cv2.isContourConvex(corners):
            candidates.append((area, corners))
    for _, corners in sorted(candidates, key=lambda candidate: candidate[0], reverse=True)[:32]:
        warped = _rectify(gray, np.asarray(corners, dtype=np.float32))
        layout = _letter_rows(warped)
        if layout is not None:
            return layout
    raise GridExtractionError(
        "No clear bordered, evenly spaced letter grid was detected. "
        "Crop to the grid, keep its outer border visible, and upload a sharper image."
    )


def _run_ocr(
    executable: str,
    crop: GrayImage,
    mode: int,
    deadline: float,
) -> tuple[str, float] | None:
    encoded, png = cv2.imencode(".png", crop)
    if not encoded:
        raise GridExtractionError("Could not prepare an image for local OCR.")
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise GridExtractionError("Local OCR timed out.")
    try:
        result = subprocess.run(
            [
                executable,
                "stdin",
                "stdout",
                "-l",
                "eng",
                "--psm",
                str(mode),
                "-c",
                "tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ",
                "tsv",
            ],
            input=png.tobytes(),
            capture_output=True,
            timeout=remaining,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise GridExtractionError("Local OCR timed out.") from exc
    except OSError as exc:
        raise GridExtractionUnavailable("Could not start the local OCR engine.") from exc
    if result.returncode:
        raise GridExtractionError(
            "Tesseract failed. Verify the executable and English language data."
        )
    try:
        records = csv.DictReader(
            io.StringIO(result.stdout.decode("utf-8")),
            delimiter="\t",
        )
        recognized = [
            (record["text"].strip(), float(record["conf"]))
            for record in records
            if record["level"] == "5" and record["text"].strip()
        ]
    except (KeyError, ValueError, UnicodeDecodeError) as exc:
        raise GridExtractionError("Tesseract returned an invalid recognition result.") from exc
    if len(recognized) != 1:
        return None
    letter, confidence = recognized[0]
    if len(letter) != 1 or not letter.isascii() or not letter.isalpha():
        return None
    if not np.isfinite(confidence) or not 0 <= confidence <= 100:
        return None
    return letter, confidence / 100


def _recognize_cell(
    executable: str,
    binary: GrayImage,
    gray: GrayImage,
    deadline: float,
) -> tuple[str, float]:
    variants = (
        (binary, 10),
        (binary, 13),
        (gray, 10),
    )
    candidates: list[tuple[str, float]] = []
    for image, mode in variants:
        padded = np.asarray(
            cv2.copyMakeBorder(image, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255),
            dtype=np.uint8,
        )
        recognized = _run_ocr(executable, padded, mode, deadline)
        if recognized is not None:
            candidates.append(recognized)
            if recognized[1] >= 0.7:
                return max(candidates, key=lambda candidate: candidate[1])
    if not candidates or max(candidate[1] for candidate in candidates) < 0.5:
        raise GridExtractionError(
            "A grid cell could not be read confidently; upload a clearer image."
        )
    return max(candidates, key=lambda candidate: candidate[1])


class LocalGridExtractor:
    """Run Tesseract locally without a key, network request, or persisted upload."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def extract_grid(self, image_bytes: bytes, media_type: str) -> ExtractedGrid:
        return await run_in_threadpool(self._extract, image_bytes)

    def _extract(self, image_bytes: bytes) -> ExtractedGrid:
        deadline = time.monotonic() + self._settings.local_ocr_timeout_seconds
        executable = _find_tesseract(self._settings.tesseract_cmd)
        with Image.open(io.BytesIO(image_bytes)) as source:
            gray = np.asarray(ImageOps.exif_transpose(source).convert("L"), dtype=np.uint8)
        inner, rows = _locate_grid(gray)
        _, thresholded = cv2.threshold(
            inner,
            0,
            255,
            cv2.THRESH_BINARY + cv2.THRESH_OTSU,
        )
        binary = np.asarray(thresholded, dtype=np.uint8)
        grid: list[list[str]] = []
        confidences: list[float] = []
        for row in rows:
            letters: list[str] = []
            for x, y, width, height in row:
                region = (
                    slice(max(0, y - 6), y + height + 6),
                    slice(max(0, x - 6), x + width + 6),
                )
                gray_region = (
                    slice(max(0, y - 4), y + height + 4),
                    slice(max(0, x - 4), x + width + 4),
                )
                letter, confidence = _recognize_cell(
                    executable,
                    binary[region],
                    inner[gray_region],
                    deadline,
                )
                letters.append(letter)
                confidences.append(confidence)
            grid.append(letters)
        confidence = sum(confidences) / len(confidences)
        if confidence < self._settings.extraction_confidence_threshold:
            raise GridExtractionError("Local OCR confidence is too low; upload a clearer image.")
        return ExtractedGrid(grid=grid, confidence=confidence)
