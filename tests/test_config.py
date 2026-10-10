"""Settings validation without live endpoints or real credentials."""

from dataclasses import replace

import pytest

from app.core.config import Settings


@pytest.mark.parametrize(
    "url",
    [
        "https://gateway.example/v1",
        "http://localhost:8001/v1",
        "http://127.0.0.1:8001/v1",
        "http://[::1]:8001/v1",
    ],
)
def test_accepts_https_or_loopback(url: str, gateway_settings: Settings) -> None:
    replace(gateway_settings, route_llm_base_url=url).validate_route_llm_url()


@pytest.mark.parametrize(
    "url",
    [
        "",
        "ftp://gateway.example/v1",
        "http://gateway.example/v1",
        "http://localhost.evil.example/v1",
        "https://user:password@gateway.example/v1",
        "https://gateway.example/v1?secret=value",
        "https://gateway.example:bad/v1",
        "https://gateway.example/v1#fragment",
    ],
)
def test_rejects_unsafe_urls(url: str, gateway_settings: Settings) -> None:
    with pytest.raises(ValueError):
        replace(gateway_settings, route_llm_base_url=url).validate_route_llm_url()


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("IMAGE_MAX_BYTES", "0"),
        ("IMAGE_MAX_WIDTH", "-1"),
        ("IMAGE_MAX_HEIGHT", "bad"),
        ("EXTRACTION_CONFIDENCE_THRESHOLD", "1.1"),
        ("EXTRACTION_CONFIDENCE_THRESHOLD", "nan"),
        ("ROUTE_LLM_TIMEOUT_SECONDS", "0"),
        ("ROUTE_LLM_TIMEOUT_SECONDS", "nan"),
        ("ROUTE_LLM_TIMEOUT_SECONDS", "inf"),
    ],
)
def test_rejects_invalid_configuration(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    value: str,
) -> None:
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError):
        Settings.from_environment()


def test_settings_repr_hides_key(gateway_settings: Settings) -> None:
    assert gateway_settings.route_llm_api_key not in repr(gateway_settings)
