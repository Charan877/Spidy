"""Integration tests for SPIDY Server Resume, Restart Reconciliation, and Recovery Architecture."""

import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch, MagicMock
import uuid
from starlette.testclient import TestClient

from backend.core.project_state import ProjectState, Task
from backend.database.database_manager import DatabaseManager
from backend.core.workspace_manager import WorkspaceManager
import server


class TestServerResumeAndRecovery(unittest.TestCase):
    """Test suite verifying robust execution, startup reconciliation, and project resumption."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(server.app)

    def test_project_state_fail_and_interrupt(self):
        """ProjectState.fail and ProjectState.interrupt must update state cleanly without error."""
        st = ProjectState(goal="Build API", selected_language="Python")
        st.is_running = True
        st.current_phase = "BUILD"
        st.project_state = "BUILDING"

        # 1. Test fail()
        st.fail("Compilation syntax error", classification="SYNTAX_ERROR")
        self.assertFalse(st.is_running)
        self.assertEqual(st.current_phase, "FAILED")
        self.assertEqual(st.project_state, "FAILED")
        self.assertEqual(st.failure_classification, "SYNTAX_ERROR")
        self.assertEqual(st.failure_reason, "Compilation syntax error")
        self.assertIn("Compilation syntax error", st.errors)

        # 2. Test interrupt()
        st.is_running = True
        st.interrupt("Server restarted during execution")
        self.assertFalse(st.is_running)
        self.assertEqual(st.current_phase, "FAILED")
        self.assertEqual(st.project_state, "FAILED")
        self.assertEqual(st.failure_classification, "EXECUTION_INTERRUPTED")
        self.assertIn("Server restarted during execution", st.failure_reason)

    def test_server_startup_reconciliation_cleans_orphaned_builds(self):
        """reconcile_startup_state must transition dead/orphaned in-progress builds to INTERRUPTED."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            test_db_path = Path(tmp_dir) / "test_reconcile.db"
            db_mgr = DatabaseManager(test_db_path)
            db_mgr.initialize()

            # Seed an orphaned build
            pid = "proj_test_orphan_01"
            bid = "bld_test_orphan_01"
            db_mgr.sync_project_and_build_start(
                project_id=pid,
                project_name="Orphaned Test Project",
                build_id=bid,
                requirement="Build app that was interrupted by crash",
                detected_stack="FastAPI",
                workspace_path=str(tmp_dir),
            )

            # Confirm it's recorded as in-progress
            in_prog = db_mgr.builds.get_in_progress_builds()
            self.assertEqual(len(in_prog), 1)
            self.assertEqual(in_prog[0]["build_id"], bid)

            # Run reconciliation
            mock_runner = MagicMock()
            mock_pipeline = MagicMock()
            temp_state = ProjectState()
            server.reconcile_startup_state(db_mgr, mock_runner, mock_pipeline, temp_state)

            # Verify in-progress builds are now 0 and build is marked INTERRUPTED
            after_prog = db_mgr.builds.get_in_progress_builds()
            self.assertEqual(len(after_prog), 0)

            build_record = db_mgr.builds.get_build(bid)
            self.assertEqual(build_record["status"], "INTERRUPTED")
            self.assertIsNotNone(build_record["failure_reason"])

    def test_api_resume_project_restores_context_and_tasks(self):
        """POST /api/projects/{id}/resume must reconstruct real state, tasks, and gates."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            test_tag = uuid.uuid4().hex[:6]
            proj_id = f"proj_test_resume_{test_tag}"
            build_id = f"bld_test_resume_{test_tag}"

            # Create a mock project workspace with real files
            proj_ws = WorkspaceManager.for_project(proj_id)
            proj_ws.write_file("main.py", "print('hello world')")
            proj_ws.write_file("README.md", "# Test Project\nFunctional documentation")

            db_mgr = server.db_manager
            db_mgr.sync_project_and_build_start(
                project_id=proj_id,
                project_name="Resume Test App",
                build_id=build_id,
                requirement="Build and resume a verified project",
                detected_stack="Python",
                workspace_path=str(proj_ws.root),
            )
            db_mgr.sync_verification_gate(build_id, "build", "PASSED", "All files built")
            db_mgr.sync_build_finish(
                build_id=build_id,
                project_id=proj_id,
                status="COMPLETED",
                final_result="Success",
            )

            # Invoke resume endpoint
            res = self.client.post(f"/api/projects/{proj_id}/resume")
            self.assertEqual(res.status_code, 200)

            # Inspect state
            with server.state_lock:
                self.assertEqual(server.state.project_id, proj_id)
                self.assertEqual(server.state.build_id, build_id)
                self.assertEqual(server.state.current_phase, "COMPLETE")
                self.assertTrue(server.state.project_success)
                self.assertIn("main.py", server.state.files)
                self.assertIn("README.md", server.state.files)
                # Tasks must be reconstructed from workspace files rather than wiped to []
                self.assertGreaterEqual(len(server.state.tasks), 2)
                task_files = [t.file_path for t in server.state.tasks if t.file_path]
                self.assertIn("main.py", task_files)

    def test_is_safe_to_reclaim_process_protects_system(self):
        """is_safe_to_reclaim_process must NEVER allow killing PID 0, 4, or current server PID."""
        self.assertFalse(server.is_safe_to_reclaim_process(0))
        self.assertFalse(server.is_safe_to_reclaim_process(4))
        self.assertFalse(server.is_safe_to_reclaim_process(os.getpid()))

    def test_ui_status_differentiation_failed_vs_interrupted(self):
        """UI components must distinguish between genuine INTERRUPTED state and other FAILURE states."""
        from backend.ui.components import render_minimal_nav

        # Case 1: Interrupted
        st_interrupted = ProjectState()
        st_interrupted.current_phase = "FAILED"
        st_interrupted.failure_classification = "EXECUTION_INTERRUPTED"

        def columns_side_effect(spec, *args, **kwargs):
            count = len(spec) if isinstance(spec, (list, tuple)) else int(spec)
            return tuple(MagicMock() for _ in range(count))

        with patch("streamlit.columns", side_effect=columns_side_effect):
            with patch("streamlit.markdown") as mock_md:
                render_minimal_nav(None, st_interrupted, True, "model")
                found_interrupted = False
                for call in mock_md.call_args_list:
                    rendered_text = str(call)
                    if "INTERRUPTED" in rendered_text:
                        found_interrupted = True
                        break
                self.assertTrue(found_interrupted, "Should display INTERRUPTED when classification is EXECUTION_INTERRUPTED")

        # Case 2: Failed due to syntax/runtime error
        st_failed = ProjectState()
        st_failed.current_phase = "FAILED"
        st_failed.failure_classification = "SYNTAX_ERROR"

        with patch("streamlit.columns", side_effect=columns_side_effect):
            with patch("streamlit.markdown") as mock_md:
                render_minimal_nav(None, st_failed, True, "model")
                found_failed = False
                for call in mock_md.call_args_list:
                    rendered_text = str(call)
                    if "FAILED" in rendered_text:
                        found_failed = True
                        break
                self.assertTrue(found_failed, "Should display FAILED when classification is SYNTAX_ERROR")

    def test_websocket_disconnect_and_reconnect_preserves_build_state(self):
        """WebSocket client disconnection must NEVER cancel or interrupt an active build."""
        with server.state_lock:
            server.state.is_running = True
            server.state.current_phase = "BUILD"
            server.state.project_state = "BUILDING"
            server.state.build_id = "bld_ws_test_01"

        # Connect WebSocket and receive initial state
        with self.client.websocket_connect("/ws") as ws:
            data = ws.receive_json()
            self.assertEqual(data.get("type"), "STATE_UPDATE")
            self.assertTrue(data.get("state", {}).get("is_running"))
            self.assertEqual(data.get("state", {}).get("build_id"), "bld_ws_test_01")

        # After WebSocket disconnect context exits, build state must remain RUNNING!
        with server.state_lock:
            self.assertTrue(server.state.is_running, "Build must remain running after WebSocket disconnect")
            self.assertEqual(server.state.current_phase, "BUILD")
            self.assertEqual(server.state.project_state, "BUILDING")

        # Reconnecting WebSocket gets the running state intact
        with self.client.websocket_connect("/ws") as ws2:
            data2 = ws2.receive_json()
            self.assertEqual(data2.get("type"), "STATE_UPDATE")
            self.assertTrue(data2.get("state", {}).get("is_running"))
            self.assertEqual(data2.get("state", {}).get("build_id"), "bld_ws_test_01")

        # Clean up
        with server.state_lock:
            server.state.is_running = False

    def test_pipeline_failure_is_strictly_classified_and_never_interrupted(self):
        """Under no circumstances should an agent error, exception, or runtime verification failure become INTERRUPTED."""
        st = ProjectState()
        st.is_running = True
        st.fail("Runtime test suite failed", classification="TEST_FAILURE")
        self.assertEqual(st.current_phase, "FAILED")
        self.assertEqual(st.project_state, "FAILED")
        self.assertEqual(st.failure_classification, "TEST_FAILURE")
        self.assertNotEqual(st.failure_classification, "EXECUTION_INTERRUPTED")

    def test_generation_gate_scoping_ignores_downstream_task_statuses(self):
        """Generation Gate must only evaluate BUILD phase tasks, not downstream RUN or TEST tasks."""
        st = ProjectState()
        st.build_id = "bld_gate_test_01"
        st.add_task("t-1", "Generate main.py", "BUILD", is_required=True, build_id="bld_gate_test_01")
        st.complete_task("t-1")
        st.add_task("t-run", "Launch server", "RUN", is_required=True, build_id="bld_gate_test_01")
        st.fail_task("t-run", "Runtime failure from previous cycle")

        # Scoped to BUILD: must be False
        self.assertFalse(st.has_failed_required_tasks(phase="BUILD"))
        # Unscoped: checks all phases, returns True
        self.assertTrue(st.has_failed_required_tasks())

    def test_process_manager_wait_for_port_does_not_return_prematurely_when_unbound(self):
        """wait_for_port must not immediately return an explicit port if no process is listening."""
        from backend.runtime.process_manager import ProcessManager
        from backend.runtime.runtime_session import RuntimeSession

        pm = ProcessManager()
        # Create a mock session with an explicit port that is definitely not listening
        session = RuntimeSession(
            command=["mock"],
            cwd=".",
            port=59999,
        )
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None  # Process is alive
        session.process = mock_proc
        session.pid = 999999

        # wait_for_port with short timeout must timeout and return None, NOT return 59999 immediately
        start_t = time.time()
        detected = pm.wait_for_port(session, timeout=0.6)
        elapsed = time.time() - start_t

        self.assertIsNone(detected, "Must return None when port is not actually listening")
        self.assertGreaterEqual(elapsed, 0.4, "Must wait rather than returning instantly")


if __name__ == "__main__":
    unittest.main()
