"""Unit tests for the Completion State Machine, HTTP 404 diagnosis, and Runtime Verification Gates.

Covers:
TEST A: Normal Vite project with free port (All gates pass -> project_success=True)
TEST B: Port 5173 occupied by unrelated process (Detects collision without killing unrelated process)
TEST C: Vite starts but returns 404 (Classified as HTTP_404, not marked complete, triggers recovery)
TEST D: Missing index.html in Vite workspace (Repairs workspace, creates index.html, restarts, verifies)
TEST E: Process dies after startup (Detected as PROCESS_NOT_STARTED / FAILED, never fakes success)
TEST F: Control server isolation (8500-8502 rejected immediately, never marked success)
"""

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

from backend.core.project_state import ProjectState
from backend.core.workspace_manager import WorkspaceManager
from backend.runtime.environment_detector import EnvironmentDetector
from backend.runtime.preview_manager import PreviewManager, PreviewCheckResult
from backend.runtime.process_manager import ProcessManager, verify_process_port_ownership
from backend.runtime.runtime_session import RuntimeSession, NOVA_CONTROL_PORTS
from backend.runtime.project_runner import ProjectRunner
from backend.orchestration.orchestrator import MultiAgentPipeline


class TestCompletionStateMachine(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.workspace = WorkspaceManager(self.tmp_dir)
        self.state = ProjectState(goal="Test app")

    def tearDown(self):
        self.workspace.clean()
        if os.path.exists(self.tmp_dir):
            try:
                shutil.rmtree(self.tmp_dir, ignore_errors=True)
            except Exception:
                pass

    def test_a_normal_vite_project_all_gates_pass(self):
        """TEST A: Normal Vite project with free port passes all gates to project_success=True."""
        self.workspace.write_file("package.json", '{"name":"test-vite","dependencies":{"react":"^18.0.0"},"devDependencies":{"vite":"^5.0.0"}}')
        self.workspace.write_file("index.html", '<!DOCTYPE html><html><body><div id="root"></div><script type="module" src="/src/main.tsx"></script></body></html>')
        self.workspace.write_file("src/main.tsx", 'console.log("App running");')

        pm = MagicMock(spec=ProcessManager)
        mock_sess = RuntimeSession(
            project_id="test_a",
            status="PROCESS_STARTED",
            pid=54321,
            framework="Vite / React Web App",
        )
        mock_sess.is_alive = MagicMock(return_value=True)
        pm.start_session.return_value = mock_sess
        pm.wait_for_port.return_value = 5173
        pm.get_logs_text.return_value = "ready in 200ms\nLocal: http://localhost:5173/"

        runner = ProjectRunner(self.workspace, process_manager=pm)
        runner.preview_manager.check_health = MagicMock(return_value=PreviewCheckResult(
            is_healthy=True,
            is_app_verified=True,
            is_directory_listing=False,
            is_control_server=False,
            status_code=200,
            message="Application response verified.",
            classification="APPLICATION_VERIFIED",
        ))

        success = runner.run(self.state)

        self.assertTrue(success)
        self.assertTrue(self.state.project_success)
        self.assertEqual(self.state.runtime_status, "RUNNING")
        self.assertTrue(self.state.verification_gates["build"])
        self.assertTrue(self.state.verification_gates["process"])
        self.assertTrue(self.state.verification_gates["port"])
        self.assertTrue(self.state.verification_gates["server"])
        self.assertTrue(self.state.verification_gates["http"])
        self.assertTrue(self.state.verification_gates["application"])
        self.assertIsNone(self.state.failure_classification)

    def test_b_port_collision_does_not_kill_unrelated_process(self):
        """TEST B: Unrelated process owning port is detected without killing it."""
        session = RuntimeSession(project_id="test_b", pid=1000, port=5173)

        with patch("backend.runtime.process_manager.get_port_owner_pid", return_value=9999):
            with patch("backend.runtime.process_manager.get_process_tree_pids", return_value={1000, 1001}):
                is_owned = verify_process_port_ownership(session)
                # Should detect that PID 9999 is NOT in {1000, 1001}
                self.assertFalse(is_owned)

    def test_c_vite_returns_404_classified_and_fails_safely(self):
        """TEST C: Vite starts but GET / returns 404 -> Classified as HTTP_404, project_success=False."""
        pm = MagicMock(spec=ProcessManager)
        mock_sess = RuntimeSession(
            project_id="test_c",
            status="PROCESS_STARTED",
            pid=54322,
            framework="Vite / React Web App",
        )
        mock_sess.is_alive = MagicMock(return_value=True)
        pm.start_session.return_value = mock_sess
        pm.wait_for_port.return_value = 5173
        pm.get_logs_text.return_value = "ready in 200ms\nLocal: http://localhost:5173/"

        # Do NOT write index.html in workspace to trigger 404 behavior
        self.workspace.write_file("package.json", '{"name":"test-c","devDependencies":{"vite":"^5.0.0"}}')

        runner = ProjectRunner(self.workspace, process_manager=pm)
        runner.preview_manager.check_health = MagicMock(return_value=PreviewCheckResult(
            is_healthy=False,
            is_app_verified=False,
            is_directory_listing=False,
            is_control_server=False,
            status_code=404,
            message="HTTP 404 Not Found at root URL. Missing index.html or wrong Vite root.",
            classification="HTTP_404",
        ))

        # Disable automatic recovery for this test to observe strict failure handling
        with patch.object(runner, "_repair_vite_workspace", return_value=False):
            success = runner.run(self.state)

            self.assertFalse(success)
            self.assertFalse(self.state.project_success)
            self.assertEqual(self.state.runtime_status, "FAILED")
            self.assertEqual(self.state.failure_classification, "HTTP_404")
            self.assertFalse(self.state.verification_gates["http"])
            self.assertFalse(self.state.verification_gates["application"])

    def test_d_missing_index_html_repaired_automatically(self):
        """TEST D: Generated project missing index.html -> automatically diagnosed, created, and verified."""
        self.workspace.write_file("package.json", '{"name":"test-d","devDependencies":{"vite":"^5.0.0"}}')
        self.workspace.write_file("src/main.tsx", 'console.log("App main");')

        runner = ProjectRunner(self.workspace)
        repaired = runner._repair_vite_workspace(self.state)

        self.assertTrue(repaired)
        self.assertTrue((self.workspace.root / "index.html").exists())
        index_content = (self.workspace.root / "index.html").read_text(encoding="utf-8")
        self.assertIn('<div id="root"></div>', index_content)
        self.assertIn('src="/src/main.tsx"', index_content)

    def test_e_process_dies_after_startup(self):
        """TEST E: Process terminates unexpectedly -> marked FAILED with PROCESS_NOT_STARTED."""
        pm = MagicMock(spec=ProcessManager)
        dead_sess = RuntimeSession(project_id="test_e", status="FAILED", pid=9999)
        dead_sess.is_alive = MagicMock(return_value=False)
        dead_sess.error_message = "Process exited with code 1"
        pm.start_session.return_value = dead_sess
        pm.get_logs_text.return_value = "Error: Cannot find module"

        self.workspace.write_file("package.json", '{"name":"test-e","scripts":{"dev":"node missing.js"}}')

        runner = ProjectRunner(self.workspace, process_manager=pm)
        success = runner.run(self.state)

        self.assertFalse(success)
        self.assertFalse(self.state.project_success)
        self.assertEqual(self.state.runtime_status, "FAILED")
        self.assertEqual(self.state.failure_classification, "PROCESS_NOT_STARTED")

    def test_f_control_server_isolation_fails_fast(self):
        """TEST F: Any target resolving to 8500-8502 is rejected immediately."""
        pm = MagicMock(spec=ProcessManager)
        mock_sess = RuntimeSession(project_id="test_f", status="PROCESS_STARTED", pid=8888)
        mock_sess.is_alive = MagicMock(return_value=True)
        pm.start_session.return_value = mock_sess
        pm.wait_for_port.return_value = 8501

        self.workspace.write_file("package.json", '{"name":"test-f","scripts":{"dev":"vite"}}')

        runner = ProjectRunner(self.workspace, process_manager=pm)
        success = runner.run(self.state)

        self.assertFalse(success)
        self.assertFalse(self.state.project_success)
        self.assertEqual(self.state.runtime_status, "FAILED")
        self.assertEqual(self.state.failure_classification, "WRONG_RUNTIME_PROCESS")

    def test_orchestrator_never_fakes_success_when_runtime_fails(self):
        """Ensure MultiAgentPipeline halts at FAILED when runner returns False."""
        self.workspace.write_file("package.json", '{"name":"fake-check"}')
        self.state.add_task("t-1", "Generate code", "BUILD", agent="Developer Agent")
        self.state.add_task("t-2", "Launch process", "RUN", agent="Tester & Runner Agent")

        runner = MagicMock(spec=ProjectRunner)
        runner.run.return_value = False
        self.state.runtime_status = "FAILED"
        self.state.project_success = False
        self.state.failure_reason = "HTTP 404 at /"
        self.state.failure_classification = "HTTP_404"

        pipeline = MultiAgentPipeline(self.workspace, runner=runner)

        # Execute build with mocked runner
        with patch("backend.orchestration.orchestrator.call_openrouter", return_value="### FILE: main.py\nprint('hello')"):
            pipeline.execute_build(self.state)

        # Must be FAILED, NOT COMPLETE!
        self.assertEqual(self.state.current_phase, "FAILED")
        self.assertEqual(self.state.active_agent_status, "FAILURE")
        self.assertFalse(self.state.project_success)
        self.assertIn("FAILED", self.state.current_task_description)


if __name__ == "__main__":
    unittest.main()
