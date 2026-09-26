"""Integration tests for SPIDY Conversational API endpoints."""

import uuid
import unittest
from starlette.testclient import TestClient


class TestConversationalApiIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import server
        cls.server_module = server
        cls.client = TestClient(server.app)

    def test_01_chat_endpoint_validations(self):
        """1. POST /api/chat rejects empty message."""
        res = self.client.post("/api/chat", json={"message": ""})
        self.assertEqual(res.status_code, 400)
        self.assertIn("error", res.json())

    def test_02_project_messages_endpoint(self):
        """2. GET /api/projects/{id}/messages returns message history."""
        db_mgr = self.server_module.db_manager
        proj_id = f"proj_int_{uuid.uuid4().hex[:6]}"
        db_mgr.projects.ensure_project(project_id=proj_id, name="Message Test Project")

        db_mgr.messages.save_message(
            project_id=proj_id,
            role="user",
            content="Create fullstack dashboard",
            classification="NEW_PROJECT",
        )
        db_mgr.messages.save_message(
            project_id=proj_id,
            role="assistant",
            content="Dashboard created and online.",
            classification="NEW_PROJECT",
        )

        res = self.client.get(f"/api/projects/{proj_id}/messages")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["project_id"], proj_id)
        self.assertEqual(len(data["messages"]), 2)
        self.assertEqual(data["messages"][0]["content"], "Create fullstack dashboard")

    def test_03_resume_project_endpoint(self):
        """3. POST /api/projects/{id}/resume restores project into server state."""
        db_mgr = self.server_module.db_manager
        proj_id = f"proj_resume_{uuid.uuid4().hex[:6]}"
        db_mgr.projects.ensure_project(
            project_id=proj_id,
            name="Resume Test App",
            description="Testing resume endpoint",
            detected_stack="HTML/CSS/JS",
        )

        res = self.client.post(f"/api/projects/{proj_id}/resume")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("project", data)
        self.assertEqual(data["project"]["project_id"], proj_id)

        # State should now reflect this project
        state_res = self.client.get("/api/state")
        self.assertEqual(state_res.status_code, 200)
        state_data = state_res.json()
        self.assertEqual(state_data.get("project_id"), proj_id)
        self.assertEqual(state_data.get("project_name"), "Resume Test App")


if __name__ == "__main__":
    unittest.main()
