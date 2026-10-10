"""HTTP-level tests for the FastAPI application."""

from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app

client = TestClient(app)


def test_health_does_not_expose_configuration() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_solve_endpoint_returns_matches_and_missing_words() -> None:
    response = client.post(
        "/api/v1/solve",
        json={"grid": [["C", "A", "T"]], "words": ["cat", "dog"]},
    )

    assert response.status_code == 200
    assert response.json() == {
        "grid_size": {"rows": 1, "columns": 3},
        "results": [
            {
                "word": "CAT",
                "found": True,
                "start": {"row": 0, "column": 0},
                "end": {"row": 0, "column": 2},
                "direction": "east",
            }
        ],
        "not_found": ["DOG"],
    }


def test_solve_endpoint_rejects_ragged_grid() -> None:
    response = client.post(
        "/api/v1/solve",
        json={"grid": [["A"], ["B", "C"]], "words": ["A"]},
    )

    assert response.status_code == 422


def test_openapi_documents_zero_based_coordinates() -> None:
    schema = client.get("/openapi.json").json()
    coordinate = schema["components"]["schemas"]["Coordinate"]

    assert "Zero-based row index." in coordinate["properties"]["row"]["description"]
    assert "Zero-based column index." in coordinate["properties"]["column"]["description"]


def test_image_endpoint_rejects_unsupported_media_type() -> None:
    response = client.post(
        "/api/v1/solve/image",
        files={"image": ("puzzle.txt", b"not an image", "text/plain")},
        data={"words": '["CAT"]'},
    )

    assert response.status_code == 415


def test_image_endpoint_reports_unconfigured_extractor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ROUTE_LLM_API_KEY", "")
    monkeypatch.setenv("ROUTE_LLM_MODEL", "")
    monkeypatch.setenv("IMAGE_EXTRACTION_PROVIDER", "route_llm")
    image_data = BytesIO()
    Image.new("RGB", (2, 2), color="white").save(image_data, format="PNG")

    response = client.post(
        "/api/v1/solve/image",
        files={"image": ("puzzle.png", image_data.getvalue(), "image/png")},
        data={"words": '["CAT"]'},
    )

    assert response.status_code == 503
    assert "not configured" in response.json()["detail"]


def test_json_solver_is_independent_of_invalid_image_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ROUTE_LLM_TIMEOUT_SECONDS", "invalid")
    response = client.post(
        "/api/v1/solve",
        json={"grid": [["A"]], "words": ["A"]},
    )
    assert response.status_code == 200
    assert client.get("/health").status_code == 200


def test_request_body_limit_cannot_be_bypassed_by_streaming() -> None:
    response = client.post(
        "/api/v1/solve",
        content=iter([b" " * 200000, b" " * 200000]),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413
