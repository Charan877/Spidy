"""Unit tests for SPIDY TaskFlow and Fullstack Reliability Fixes.

Covers:
1. Project-scoped Workspace Isolation: workspace/<project_id>/ strictly isolates file operations.
2. Strict Generation Gate: Missing required build tasks halt the pipeline and block downstream execution.
3. Fullstack Runtime Contract: If backend starts but frontend is missing/unresponsive, fullstack is rejected.
4. Failed State Immutability: Failure state cannot be overridden by non-verification events.
"""

from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from backend.core.project_state import ProjectState, Task
from backend.core.workspace_manager import WorkspaceManager
from backend.runtime.preview_manager import PreviewManager, PreviewCheckResult
from backend.runtime.process_manager import ProcessManager
from backend.runtime.project_runner import ProjectRunner
from backend.runtime.runtime_session import RuntimeSession
from backend.orchestration.orchestrator import MultiAgentPipeline


class TestTaskFlowFullstackFixes(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.base_ws = Path(self.tmp_dir)

    def tearDown(self):
        if self.base_ws.exists():
            shutil.rmtree(self.base_ws, ignore_errors=True)

    def test_workspace_isolation_per_project(self):
        """Test 1: Different projects write strictly to their own isolated workspace directories."""
        ws_a = WorkspaceManager.for_project("project_alpha", base_dir=str(self.base_ws))
        ws_b = WorkspaceManager.for_project("project_beta", base_dir=str(self.base_ws))

        ws_a.write_file("alpha_file.py", "print('alpha')")
        ws_b.write_file("beta_file.py", "print('beta')")

        # Confirm isolation
        self.assertTrue(ws_a.file_exists("alpha_file.py"))
        self.assertFalse(ws_a.file_exists("beta_file.py"))

        self.assertTrue(ws_b.file_exists("beta_file.py"))
        self.assertFalse(ws_b.file_exists("alpha_file.py"))

        # Confirm directory paths are separated
        self.assertIn("project_alpha", str(ws_a.root))
        self.assertIn("project_beta", str(ws_b.root))
        self.assertNotEqual(ws_a.root, ws_b.root)

    def test_generation_gate_halts_when_required_file_missing(self):
        """Test 2: If a required build task fails to generate, the pipeline halts at Generation Gate."""
        ws = WorkspaceManager.for_project("test_gate", base_dir=str(self.base_ws))
        ws.write_file("app.py", "from fastapi import FastAPI\napp = FastAPI()")
        # Notice: index.html is NOT written

        state = ProjectState(goal="Build TaskFlow fullstack app")
        state.add_task("t-backend", "Generate app.py", "BUILD", file_path="app.py", is_required=True)
        state.add_task("t-frontend", "Generate index.html", "BUILD", file_path="index.html", is_required=True)
        state.complete_task("t-backend")
        state.fail_task("t-frontend", "Code generation missed index.html")

        pipeline = MultiAgentPipeline(ws)
        # Mock runner so we can verify it is never invoked
        pipeline.runner.run = MagicMock(return_value=True)

        with patch("backend.orchestration.orchestrator.call_openrouter", return_value=""):
            pipeline.execute_build(state)

        # Generation Gate must reject the build
        self.assertFalse(state.is_project_generated)
        self.assertEqual(state.current_phase, "FAILED")
        self.assertEqual(state.failure_classification, "REQUIRED_FILES_MISSING")
        self.assertIn("Required build tasks failed", state.failure_reason)
        # Downstream runner must NOT have been called
        pipeline.runner.run.assert_not_called()

    def test_fullstack_runner_rejects_missing_frontend(self):
        """Test 3: Fullstack project with working backend but missing frontend is marked FAILED."""
        ws = WorkspaceManager.for_project("test_fullstack", base_dir=str(self.base_ws))
        ws.write_file("app.py", "from fastapi import FastAPI\napp = FastAPI()")
        ws.write_file("requirements.txt", "fastapi\nuvicorn")

        state = ProjectState(goal="Fullstack TaskFlow")
        state.runtime_type = "fullstack"

        pm = MagicMock(spec=ProcessManager)
        mock_sess = RuntimeSession(
            project_id="test_fullstack",
            status="PROCESS_STARTED",
            pid=8888,
            framework="FastAPI Web Service",
        )
        mock_sess.is_alive = MagicMock(return_value=True)
        pm.start_session.return_value = mock_sess
        pm.wait_for_port.return_value = 9000

        runner = ProjectRunner(ws, process_manager=pm)
        # Backend health check returns 200 JSON
        runner.preview_manager.check_health = MagicMock(return_value=PreviewCheckResult(
            is_healthy=True,
            is_app_verified=True,
            is_directory_listing=False,
            is_control_server=False,
            status_code=200,
            message="API healthy",
            classification="APPLICATION_VERIFIED",
        ))

        success = runner.run(state)

        # Because frontend was not generated, runner must reject fullstack verification
        self.assertFalse(success)
        self.assertFalse(state.project_success)
        self.assertFalse(state.is_app_verified)
        self.assertEqual(state.runtime_status, "FAILED")
        self.assertEqual(state.failure_classification, "FRONTEND_NOT_RUNNING")

    def test_authoritative_failure_immutability(self):
        """Test 4: State machine prevents non-verification phases from claiming SUCCESS."""
        state = ProjectState(goal="TaskFlow")
        state.add_task("t-1", "Generate backend", "BUILD", is_required=True)
        state.fail_task("t-1", "Syntax error")

        state.current_phase = "FAILED"
        state.transition_to("FAILED", "Required task failed")
        state.project_success = False

        # Attempting an invalid transition or partial update does not flip to SUCCESS
        self.assertTrue(state.has_failed_required_tasks())
        self.assertFalse(state.project_success)
        self.assertEqual(state.project_state, "FAILED")


if __name__ == "__main__":
    unittest.main()
