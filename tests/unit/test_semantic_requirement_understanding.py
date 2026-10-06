import pytest
from backend.core.task_classifier import TaskClassifier, TaskClassification
from backend.core.semantic_requirement import (
    SemanticRequirementAnalyzer,
    EngineeringSpecification,
)
from backend.core.project_state import ProjectState


class TestSemanticRequirementUnderstanding:
    """Test suite for Milestone 1 Intent Understanding and Semantic Requirements."""

    def setup_method(self):
        self.classifier = TaskClassifier()
        self.analyzer = SemanticRequirementAnalyzer()

    def test_classify_contextual_modifications(self):
        """Contextual requests referencing an existing project must be classified as MODIFICATION/FEATURE_REQUEST, not NEW_PROJECT."""
        # When has_existing_project is True, continuation and modification phrases should not wipe the project
        res1 = self.classifier.classify("Make it about Messi", has_existing_project=True, existing_files_count=3)
        assert res1 in (TaskClassification.MODIFICATION, TaskClassification.FEATURE_REQUEST)

        res2 = self.classifier.classify("Add a timeline of his trophies", has_existing_project=True, existing_files_count=3)
        assert res2 in (TaskClassification.MODIFICATION, TaskClassification.FEATURE_REQUEST)

        res3 = self.classifier.classify("Make it more interactive with 3D models", has_existing_project=True, existing_files_count=3)
        assert res3 in (TaskClassification.MODIFICATION, TaskClassification.FEATURE_REQUEST)

        # But a fresh instruction without an existing project should be NEW_PROJECT
        res4 = self.classifier.classify("Build a 3D website about Messi's career", has_existing_project=False, existing_files_count=0)
        assert res4 == TaskClassification.NEW_PROJECT

    def test_semantic_analysis_3d_webgl(self):
        """Infer 3D WebGL requirements without asking user for technical trivia."""
        prompt = "Build a 3D interactive website showcasing Lionel Messi's career achievements"
        spec = self.analyzer.analyze(prompt)

        assert isinstance(spec, EngineeringSpecification)
        assert spec.application_type == "web_3d"
        assert spec.is_confirmed is False
        assert spec.interpretation_status == "PENDING"
        assert len(spec.interpretation) > 20
        # Verification requirements must expect WebGL and canvas
        assert spec.verification_requirements.get("requires_webgl") is True
        assert spec.verification_requirements.get("requires_canvas") is True
        # Engineering defaults must include Three.js or WebGL
        assert any("three" in t.lower() or "webgl" in t.lower() for t in spec.engineering_defaults["tech_stack"])

    def test_semantic_analysis_expense_tracker(self):
        """Infer web application requirements for an expense tracker."""
        prompt = "Create a personal finance and expense tracking web app"
        spec = self.analyzer.analyze(prompt)

        assert spec.application_type in ("web", "fullstack")
        assert len(spec.core_capabilities) >= 2
        # Should infer budgeting, tracking, or categorization
        caps_str = " ".join(spec.core_capabilities).lower()
        assert "expense" in caps_str or "track" in caps_str or "budget" in caps_str
        assert spec.verification_requirements.get("requires_webgl", False) is False

    def test_semantic_analysis_portfolio(self):
        """Infer portfolio requirements."""
        prompt = "Make a modern portfolio website for a creative UI designer"
        spec = self.analyzer.analyze(prompt)

        assert spec.application_type == "web"
        caps_str = " ".join(spec.core_capabilities).lower()
        assert "portfolio" in caps_str or "showcase" in caps_str or "project" in caps_str or "design" in caps_str

    def test_semantic_analysis_rest_api(self):
        """Infer API requirements."""
        prompt = "Build a REST API for managing a bookstore inventory"
        spec = self.analyzer.analyze(prompt)

        assert spec.application_type == "api"
        assert spec.verification_requirements.get("requires_api_endpoints") is True
        assert spec.verification_requirements.get("requires_webgl", False) is False

    def test_contextual_request_analysis(self):
        """Semantic analysis of contextual modifications preserves context."""
        context = {
            "current_goal": "A personal website for a sports athlete",
            "files": ["index.html", "style.css", "main.js"],
            "application_type": "web_3d",
        }
        spec = self.analyzer.analyze("Make it about Messi and add his career timeline", context=context)

        assert spec.application_type == "web_3d"
        assert "Messi" in spec.interpretation or "messi" in " ".join(spec.core_capabilities).lower()
        assert any("timeline" in cap.lower() for cap in spec.core_capabilities)

    def test_confirmation_and_feedback_flow(self):
        """User can confirm or reject with feedback, updating the specification."""
        prompt = "Build a 3D website about Messi"
        spec = self.analyzer.analyze(prompt)

        assert spec.is_confirmed is False
        assert spec.interpretation_status == "PENDING"

        # User rejects with corrective feedback
        updated_spec = self.analyzer.update_with_feedback(
            spec,
            feedback="Add a golden Ballon d'Or showcase and make the theme dark gold",
        )

        assert updated_spec.is_confirmed is False
        assert updated_spec.interpretation_status == "PENDING"
        # Content requirements or capabilities must include the feedback
        content_and_caps = " ".join(updated_spec.content_requirements + updated_spec.core_capabilities).lower()
        assert "ballon d'or" in content_and_caps or "gold" in content_and_caps or "troph" in content_and_caps

        # User confirms
        updated_spec.user_confirmed = True
        updated_spec.interpretation_status = "CONFIRMED"
        assert updated_spec.is_confirmed is True

    def test_project_state_serialization(self):
        """ProjectState properly serializes and restores engineering specification and confirmation state."""
        state = ProjectState(goal="Build a 3D website")
        spec = self.analyzer.analyze("Build a 3D website about space exploration")
        state.engineering_spec = spec
        state.requirement_interpretation = spec.interpretation
        state.interpretation_status = spec.interpretation_status

        state_dict = state.to_dict()
        assert "engineering_spec" in state_dict
        assert state_dict["engineering_spec"]["application_type"] == "web_3d"
        assert state_dict["requirement_interpretation"] == spec.interpretation
        assert state_dict["interpretation_status"] == "PENDING"

        # Resetting state clears it
        state.reset()
        assert state.engineering_spec is None
        assert not state.requirement_interpretation
        assert state.interpretation_status == "PENDING"

    def test_model_router_authoritative_import_and_llm_execution(self, monkeypatch):
        """SemanticRequirementAnalyzer imports and utilizes authoritative ModelRouter without ModuleNotFoundError."""
        import json
        from backend.core.llm.model_router import get_model_router

        router = get_model_router()
        assert router is not None

        mock_spec_dict = {
            "user_intent": "Build an interactive 3D solar system",
            "domain": "Astronomy",
            "audience": "Students and space enthusiasts",
            "application_type": "web_3d",
            "core_capabilities": ["3D planet models", "Orbital simulation", "Information cards"],
            "content_requirements": ["Eight planets", "Sun texture"],
            "experience_expectations": ["Smooth 60fps WebGL", "Interactive zoom"],
            "explicit_constraints": [],
            "engineering_defaults": {
                "frontend": "Three.js",
                "backend": "None",
                "styling": "Dark space theme",
                "storage": "None",
            },
            "verification_requirements": ["WebGL canvas initialization", "Render loop active"],
            "concise_interpretation": "A 3D solar system exploration web application using Three.js.",
        }

        monkeypatch.setattr(router, "is_configured", lambda: True)
        monkeypatch.setattr(
            "backend.core.openrouter_client.call_openrouter",
            lambda *args, **kwargs: json.dumps(mock_spec_dict),
        )

        spec = SemanticRequirementAnalyzer._try_llm_analysis(
            requirement="Build a 3D solar system with planets",
            has_active_project=False,
            existing_project_spec=None,
            selected_language="Auto Detect",
        )

        assert spec is not None
        assert spec.application_type == "web_3d"
        assert spec.user_intent == "Build an interactive 3D solar system"
        assert spec.domain == "Astronomy"
        assert "WebGL canvas initialization" in spec.verification_requirements

    def test_model_router_provider_failure_falls_back_to_heuristics(self, monkeypatch):
        """When LLM provider raises a runtime error, analyzer logs warning and cleanly falls back."""
        from backend.core.llm.model_router import get_model_router
        router = get_model_router()
        monkeypatch.setattr(router, "is_configured", lambda: True)

        def raise_runtime_err(*args, **kwargs):
            raise RuntimeError("Provider API rate limit or network timeout")

        monkeypatch.setattr("backend.core.openrouter_client.call_openrouter", raise_runtime_err)

        spec = SemanticRequirementAnalyzer._try_llm_analysis(
            requirement="Build a 3D solar system",
            has_active_project=False,
            existing_project_spec=None,
            selected_language="Auto Detect",
        )
        assert spec is None

        full_spec = self.analyzer.analyze("Build a 3D solar system")
        assert full_spec is not None
        assert full_spec.application_type == "web_3d"
