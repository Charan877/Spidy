"""Unit tests for ModelRouter, NvidiaProvider, OpenRouterProvider, and secret redaction."""

import os
import unittest
from unittest.mock import MagicMock, patch

from backend.core.llm.model_router import ModelRouter
from backend.core.llm.providers.nvidia_provider import NvidiaProvider
from backend.core.llm.providers.openrouter_provider import OpenRouterProvider
from backend.core.llm.types import LLMResponse, redact_secrets


class TestModelRouter(unittest.TestCase):
    def setUp(self):
        # Set up mock providers
        self.mock_nvidia = MagicMock(spec=NvidiaProvider)
        self.mock_nvidia.name = "NVIDIA"
        self.mock_nvidia.is_configured = True

        self.mock_openrouter = MagicMock(spec=OpenRouterProvider)
        self.mock_openrouter.name = "OpenRouter"
        self.mock_openrouter.is_configured = True

        self.router = ModelRouter(
            nvidia_provider=self.mock_nvidia,
            openrouter_provider=self.mock_openrouter,
            max_retries=2,
            timeout=10.0,
        )

    def test_role_resolution(self):
        """Verify that functional roles resolve to configured model IDs."""
        self.assertEqual(self.router.resolve_model("planner"), "z-ai/glm-5.3")
        self.assertEqual(self.router.resolve_model("architect"), "z-ai/glm-5.3")
        self.assertEqual(self.router.resolve_model("fast"), "nvidia/nemotron-3.5-lightning-30b-a3b")
        self.assertEqual(self.router.resolve_model("general"), "google/gemma-4-31b-it")
        self.assertEqual(self.router.resolve_model("embedding"), "nvidia/nemotron-3-embed-1b")

    def test_nvidia_success(self):
        """Test primary provider successful completion."""
        self.mock_nvidia.generate.return_value = LLMResponse(
            content="Plan generated successfully.",
            role="planner",
            model="z-ai/glm-5.3",
            provider="NVIDIA",
            latency_ms=120.0,
            success=True,
            prompt_tokens=15,
            completion_tokens=40,
        )

        resp = self.router.generate(role="planner", messages=[{"role": "user", "content": "hello"}])
        self.assertTrue(resp.success)
        self.assertEqual(resp.content, "Plan generated successfully.")
        self.assertEqual(resp.provider, "NVIDIA")
        self.mock_nvidia.generate.assert_called_once()
        self.mock_openrouter.generate.assert_not_called()

    def test_openrouter_fallback_on_primary_failure(self):
        """Test graceful fallback to OpenRouter when NVIDIA fails."""
        self.mock_nvidia.generate.return_value = LLMResponse(
            content="",
            role="coder",
            model="z-ai/glm-5.3",
            provider="NVIDIA",
            latency_ms=80.0,
            success=False,
            error="NVIDIA rate limit 429",
        )
        self.mock_openrouter.generate.return_value = LLMResponse(
            content="Fallback code generated.",
            role="coder",
            model="openrouter/free",
            provider="OpenRouter",
            latency_ms=150.0,
            success=True,
        )

        resp = self.router.generate(role="coder", messages=[{"role": "user", "content": "write code"}])
        self.assertTrue(resp.success)
        self.assertEqual(resp.content, "Fallback code generated.")
        self.assertEqual(resp.provider, "OpenRouter")
        self.assertGreaterEqual(self.mock_nvidia.generate.call_count, 1)
        self.mock_openrouter.generate.assert_called_once()

    def test_bounded_retries_does_not_loop_infinitely(self):
        """Verify that retries are strictly bounded by max_retries."""
        self.mock_nvidia.generate.return_value = LLMResponse(
            content="",
            role="fast",
            model="nvidia/nemotron-3.5-lightning-30b-a3b",
            provider="NVIDIA",
            latency_ms=50.0,
            success=False,
            error="Server error 503",
        )
        self.mock_openrouter.generate.return_value = LLMResponse(
            content="",
            role="fast",
            model="openrouter/free",
            provider="OpenRouter",
            latency_ms=50.0,
            success=False,
            error="Fallback timeout",
        )

        resp = self.router.generate(role="fast", messages=[{"role": "user", "content": "ping"}])
        self.assertFalse(resp.success)
        # Should call exactly max_retries for each provider
        self.assertEqual(self.mock_nvidia.generate.call_count, 2)
        self.assertEqual(self.mock_openrouter.generate.call_count, 2)

    def test_timeout_handling(self):
        """Verify that timeout errors return clean non-crashing responses."""
        self.mock_nvidia.generate.return_value = LLMResponse(
            content="",
            role="general",
            model="google/gemma-4-31b-it",
            provider="NVIDIA",
            latency_ms=10000.0,
            success=False,
            error="ReadTimeout: Request timed out after 10.0 seconds",
        )
        self.mock_openrouter.generate.return_value = LLMResponse(
            content="",
            role="general",
            model="openrouter/free",
            provider="OpenRouter",
            latency_ms=5000.0,
            success=False,
            error="ReadTimeout: Request timed out after 5.0 seconds",
        )

        resp = self.router.generate(role="general", messages=[{"role": "user", "content": "test"}])
        self.assertFalse(resp.success)
        self.assertIn("timed out", resp.error)

    def test_missing_credentials_handling(self):
        """Test behavior when no provider credentials are configured."""
        unconfigured_nvidia = NvidiaProvider(api_key="")
        unconfigured_openrouter = OpenRouterProvider(api_key="")
        router = ModelRouter(nvidia_provider=unconfigured_nvidia, openrouter_provider=unconfigured_openrouter)

        resp = router.generate(role="planner", messages=[{"role": "user", "content": "plan"}])
        self.assertFalse(resp.success)
        self.assertIn("No AI provider configured", resp.error)

    def test_secret_redaction(self):
        """Verify that live API keys are never exposed in error text or diagnostics."""
        leaked_msg = "Error 401 with key nvapi-abc123XYZ456 and token sk-or-v1-998877665544"
        clean_msg = redact_secrets(leaked_msg)
        self.assertNotIn("abc123XYZ456", clean_msg)
        self.assertNotIn("998877665544", clean_msg)
        self.assertIn("nvapi-***REDACTED***", clean_msg)
        self.assertIn("sk-or-***REDACTED***", clean_msg)

    def test_diagnostics_exposure(self):
        """Ensure get_diagnostics provides telemetry without exposing secrets."""
        diags = self.router.get_diagnostics()
        self.assertIsInstance(diags, list)
        self.assertGreaterEqual(len(diags), 1)
        for d in diags:
            self.assertIn("provider", d)
            self.assertIn("model", d)
            self.assertIn("role", d)
            self.assertIn("status", d)
            self.assertNotIn("api_key", d)
            self.assertNotIn("key", d)


class TestNvidiaProvider(unittest.TestCase):
    @patch("backend.core.llm.providers.nvidia_provider.OpenAI")
    def test_nemotron_extra_body_injection(self, mock_openai_cls):
        """Verify that Nemotron models receive thinking and reasoning budget parameters."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="Reasoned solution", reasoning_content=None))],
            usage=MagicMock(prompt_tokens=10, completion_tokens=25, total_tokens=35),
        )

        provider = NvidiaProvider(api_key="test-key-mock")
        resp = provider.generate(
            model="nvidia/nemotron-3.5-lightning-30b-a3b",
            messages=[{"role": "user", "content": "Solve puzzle"}],
        )

        self.assertTrue(resp.success)
        self.assertEqual(resp.content, "Reasoned solution")
        
        # Verify extra_body arguments passed
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        self.assertIn("extra_body", call_kwargs)
        self.assertTrue(call_kwargs["extra_body"]["chat_template_kwargs"]["enable_thinking"])
        self.assertEqual(call_kwargs["extra_body"]["reasoning_budget"], 16384)


class TestLiveIntegration(unittest.TestCase):
    @unittest.skipUnless(
        os.getenv("RUN_LIVE_AI_TESTS") == "1",
        "Skipping live integration test: Set RUN_LIVE_AI_TESTS=1 to run live network calls.",
    )
    def test_live_nvidia_call(self):
        """Optional integration check that runs only when a real NVIDIA_API_KEY is available."""
        provider = NvidiaProvider()
        fast_model = os.getenv("NVIDIA_FAST_MODEL", "nvidia/nemotron-3.5-lightning-30b-a3b")
        resp = provider.generate(
            model=fast_model,
            messages=[{"role": "user", "content": "Say 'hello' in one word."}],
            max_tokens=32,
            timeout=30.0,
        )
        self.assertTrue(resp.success)
        self.assertTrue(len(resp.content.strip()) > 0)


if __name__ == "__main__":
    unittest.main()
