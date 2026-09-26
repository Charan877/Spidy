"""Unit tests for Pipeline Prerequisites, Task Dependency Graphs & Generation Gates."""

import unittest
from unittest.mock import MagicMock, patch
from backend.core.workspace_manager import WorkspaceManager
from backend.runtime.project_runner import ProjectRunner
from backend.core.project_state import ProjectState, Task
from backend.orchestration.orchestrator import MultiAgentPipeline


class TestPipelinePrerequisites(unittest.TestCase):
    """Tests ensuring pipeline prerequisite gates, task dependencies, and error classifications."""

    def setUp(self):
        self.workspace = MagicMock(spec=WorkspaceManager)
        self.workspace.list_files.return_value = []
        self.runner = MagicMock(spec=ProjectRunner)
        self.pipeline = MultiAgentPipeline(self.workspace, self.runner)

    # -------------------------------------------------------------------------
    # SCENARIO 1: Valid project generation flow
    # -------------------------------------------------------------------------
    @patch("backend.orchestration.orchestrator.call_openrouter")
    def test_valid_project_generation_flow(self, mock_openrouter):
        """Valid project passes all gates and completes successfully."""
        mock_openrouter.side_effect = [
            # 1. analyze_and_plan response
            '{"project_name": "Counter App", "detected_language": "HTML/JS", "architecture_summary": "Simple web app", "tech_stack": ["HTML", "JS"], "is_complex": false, "clarifying_questions": [], "files": ["index.html", "app.js"]}',
            # 2. execute_build Developer Agent response
            '### FILE: index.html\n```html\n<!DOCTYPE html><html><body><h1>Counter</h1></body></html>\n```\n### FILE: app.js\n```javascript\nconsole.log("ready");\n```',
            # 3. execute_build Documentation Agent response
            '# Counter App\nA simple counter web app.',
        ]

        state = ProjectState(goal="Create a counter app in HTML and JS")
        self.workspace.list_files.return_value = ["index.html", "app.js"]

        # Configure runner to succeed
        def mock_run(st: ProjectState):
            st.project_success = True
            st.runtime_status = "RUNNING"
            st.is_web_project = True
            st.is_app_verified = True
            return True

        self.runner.run.side_effect = mock_run

        # Execute Plan
        self.pipeline.analyze_and_plan(state)
        self.assertEqual(state.project_name, "Counter App")
        self.assertEqual(state.original_goal, "Create a counter app in HTML and JS")
        self.assertIsNotNone(state.project_spec)

        # Verify task dependency graph was built
        build_tasks = [t for t in state.tasks if t.phase == "BUILD"]
        run_tasks = [t for t in state.tasks if t.phase == "RUN"]
        test_tasks = [t for t in state.tasks if t.phase == "TEST"]
        doc_tasks = [t for t in state.tasks if t.phase == "DOCUMENT"]

        self.assertTrue(len(build_tasks) >= 2)
        self.assertEqual(len(run_tasks), 1)
        self.assertEqual(len(test_tasks), 1)
        self.assertEqual(len(doc_tasks), 1)

        # Run task must depend on all build tasks
        for b_task in build_tasks:
            self.assertIn(b_task.id, run_tasks[0].dependencies)

        # Test task must depend on run task
        self.assertIn(run_tasks[0].id, test_tasks[0].dependencies)

        # Execute Build & Pipeline
        self.pipeline.execute_build(state)

        self.assertTrue(state.is_project_generated)
        self.assertEqual(state.project_generation_status, "GENERATED")
        self.assertEqual(state.current_phase, "COMPLETE")
        self.assertEqual(state.project_state, "SUCCESS")
        self.assertEqual(state.active_agent_status, "SUCCESS")

    # -------------------------------------------------------------------------
    # SCENARIO 2: Empty workspace blocks RUN and TEST without Debugger Agent
    # -------------------------------------------------------------------------
    @patch("backend.orchestration.orchestrator.call_openrouter")
    def test_empty_workspace_blocks_downstream_without_debugger(self, mock_openrouter):
        """If generation yields no files, pipeline enters BLOCKED and NEVER activates Debugger Agent."""
        mock_openrouter.side_effect = [
            # 1. Plan
            '{"project_name": "Empty Project", "detected_language": "Python", "architecture_summary": "App", "tech_stack": ["Python"], "is_complex": false, "clarifying_questions": [], "files": ["main.py"]}',
            # 2. Build returns empty/malformed text (no files written)
            'I cannot generate files right now due to token limits or error.',
        ]

        state = ProjectState(goal="Build a large application")
        self.workspace.list_files.return_value = []  # Workspace remains empty

        self.pipeline.analyze_and_plan(state)
        self.pipeline.execute_build(state)

        # Assert Generation Gate triggered
        self.assertFalse(state.is_project_generated)
        self.assertEqual(state.project_generation_status, "GENERATION_FAILED")
        self.assertEqual(state.failure_type, "PROJECT_GENERATION_FAILURE")
        self.assertEqual(state.failure_classification, "PRECONDITION_FAILURE")
        self.assertEqual(state.current_phase, "BLOCKED")
        self.assertEqual(state.active_agent_status, "BLOCKED")

        # Crucial check: Runner must NEVER have been called on an empty workspace
        self.runner.run.assert_not_called()

        # Crucial check: Debugger agent must NEVER have been called
        self.assertNotEqual(state.active_agent, "Debugger Agent")
        self.assertNotEqual(state.active_agent_status, "FAILURE")

        # Downstream tasks must be BLOCKED, not FAILED
        downstream_tasks = [t for t in state.tasks if t.phase in ("RUN", "TEST", "DOCUMENT")]
        for task in downstream_tasks:
            self.assertEqual(task.status, "BLOCKED", f"Task {task.id} should be BLOCKED")
            self.assertIn("Precondition failed", task.blocked_reason)

    # -------------------------------------------------------------------------
    # SCENARIO 3: Missing execution command sets PRECONDITION_FAILURE and blocks
    # -------------------------------------------------------------------------
    @patch("backend.orchestration.orchestrator.call_openrouter")
    def test_missing_execution_command_blocks_run(self, mock_openrouter):
        """Runner reports PRECONDITION_FAILURE when no valid command is found, marking task BLOCKED."""
        mock_openrouter.side_effect = [
            '{"project_name": "NoCommand App", "detected_language": "Unknown", "architecture_summary": "Static config", "tech_stack": [], "is_complex": false, "clarifying_questions": [], "files": ["config.xyz"]}',
            '### FILE: config.xyz\n```\nkey=val\n```',
        ]

        state = ProjectState(goal="Unknown stack project")
        self.workspace.list_files.return_value = ["config.xyz"]

        def mock_precondition_failure(st: ProjectState):
            st.runtime_status = "FAILED"
            st.failure_classification = "PRECONDITION_FAILURE"
            st.failure_reason = "No valid execution command found for workspace."
            return False

        self.runner.run.side_effect = mock_precondition_failure

        self.pipeline.analyze_and_plan(state)
        self.pipeline.execute_build(state)

        # Run task should be BLOCKED due to PRECONDITION_FAILURE
        run_tasks = [t for t in state.tasks if t.phase == "RUN"]
        self.assertTrue(len(run_tasks) > 0)
        self.assertEqual(run_tasks[0].status, "BLOCKED")
        self.assertEqual(state.active_agent_status, "BLOCKED")

        # Debugger agent must NOT be invoked for precondition failure
        self.assertNotEqual(state.active_agent, "Debugger Agent")

    # -------------------------------------------------------------------------
    # SCENARIO 4: Task dependency missing marks task BLOCKED rather than FAILED
    # -------------------------------------------------------------------------
    def test_task_dependency_readiness(self):
        """Tasks with unfulfilled dependencies are not ready and can be blocked."""
        state = ProjectState(goal="Dependency Test")
        state.add_task("t-build", "Build main code", "BUILD")
        state.add_task("t-run", "Launch process", "RUN", dependencies=["t-build"])
        state.add_task("t-test", "Run tests", "TEST", dependencies=["t-run"])

        run_task = state.tasks[1]
        test_task = state.tasks[2]

        # Before build completes: run and test are not ready
        self.assertFalse(state.is_task_ready(run_task))
        self.assertFalse(state.is_task_ready(test_task))

        # Complete build task
        state.complete_task("t-build")
        self.assertTrue(state.is_task_ready(run_task))
        self.assertFalse(state.is_task_ready(test_task))

        # Block run task
        state.block_task("t-run", "Missing runtime prerequisite")
        self.assertEqual(run_task.status, "BLOCKED")
        self.assertEqual(run_task.blocked_reason, "Missing runtime prerequisite")
        self.assertFalse(state.is_task_ready(test_task))

    # -------------------------------------------------------------------------
    # SCENARIO 5: State machine rejects invalid transitions
    # -------------------------------------------------------------------------
    def test_state_machine_invalid_transitions(self):
        """Cannot jump from PLANNING/INTAKE to DEBUGGING or RUNNING before GENERATED."""
        state = ProjectState(goal="State Machine Test")
        self.assertEqual(state.project_state, "INTAKE")

        # Attempt to jump to DEBUGGING from INTAKE
        res1 = state.transition_to("DEBUGGING", "Premature debugging")
        self.assertFalse(res1)
        self.assertEqual(state.project_state, "INTAKE")

        # Transition to PLANNING
        state.transition_to("PLANNING")
        self.assertEqual(state.project_state, "PLANNING")

        # Attempt to jump to RUNNING from PLANNING
        res2 = state.transition_to("RUNNING", "Premature running")
        self.assertFalse(res2)
        self.assertEqual(state.project_state, "PLANNING")

        # Attempt to jump to TESTING before project is generated
        res3 = state.transition_to("TESTING", "Testing before generated")
        self.assertFalse(res3)
        self.assertEqual(state.project_state, "PLANNING")

    # -------------------------------------------------------------------------
    # SCENARIO 6: Backward prerequisite tracing resumes from earliest missing step
    # -------------------------------------------------------------------------
    def test_backward_prerequisite_tracing(self):
        """get_earliest_missing_prerequisite correctly identifies the earliest missing step."""
        state = ProjectState(goal="")
        self.assertEqual(self.pipeline.get_earliest_missing_prerequisite(state), "INTAKE")

        state.goal = "Build a web app"
        self.assertEqual(self.pipeline.get_earliest_missing_prerequisite(state), "PLANNING")

        state.project_spec = {"project_name": "Test"}
        state.architecture_summary = "Web App"
        self.workspace.list_files.return_value = []
        state.is_project_generated = False
        self.assertEqual(self.pipeline.get_earliest_missing_prerequisite(state), "BUILD")

        # Files exist and project generated, but not run yet
        self.workspace.list_files.return_value = ["index.html"]
        state.is_project_generated = True
        state.add_task("t-1", "Build index", "BUILD")
        state.complete_task("t-1")
        state.runtime_status = "NOT_STARTED"
        self.assertEqual(self.pipeline.get_earliest_missing_prerequisite(state), "RUN")

        # Running but web project verification unconfirmed
        state.runtime_status = "RUNNING"
        state.is_web_project = True
        state.is_app_verified = False
        self.assertEqual(self.pipeline.get_earliest_missing_prerequisite(state), "TEST")

        # Verified
        state.is_app_verified = True
        self.assertEqual(self.pipeline.get_earliest_missing_prerequisite(state), "COMPLETE")

    # -------------------------------------------------------------------------
    # SCENARIO 7: Context persistence across pipeline stages
    # -------------------------------------------------------------------------
    @patch("backend.orchestration.orchestrator.call_openrouter")
    def test_context_persistence_across_pipeline(self, mock_openrouter):
        """Original goal and specification persist throughout all stages."""
        mock_openrouter.side_effect = [
            '{"project_name": "Persistent App", "detected_language": "Python", "architecture_summary": "CLI tool", "tech_stack": ["Python"], "is_complex": false, "clarifying_questions": [], "files": ["main.py"]}',
            '### FILE: main.py\n```python\nprint("hello")\n```',
            '# Persistent App\nDocs',
        ]

        state = ProjectState(goal="Build a persistence testing application")
        self.workspace.list_files.return_value = ["main.py"]

        self.pipeline.analyze_and_plan(state)
        self.assertEqual(state.original_goal, "Build a persistence testing application")
        self.assertEqual(state.requirements, "Build a persistence testing application")
        self.assertIn("project_name", state.project_spec)

        self.pipeline.execute_build(state)
        self.assertEqual(state.original_goal, "Build a persistence testing application")
        self.assertEqual(state.requirements, "Build a persistence testing application")


if __name__ == "__main__":
    unittest.main()
