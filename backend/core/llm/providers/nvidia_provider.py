"""NVIDIA OpenAI-compatible LLM Provider for NOVA Code Lab.

Communicates with NVIDIA NIM endpoints at https://integrate.api.nvidia.com/v1.
Supports specialized models: GLM-5.3, Nemotron-3.5 Lightning, Gemma-4-31B-IT, Nemotron-3 Embed.
"""

import os
import time
from typing import Any, Dict, List, Optional
from openai import OpenAI

from backend.core.llm.providers.base_provider import BaseProvider
from backend.core.llm.types import LLMResponse, redact_secrets


class NvidiaProvider(BaseProvider):
    """Integrates NVIDIA NIM endpoints via OpenAI client compatibility."""

    DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        key = api_key if api_key is not None else os.getenv("NVIDIA_API_KEY", "")
        url = base_url or os.getenv("NVIDIA_BASE_URL", self.DEFAULT_BASE_URL)
        super().__init__(name="NVIDIA", api_key=key, base_url=url)
        self._client: Optional[OpenAI] = None

    def _get_client(self, timeout: float = 60.0) -> OpenAI:
        if not self._client:
            if not self.is_configured:
                raise ValueError("NVIDIA_API_KEY is not configured.")
            self._client = OpenAI(
                api_key=self._api_key,
                base_url=self.base_url,
                timeout=timeout,
                max_retries=0,  # Retries handled at router level
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
        
        # Model-specific payload configurations
        req_extra = extra_body.copy() if extra_body else {}
        if "nemotron-3.5-lightning" in model and "chat_template_kwargs" not in req_extra:
            req_extra["chat_template_kwargs"] = {"enable_thinking": True}
            req_extra.setdefault("reasoning_budget", 16384)

        try:
            client = self._get_client(timeout=timeout)
            create_kwargs: Dict[str, Any] = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "timeout": timeout,
            }
            if req_extra:
                create_kwargs["extra_body"] = req_extra

            response = client.chat.completions.create(**create_kwargs)
            latency_ms = (time.time() - t0) * 1000.0

            content = ""
            if response.choices and len(response.choices) > 0:
                choice = response.choices[0]
                msg = choice.message
                content = getattr(msg, "content", "") or ""
                # Also check reasoning content if content is empty
                if not content.strip() and hasattr(msg, "reasoning_content"):
                    content = getattr(msg, "reasoning_content", "") or ""

            # Token usage
            usage = getattr(response, "usage", None)
            p_tok = getattr(usage, "prompt_tokens", 0) if usage else 0
            c_tok = getattr(usage, "completion_tokens", 0) if usage else 0
            t_tok = getattr(usage, "total_tokens", 0) if usage else (p_tok + c_tok)

            if not content.strip():
                return LLMResponse(
                    content="",
                    role=role,
                    model=model,
                    provider=self.name,
                    latency_ms=latency_ms,
                    success=False,
                    error="Model returned empty completion content.",
                )

            return LLMResponse(
                content=content.strip(),
                role=role,
                model=model,
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
                model=model,
                provider=self.name,
                latency_ms=latency_ms,
                success=False,
                error=f"NVIDIA API request failed ({model}): {error_str}",
            )

    def generate_stream(
        self,
        model: str,
        messages: List[Dict[str, str]],
        role: str = "general",
        temperature: float = 0.2,
        max_tokens: int = 4096,
        timeout: float = 60.0,
        extra_body: Optional[Dict[str, Any]] = None,
    ):
        """Streaming generator yielding text chunks from NVIDIA API."""
        req_extra = extra_body.copy() if extra_body else {}
        if "nemotron-3.5-lightning" in model and "chat_template_kwargs" not in req_extra:
            req_extra["chat_template_kwargs"] = {"enable_thinking": True}
            req_extra.setdefault("reasoning_budget", 16384)

        client = self._get_client(timeout=timeout)
        stream_resp = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            timeout=timeout,
            extra_body=req_extra if req_extra else None,
        )
        for chunk in stream_resp:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            content = getattr(delta, "content", None)
            if content:
                yield content
            elif hasattr(delta, "reasoning_content") and getattr(delta, "reasoning_content"):
                yield getattr(delta, "reasoning_content")

    def embed(
        self,
        texts: List[str],
        model: Optional[str] = None,
        timeout: float = 30.0,
    ) -> List[List[float]]:
        """Dedicated embedding endpoint via OpenAI client compatibility."""
        target_model = model or os.getenv("NVIDIA_EMBEDDING_MODEL", "nvidia/nemotron-3-embed-1b")
        client = self._get_client(timeout=timeout)
        resp = client.embeddings.create(
            model=target_model,
            input=texts,
            timeout=timeout,
        )
        return [item.embedding for item in resp.data]
