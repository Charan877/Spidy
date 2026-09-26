"""Base provider interface for NOVA Code Lab LLM integrations."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from backend.core.llm.types import LLMResponse, redact_secrets


class BaseProvider(ABC):
    """Abstract base class for OpenAI-compatible and custom LLM providers."""

    def __init__(self, name: str, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.name = name
        self._api_key = api_key or ""
        self.base_url = base_url or ""

    @property
    def is_configured(self) -> bool:
        """Return True if an API key is available."""
        return bool(self._api_key and len(self._api_key.strip()) > 5)

    @abstractmethod
    def generate(
        self,
        model: str,
        messages: List[Dict[str, str]],
        role: str = "general",
        temperature: float = 0.2,
        max_tokens: int = 4096,
        timeout: float = 60.0,
        extra_body: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> LLMResponse:
        """Execute chat completion and return standardized LLMResponse."""
        pass

    @abstractmethod
    def embed(
        self,
        texts: List[str],
        model: Optional[str] = None,
        timeout: float = 30.0,
    ) -> List[List[float]]:
        """Generate vector embeddings for input texts using dedicated embedding endpoint."""
        pass
