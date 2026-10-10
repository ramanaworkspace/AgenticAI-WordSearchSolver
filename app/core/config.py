"""Environment-backed application settings."""

import os
from dataclasses import dataclass, field
from math import isfinite
from urllib.parse import urlparse


def _positive_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a positive integer.") from exc
    if value <= 0:
        raise ValueError(f"{name} must be a positive integer.")
    return value


def _confidence_threshold() -> float:
    raw_value = os.getenv("EXTRACTION_CONFIDENCE_THRESHOLD", "0.7")
    try:
        value = float(raw_value)
    except ValueError as exc:
        raise ValueError("EXTRACTION_CONFIDENCE_THRESHOLD must be between 0 and 1.") from exc
    if not 0 <= value <= 1:
        raise ValueError("EXTRACTION_CONFIDENCE_THRESHOLD must be between 0 and 1.")
    return value


@dataclass(frozen=True)
class Settings:
    """Settings loaded from the process environment."""

    route_llm_base_url: str
    route_llm_api_key: str = field(repr=False)
    route_llm_model: str
    route_llm_timeout_seconds: float
    image_max_bytes: int
    image_max_width: int
    image_max_height: int
    extraction_confidence_threshold: float
    image_extraction_provider: str = "local"
    tesseract_cmd: str = ""
    local_ocr_timeout_seconds: int = 60

    @classmethod
    def from_environment(cls) -> "Settings":
        timeout_raw = os.getenv("ROUTE_LLM_TIMEOUT_SECONDS", "30")
        try:
            timeout = float(timeout_raw)
        except ValueError as exc:
            raise ValueError("ROUTE_LLM_TIMEOUT_SECONDS must be positive.") from exc
        if not isfinite(timeout) or timeout <= 0:
            raise ValueError("ROUTE_LLM_TIMEOUT_SECONDS must be positive.")

        return cls(
            route_llm_base_url=os.getenv("ROUTE_LLM_BASE_URL", "").rstrip("/"),
            route_llm_api_key=os.getenv("ROUTE_LLM_API_KEY", ""),
            route_llm_model=os.getenv("ROUTE_LLM_MODEL", ""),
            route_llm_timeout_seconds=timeout,
            image_max_bytes=_positive_int("IMAGE_MAX_BYTES", 5 * 1024 * 1024),
            image_max_width=_positive_int("IMAGE_MAX_WIDTH", 4096),
            image_max_height=_positive_int("IMAGE_MAX_HEIGHT", 4096),
            extraction_confidence_threshold=_confidence_threshold(),
            image_extraction_provider=os.getenv("IMAGE_EXTRACTION_PROVIDER", "local"),
            tesseract_cmd=os.getenv("TESSERACT_CMD", ""),
            local_ocr_timeout_seconds=_positive_int("LOCAL_OCR_TIMEOUT_SECONDS", 60),
        )

    def validate_route_llm_url(self) -> None:
        """Require TLS except for a local development endpoint."""
        parsed = urlparse(self.route_llm_base_url)
        if (
            parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("ROUTE_LLM_BASE_URL must not contain credentials, query, or fragment.")
        try:
            _ = parsed.port
        except ValueError as exc:
            raise ValueError("ROUTE_LLM_BASE_URL contains an invalid port.") from exc
        if parsed.scheme == "https" and parsed.hostname:
            return
        if parsed.scheme == "http" and parsed.hostname in {
            "localhost",
            "127.0.0.1",
            "::1",
        }:
            return
        raise ValueError(
            "ROUTE_LLM_BASE_URL must use HTTPS; HTTP is allowed only for a loopback host."
        )


def get_settings() -> Settings:
    """Load settings for the current request."""
    return Settings.from_environment()
