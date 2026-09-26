"""Unit and integration tests for dynamic port discovery and runtime preview isolation.

Covers:
1. NOVA control port isolation (8500-8502)
2. Dev server stdout parsing with auto-incrementing in-use ports (e.g. Vite 5173->5176)
3. Diverse framework log patterns and ANSI sequence handling
4. ProcessManager.wait_for_port() polling and fallback discovery
5. Process crash detection and status handling
6. Clean process termination and PID tree cleanup
7. PreviewManager verification of HTML vs Directory Listing / Streamlit UI
8. ProjectRunner end-to-end 5-step verification lifecycle
"""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

from backend.core.project_state import ProjectState
from backend.core.workspace_manager import WorkspaceManager
from backend.runtime.environment_detector import EnvironmentDetector, find_free_port
from backend.runtime.preview_manager import PreviewManager, PreviewCheckResult
from backend.runtime.process_manager import ProcessManager, discover_ports_by_pid
from backend.runtime.runtime_session import RuntimeSession, NOVA_CONTROL_PORTS
from backend.runtime.project_runner import ProjectRunner


class TestPortDetectionAndRuntimeIsolation(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.workspace = WorkspaceManager(self.tmp_dir)
        self.state = ProjectState(goal="Test web app")

    def tearDown(self):
        self.workspace.clean()
        if os.path.exists(self.tmp_dir):
            try:
                import shutil
                shutil.rmtree(self.tmp_dir, ignore_errors=True)
            except Exception:
                pass

    def test_1_control_port_isolation(self):
        """Ensure NOVA control ports (8500, 8501, 8502) are never assigned or accepted as project ports."""
        # 1. find_free_port starting in 8500 must skip 8500, 8501, 8502
        allocated_port = find_free_port(8500)
        self.assertNotIn(allocated_port, NOVA_CONTROL_PORTS)

        # 2. Static server range in EnvironmentDetector must not touch 8500-8502
        self.workspace.write_file("index.html", "<h1>Hello</h1>")
        config = EnvironmentDetector.detect(self.workspace)
        if config.get("port"):
            self.assertNotIn(config["port"], NOVA_CONTROL_PORTS)
            self.assertGreaterEqual(config["port"], 9000)

        # 3. PreviewManager must immediately reject control ports without making HTTP requests
        for ctrl_port in NOVA_CONTROL_PORTS:
            res = PreviewManager.check_health(f"http://localhost:{ctrl_port}")
            self.assertTrue(res.is_control_server)
            self.assertFalse(res.is_healthy)
            self.assertFalse(res.is_app_verified)

    def test_2_vite_port_auto_increment_capture(self):
        """Ensure Vite auto-incrementing occupied ports (5173..5176) resolves to the final bound port 5177."""
        session = RuntimeSession(project_id="test_vite", framework="Vite / React Web App")

        vite_stdout_stream = [
            "  VITE v5.4.2  ready in 210 ms",
            "Port 5173 is in use, trying another one...",
            "Port 5174 is in use, trying another one...",
            "Port 5175 is in use, trying another one...",
            "Port 5176 is in use, trying another one...",
            "",
            "  ➜  Local:   http://localhost:5177/",
            "  ➜  Network: use --host to expose",
            "  ➜  press h + enter to show help",
        ]

        for line in vite_stdout_stream:
            session.add_stdout(line)

        # Occupied ports list should record 5173, 5174, 5175, 5176
        self.assertEqual(session.occupied_ports_seen, [5173, 5174, 5175, 5176])

        # Final detected port must be 5177, NOT 5173 or 5176
        self.assertEqual(session.port, 5177)
        self.assertEqual(session.url, "http://localhost:5177")
        self.assertEqual(session.status, "PORT_DETECTED")

    def test_3_various_framework_stdout_patterns(self):
        """Ensure regex parsing handles Next.js, CRA, Express, Flask, and ANSI sequences."""
        test_cases = [
            # Next.js
            ("- ready on http://localhost:3000", 3000),
            # Create React App with ANSI escapes
            ("\x1b[32mCompiled successfully!\x1b[39m\n  http://localhost:3002/", 3002),
            # Express / Node
            ("Server listening on port 4000", 4000),
            # Python Flask
            (" * Running on http://127.0.0.1:5000 (Press CTRL+C to quit)", 5000),
            # Vite default
            ("  ➜  Local:   http://localhost:5173/", 5173),
        ]

        for line, expected_port in test_cases:
            sess = RuntimeSession(project_id="test_framework")
            sess.add_stdout(line)
            self.assertEqual(sess.port, expected_port, f"Failed for line: {line}")
            self.assertEqual(sess.url, f"http://localhost:{expected_port}")

    def test_4_wait_for_port_polling(self):
        """Ensure ProcessManager.wait_for_port polls until dev server logs the port."""
        pm = ProcessManager()
        session = RuntimeSession(project_id="test_poll")
        # Mock session alive
        session.is_alive = MagicMock(return_value=True)

        def delayed_log():
            time.sleep(0.3)
            session.add_stdout("  ➜  Local:   http://localhost:5180/")

        threading.Thread(target=delayed_log, daemon=True).start()

        detected = pm.wait_for_port(session, timeout=3.0)
        self.assertEqual(detected, 5180)
        self.assertEqual(session.port, 5180)

    def test_5_process_crash_detection(self):
        """Ensure process crash or immediate exit updates status to FAILED or STOPPED."""
        sess = RuntimeSession(project_id="test_crash", status="STARTING")

        # Fake process that terminated with exit code 1
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 1
        mock_proc.returncode = 1
        sess.process = mock_proc

        alive = sess.is_alive()
        self.assertFalse(alive)
        self.assertEqual(sess.status, "FAILED")

    def test_6_session_termination_and_tree_kill(self):
        """Ensure session terminate kills the spawned process and clears state."""
        # Launch lightweight python process
        proc = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(10)"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        session = RuntimeSession(project_id="test_term", process=proc, pid=proc.pid, status="RUNNING")
        self.assertTrue(session.is_alive())

        session.terminate()
        time.sleep(0.5)

        self.assertFalse(session.is_alive())
        self.assertEqual(session.status, "STOPPED")
        if proc.stdout:
            proc.stdout.close()
        if proc.stderr:
            proc.stderr.close()

    def test_7_preview_manager_html_validation(self):
        """Ensure PreviewManager flags directory listing and Streamlit controls, and accepts valid apps."""
        # Directory listing body
        dir_listing_html = "<!DOCTYPE html><html><head><title>Directory listing for /</title></head><body><h1>Directory listing for /</h1></body></html>"
        with patch("urllib.request.urlopen") as mock_url:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.read.return_value = dir_listing_html.encode("utf-8")
            mock_resp.__enter__.return_value = mock_resp
            mock_url.return_value = mock_resp

            res = PreviewManager.check_health("http://localhost:9005")
            self.assertTrue(res.is_directory_listing)
            self.assertFalse(res.is_app_verified)

        # Streamlit control UI body
        streamlit_html = "<!DOCTYPE html><html><head><title>Streamlit</title></head><body><div id='stApp'></div></body></html>"
        with patch("urllib.request.urlopen") as mock_url:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.read.return_value = streamlit_html.encode("utf-8")
            mock_resp.__enter__.return_value = mock_resp
            mock_url.return_value = mock_resp

            res = PreviewManager.check_health("http://localhost:9006")
            self.assertTrue(res.is_control_server)
            self.assertFalse(res.is_app_verified)

        # Valid Application HTML body
        valid_app_html = "<!DOCTYPE html><html><head><title>React App</title></head><body><div id='root'></div></body></html>"
        with patch("urllib.request.urlopen") as mock_url:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.read.return_value = valid_app_html.encode("utf-8")
            mock_resp.__enter__.return_value = mock_resp
            mock_url.return_value = mock_resp

            res = PreviewManager.check_health("http://localhost:9007")
            self.assertTrue(res.is_healthy)
            self.assertTrue(res.is_app_verified)
            self.assertFalse(res.is_directory_listing)
            self.assertFalse(res.is_control_server)

    def test_8_project_runner_5_step_verification(self):
        """Ensure ProjectRunner executes 5-step lifecycle: PROCESS_STARTED -> PORT_DETECTED -> SERVER_READY -> HTTP_RESPONSIVE -> APPLICATION_VERIFIED."""
        self.workspace.write_file("package.json", '{"name":"mock-app","scripts":{"dev":"node server.js"}}')
        self.workspace.write_file("server.js", 'console.log("Mock server");')

        pm = MagicMock(spec=ProcessManager)
        mock_sess = RuntimeSession(
            project_id="mock_app",
            status="PROCESS_STARTED",
            pid=12345,
            framework="Vite / React Web App",
        )
        mock_sess.is_alive = MagicMock(return_value=True)
        pm.start_session.return_value = mock_sess
        pm.wait_for_port.return_value = 5176
        pm.get_logs_text.return_value = "Mock logs"

        runner = ProjectRunner(self.workspace, process_manager=pm)
        runner.detector.detect = MagicMock(return_value={
            "project_type": "Vite / React Web App",
            "command": ["npm.cmd", "run", "dev"],
            "cwd": str(self.workspace.root),
            "port": None,
            "url": None,
            "is_web": True,
            "has_dev_server": True,
            "requires_install": False,
        })
        runner.preview_manager.check_health = MagicMock(return_value=PreviewCheckResult(
            is_healthy=True,
            is_app_verified=True,
            is_directory_listing=False,
            is_control_server=False,
            status_code=200,
            message="Application response verified.",
        ))

        success = runner.run(self.state)

        self.assertTrue(success)
        self.assertEqual(self.state.runtime_status, "RUNNING")
        self.assertEqual(self.state.runtime_pid, 12345)
        self.assertEqual(self.state.runtime_port, 5176)
        self.assertEqual(self.state.runtime_url, "http://localhost:5176")
        self.assertTrue(self.state.is_app_verified)

        # Check that verification steps recorded the progression
        self.assertIn("Process started", self.state.runtime_verification_steps)
        self.assertIn("Port 5176 detected", self.state.runtime_verification_steps)
        self.assertIn("HTTP responsive", self.state.runtime_verification_steps)
        self.assertIn("Application verified", self.state.runtime_verification_steps)


if __name__ == "__main__":
    unittest.main()
