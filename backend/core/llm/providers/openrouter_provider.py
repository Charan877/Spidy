"""OpenRouter LLM Provider for NOVA Code Lab (Fallback and Secondary Provider)."""

import os
import time
from typing import Any, Dict, List, Optional
from openai import OpenAI

from backend.core.llm.providers.base_provider import BaseProvider
from backend.core.llm.types import LLMResponse, redact_secrets


class OpenRouterProvider(BaseProvider):
    """Integrates OpenRouter endpoints via OpenAI client compatibility."""

    DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
    DEFAULT_MODEL = "openrouter/free"

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        key = api_key if api_key is not None else os.getenv("OPENROUTER_API_KEY", "")
        url = base_url or os.getenv("OPENROUTER_BASE_URL", self.DEFAULT_BASE_URL)
        super().__init__(name="OpenRouter", api_key=key, base_url=url)
        self._client: Optional[OpenAI] = None

    def _get_client(self, timeout: float = 60.0) -> OpenAI:
        if not self._client:
            if not self.is_configured:
                raise ValueError("OPENROUTER_API_KEY is not configured.")
            self._client = OpenAI(
                api_key=self._api_key,
                base_url=self.base_url,
                timeout=timeout,
                max_retries=0,
            )
        return self._client

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
        t0 = time.time()
        target_model = model or os.getenv("OPENROUTER_MODEL", self.DEFAULT_MODEL)

        try:
            client = self._get_client(timeout=timeout)
            create_kwargs: Dict[str, Any] = {
                "model": target_model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "timeout": timeout,
            }
            if extra_body:
                create_kwargs["extra_body"] = extra_body

            response = client.chat.completions.create(**create_kwargs)
            latency_ms = (time.time() - t0) * 1000.0

            content = ""
            if response.choices and len(response.choices) > 0:
                content = response.choices[0].message.content or ""

            usage = getattr(response, "usage", None)
            p_tok = getattr(usage, "prompt_tokens", 0) if usage else 0
            c_tok = getattr(usage, "completion_tokens", 0) if usage else 0
            t_tok = getattr(usage, "total_tokens", 0) if usage else (p_tok + c_tok)

            if not content.strip():
                return LLMResponse(
                    content="",
                    role=role,
                    model=target_model,
                    provider=self.name,
                    latency_ms=latency_ms,
                    success=False,
                    error="OpenRouter returned empty content.",
                )

            return LLMResponse(
                content=content.strip(),
                role=role,
                model=target_model,
                provider=self.name,
                latency_ms=latency_ms,
                success=True,
                prompt_tokens=p_tok,
                completion_tokens=c_tok,
                total_tokens=t_tok,
                raw_response=response,
            )

        except Exception as exc:
            latency_ms = (time.time() - t0) * 1000.0
            error_str = redact_secrets(str(exc))
            return LLMResponse(
                content="",
                role=role,
                model=target_model,
                provider=self.name,
                latency_ms=latency_ms,
                success=False,
                error=f"OpenRouter API request failed ({target_model}): {error_str}",
            )

    def embed(
        self,
        texts: List[str],
        model: Optional[str] = None,
        timeout: float = 30.0,
    ) -> List[List[float]]:
        """Dedicated embedding endpoint via OpenRouter."""
        target_model = model or "openai/text-embedding-3-small"
        client = self._get_client(timeout=timeout)
        resp = client.embeddings.create(
            model=target_model,
            input=texts,
            timeout=timeout,
        )
        return [item.embedding for item in resp.data]
