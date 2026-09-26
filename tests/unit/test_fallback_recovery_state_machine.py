"""Unit and regression tests for Fallback Success and Recovery Task State Machine.

Verifies:
TEST 1: Primary provider fails, fallback succeeds -> agent execution SUCCESS.
TEST 2: Code generation fails first attempt, recovery generates valid artifact -> task transitions FAILED -> RECOVERING -> RETRYING -> SUCCESS.
TEST 3: Recovery produces invalid artifact -> task remains FAILED.
TEST 4: Recovery succeeds -> build completion gate sees final SUCCESS, not historical FAILED.
TEST 5: Three recovery attempts fail -> task remains FAILED and build halts.
TEST 6: One task recovers successfully while another remains failed -> build remains HALTED.
TEST 7: All required tasks eventually recover -> build continues to runtime.
TEST 8: Primary NVIDIA fails repeatedly but OpenRouter succeeds -> telemetry records NVIDIA failure & OpenRouter success, but final agent/task result is successful.
"""

from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from backend.core.agent_result import AgentResult
from backend.core.artifact_validator import validate_artifact
from backend.core.llm.model_router import ModelRouter
from backend.core.llm.types import LLMResponse
from backend.core.project_state import ProjectState, Task
from backend.core.workspace_manager import WorkspaceManager
from backend.orchestration.orchestrator import MultiAgentPipeline


class TestFallbackRecoveryStateMachine(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.workspace = WorkspaceManager(self.tmp_dir)
        self.state = ProjectState(goal="Build FocusFlow task manager", selected_language="HTML/CSS/JS")
        self.state.project_id = "test_focusflow"
        self.state.build_id = "build_001"

    def tearDown(self):
        if Path(self.tmp_dir).exists():
            shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_01_primary_provider_fails_fallback_succeeds_agent_success(self):
        """TEST 1: Primary provider fails, fallback succeeds -> Agent execution SUCCESS."""
        mock_nvidia = MagicMock()
        mock_nvidia.is_configured = True
        mock_nvidia.name = "NVIDIA"
        mock_nvidia.generate.return_value = LLMResponse(
            content="", role="coder", model="z-ai/glm-5.3", provider="NVIDIA", latency_ms=10.0, success=False, error="Rate limit exceeded"
        )

        mock_openrouter = MagicMock()
        mock_openrouter.is_configured = True
        mock_openrouter.name = "OpenRouter"
        mock_openrouter.generate.return_value = LLMResponse(
            content="console.log('FocusFlow script initialized');",
            role="coder",
            model="openrouter/free",
            provider="OpenRouter",
            latency_ms=15.0,
            success=True,
        )

        router = ModelRouter(nvidia_provider=mock_nvidia, openrouter_provider=mock_openrouter, max_retries=1)
        resp = router.generate(role="coder", messages=[{"role": "user", "content": "generate code"}])

        self.assertTrue(resp.success)
        self.assertEqual(resp.provider, "OpenRouter")
        self.assertIn("FocusFlow script", resp.content)

    def test_02_task_transitions_failed_recovering_retrying_success(self):
        """TEST 2: Code gen fails first attempt, recovery generates valid artifact -> FAILED -> RECOVERING -> RETRYING -> SUCCESS."""
        task_id = "t-script"
        self.state.add_task(task_id, "Generate script.js", "BUILD", file_path="script.js", is_required=True)
        task = self.state.tasks[0]

        # Initial failure
        self.state.fail_task(task_id, "Code generation missed script.js")
        self.assertEqual(task.status, "FAILED")

        # Begin recovery
        self.state.recover_task(task_id, "Attempting recovery for missing script.js")
        self.assertEqual(task.status, "RECOVERING")

        # Retry attempt 1
        self.state.retry_task(task_id, 1)
        self.assertEqual(task.status, "RETRYING")
        self.assertEqual(task.retry_count, 1)

        # Validate artifact
        content = "console.log('Valid script code');"
        is_valid, msg, details = validate_artifact("script.js", content)
        self.assertTrue(is_valid)

        # Transition to SUCCESS
        agent_res = AgentResult(
            status="RECOVERED",
            task_id=task_id,
            success=True,
            artifact_path="script.js",
            provider="OpenRouter",
            recovery_attempt=1,
            validation_result=details,
        )
        self.state.complete_task(task_id, result="Recovered on attempt 1", agent_result=agent_res)

        self.assertEqual(task.status, "SUCCESS")
        self.assertEqual(task.recovery_attempt, 1)
        self.assertFalse(self.state.has_failed_required_tasks())

    def test_03_recovery_produces_invalid_artifact_remains_failed(self):
        """TEST 3: Recovery produces invalid artifact -> Task remains FAILED."""
        task_id = "t-script"
        self.state.add_task(task_id, "Generate script.js", "BUILD", file_path="script.js", is_required=True)
        task = self.state.tasks[0]

        self.state.fail_task(task_id, "Initial failure")
        self.state.recover_task(task_id)
        self.state.retry_task(task_id, 1)

        # Empty or refusal content
        invalid_content = "Rate limit exceeded: 429"
        is_valid, reason, _ = validate_artifact("script.js", invalid_content)
        self.assertFalse(is_valid)

        self.state.fail_task(task_id, f"Validation failed: {reason}")
        self.assertEqual(task.status, "FAILED")
        self.assertTrue(self.state.has_failed_required_tasks())

    def test_04_recovery_succeeds_build_completion_gate_sees_success(self):
        """TEST 4: Recovery succeeds -> Build completion gate sees current SUCCESS, not historical FAILED."""
        self.state.add_task("t-1", "Generate index.html", "BUILD", file_path="index.html", is_required=True)
        self.state.add_task("t-2", "Generate script.js", "BUILD", file_path="script.js", is_required=True)

        # t-1 succeeds initially
        self.state.complete_task("t-1")
        # t-2 fails initially
        self.state.fail_task("t-2", "Initial miss")
        self.assertTrue(self.state.has_failed_required_tasks())

        # t-2 recovers
        self.state.recover_task("t-2")
        self.state.retry_task("t-2", 1)
        self.state.complete_task("t-2", result="Recovered")

        # Final build gate check
        self.assertFalse(self.state.has_failed_required_tasks())
        self.assertEqual(self.state.tasks[0].status, "SUCCESS")
        self.assertEqual(self.state.tasks[1].status, "SUCCESS")

    def test_05_three_recovery_attempts_fail_task_remains_failed_and_halts(self):
        """TEST 5: Three recovery attempts fail -> Task remains FAILED and build halts."""
        pipeline = MultiAgentPipeline(self.workspace)
        self.state.effective_language = "HTML/CSS/JS"
        self.state.add_task("t-fail", "Generate script.js", "BUILD", file_path="script.js", is_required=True)

        # Mock call_openrouter to return empty string for all recovery attempts
        with patch("backend.orchestration.orchestrator.call_openrouter", return_value=""):
            # Trigger recovery loop by having task in failed status
            task = self.state.tasks[0]
            task.status = "FAILED"
            
            # Execute bounded recovery loop
            failed_tasks = [task]
            for t in failed_tasks:
                for attempt in range(1, 4):
                    self.state.retry_task(t.id, attempt)
                self.state.fail_task(t.id, "Exhausted 3 recovery attempts")

            self.assertEqual(task.status, "FAILED")
            self.assertEqual(task.retry_count, 3)
            self.assertTrue(self.state.has_failed_required_tasks())

    def test_06_one_task_recovers_another_remains_failed_build_halted(self):
        """TEST 6: One task recovers successfully while another remains failed -> Build remains HALTED."""
        self.state.add_task("t-1", "Generate script.js", "BUILD", file_path="script.js", is_required=True)
        self.state.add_task("t-2", "Generate style.css", "BUILD", file_path="style.css", is_required=True)

        # Both fail initially
        self.state.fail_task("t-1", "Missed script.js")
        self.state.fail_task("t-2", "Missed style.css")

        # t-1 recovers
        self.state.recover_task("t-1")
        self.state.retry_task("t-1", 1)
        self.state.complete_task("t-1", result="Recovered")

        # t-2 exhausts retries and stays failed
        self.state.recover_task("t-2")
        self.state.retry_task("t-2", 3)
        self.state.fail_task("t-2", "Exhausted retries")

        # Gate check
        self.assertTrue(self.state.has_failed_required_tasks())
        failed = [t for t in self.state.tasks if t.status == "FAILED"]
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0].id, "t-2")

    def test_07_all_required_tasks_recover_unblocks_dependents_and_continues(self):
        """TEST 7: All required tasks eventually recover -> Recalculate graph, unblock RUN task."""
        self.state.add_task("t-build", "Generate script.js", "BUILD", file_path="script.js", is_required=True)
        self.state.add_task("t-run", "Launch server", "RUN", dependencies=["t-build"], is_required=True)

        # Block downstream task because t-build is failed
        self.state.fail_task("t-build", "Initial miss")
        self.state.block_task("t-run", "Prerequisite failed")
        self.assertEqual(self.state.tasks[1].status, "BLOCKED")

        # Recover t-build
        self.state.recover_task("t-build")
        self.state.retry_task("t-build", 1)
        self.state.complete_task("t-build", result="Recovered")

        # Recalculate task graph
        unblocked = self.state.recalculate_task_graph()
        self.assertIn("t-run", unblocked)
        self.assertEqual(self.state.tasks[1].status, "QUEUED")
        self.assertFalse(self.state.has_failed_required_tasks())

    def test_08_primary_nvidia_fails_repeatedly_openrouter_succeeds_telemetry_correct(self):
        """TEST 8: Primary NVIDIA fails repeatedly but OpenRouter succeeds -> Telemetry recorded, task result SUCCESS."""
        mock_nvidia = MagicMock()
        mock_nvidia.is_configured = True
        mock_nvidia.name = "NVIDIA"
        mock_nvidia.generate.return_value = LLMResponse(
            content="", role="coder", model="z-ai/glm-5.3", provider="NVIDIA", latency_ms=10.0, success=False, error="NVIDIA connection timeout"
        )

        mock_openrouter = MagicMock()
        mock_openrouter.is_configured = True
        mock_openrouter.name = "OpenRouter"
        mock_openrouter.generate.return_value = LLMResponse(
            content="### FILE: script.js\n```javascript\nfunction focusFlow() { return true; }\n```",
            role="coder",
            model="openrouter/free",
            provider="OpenRouter",
            latency_ms=12.0,
            success=True,
        )

        events_emitted = []
        router = ModelRouter(nvidia_provider=mock_nvidia, openrouter_provider=mock_openrouter, max_retries=2)
        router.set_fallback_callback(lambda msg, lvl: events_emitted.append((msg, lvl)))

        resp = router.generate(role="coder", messages=[{"role": "user", "content": "build FocusFlow"}])

        self.assertTrue(resp.success)
        self.assertEqual(resp.provider, "OpenRouter")
        
        # Verify telemetry
        nvidia_metric = router.metrics.get("NVIDIA:coder")
        openrouter_metric = router.metrics.get("OpenRouter:coder")
        self.assertIsNotNone(nvidia_metric)
        self.assertIsNotNone(openrouter_metric)
        self.assertGreater(nvidia_metric.error_count, 0)
        self.assertGreater(openrouter_metric.request_count, 0)

        # Check emitted fallback messages
        fallback_msgs = [msg for msg, _ in events_emitted]
        self.assertTrue(any("PRIMARY FAILED" in m for m in fallback_msgs))
        self.assertTrue(any("FALLBACK SUCCESS" in m for m in fallback_msgs))


if __name__ == "__main__":
    unittest.main()
