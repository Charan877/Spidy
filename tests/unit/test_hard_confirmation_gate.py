import pytest
from unittest.mock import MagicMock, patch
from backend.core.project_state import ProjectState, Task
from backend.core.base_agent import BaseAgent
from backend.core.semantic_requirement import (
    SemanticRequirementAnalyzer,
    EngineeringSpecification,
)
from backend.orchestration.orchestrator import MultiAgentPipeline


class TestHardConfirmationGate:
    """Tests verifying that AWAITING_CONFIRMATION is a hard, authoritative execution barrier."""

    def setup_method(self):
        self.workspace = MagicMock()
        self.workspace.list_files.return_value = []
        self.runner = MagicMock()
        self.pipeline = MultiAgentPipeline(workspace=self.workspace, runner=self.runner)

    def test_new_requirement_halts_at_awaiting_confirmation_without_executing_agents(self):
        """When a new requirement is received with auto_confirm=False:
        1. Non-executing understanding runs.
        2. State transitions to AWAITING_CONFIRMATION.
        3. Zero engineering tasks are generated or executed.
        4. No Planner or Architect completion activities are logged.
        """
        state = ProjectState(goal="Build a 3D interactive planetary simulation in WebGL")
        state.auto_confirm = False

        confirmed = self.pipeline.understand_requirement(state)

        assert confirmed is False
        assert state.project_state == "AWAITING_CONFIRMATION"
        assert state.is_awaiting_confirmation() is True
        assert state.can_execute_engineering() is False
        assert state.interpretation_status == "PENDING"
        assert state.user_approved is False
        assert state.engineering_spec is not None
        assert state.requirement_interpretation is not None
        assert len(state.tasks) == 0

        # Verify activity feed reports interpretation, but NOT planner or architect completion
        activity_messages = [a.message for a in state.activity_feed]
        assert any("Interpreted Intent:" in m for m in activity_messages)
        assert any("Please confirm this interpretation" in m for m in activity_messages)
        assert not any("Planner & Architect Agent completed task successfully" in m for m in activity_messages)
        assert not any("Developer Agent completed task successfully" in m for m in activity_messages)

    def test_analyze_and_plan_stops_cleanly_at_awaiting_confirmation(self):
        """analyze_and_plan must stop immediately after understanding when awaiting confirmation."""
        state = ProjectState(goal="Build a personal portfolio web application")
        state.auto_confirm = False

        self.pipeline.analyze_and_plan(state)

        assert state.project_state == "AWAITING_CONFIRMATION"
        assert state.is_awaiting_confirmation() is True
        assert len(state.tasks) == 0

        activity_messages = [a.message for a in state.activity_feed]
        assert not any("Planner & Architect Agent completed task successfully" in m for m in activity_messages)

    def test_can_execute_prerequisites_reject_awaiting_confirmation(self):
        """can_execute_plan, can_execute_build, can_execute_run, can_execute_test must all reject AWAITING_CONFIRMATION."""
        state = ProjectState(goal="Build a REST API for task tracking")
        state.project_state = "AWAITING_CONFIRMATION"
        state.interpretation_status = "PENDING"
        state.auto_confirm = False

        assert self.pipeline.can_execute_plan(state) is False
        assert self.pipeline.can_execute_build(state) is False
        assert self.pipeline.can_execute_run(state) is False
        assert self.pipeline.can_execute_test(state) is False
        assert self.pipeline.can_execute_debug(state) is False

    def test_execute_build_strictly_blocked_while_awaiting_confirmation(self):
        """Calling execute_build while in AWAITING_CONFIRMATION must abort immediately without mutating state."""
        state = ProjectState(goal="Build a REST API")
        state.project_state = "AWAITING_CONFIRMATION"
        state.interpretation_status = "PENDING"
        state.auto_confirm = False

        self.pipeline.execute_build(state)

        # State remains AWAITING_CONFIRMATION and did not transition to GENERATING or BUILDING
        assert state.project_state == "AWAITING_CONFIRMATION"
        assert any("execute_build blocked" in a.message for a in state.activity_feed)

    def test_invalid_state_transition_from_awaiting_confirmation_rejected(self):
        """Direct transition from AWAITING_CONFIRMATION to engineering states must be rejected."""
        state = ProjectState(goal="Test app")
        state.project_state = "AWAITING_CONFIRMATION"

        # Attempt to jump straight to PLANNING or BUILDING
        assert state.transition_to("PLANNING") is False
        assert state.project_state == "AWAITING_CONFIRMATION"

        assert state.transition_to("BUILDING") is False
        assert state.project_state == "AWAITING_CONFIRMATION"

        assert state.transition_to("RUNNING") is False
        assert state.project_state == "AWAITING_CONFIRMATION"

        # Valid transition to CONFIRMED or WAITING_FOR_USER is permitted
        assert state.transition_to("CONFIRMED") is True
        assert state.project_state == "CONFIRMED"

    def test_base_agent_execute_blocks_when_awaiting_confirmation(self):
        """BaseAgent.execute must refuse to run actions when system is awaiting confirmation."""
        state = ProjectState(goal="Test app")
        state.project_state = "AWAITING_CONFIRMATION"
        state.interpretation_status = "PENDING"
        state.auto_confirm = False

        agent = BaseAgent("Developer Agent", "Code Generator")
        mock_action = MagicMock()

        result = agent.execute(state, mock_action, task_id="t-1")

        assert result is None
        mock_action.assert_not_called()
        assert any("Developer Agent blocked: execution prohibited while awaiting user confirmation" in a.message for a in state.activity_feed)

    def test_task_graph_readiness_blocked_while_awaiting_confirmation(self):
        """is_task_ready must return False while awaiting confirmation, even if dependencies are empty."""
        state = ProjectState(goal="Test app")
        state.project_state = "AWAITING_CONFIRMATION"
        state.interpretation_status = "PENDING"
        state.auto_confirm = False

        task = Task(id="t-1", title="Build component", phase="BUILD")
        assert state.is_task_ready(task) is False

    def test_user_confirmation_releases_barrier_and_unlocks_planning(self):
        """When user confirms:
        1. confirm_interpretation transitions to CONFIRMED.
        2. is_awaiting_confirmation becomes False.
        3. can_execute_engineering becomes True.
        4. plan_and_architect can execute.
        """
        state = ProjectState(goal="Build a simple calculator")
        state.auto_confirm = False

        self.pipeline.understand_requirement(state)
        assert state.is_awaiting_confirmation() is True

        # User confirms
        success = self.pipeline.confirm_interpretation(state)
        assert success is True
        assert state.project_state in ("CONFIRMED", "ENGINEERING_READY")
        assert state.interpretation_status == "CONFIRMED"
        assert state.user_approved is True
        assert state.is_awaiting_confirmation() is False
        assert state.can_execute_engineering() is True
        assert self.pipeline.can_execute_plan(state) is True

    def test_rejection_and_revision_preserves_hard_gate(self):
        """When user rejects with corrective feedback:
        1. EngineeringSpecification is updated with feedback.
        2. State remains or cleanly transitions to AWAITING_CONFIRMATION.
        3. interpretation_status remains PENDING.
        4. Execution remains blocked.
        """
        state = ProjectState(goal="Build a 3D website about space")
        state.auto_confirm = False

        self.pipeline.understand_requirement(state)
        assert state.project_state == "AWAITING_CONFIRMATION"

        # User rejects with feedback
        raw_spec = state.engineering_spec
        spec = EngineeringSpecification.from_dict(raw_spec)
        revised = SemanticRequirementAnalyzer.update_with_feedback(
            spec,
            feedback="Actually make it a 2D solar system educational dashboard with React",
            is_rejection=True,
        )

        state.engineering_spec = revised.to_dict()
        state.requirement_interpretation = revised.concise_interpretation
        state.interpretation_status = "PENDING"
        state.transition_to("AWAITING_CONFIRMATION", f"Revised: {revised.concise_interpretation}")

        assert state.project_state == "AWAITING_CONFIRMATION"
        assert state.is_awaiting_confirmation() is True
        assert state.can_execute_engineering() is False
        assert len(state.tasks) == 0
        assert "2d" in revised.concise_interpretation.lower() or "solar" in revised.concise_interpretation.lower()

    def test_auto_confirm_mode_proceeds_smoothly(self):
        """When auto_confirm is True, understand_requirement confirms intent immediately."""
        state = ProjectState(goal="Build a countdown timer in HTML and JS")
        state.auto_confirm = True

        confirmed = self.pipeline.understand_requirement(state)

        assert confirmed is True
        assert state.project_state in ("CONFIRMED", "ENGINEERING_READY")
        assert state.interpretation_status == "CONFIRMED"
        assert state.is_awaiting_confirmation() is False
        assert state.can_execute_engineering() is True
        assert self.pipeline.can_execute_plan(state) is True


class TestServerConfirmationEndpoints:
    """Test server REST endpoints and conversational worker confirmation gate handling."""

    def setup_method(self):
        import server
        from starlette.testclient import TestClient
        self.server = server
        self.client = TestClient(server.app)

    def test_api_confirm_transitions_state_and_triggers_pipeline(self):
        with self.server.state_lock:
            self.server.state.reset(new_goal="Build 3D galaxy")
            self.server.state.project_state = "AWAITING_CONFIRMATION"
            self.server.state.interpretation_status = "PENDING"
            self.server.state.requirement_interpretation = "3D Galaxy Simulation"
            self.server.state.auto_confirm = False

        with patch.object(self.server.pipeline, "plan_and_architect") as mock_plan, \
             patch.object(self.server.pipeline, "execute_build") as mock_build:
            res = self.client.post("/api/confirm")
            assert res.status_code == 200
            data = res.json()
            assert data["status"] == "CONFIRMED"
            assert self.server.state.project_state in ("CONFIRMED", "ENGINEERING_READY")
            assert self.server.state.is_awaiting_confirmation() is False

    def test_api_reject_updates_specification_and_stays_awaiting_confirmation(self):
        with self.server.state_lock:
            self.server.state.reset(new_goal="Build 3D galaxy")
            spec = SemanticRequirementAnalyzer.analyze("Build 3D galaxy")
            self.server.state.engineering_spec = spec.to_dict()
            self.server.state.project_state = "AWAITING_CONFIRMATION"
            self.server.state.interpretation_status = "PENDING"
            self.server.state.auto_confirm = False

        res = self.client.post("/api/reject", json={"feedback": "Make it a 2D canvas simulation"})
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "REVISED"
        assert self.server.state.project_state == "AWAITING_CONFIRMATION"
        assert self.server.state.is_awaiting_confirmation() is True
        assert self.server.state.can_execute_engineering() is False

    def test_conversational_worker_affirmative_confirms(self):
        with self.server.state_lock:
            self.server.state.reset(new_goal="Build 3D galaxy")
            self.server.state.project_state = "AWAITING_CONFIRMATION"
            self.server.state.interpretation_status = "PENDING"
            self.server.state.auto_confirm = False

        with patch.object(self.server.pipeline, "plan_and_architect") as mock_plan, \
             patch.object(self.server.pipeline, "execute_build") as mock_build:
            self.server._run_conversational_worker("yes, looks good! build it")
            assert self.server.state.project_state in ("CONFIRMED", "ENGINEERING_READY")
            assert self.server.state.is_awaiting_confirmation() is False
            mock_plan.assert_called_once()
            mock_build.assert_called_once()

    def test_conversational_worker_question_does_not_confirm(self):
        with self.server.state_lock:
            self.server.state.reset(new_goal="Build 3D galaxy")
            self.server.state.project_state = "AWAITING_CONFIRMATION"
            self.server.state.interpretation_status = "PENDING"
            self.server.state.auto_confirm = False

        with patch.object(self.server.pipeline, "plan_and_architect") as mock_plan, \
             patch.object(self.server.pipeline, "execute_build") as mock_build:
            self.server._run_conversational_worker("What version of Three.js will you be using?")
            # Must remain in AWAITING_CONFIRMATION and not execute plan or build
            assert self.server.state.project_state == "AWAITING_CONFIRMATION"
            assert self.server.state.is_awaiting_confirmation() is True
            mock_plan.assert_not_called()
            mock_build.assert_not_called()

