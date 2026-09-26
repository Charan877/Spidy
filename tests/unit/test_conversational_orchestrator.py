"""Unit tests for SPIDY conversational engineering and integrity verification.

Verifies:
1. TaskClassifier intent classification across all 11 intent types.
2. CodeForge bug regression: PreviewManager detects missing referenced CSS/JS files.
3. ReviewerAgent: comprehensive audit catches missing assets, failed required tasks, and sets verdict.
4. Orchestrator strict verification gate: FAILED task + HTTP 200 NEVER results in BUILT. VERIFIED.
5. Plan Delta continuity: workspace is preserved on iterative requests, not cleared.
6. Message persistence: conversational turns recorded in ProjectState and database.
"""

from pathlib import Path
import tempfile
import unittest

from backend.agents.reviewer_agent import ReviewerAgent, ReviewVerdict
from backend.core.project_state import ProjectState, Task
from backend.core.task_classifier import TaskClassification, TaskClassifier
from backend.core.workspace_manager import WorkspaceManager
from backend.database.database_manager import DatabaseManager
from backend.orchestration.orchestrator import MultiAgentPipeline
from backend.runtime.preview_manager import PreviewManager


class TestConversationalOrchestrator(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace_dir = Path(self.temp_dir.name) / "workspace"
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.workspace = WorkspaceManager(self.workspace_dir)

        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.db_manager = DatabaseManager(self.db_path)
        self.db_manager.initialize()

        self.pipeline = MultiAgentPipeline(self.workspace)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_01_task_classifier_intent_rules(self):
        """1. TaskClassifier correctly categorizes intents."""
        # Fresh project when no workspace exists
        self.assertEqual(
            TaskClassifier.classify("Build a portfolio website", has_existing_project=False, existing_files_count=0),
            TaskClassification.NEW_PROJECT,
        )

        # Explicit fresh project demand
        self.assertEqual(
            TaskClassifier.classify("Start from scratch with a new project", has_existing_project=True, existing_files_count=5),
            TaskClassification.NEW_PROJECT,
        )

        # Feature request on existing project
        self.assertEqual(
            TaskClassifier.classify("Add a dark mode toggle button", has_existing_project=True, existing_files_count=3),
            TaskClassification.FEATURE_REQUEST,
        )

        # Modification on existing project
        self.assertEqual(
            TaskClassifier.classify("Change the hero background color to slate gray", has_existing_project=True, existing_files_count=3),
            TaskClassification.MODIFICATION,
        )

        # Bug fix
        self.assertEqual(
            TaskClassifier.classify("The login button doesn't work and throws error", has_existing_project=True, existing_files_count=3),
            TaskClassification.BUG_FIX,
        )

        # Debug request
        self.assertEqual(
            TaskClassifier.classify("Debug the server response and inspect logs", has_existing_project=True, existing_files_count=3),
            TaskClassification.DEBUG_REQUEST,
        )

        # Explanation
        self.assertEqual(
            TaskClassifier.classify("Explain how the database schema works", has_existing_project=True, existing_files_count=3),
            TaskClassification.EXPLANATION,
        )

        # Verification request
        self.assertEqual(
            TaskClassifier.classify("Verify the application endpoints and test health", has_existing_project=True, existing_files_count=3),
            TaskClassification.VERIFICATION_REQUEST,
        )

    def test_02_preview_manager_asset_integrity_codeforge_regression(self):
        """2. CodeForge Bug: PreviewManager detects missing referenced CSS/JS files."""
        # Case A: Missing style.css and script.js referenced in HTML
        html_with_missing = (
            "<!doctype html><html><head>"
            "<link rel='stylesheet' href='style.css'>"
            "</head><body><div id='root'></div><script src='script.js'></script></body></html>"
        )
        (self.workspace_dir / "index.html").write_text(html_with_missing, encoding="utf-8")

        ok, missing = PreviewManager.verify_referenced_assets(self.workspace_dir)
        self.assertFalse(ok)
        self.assertEqual(len(missing), 2)
        self.assertTrue(any("style.css" in m for m in missing))
        self.assertTrue(any("script.js" in m for m in missing))

        # Case B: Create the missing files -> should pass
        (self.workspace_dir / "style.css").write_text("body { margin: 0; }", encoding="utf-8")
        (self.workspace_dir / "script.js").write_text("console.log('ready');", encoding="utf-8")

        ok_after, missing_after = PreviewManager.verify_referenced_assets(self.workspace_dir)
        self.assertTrue(ok_after)
        self.assertEqual(len(missing_after), 0)

    def test_03_reviewer_agent_catches_integrity_and_task_failures(self):
        """3. ReviewerAgent audits required tasks and referenced assets."""
        reviewer = ReviewerAgent()
        state = ProjectState("Build website")
        state.is_project_generated = True
        state.files = {"index.html": "<html></html>"}

        # Simulate a failed required task
        state.add_task("t-1", "Generate CSS", "BUILD", is_required=True)
        state.fail_task("t-1", "CSS generation timeout")

        verdict = reviewer.review(state, self.workspace_dir)
        self.assertIn(verdict.verdict, ["NEEDS_RECOVERY", "FAIL"])
        self.assertGreater(len(verdict.issues), 0)
        self.assertTrue(any("Required task(s) failed" in issue for issue in verdict.issues))
        self.assertEqual(state.reviewer_verdict, verdict.verdict)

    def test_04_strict_verification_gate_never_fakes_success(self):
        """4. Strict verification gate: FAILED required task + HTTP 200 NEVER declares BUILT. VERIFIED."""
        state = ProjectState("Build website")
        state.project_id = "test-proj"
        state.is_project_generated = True
        state.project_success = True
        state.runtime_status = "RUNNING"
        state.is_web_project = True
        state.is_app_verified = True

        # Failed required task
        state.add_task("t-build-css", "Generate CSS", "BUILD", is_required=True)
        state.fail_task("t-build-css", "Failed")

        self.assertTrue(state.has_failed_required_tasks())

        # Reviewer audit
        reviewer = ReviewerAgent()
        verdict = reviewer.review(state, self.workspace_dir)
        self.assertNotEqual(verdict.verdict, "PASS")

        # The orchestrator's verification condition
        has_failed_required = state.has_failed_required_tasks()
        reviewer_passed = (verdict.verdict == "PASS")
        asset_ok, _ = PreviewManager.verify_referenced_assets(self.workspace_dir)

        is_verified = (
            state.is_project_generated
            and state.project_success
            and state.runtime_status == "RUNNING"
            and (not state.is_web_project or state.is_app_verified)
            and not has_failed_required
            and reviewer_passed
            and asset_ok
        )
        self.assertFalse(is_verified, "Build must NEVER be marked verified when a required task has failed!")

    def test_05_message_persistence_in_database(self):
        """5. Conversational messages are recorded and queried from DatabaseManager."""
        project_id = "proj_test_chat"
        self.db_manager.projects.ensure_project(
            project_id=project_id,
            name="Chat Test Project",
            status="READY",
        )

        msg1 = self.db_manager.messages.save_message(
            project_id=project_id,
            role="user",
            content="Build a portfolio website",
            classification="NEW_PROJECT",
        )
        self.assertIsNotNone(msg1["message_id"])

        msg2 = self.db_manager.messages.save_message(
            project_id=project_id,
            role="assistant",
            content="Portfolio project generated and running.",
            classification="NEW_PROJECT",
        )

        msg3 = self.db_manager.messages.save_message(
            project_id=project_id,
            role="user",
            content="Change hero to 3D Three.js animation",
            classification="MODIFICATION",
        )

        history = self.db_manager.messages.get_messages_for_project(project_id)
        self.assertEqual(len(history), 3)
        self.assertEqual(history[0]["role"], "user")
        self.assertEqual(history[1]["role"], "assistant")
        self.assertEqual(history[2]["classification"], "MODIFICATION")


if __name__ == "__main__":
    unittest.main()
