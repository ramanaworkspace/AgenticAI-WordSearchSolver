"""Isolate tests from machine credentials and live gateway configuration."""

import pytest

from app.core.config import Settings


@pytest.fixture(autouse=True)
def clear_gateway_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "ROUTE_LLM_BASE_URL",
        "ROUTE_LLM_API_KEY",
        "ROUTE_LLM_MODEL",
        "ROUTE_LLM_TIMEOUT_SECONDS",
        "IMAGE_MAX_BYTES",
        "IMAGE_MAX_WIDTH",
        "IMAGE_MAX_HEIGHT",
        "EXTRACTION_CONFIDENCE_THRESHOLD",
        "IMAGE_EXTRACTION_PROVIDER",
        "TESSERACT_CMD",
        "LOCAL_OCR_TIMEOUT_SECONDS",
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def gateway_settings() -> Settings:
    return Settings(
        route_llm_base_url="https://gateway.example/v1",
        route_llm_api_key="test-placeholder-not-a-credential",
        route_llm_model="test-vision",
        route_llm_timeout_seconds=30,
        image_max_bytes=1024 * 1024,
        image_max_width=1024,
        image_max_height=1024,
        extraction_confidence_threshold=0.7,
    )
