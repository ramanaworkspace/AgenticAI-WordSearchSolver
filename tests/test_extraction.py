"""Validate image processing and the remote adapter without live network access."""

import asyncio
import base64
import json
from collections.abc import Iterator
from dataclasses import replace
from io import BytesIO

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.api.routes import get_grid_extractor
from app.core.config import Settings
from app.main import app
from app.schemas.puzzle import ExtractedGrid
from app.services.extraction import GridExtractionError, GridExtractionUnavailable
from app.services.route_llm import RouteLLMGridExtractor


class FakeExtractor:
    def __init__(self, confidence: float = 0.95) -> None:
        self.confidence = confidence
        self.called = False

    async def extract_grid(self, image_bytes: bytes, media_type: str) -> ExtractedGrid:
        self.called = True
        assert image_bytes
        assert media_type in {"image/png", "image/jpeg", "image/gif", "image/webp"}
        return ExtractedGrid(grid=[list("CAT")], confidence=self.confidence)


@pytest.fixture
def extractor() -> Iterator[FakeExtractor]:
    fake = FakeExtractor()
    app.dependency_overrides[get_grid_extractor] = lambda: fake
    try:
        yield fake
    finally:
        app.dependency_overrides.clear()


def make_image(width: int = 2, height: int = 2, image_format: str = "PNG") -> bytes:
    with BytesIO() as buffer:
        Image.new("RGB", (width, height), color="white").save(buffer, format=image_format)
        return buffer.getvalue()


def test_image_endpoint_returns_extracted_grid_and_solution(extractor: FakeExtractor) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/solve/image",
            files={"image": ("puzzle.png", make_image(), "image/png")},
            data={"words": '["cat", "DOG", "CAT"]'},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["grid"] == [list("CAT")]
    assert body["confidence"] == 0.95
    assert body["solution"]["not_found"] == ["DOG"]
    assert len(body["solution"]["results"]) == 1
    assert body["solution"]["results"][0]["end"] == {"row": 0, "column": 2}
    assert extractor.called


@pytest.mark.parametrize(
    ("content", "media_type", "expected_status"),
    [
        (b"", "image/png", 400),
        (b"not a valid image", "image/png", 400),
        (make_image(), "image/jpeg", 415),
        (b"plain text", "text/plain", 415),
        (make_image()[:-20], "image/png", 400),
    ],
)
def test_rejects_invalid_uploads_before_extraction(
    extractor: FakeExtractor,
    content: bytes,
    media_type: str,
    expected_status: int,
) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/solve/image",
            files={"image": ("puzzle", content, media_type)},
            data={"words": '["CAT"]'},
        )
    assert response.status_code == expected_status
    assert not extractor.called


@pytest.mark.parametrize("words", ["not json", '"CAT"', "[]", '["A1"]', "[1]", '[""]'])
def test_rejects_invalid_words(extractor: FakeExtractor, words: str) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/solve/image",
            files={"image": ("puzzle.png", make_image(), "image/png")},
            data={"words": words},
        )
    assert response.status_code == 422
    assert not extractor.called


def test_upload_byte_limit(
    extractor: FakeExtractor,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image = make_image()
    monkeypatch.setenv("IMAGE_MAX_BYTES", str(len(image) - 1))
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/solve/image",
            files={"image": ("puzzle.png", image, "image/png")},
            data={"words": '["CAT"]'},
        )
    assert response.status_code == 413
    assert not extractor.called


def test_accepts_exact_upload_and_dimension_limits(
    extractor: FakeExtractor,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image = make_image()
    monkeypatch.setenv("IMAGE_MAX_BYTES", str(len(image)))
    monkeypatch.setenv("IMAGE_MAX_WIDTH", "2")
    monkeypatch.setenv("IMAGE_MAX_HEIGHT", "2")
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/solve/image",
            files={"image": ("puzzle.png", image, "image/png")},
            data={"words": '["CAT"]'},
        )
    assert response.status_code == 200


def test_dimension_limit(
    extractor: FakeExtractor,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("IMAGE_MAX_WIDTH", "1")
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/solve/image",
            files={"image": ("puzzle.png", make_image(), "image/png")},
            data={"words": '["CAT"]'},
        )
    assert response.status_code == 413
    assert not extractor.called


def test_rejects_animated_image(extractor: FakeExtractor) -> None:
    with BytesIO() as buffer:
        first = Image.new("RGB", (2, 2), color="white")
        second = Image.new("RGB", (2, 2), color="black")
        first.save(buffer, format="GIF", save_all=True, append_images=[second], duration=100)
        content = buffer.getvalue()
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/solve/image",
            files={"image": ("puzzle.gif", content, "image/gif")},
            data={"words": '["CAT"]'},
        )
    assert response.status_code == 415
    assert not extractor.called


def test_uncertain_extraction_is_an_error(extractor: FakeExtractor) -> None:
    extractor.confidence = 0.69
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/solve/image",
            files={"image": ("puzzle.png", make_image(), "image/png")},
            data={"words": '["CAT"]'},
        )
    assert response.status_code == 502
    assert "solution" not in response.json()


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (GridExtractionError("Extraction failed."), 502),
        (GridExtractionUnavailable("Extraction unavailable."), 503),
    ],
)
def test_provider_error_http_mapping(
    error: Exception,
    expected_status: int,
) -> None:
    class FailingExtractor:
        async def extract_grid(self, image_bytes: bytes, media_type: str) -> ExtractedGrid:
            raise error

    app.dependency_overrides[get_grid_extractor] = lambda: FailingExtractor()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/solve/image",
                files={"image": ("puzzle.png", make_image(), "image/png")},
                data={"words": '["CAT"]'},
            )
        assert response.status_code == expected_status
        assert response.json() == {"detail": str(error)}
    finally:
        app.dependency_overrides.clear()


def install_mock_client(
    monkeypatch: pytest.MonkeyPatch,
    handler: httpx.MockTransport,
) -> None:
    original_client = httpx.AsyncClient

    def client_factory(*, timeout: float) -> httpx.AsyncClient:
        return original_client(transport=handler, timeout=timeout)

    monkeypatch.setattr("app.services.route_llm.httpx.AsyncClient", client_factory)


def test_adapter_sends_data_url_and_configured_model(
    monkeypatch: pytest.MonkeyPatch,
    gateway_settings: Settings,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://gateway.example/v1/chat/completions"
        assert request.headers["authorization"] == ("Bearer " + gateway_settings.route_llm_api_key)
        payload = json.loads(request.content)
        assert payload["model"] == "test-vision"
        assert payload["messages"][1]["role"] == "user"
        url = payload["messages"][1]["content"][1]["image_url"]["url"]
        assert url == "data:image/png;base64," + base64.b64encode(b"image").decode("ascii")
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {"content": '{"grid":[["A"]],"confidence":0.95}'},
                        "finish_reason": "stop",
                    }
                ]
            },
        )

    install_mock_client(monkeypatch, httpx.MockTransport(handler))
    result = asyncio.run(
        RouteLLMGridExtractor(gateway_settings).extract_grid(b"image", "image/png")
    )
    assert result.grid == [["A"]]
    assert result.confidence == 0.95


@pytest.mark.parametrize(
    "content",
    [
        "not JSON",
        '{"grid":[["AB"]],"confidence":0.9}',
        '{"grid":[["A"],["A","B"]],"confidence":0.9}',
        '{"grid":[["A"]],"confidence":0.1}',
        '{"grid":[["A"]],"confidence":2}',
        '{"grid":[["A"]],"confidence":"0.9"}',
        '{"grid":[["A"]]}',
    ],
)
def test_adapter_rejects_invalid_or_uncertain_grid(
    monkeypatch: pytest.MonkeyPatch,
    gateway_settings: Settings,
    content: str,
) -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {"content": content},
                        "finish_reason": "stop",
                    }
                ]
            },
        )
    )
    install_mock_client(monkeypatch, transport)
    with pytest.raises(GridExtractionError):
        asyncio.run(RouteLLMGridExtractor(gateway_settings).extract_grid(b"image", "image/png"))


@pytest.mark.parametrize("body", [{}, {"choices": []}, {"choices": [None]}])
def test_adapter_rejects_malformed_completion(
    monkeypatch: pytest.MonkeyPatch,
    gateway_settings: Settings,
    body: object,
) -> None:
    install_mock_client(
        monkeypatch,
        httpx.MockTransport(lambda request: httpx.Response(200, json=body)),
    )
    with pytest.raises(GridExtractionError):
        asyncio.run(RouteLLMGridExtractor(gateway_settings).extract_grid(b"image", "image/png"))


def test_adapter_rejects_truncated_completion(
    monkeypatch: pytest.MonkeyPatch,
    gateway_settings: Settings,
) -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {"content": '{"grid":[["A"]],"confidence":0.9}'},
                        "finish_reason": "length",
                    }
                ]
            },
        )
    )
    install_mock_client(monkeypatch, transport)
    with pytest.raises(GridExtractionError, match="incomplete"):
        asyncio.run(RouteLLMGridExtractor(gateway_settings).extract_grid(b"image", "image/png"))


@pytest.mark.parametrize("status_code", [400, 401, 403, 413, 429, 500, 503])
def test_adapter_does_not_expose_upstream_error_details(
    monkeypatch: pytest.MonkeyPatch,
    gateway_settings: Settings,
    status_code: int,
) -> None:
    install_mock_client(
        monkeypatch,
        httpx.MockTransport(
            lambda request: httpx.Response(status_code, text="sensitive upstream response"),
        ),
    )
    with pytest.raises(GridExtractionError) as error:
        asyncio.run(RouteLLMGridExtractor(gateway_settings).extract_grid(b"image", "image/png"))
    assert "sensitive" not in str(error.value)
    assert gateway_settings.route_llm_api_key not in str(error.value)


def test_adapter_timeout_is_explicit(
    monkeypatch: pytest.MonkeyPatch,
    gateway_settings: Settings,
) -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("sensitive timeout details", request=request)

    install_mock_client(monkeypatch, httpx.MockTransport(timeout))
    with pytest.raises(GridExtractionError, match="timed out"):
        asyncio.run(RouteLLMGridExtractor(gateway_settings).extract_grid(b"image", "image/png"))


def test_adapter_rejects_insecure_gateway_before_network(gateway_settings: Settings) -> None:
    insecure = replace(gateway_settings, route_llm_base_url="http://gateway.example/v1")
    with pytest.raises(GridExtractionUnavailable):
        asyncio.run(RouteLLMGridExtractor(insecure).extract_grid(b"image", "image/png"))
