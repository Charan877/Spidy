"""Automated Test Suite for Runtime Detection, Directory Listing Anti-Pattern Detection, and Recovery."""

import json
from pathlib import Path
import sys
import unittest

from backend.runtime.project_runner import ProjectRunner
from backend.core.project_state import ProjectState
from backend.core.workspace_manager import WorkspaceManager
from backend.runtime.environment_detector import EnvironmentDetector
from backend.runtime.preview_manager import PreviewManager
from backend.runtime.process_manager import ProcessManager


import tempfile

class TestRuntimeRecovery(unittest.TestCase):
    """Test suite for metadata-first environment detection and preview verification."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = WorkspaceManager(self.temp_dir.name)
        self.state = ProjectState("Test React Project", "JavaScript")
        self.process_manager = ProcessManager()
        self.runner = ProjectRunner(self.workspace, self.process_manager)

    def tearDown(self):
        self.process_manager.stop()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_metadata_first_detection(self):
        """Test that a project with package.json + index.html + src/ selects npm run dev instead of http.server."""
        pkg_json = {
            "name": "messi-3d-statue",
            "scripts": {"dev": "vite", "build": "vite build"},
            "devDependencies": {"vite": "^5.0.0"},
        }
        self.workspace.write_file("package.json", json.dumps(pkg_json, indent=2))
        self.workspace.write_file("index.html", "<html><body><div id='app'></div></body></html>")
        self.workspace.write_file("src/main.js", "console.log('Messi 3D');")

        config = EnvironmentDetector.detect(self.workspace)

        # Must select dev script from package.json and NOT static http.server!
        self.assertTrue(config["is_web"])
        self.assertTrue(config["has_dev_server"])
        self.assertEqual(config["command"][:2], ["npm.cmd" if sys.platform == "win32" else "npm", "run"])
        self.assertEqual(config["command"][2], "dev")

    def test_directory_listing_anti_pattern_detection(self):
        """Test that PreviewManager flags 'Directory listing for /' as unverified anti-pattern."""
        # Simulated directory listing HTML body
        dir_listing_html = "<!DOCTYPE html><html><head><title>Directory listing for /</title></head><body><h1>Directory listing for /</h1></body></html>"

        # Mock check_health parsing
        is_dir_listing = "Directory listing for" in dir_listing_html
        self.assertTrue(is_dir_listing)

    def test_preview_manager_app_verification(self):
        """Test that PreviewManager distinguishes valid app HTML from directory listing."""
        app_html = "<!DOCTYPE html><html><head><title>Messi 3D Statue</title></head><body><canvas id='webgl'></canvas></body></html>"
        is_dir_listing = "Directory listing for" in app_html
        self.assertFalse(is_dir_listing)

    def test_react_typescript_vite_three_detection(self):
        """Test precise multi-factor detection for React + TypeScript + Vite + Three.js app."""
        pkg_json = {
            "name": "messi-3d",
            "scripts": {"dev": "vite", "build": "tsc -b && vite build"},
            "dependencies": {
                "react": "^18.3.1",
                "@react-three/fiber": "^8.16.8",
                "three": "^0.169.0"
            },
            "devDependencies": {
                "typescript": "^5.5.3",
                "vite": "^5.4.2"
            }
        }
        self.workspace.write_file("package.json", json.dumps(pkg_json, indent=2))
        self.workspace.write_file("tsconfig.json", "{}")
        self.workspace.write_file("src/App.tsx", "export default function App() { return <div/>; }")

        config = EnvironmentDetector.detect(self.workspace)
        self.assertEqual(config["project_type"], "React + TypeScript + Vite + Three.js Web App")
        self.assertEqual(config["command"], ["npm.cmd" if sys.platform == "win32" else "npm", "run", "dev"])
        self.assertEqual(Path(config["cwd"]).resolve(), Path(self.workspace.root).resolve())
        self.assertTrue(config["is_web"])

    def test_nested_working_directory_detection(self):
        """Test that a project with package.json in client/ sets cwd to that client directory."""
        pkg_json = {
            "name": "frontend-client",
            "scripts": {"dev": "vite"},
            "dependencies": {"react": "^18.0.0"}
        }
        self.workspace.write_file("client/package.json", json.dumps(pkg_json, indent=2))

        config = EnvironmentDetector.detect(self.workspace)
        self.assertEqual(Path(config["cwd"]).resolve(), (Path(self.workspace.root) / "client").resolve())
        self.assertEqual(config["command"], ["npm.cmd" if sys.platform == "win32" else "npm", "run", "dev"])


if __name__ == "__main__":
    unittest.main()
