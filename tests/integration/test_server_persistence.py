"""Integration tests for SPIDY Server SQLite persistence and API endpoints."""

import os
from pathlib import Path
import tempfile
import unittest
from starlette.testclient import TestClient

from backend.database.database_manager import DatabaseManager
from backend.core.project_state import ProjectState


class TestServerPersistenceIntegration(unittest.TestCase):
    """Test server endpoints with integrated SQLite database."""

    @classmethod
    def setUpClass(cls):
        # We import the Starlette app from server
        import server
        cls.server_module = server
        cls.client = TestClient(server.app)

    def test_api_diagnostics_includes_database(self):
        """GET /api/diagnostics must return database health and schema info."""
        response = self.client.get("/api/diagnostics")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("database", data)
        db_info = data["database"]
        self.assertEqual(db_info.get("status"), "HEALTHY")
        self.assertGreaterEqual(db_info.get("schema_version", 0), 1)
        self.assertIn("counts", db_info)

    def test_api_projects_and_builds_endpoints(self):
        """Test /api/projects, /api/projects/{id}, and /api/builds/{id}."""
        import uuid
        db_mgr = self.server_module.db_manager

        # Seed test project and build with unique IDs
        uid = uuid.uuid4().hex[:8]
        test_proj_id = f"test-proj-{uid}"
        test_build_id = f"bld-test-{uid}"
        db_mgr.sync_project_and_build_start(
            project_id=test_proj_id,
            project_name="Integration Test Project",
            build_id=test_build_id,
            requirement="Create a REST API with FastAPI",
            detected_stack="Python / FastAPI",
            workspace_path="/tmp/test_workspace",
            estimated_duration="~5 MIN",
        )
        db_mgr.sync_activity(
            build_id=test_build_id,
            message="Integration activity check",
            event_type="TEST",
            agent="TesterAgent",
            status="PASSED",
        )
        db_mgr.sync_verification_gate(
            build_id=test_build_id,
            gate_name="build",
            status="PASSED",
            message="Integration gate check",
        )
        db_mgr.sync_build_finish(
            build_id=test_build_id,
            project_id=test_proj_id,
            status="COMPLETED",
            duration=42.5,
            final_result="Successfully built and verified",
            detected_stack="Python / FastAPI",
        )

        # 1. GET /api/projects
        res = self.client.get("/api/projects")
        self.assertEqual(res.status_code, 200)
        proj_list = res.json().get("projects", [])
        self.assertTrue(any(p["project_id"] == test_proj_id for p in proj_list))

        # 2. GET /api/projects/{project_id}
        res = self.client.get(f"/api/projects/{test_proj_id}")
        self.assertEqual(res.status_code, 200)
        proj_detail = res.json()
        self.assertEqual(proj_detail["project"]["project_id"], test_proj_id)
        self.assertEqual(proj_detail["project"]["status"], "COMPLETED")
        self.assertTrue(any(b["build_id"] == test_build_id for b in proj_detail.get("builds", [])))

        # 3. GET /api/builds/{build_id}
        res = self.client.get(f"/api/builds/{test_build_id}")
        self.assertEqual(res.status_code, 200)
        build_detail = res.json()
        self.assertEqual(build_detail["build"]["build_id"], test_build_id)
        self.assertEqual(build_detail["build"]["status"], "COMPLETED")
        self.assertTrue(any("Integration activity check" in a["message"] for a in build_detail.get("activities", [])))
        self.assertTrue(any(g["gate_name"] == "build" for g in build_detail.get("verification", [])))

        # 4. GET /api/history returns SQLite records
        res = self.client.get("/api/history")
        self.assertEqual(res.status_code, 200)
        hist = res.json().get("history", [])
        self.assertTrue(any(h.get("build_id") == test_build_id for h in hist))

    def test_api_state_contains_ids(self):
        """GET /api/state must serialize project_id and build_id."""
        res = self.client.get("/api/state")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("project_id", data)
        self.assertIn("build_id", data)


if __name__ == "__main__":
    unittest.main()
