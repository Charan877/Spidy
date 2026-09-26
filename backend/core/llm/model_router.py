"""Central Model Router for NOVA Code Lab.

Decouples agent workflows from direct provider APIs. Resolves role-based model requests,
coordinates primary NVIDIA models, orchestrates bounded retries, falls back to OpenRouter,
tracks telemetry, and sanitizes secrets.
"""

from dataclasses import asdict
import os
import time
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

from backend.core.llm.providers.base_provider import BaseProvider
from backend.core.llm.providers.nvidia_provider import NvidiaProvider
from backend.core.llm.providers.openrouter_provider import OpenRouterProvider
from backend.core.llm.types import LLMResponse, ProviderUsageMetrics, redact_secrets

load_dotenv()


class ModelRouter:
    """Central model router that maps functional roles to models with bounded fallback."""

    # Default model identifiers extracted from reference specifications
    DEFAULT_ROLE_MODELS = {
        "planner": "z-ai/glm-5.3",
        "architect": "z-ai/glm-5.3",
        "fast": "nvidia/nemotron-3.5-lightning-30b-a3b",
        "general": "google/gemma-4-31b-it",
        "vision": "google/gemma-4-31b-it",
        "embedding": "nvidia/nemotron-3-embed-1b",
        "coder": "z-ai/glm-5.3",
        "debugger": "z-ai/glm-5.3",
    }

    def __init__(
        self,
        nvidia_provider: Optional[NvidiaProvider] = None,
        openrouter_provider: Optional[OpenRouterProvider] = None,
        max_retries: int = 2,
        timeout: float = 60.0,
    ):
        self.nvidia = nvidia_provider or NvidiaProvider()
        self.openrouter = openrouter_provider or OpenRouterProvider()
        self.max_retries = int(os.getenv("LLM_MAX_RETRIES", max_retries))
        self.timeout = float(os.getenv("LLM_TIMEOUT", timeout))
        self.fallback_callback = None
        self.metrics: Dict[str, ProviderUsageMetrics] = {}
        self._init_metrics()

    def set_fallback_callback(self, callback) -> None:
        """Register a callback (message: str, level: str) for provider fallback events."""
        self.fallback_callback = callback

    def _emit_event(self, message: str, level: str = "ok") -> None:
        if self.fallback_callback:
            try:
                self.fallback_callback(message, level)
            except Exception:
                pass

    @property
    def primary_provider(self) -> BaseProvider:
        return self.nvidia

    @property
    def fallback_provider(self) -> BaseProvider:
        return self.openrouter

    def is_configured(self) -> bool:
        """Return True if at least one provider (NVIDIA or OpenRouter) is configured."""
        return bool(self.nvidia.is_configured or self.openrouter.is_configured)

    def _init_metrics(self) -> None:
        """Initialize telemetry slots for configured roles."""
        for role in self.DEFAULT_ROLE_MODELS.keys():
            model = self.resolve_model(role)
            provider_name = "NVIDIA" if self.nvidia.is_configured else "OpenRouter"
            key = f"{provider_name}:{role}"
            self.metrics[key] = ProviderUsageMetrics(
                provider=provider_name,
                model=model,
                role=role,
                status="READY" if (self.nvidia.is_configured or self.openrouter.is_configured) else "OFFLINE",
            )

    def resolve_model(self, role: str) -> str:
        """Resolve model ID from environment configuration or default."""
        role_upper = role.upper()
        env_key = f"NVIDIA_{role_upper}_MODEL"
        model = os.getenv(env_key)

        if not model or not model.strip():
            model = self.DEFAULT_ROLE_MODELS.get(role.lower(), "google/gemma-4-31b-it")

        return model.strip()

    def get_effective_provider_and_model(self, role: str) -> tuple[BaseProvider, str]:
        """Determine primary provider and model for a given role."""
        if self.nvidia.is_configured:
            return self.nvidia, self.resolve_model(role)
        elif self.openrouter.is_configured:
            or_model = os.getenv("OPENROUTER_MODEL", "openrouter/free")
            return self.openrouter, or_model
        else:
            # Return primary with unconfigured flag for descriptive error handling
            return self.nvidia, self.resolve_model(role)

    def generate(
        self,
        role: str,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        timeout: Optional[float] = None,
        extra_body: Optional[Dict[str, Any]] = None,
    ) -> LLMResponse:
        """Route request by role, with bounded retries and graceful fallback to OpenRouter."""
        effective_timeout = timeout or self.timeout
        role_lower = role.lower()

        full_messages = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        # 1. Check available providers
        if not self.nvidia.is_configured and not self.openrouter.is_configured:
            return LLMResponse(
                content="",
                role=role,
                model="unknown",
                provider="None",
                latency_ms=0.0,
                success=False,
                error="No AI provider configured. Set NVIDIA_API_KEY or OPENROUTER_API_KEY in .env.",
            )

        # Primary provider selection
        primary_provider = self.nvidia if self.nvidia.is_configured else self.openrouter
        primary_model = self.resolve_model(role_lower) if primary_provider == self.nvidia else os.getenv("OPENROUTER_MODEL", "openrouter/free")
        metric_key = f"{primary_provider.name}:{role_lower}"

        if metric_key not in self.metrics:
            self.metrics[metric_key] = ProviderUsageMetrics(
                provider=primary_provider.name, model=primary_model, role=role_lower
            )
        metric = self.metrics[metric_key]

        last_error = None

        # 2. Attempt with Primary Provider (bounded retries)
        for attempt in range(self.max_retries):
            if attempt > 0:
                metric.retry_count += 1
                time.sleep(0.4 * attempt)

            resp = primary_provider.generate(
                model=primary_model,
                messages=full_messages,
                role=role_lower,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=effective_timeout,
                extra_body=extra_body,
            )

            if resp.success and resp.content.strip():
                metric.record_success(resp.latency_ms, resp.prompt_tokens, resp.completion_tokens)
                return resp
            
            last_error = resp.error or "Empty response"
            metric.record_error(last_error)

        # 3. Fallback to OpenRouter (if primary was NVIDIA and OpenRouter is configured)
        if primary_provider == self.nvidia and self.openrouter.is_configured:
            fallback_model = os.getenv("OPENROUTER_MODEL", "openrouter/free")
            fallback_msg = f"[FALLBACK] PRIMARY FAILED (model: {primary_model}) -> FALLBACK ACTIVATED: Trying OpenRouter ({fallback_model})"
            print(fallback_msg)
            self._emit_event(fallback_msg, level="run")

            fb_key = f"OpenRouter:{role_lower}"
            if fb_key not in self.metrics:
                self.metrics[fb_key] = ProviderUsageMetrics(
                    provider="OpenRouter", model=fallback_model, role=role_lower
                )
            fb_metric = self.metrics[fb_key]

            for attempt in range(self.max_retries):
                if attempt > 0:
                    fb_metric.retry_count += 1
                    time.sleep(0.4 * attempt)

                fb_resp = self.openrouter.generate(
                    model=fallback_model,
                    messages=full_messages,
                    role=role_lower,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=effective_timeout,
                    extra_body=extra_body,
                )

                if fb_resp.success and fb_resp.content.strip():
                    stripped = fb_resp.content.strip()
                    lower_content = stripped.lower()
                    is_disguised_refusal = any(
                        ind in lower_content[:300]
                        for ind in ("i cannot fulfill this request", "rate limit exceeded", '{"error":', "error: 429")
                    )
                    if not is_disguised_refusal:
                        fb_metric.record_success(fb_resp.latency_ms, fb_resp.prompt_tokens, fb_resp.completion_tokens)
                        success_msg = f"[FALLBACK] FALLBACK SUCCESS: Response received from OpenRouter ({fallback_model})"
                        print(success_msg)
                        self._emit_event(success_msg, level="ok")
                        return fb_resp
                    else:
                        last_error = f"Fallback response contained refusal/error content: {stripped[:80]}"
                else:
                    last_error = fb_resp.error or "Fallback empty response"
                fb_metric.record_error(last_error)

            fail_msg = f"[FALLBACK] FALLBACK FAILED: All fallback attempts exhausted ({last_error})"
            print(fail_msg)
            self._emit_event(fail_msg, level="bad")

        # All attempts failed
        clean_err = redact_secrets(last_error or "Unknown error")
        return LLMResponse(
            content="",
            role=role,
            model=primary_model,
            provider=primary_provider.name,
            latency_ms=0.0,
            success=False,
            error=f"Model routing failed across configured providers: {clean_err}",
        )

    def generate_text(
        self,
        role: str,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        timeout: Optional[float] = None,
        extra_body: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Convenience method returning response text directly or raising descriptive error."""
        resp = self.generate(
            role=role,
            messages=messages,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            extra_body=extra_body,
        )
        if not resp.success:
            raise RuntimeError(resp.error or "LLM generation failed")
        return resp.content

    def embed(
        self,
        texts: List[str],
        model: Optional[str] = None,
        timeout: float = 30.0,
    ) -> List[List[float]]:
        """Generate vector embeddings using primary NVIDIA embedding model or fallback."""
        if self.nvidia.is_configured:
            emb_model = model or self.resolve_model("embedding")
            try:
                return self.nvidia.embed(texts=texts, model=emb_model, timeout=timeout)
            except Exception:
                if self.openrouter.is_configured:
                    print("NVIDIA embedding failed. Attempting configured fallback provider.")
                    return self.openrouter.embed(texts=texts, timeout=timeout)
                raise
        elif self.openrouter.is_configured:
            return self.openrouter.embed(texts=texts, timeout=timeout)
        else:
            raise ValueError("No AI provider configured for embeddings.")

    def get_diagnostics(self) -> List[Dict[str, Any]]:
        """Return provider status telemetry suitable for UI rendering. Redacts all secrets."""
        results = []
        for key, m in self.metrics.items():
            results.append({
                "provider": m.provider,
                "model": m.model,
                "role": m.role.capitalize(),
                "status": m.status,
                "avg_latency_ms": f"{m.avg_latency_ms}ms" if m.request_count > 0 else "—",
                "request_count": m.request_count,
                "error_count": m.error_count,
                "retry_count": m.retry_count,
                "last_error": redact_secrets(m.last_error) if m.last_error else None,
            })
        return results


# Global singleton instance
_GLOBAL_ROUTER: Optional[ModelRouter] = None


def get_model_router() -> ModelRouter:
    """Retrieve global ModelRouter instance."""
    global _GLOBAL_ROUTER
    if _GLOBAL_ROUTER is None:
        _GLOBAL_ROUTER = ModelRouter()
    return _GLOBAL_ROUTER
