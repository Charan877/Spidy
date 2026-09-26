"""Regression Test Suite for SPIDY Project Context Isolation.

Verifies:
- TaskClassifier deterministically distinguishes NEW_PROJECT from continuations even when workspaces exist.
- Generated architecture plans are strictly validated against requirement to prevent stale domain leaks.
- Consecutive project creations (Merge Sorted Lists -> TaskFlow) produce completely isolated workspaces,
  task graphs, build IDs, and verification verdicts.
- Project resume and multi-project modifications remain strictly isolated.
"""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import uuid

from backend.agents.reviewer_agent import ReviewerAgent
from backend.core.active_context import ActiveProjectContext
from backend.core.project_state import ProjectState, Task
from backend.core.task_classifier import TaskClassifier, TaskClassification
from backend.core.workspace_manager import WorkspaceManager
from backend.database import get_database_manager
from backend.orchestration.orchestrator import MultiAgentPipeline, validate_plan_against_requirement


class TestProjectContextIsolationRegression(unittest.TestCase):
    """Verifies strict isolation across projects, task graphs, builds, and workspaces."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temp_dir.name)
        self.db = get_database_manager()
        self.db.initialize()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_task_classifier_distinguishes_new_project_with_existing_files(self):
        """TaskClassifier must classify 'Build a full-stack...' as NEW_PROJECT even if files exist."""
        # Scenario: Previous project exists with 15 files
        has_existing = True
        existing_count = 15

        taskflow_msg = "Build a full-stack web application called TaskFlow using FastAPI and React"
        self.assertEqual(
            TaskClassifier.classify(taskflow_msg, has_existing_project=has_existing, existing_files_count=existing_count),
            TaskClassification.NEW_PROJECT,
        )

        merge_msg = "Write A Python Program to Merge Two Sorted Lists using a two-pointer algorithm"
        self.assertEqual(
            TaskClassifier.classify(merge_msg, has_existing_project=has_existing, existing_files_count=existing_count),
            TaskClassification.NEW_PROJECT,
        )

        create_msg = "Create a modern real-time chat application with WebSockets"
        self.assertEqual(
            TaskClassifier.classify(create_msg, has_existing_project=has_existing, existing_files_count=existing_count),
            TaskClassification.NEW_PROJECT,
        )

        # Continuation requests must be classified appropriately
        feature_msg = "Add a search filter and tag selector to the task list"
        self.assertEqual(
            TaskClassifier.classify(feature_msg, has_existing_project=has_existing, existing_files_count=existing_count),
            TaskClassification.FEATURE_REQUEST,
        )

        mod_msg = "Change the header navbar background color to deep navy and increase padding"
        self.assertEqual(
            TaskClassifier.classify(mod_msg, has_existing_project=has_existing, existing_files_count=existing_count),
            TaskClassification.MODIFICATION,
        )

        bug_msg = "Fix TypeError: Cannot read properties of undefined in TaskCard.tsx"
        self.assertEqual(
            TaskClassifier.classify(bug_msg, has_existing_project=has_existing, existing_files_count=existing_count),
            TaskClassification.BUG_FIX,
        )

    def test_architecture_mismatch_validator(self):
        """Architecture validator must reject plans containing foreign puzzle/algorithm signatures."""
        req = "Build a full-stack web application called TaskFlow with React and FastAPI"

        # Stale/contaminated plan containing merge_sorted_lists
        contaminated_plan = {
            "project_name": "Merge Sorted Lists",
            "architecture_summary": "Two-pointer algorithm to merge two sorted arrays.",
            "detected_language": "Python",
            "files": ["merge_sorted_lists.py", "test_merge.py"],
            "tasks": [
                {"id": "t-1", "title": "Implement merge_sorted_lists function using two-pointer algorithm", "file_path": "merge_sorted_lists.py"}
            ],
        }

        is_valid, reason = validate_plan_against_requirement(req, contaminated_plan)
        self.assertFalse(is_valid)
        self.assertIn("merge_sorted_lists", reason)

        # Clean plan matching TaskFlow
        clean_plan = {
            "project_name": "TaskFlow",
            "architecture_summary": "Fullstack task management dashboard with FastAPI and SQLite.",
            "detected_language": "Fullstack",
            "files": ["app.py", "requirements.txt", "index.html", "style.css", "app.js"],
            "tasks": [
                {"id": "t-1", "title": "Generate app.py", "file_path": "app.py"},
                {"id": "t-2", "title": "Generate index.html", "file_path": "index.html"},
            ],
        }

        is_valid_clean, reason_clean = validate_plan_against_requirement(req, clean_plan)
        self.assertTrue(is_valid_clean)
        self.assertIsNone(reason_clean)

    def test_taskflow_and_merge_sorted_lists_complete_isolation(self):
        """Simulate creating Project A (Merge Lists with failure) then Project B (TaskFlow)."""
        pid_a = f"proj_test_a_{uuid.uuid4().hex[:6]}"
        bid_a = f"bld_test_a_{uuid.uuid4().hex[:6]}"
        ws_a = WorkspaceManager(self.base_dir / "workspaces" / pid_a)
        ws_a.write_file("merge.py", "def merge(): pass")

        state_a = ProjectState()
        state_a.reset("Write A Python Program to Merge Two Sorted Lists", project_id=pid_a, build_id=bid_a)
        state_a.add_task("task-1", "Implement the merge_sorted_lists function using the two-pointer algorithm", "BUILD", is_required=True, build_id=bid_a, project_id=pid_a)
        state_a.add_task("task-2", "Add CLI input handling and demo mode", "BUILD", is_required=True, build_id=bid_a, project_id=pid_a)
        # Mark tasks failed in Project A
        state_a.fail_task("task-1", "Code generation missed merge_sorted_lists.py")
        state_a.fail_task("task-2", "Code generation missed merge_sorted_lists.py")

        self.assertTrue(state_a.has_failed_required_tasks())
        reviewer = ReviewerAgent()
        verdict_a = reviewer.review(state_a, ws_a.root)
        self.assertIn("merge_sorted_lists", "; ".join(verdict_a.issues))

        # Now start Project B: TaskFlow
        pid_b = f"proj_test_b_{uuid.uuid4().hex[:6]}"
        bid_b = f"bld_test_b_{uuid.uuid4().hex[:6]}"
        ws_b = WorkspaceManager(self.base_dir / "workspaces" / pid_b)
        ws_b.write_file("app.py", "from fastapi import FastAPI\napp = FastAPI()")
        ws_b.write_file("index.html", "<html>TaskFlow</html>")
        ws_b.write_file("style.css", "body { margin: 0; }")
        ws_b.write_file("app.js", "console.log('TaskFlow');")

        state_b = ProjectState()
        # Reset Project B cleanly
        state_b.reset("Build a full-stack TaskFlow task management app", language="Fullstack", project_id=pid_b, build_id=bid_b)
        state_b.files = ws_b.load_all_files()
        state_b.is_project_generated = True
        state_b.project_success = True
        state_b.runtime_status = "RUNNING"
        state_b.is_app_verified = True

        state_b.add_task("t-1", "Generate app.py", "BUILD", file_path="app.py", is_required=True, build_id=bid_b, project_id=pid_b)
        state_b.add_task("t-2", "Generate index.html", "BUILD", file_path="index.html", is_required=True, build_id=bid_b, project_id=pid_b)
        state_b.add_task("t-3", "Launch application server", "RUN", is_required=True, build_id=bid_b, project_id=pid_b)
        state_b.complete_task("t-1")
        state_b.complete_task("t-2")
        state_b.complete_task("t-3")

        # Project B must have NO failed tasks and NO trace of merge_sorted_lists
        self.assertFalse(state_b.has_failed_required_tasks())
        for t in state_b.tasks:
            self.assertNotIn("merge_sorted_lists", t.title)
            self.assertNotIn("two-pointer", t.title)
            self.assertEqual(t.build_id, bid_b)
            self.assertEqual(t.project_id, pid_b)

        # Reviewer verdict on Project B must PASS and must NOT report merge_sorted_lists
        verdict_b = reviewer.review(state_b, ws_b.root)
        self.assertEqual(verdict_b.verdict, "PASS")
        self.assertEqual(len(verdict_b.issues), 0)
        self.assertNotIn("merge_sorted_lists", "; ".join(verdict_b.issues))

        # Workspaces must be completely isolated
        self.assertNotEqual(ws_a.root, ws_b.root)
        self.assertTrue((ws_a.root / "merge.py").exists())
        self.assertFalse((ws_a.root / "app.py").exists())
        self.assertTrue((ws_b.root / "app.py").exists())
        self.assertFalse((ws_b.root / "merge.py").exists())

    def test_multi_project_database_isolation(self):
        """Verify that projects, builds, and messages in SQLite remain strictly isolated."""
        pid_1 = f"proj_iso_1_{uuid.uuid4().hex[:6]}"
        pid_2 = f"proj_iso_2_{uuid.uuid4().hex[:6]}"

        self.db.projects.ensure_project(pid_1, "Project Alpha", "First project requirement", "/tmp/p1", "Python")
        self.db.projects.ensure_project(pid_2, "Project Beta", "Second project requirement", "/tmp/p2", "Fullstack")

        bid_1 = f"bld_1_{uuid.uuid4().hex[:6]}"
        bid_2 = f"bld_2_{uuid.uuid4().hex[:6]}"

        self.db.builds.create_build(bid_1, pid_1, "Requirement 1")
        self.db.builds.create_build(bid_2, pid_2, "Requirement 2")

        self.db.messages.save_message(pid_1, "user", "Message for Project 1", classification="NEW_PROJECT", build_id=bid_1)
        self.db.messages.save_message(pid_2, "user", "Message for Project 2", classification="NEW_PROJECT", build_id=bid_2)

        msgs_1 = self.db.messages.get_messages_for_project(pid_1)
        msgs_2 = self.db.messages.get_messages_for_project(pid_2)

        self.assertEqual(len(msgs_1), 1)
        self.assertEqual(msgs_1[0]["content"], "Message for Project 1")
        self.assertEqual(msgs_1[0]["project_id"], pid_1)

        self.assertEqual(len(msgs_2), 1)
        self.assertEqual(msgs_2[0]["content"], "Message for Project 2")
        self.assertEqual(msgs_2[0]["project_id"], pid_2)

        builds_1 = self.db.builds.get_builds_for_project(pid_1)
        builds_2 = self.db.builds.get_builds_for_project(pid_2)

        self.assertEqual(len(builds_1), 1)
        self.assertEqual(builds_1[0]["build_id"], bid_1)
        self.assertEqual(len(builds_2), 1)
        self.assertEqual(builds_2[0]["build_id"], bid_2)

    def test_multi_project_lifecycle_isolation(self):
        """Verify full lifecycle: Project A create -> Project B create -> modify A -> modify B -> resume A -> resume B."""
        pid_a = f"proj_life_a_{uuid.uuid4().hex[:6]}"
        pid_b = f"proj_life_b_{uuid.uuid4().hex[:6]}"

        ws_a = WorkspaceManager(self.base_dir / "workspaces" / pid_a)
        ws_b = WorkspaceManager(self.base_dir / "workspaces" / pid_b)

        # 1. Project A Create
        self.db.projects.ensure_project(pid_a, "Merge Lists", "Merge Two Sorted Lists", str(ws_a.root), "Python")
        bld_a_1 = f"bld_a_1_{uuid.uuid4().hex[:6]}"
        self.db.builds.create_build(bld_a_1, pid_a, "Implement merge sorted lists")
        ws_a.write_file("merge.py", "def merge(): pass")
        self.db.verification.record_gate_result(bld_a_1, "build", "PASSED", "Compiled")

        # 2. Project B Create
        self.db.projects.ensure_project(pid_b, "TaskFlow", "TaskFlow fullstack app", str(ws_b.root), "Fullstack")
        bld_b_1 = f"bld_b_1_{uuid.uuid4().hex[:6]}"
        self.db.builds.create_build(bld_b_1, pid_b, "Build fullstack TaskFlow")
        ws_b.write_file("app.py", "from fastapi import FastAPI")
        ws_b.write_file("index.html", "<h1>TaskFlow</h1>")
        self.db.verification.record_gate_result(bld_b_1, "build", "PASSED", "Compiled")
        self.db.verification.record_gate_result(bld_b_1, "application", "PASSED", "App Verified")

        # 3. Modify Project A
        bld_a_2 = f"bld_a_2_{uuid.uuid4().hex[:6]}"
        self.db.builds.create_build(bld_a_2, pid_a, "Add quicksort helper")
        ws_a.write_file("quicksort.py", "def quicksort(): pass")

        # 4. Modify Project B
        bld_b_2 = f"bld_b_2_{uuid.uuid4().hex[:6]}"
        self.db.builds.create_build(bld_b_2, pid_b, "Add search API")
        ws_b.write_file("search.py", "def search(): pass")

        # 5. Resume Project A
        state_resume_a = ProjectState()
        state_resume_a.project_id = pid_a
        state_resume_a.files = ws_a.load_all_files()
        state_resume_a.tasks = []

        self.assertIn("merge.py", state_resume_a.files)
        self.assertIn("quicksort.py", state_resume_a.files)
        self.assertNotIn("app.py", state_resume_a.files)
        self.assertNotIn("search.py", state_resume_a.files)

        # 6. Resume Project B
        state_resume_b = ProjectState()
        state_resume_b.project_id = pid_b
        state_resume_b.files = ws_b.load_all_files()
        state_resume_b.tasks = []

        self.assertIn("app.py", state_resume_b.files)
        self.assertIn("index.html", state_resume_b.files)
        self.assertIn("search.py", state_resume_b.files)
        self.assertNotIn("merge.py", state_resume_b.files)
        self.assertNotIn("quicksort.py", state_resume_b.files)

        # 7. Verification & build isolation in DB
        builds_a = [b["build_id"] for b in self.db.builds.get_builds_for_project(pid_a)]
        builds_b = [b["build_id"] for b in self.db.builds.get_builds_for_project(pid_b)]

        self.assertIn(bld_a_1, builds_a)
        self.assertIn(bld_a_2, builds_a)
        self.assertNotIn(bld_b_1, builds_a)
        self.assertNotIn(bld_b_2, builds_a)

        self.assertIn(bld_b_1, builds_b)
        self.assertIn(bld_b_2, builds_b)
        self.assertNotIn(bld_a_1, builds_b)
        self.assertNotIn(bld_a_2, builds_b)

        gates_b1 = self.db.verification.get_gates_for_build(bld_b_1)
        self.assertEqual(len(gates_b1), 2)
        gates_a1 = self.db.verification.get_gates_for_build(bld_a_1)
        self.assertEqual(len(gates_a1), 1)


if __name__ == "__main__":
    unittest.main()
