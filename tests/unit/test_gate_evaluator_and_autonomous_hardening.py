"""Tests for GateEvaluator, Semantic Task Graph, Dynamic Entity Extraction, and State Machine Hardening."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock

from backend.core.architecture_contract import extract_architecture_contract, _detect_resource_name
from backend.core.project_state import ProjectState, Task
from backend.orchestration.orchestrator import MultiAgentPipeline
from backend.verification.gate_evaluator import GateEvaluator, GateEvaluationResult


class TestGateEvaluatorAndAutonomousHardening(unittest.TestCase):
    def test_dynamic_entity_extraction_unfamiliar_requirements(self):
        """Verify dynamic entity extraction works for completely unfamiliar requirements without hardcoded names."""
        # Unfamiliar requirement: Recipe platform
        res, ep, payload = _detect_resource_name("Build a Recipe Sharing platform called DishCraft for home cooks")
        self.assertEqual(res, "recipe")
        self.assertEqual(ep, "/api/recipes")
        self.assertIn("title", payload)

        # Unfamiliar requirement: IoT Telemetry
        res2, ep2, payload2 = _detect_resource_name("Build an IoT Telemetry Service collecting sensor metrics")
        self.assertIn(res2, ["reading", "sensor", "metric"])
        self.assertTrue(ep2.startswith("/api/"))

        # Unfamiliar requirement: Book Library
        res3, ep3, payload3 = _detect_resource_name("Create a book lending library manager")
        self.assertEqual(res3, "book")
        self.assertEqual(ep3, "/api/books")

        # Dynamic contract extraction for unfamiliar project
        contract = extract_architecture_contract(
            requirement="Create a full-stack platform called 'AstroTracker' for tracking planets and constellations using React and FastAPI with SQLite"
        )
        self.assertEqual(contract.project_name, "AstroTracker")
        self.assertEqual(contract.frontend_framework, "React")
        self.assertEqual(contract.backend_framework, "FastAPI")
        self.assertEqual(contract.database_engine, "SQLite")
        self.assertTrue(contract.is_strict_fullstack)

    def test_gate_evaluator_build_gate(self):
        """Verify GateEvaluator.evaluate_build checks syntax, placeholders, and files."""
        # Case 1: Empty workspace files
        res = GateEvaluator.evaluate_build(None, {})
        self.assertFalse(res.passed)
        self.assertEqual(res.status, "FAILED")

        # Case 2: Placeholder path rejected
        res2 = GateEvaluator.evaluate_build(None, {"path/to/file.py": "print('hello')"})
        self.assertFalse(res2.passed)
        self.assertIn("Placeholder", res2.reason)

        # Case 3: Syntax error detected
        res3 = GateEvaluator.evaluate_build(None, {"main.py": "def broken_syntax(:\n    pass"})
        self.assertFalse(res3.passed)
        self.assertIn("Syntax error", res3.reason)

        # Case 4: Valid files pass
        res4 = GateEvaluator.evaluate_build(None, {"main.py": "def valid():\n    return 42\n"})
        self.assertTrue(res4.passed)
        self.assertEqual(res4.status, "PASSED")

    def test_gate_evaluator_port_isolation(self):
        """Verify GateEvaluator.evaluate_port rejects control server ports and accepts free ports."""
        # SPIDY control port 8501
        res = GateEvaluator.evaluate_port(8501)
        self.assertFalse(res.passed)
        self.assertIn("collides", res.reason)

        # Isolated port 9042
        res2 = GateEvaluator.evaluate_port(9042)
        self.assertTrue(res2.passed)
        self.assertEqual(res2.status, "PASSED")

    def test_semantic_task_fields_and_evidence(self):
        """Verify Task supports semantic descriptions, expected outputs, and evidence collection."""
        st = ProjectState(goal="Test Semantic Tasks")
        st.add_task(
            task_id="t-1",
            title="Generate app/main.py",
            phase="BUILD",
            agent="Developer Agent",
            file_path="app/main.py",
            description="Implement FastAPI router with CRUD endpoints",
            expected_output="Valid Python file defining FastAPI app",
            evidence_required="code_artifact_syntax_valid",
        )
        task = st.tasks[0]
        self.assertEqual(task.description, "Implement FastAPI router with CRUD endpoints")
        self.assertEqual(task.expected_output, "Valid Python file defining FastAPI app")
        self.assertEqual(task.evidence_required, "code_artifact_syntax_valid")

        # Collect evidence
        task.evidence_collected = {"size_bytes": 1024, "syntax_valid": True}
        d = task.to_dict()
        self.assertIn("evidence_collected", d)
        self.assertEqual(d["evidence_collected"]["size_bytes"], 1024)

    def test_can_execute_run_fails_if_build_failed(self):
        """can_execute_run must return False if required build tasks failed."""
        ws = MagicMock()
        ws.list_files.return_value = ["index.html"]
        pipeline = MultiAgentPipeline(ws)
        st = ProjectState(goal="Build app")
        st.add_task("t-1", "Build index", "BUILD", is_required=True)
        st.fail_task("t-1", "Artifact validation failed")

        self.assertFalse(pipeline.can_execute_run(st))


if __name__ == "__main__":
    unittest.main()
