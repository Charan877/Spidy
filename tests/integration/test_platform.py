"""Automated Test Suite for NOVA Code Lab AI Software Engineering Platform."""

import os
from pathlib import Path
import unittest

from backend.core.events import EventBus
from backend.runtime.project_runner import ProjectRunner
from backend.core.project_state import ProjectState
from backend.core.workspace_manager import WorkspaceManager
from backend.runtime.environment_detector import EnvironmentDetector
from backend.runtime.preview_manager import PreviewManager
from backend.runtime.process_manager import ProcessManager


import tempfile

class TestNovaPlatform(unittest.TestCase):
    """Test suite for core components of NOVA Code Lab."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = WorkspaceManager(self.temp_dir.name)
        self.state = ProjectState("Test requirement", "HTML/CSS/JS")
        self.process_manager = ProcessManager()
        self.runner = ProjectRunner(self.workspace, self.process_manager)

    def tearDown(self):
        self.process_manager.stop()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_workspace_manager(self):
        """Test file creation, reading, and boundary security."""
        file_path = self.workspace.write_file("test.txt", "Nova Code Lab Test")
        self.assertTrue(Path(file_path).exists())
        content = self.workspace.read_file("test.txt")
        self.assertEqual(content, "Nova Code Lab Test")

        # Security check: path traversal escape should raise PermissionError
        with self.assertRaises(PermissionError):
            self.workspace.write_file("../outside.txt", "hack")

    def test_project_state_progress(self):
        """Test task status and progress calculation."""
        self.assertEqual(self.state.progress_percentage, 0)
        self.state.add_task("t1", "Task 1", "BUILD")
        self.state.add_task("t2", "Task 2", "BUILD")
        self.assertEqual(self.state.progress_percentage, 0)

        self.state.complete_task("t1")
        self.assertEqual(self.state.progress_percentage, 50)

        self.state.complete_task("t2")
        self.assertEqual(self.state.progress_percentage, 100)

    def test_environment_detector(self):
        """Test detection of HTML static server stack."""
        self.workspace.write_file("index.html", "<h1>Nova Web Test</h1>")
        config = EnvironmentDetector.detect(self.workspace)

        self.assertTrue(config["is_web"])
        self.assertEqual(config["project_type"], "HTML / 3D WebGL Application")
        self.assertIsNotNone(config["port"])
        self.assertTrue(config["url"].startswith("http://localhost:"))

    def test_project_runner_end_to_end(self):
        """Test project start, health check, and stop."""
        self.workspace.write_file(
            "index.html", "<html><body><h1>Run Test</h1></body></html>"
        )
        started = self.runner.run(self.state)

        self.assertTrue(started)
        self.assertEqual(self.state.runtime_status, "RUNNING")
        self.assertTrue(self.state.runtime_url.startswith("http://localhost:"))

        # Check HTTP health
        healthy = PreviewManager.check_health(self.state.runtime_url)
        self.assertTrue(healthy)

        # Stop
        self.runner.stop(self.state)
        self.assertEqual(self.state.runtime_status, "STOPPED")

    def test_event_bus(self):
        """Test structured event publishing and history tracking."""
        bus = EventBus()
        evt = bus.publish("Pipeline started", level="run", source="Orchestrator")

        self.assertEqual(evt.message, "Pipeline started")
        self.assertEqual(len(bus.get_recent()), 1)


if __name__ == "__main__":
    unittest.main()
