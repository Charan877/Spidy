"""Type definitions and data models for NOVA multi-provider LLM architecture."""

from dataclasses import dataclass, field
import re
import time
from typing import Any, Dict, List, Optional


def redact_secrets(text: str) -> str:
    """Scrub sensitive API tokens from error strings, logs, and diagnostics."""
    if not text or not isinstance(text, str):
        return ""
    # Redact NVIDIA keys
    text = re.sub(r"nvapi-[A-Za-z0-9_\-]+", "nvapi-***REDACTED***", text)
    # Redact OpenRouter keys
    text = re.sub(r"sk-or-[A-Za-z0-9_\-]+", "sk-or-***REDACTED***", text)
    # Generic Bearer tokens
    text = re.sub(r"Bearer\s+[A-Za-z0-9_\-\.]{16,}", "Bearer ***REDACTED***", text)
    return text


@dataclass
class LLMResponse:
    """Standardized completion response from any provider."""

    content: str
    role: str
    model: str
    provider: str
    latency_ms: float
    success: bool = True
    error: Optional[str] = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    raw_response: Optional[Any] = None

    def __post_init__(self):
        if self.error:
            self.error = redact_secrets(self.error)


@dataclass
class ProviderUsageMetrics:
    """In-memory telemetry for provider/model performance."""

    provider: str
    model: str
    role: str
    request_count: int = 0
    error_count: int = 0
    retry_count: int = 0
    total_latency_ms: float = 0.0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    status: str = "READY"  # "READY", "ACTIVE", "ERROR", "OFFLINE"
    last_error: Optional[str] = None
    last_used: Optional[float] = None

    @property
    def avg_latency_ms(self) -> float:
        if self.request_count == 0:
            return 0.0
        return round(self.total_latency_ms / self.request_count, 1)

    def record_success(self, latency_ms: float, p_tokens: int = 0, c_tokens: int = 0) -> None:
        self.request_count += 1
        self.total_latency_ms += latency_ms
        self.total_prompt_tokens += p_tokens
        self.total_completion_tokens += c_tokens
        self.status = "READY"
        self.last_used = time.time()

    def record_error(self, error_msg: str) -> None:
        self.error_count += 1
        self.status = "ERROR"
        self.last_error = redact_secrets(error_msg)
        self.last_used = time.time()
