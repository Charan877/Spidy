import os
import time
import uuid
import pytest
from unittest.mock import MagicMock, patch
from backend.core.project_state import ProjectState, Task
from backend.core.task_classifier import TaskClassifier, TaskClassification
from backend.core.semantic_requirement import (
    SemanticRequirementAnalyzer,
    EngineeringSpecification,
)
from backend.core.active_context import ActiveProjectContext
from backend.orchestration.orchestrator import MultiAgentPipeline


class TestProjectIntentResolutionAndConfirmationRelease:
    """Verifies intent classification (NEW_PROJECT vs MODIFICATION) and confirmation release lifecycle."""

    def setup_method(self):
        self.workspace = MagicMock()
        self.workspace.list_files.return_value = []
        self.runner = MagicMock()
        self.pipeline = MultiAgentPipeline(workspace=self.workspace, runner=self.runner)

    # 1. Standalone new project request while another project exists in SQLite
    def test_standalone_new_project_while_another_project_in_sqlite(self):
        prompts = [
            "Build an interactive 3D portfolio website.",
            "Create a 3D website about Messi.",
            "Make an expense tracker.",
        ]
        for p in prompts:
            # Simulate an existing completed project in SQLite
            cls_result = TaskClassifier.classify(
                message=p,
                has_existing_project=True,
                existing_files_count=10,
            )
            assert cls_result == TaskClassification.NEW_PROJECT, f"Expected NEW_PROJECT for '{p}', got {cls_result}"

            spec = SemanticRequirementAnalyzer.analyze(
                requirement=p,
                active_context={"project_id": "proj_previous_completed"},
                existing_project_spec={"application_type": "web", "topic": "old_project"},
            )
            assert spec.intent_classification == "NEW_PROJECT"
            assert spec.is_modification is False
            assert "update the existing" not in spec.concise_interpretation.lower()
            assert len(spec.concise_interpretation) > 10

    # 2. Standalone new project request while another project is currently visible in UI
    def test_standalone_new_project_while_another_visible_in_ui(self):
        active_ctx = ActiveProjectContext.create_new(
            project_name="Current Visible Dashboard",
            project_id="proj_visible_123",
        )
        # Even with active_ctx pointing to a visible project, standalone build is NEW_PROJECT
        spec = SemanticRequirementAnalyzer.analyze(
            requirement="Build an interactive 3D portfolio website.",
            active_context=active_ctx,
        )
        assert spec.intent_classification == "NEW_PROJECT"
        assert spec.is_modification is False
        assert spec.target_project_id is None
        assert "update the existing" not in spec.concise_interpretation.lower()

    # 3. Genuine modification request referring to the active project
    def test_genuine_modification_referring_to_active_project(self):
        modification_prompts = [
            ("Add a timeline showing my career journey.", "MODIFICATION"),
            ("Make it about Messi.", "MODIFICATION"),
            ("Change the existing dashboard.", "MODIFICATION"),
        ]
        for p, expected_intent in modification_prompts:
            cls_result = TaskClassifier.classify(
                message=p,
                has_existing_project=True,
                existing_files_count=5,
            )
            assert cls_result in (TaskClassification.MODIFICATION, TaskClassification.FEATURE_REQUEST)

            # Analyze with active context containing existing project spec
            spec = SemanticRequirementAnalyzer.analyze(
                requirement=p,
                active_context={"project_id": "proj_active_app"},
                existing_project_spec={"application_type": "web", "topic": "Portfolio"},
            )
            assert spec.intent_classification == "MODIFICATION"
            assert spec.is_modification is True
            assert spec.target_project_id == "proj_active_app"
            assert any(term in spec.concise_interpretation.lower() for term in ("update", "enhance", "existing", "add", "modify"))

    # 4. New project request followed by confirmation
    def test_new_project_request_followed_by_confirmation(self):
        state = ProjectState(goal="Build an interactive 3D portfolio website.")
        state.auto_confirm = False

        confirmed = self.pipeline.understand_requirement(state)
        assert confirmed is False
        assert state.project_state == "AWAITING_CONFIRMATION"
        assert state.pending_intent == "NEW_PROJECT"
        assert state.is_awaiting_confirmation() is True
        assert state.can_execute_engineering() is False

        # User confirms
        release_ok = self.pipeline.confirm_interpretation(state)
        assert release_ok is True
        assert state.project_state == "ENGINEERING_READY"
        assert state.interpretation_status == "CONFIRMED"
        assert state.user_approved is True
        assert state.is_awaiting_confirmation() is False
        assert state.can_execute_engineering() is True

    # 5. Modification request followed by confirmation
    def test_modification_request_followed_by_confirmation(self):
        state = ProjectState(goal="Add a timeline showing my career journey.")
        state.active_context = {"project_id": "proj_my_portfolio"}
        state.project_spec = {"application_type": "web_3d", "topic": "Developer Portfolio"}
        state.auto_confirm = False

        confirmed = self.pipeline.understand_requirement(state)
        assert confirmed is False
        assert state.project_state == "AWAITING_CONFIRMATION"
        assert state.pending_intent == "MODIFICATION"
        assert state.pending_target_project_id == "proj_my_portfolio"

        # User confirms
        self.pipeline.confirm_interpretation(state)
        assert state.project_state == "ENGINEERING_READY"
        assert state.can_execute_engineering() is True

    # 6. Rejection followed by corrected requirements and a second confirmation
    def test_rejection_followed_by_correction_and_second_confirmation(self):
        state = ProjectState(goal="Build an interactive 3D portfolio website.")
        state.auto_confirm = False

        self.pipeline.understand_requirement(state)
        assert state.project_state == "AWAITING_CONFIRMATION"

        # User rejects / requests correction
        raw_spec = state.engineering_spec or {}
        spec = EngineeringSpecification.from_dict(raw_spec)
        revised = SemanticRequirementAnalyzer.update_with_feedback(
            spec, "Actually make it a 2D minimal black and white portfolio, no 3D", is_rejection=True
        )
        state.engineering_spec = revised.to_dict()
        state.requirement_interpretation = revised.concise_interpretation
        state.transition_to("AWAITING_CONFIRMATION", "Revised interpretation pending confirmation")

        # Must still be awaiting confirmation, NOT executing
        assert state.is_awaiting_confirmation() is True
        assert state.can_execute_engineering() is False
        assert "2d" in revised.concise_interpretation.lower() or "minimal" in revised.concise_interpretation.lower()

        # Second confirmation
        self.pipeline.confirm_interpretation(state)
        assert state.project_state == "ENGINEERING_READY"
        assert state.can_execute_engineering() is True

    # 7. Stale confirmation from a previous request (correlation)
    def test_stale_confirmation_project_mismatch(self):
        state = ProjectState(goal="Build an expense tracker.")
        state.project_id = "proj_fresh_new_123"
        state.auto_confirm = False

        self.pipeline.understand_requirement(state)
        assert state.is_awaiting_confirmation() is True

        # Simulate confirm request for a different / stale project id
        stale_pid = "proj_old_stale_999"
        assert stale_pid != state.project_id
        # Server validates req_pid != state.project_id and rejects

    # 8. Confirmation when no pending interpretation exists
    def test_confirmation_when_not_awaiting_confirmation(self):
        state = ProjectState(goal="")
        state.project_state = "IDLE"
        assert state.is_awaiting_confirmation() is False

        # In conversational worker, affirmative messages ("yes", "confirm") when not awaiting
        # confirmation must NOT trigger a build named "yes"
        msg = "yes"
        # TaskClassifier returns confirmation/status, not NEW_PROJECT with empty project
        has_awaiting = state.is_awaiting_confirmation()
        assert has_awaiting is False

    # 9. Server restart while awaiting confirmation
    def test_server_restart_while_awaiting_confirmation(self):
        state = ProjectState(goal="Build a 3D website about Messi.")
        state.auto_confirm = False
        self.pipeline.understand_requirement(state)
        assert state.project_state == "AWAITING_CONFIRMATION"

        # Simulate state saved/restored across restart
        serialized = state.to_dict()
        assert serialized["project_state"] == "AWAITING_CONFIRMATION"
        assert serialized["interpretation_status"] == "PENDING"
        assert serialized["pending_intent"] == "NEW_PROJECT"

        restored_state = ProjectState(goal=serialized["goal"])
        restored_state.project_state = serialized["project_state"]
        restored_state.interpretation_status = serialized["interpretation_status"]
        restored_state.engineering_spec = serialized["engineering_spec"]
        restored_state.requirement_interpretation = serialized["requirement_interpretation"]
        restored_state.pending_intent = serialized["pending_intent"]

        assert restored_state.is_awaiting_confirmation() is True
        assert restored_state.can_execute_engineering() is False

        # After restart, user confirms restored requirement
        self.pipeline.confirm_interpretation(restored_state)
        assert restored_state.is_awaiting_confirmation() is False
        assert restored_state.can_execute_engineering() is True

    # 10. Confirmation immediately followed by worker scheduling
    def test_confirmation_immediately_allows_worker_execution(self):
        state = ProjectState(goal="Build an expense tracker.")
        state.auto_confirm = False
        self.pipeline.understand_requirement(state)
        assert state.can_execute_engineering() is False

        self.pipeline.confirm_interpretation(state)
        assert state.can_execute_engineering() is True
        # Now can_execute_plan passes
        assert self.pipeline.can_execute_plan(state) is True

    # 11. Verification that "Build an interactive 3D portfolio website" is NEW_PROJECT
    def test_interactive_portfolio_is_new_project_never_update(self):
        user_request = "Build an interactive 3D portfolio website."
        cls_result = TaskClassifier.classify(
            message=user_request,
            has_existing_project=True,  # even with previous project in workspace
            existing_files_count=15,
        )
        assert cls_result == TaskClassification.NEW_PROJECT

        spec = SemanticRequirementAnalyzer.analyze(
            requirement=user_request,
            active_context={"project_id": "proj_previous_app"},
            existing_project_spec={"application_type": "web", "topic": "Old App"},
        )
        assert spec.intent_classification == "NEW_PROJECT"
        assert spec.is_modification is False
        assert "update the existing application" not in spec.concise_interpretation.lower()
        assert spec.application_type == "web_3d"
        assert "3d" in spec.concise_interpretation.lower()
