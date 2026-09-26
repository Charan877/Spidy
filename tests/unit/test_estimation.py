"""Unit tests for BuildEstimator and HistoryManager."""

import os
import tempfile
import unittest
from backend.core.estimation import BuildEstimator
from backend.core.history_manager import HistoryManager
from backend.core.project_state import Task


class TestBuildEstimator(unittest.TestCase):
    def test_pre_build_estimation_complex(self):
        tasks = [
            Task(id=f"t{i}", title=f"Task {i}", phase="BUILD", dependencies=[f"t{i-1}"] if i > 0 else [])
            for i in range(18)
        ]
        result = BuildEstimator.estimate_pre_build(
            goal="Build a 3D interactive portfolio website with Three.js and WebGL shaders",
            tech_stack="React / Three.js",
            tasks=tasks,
        )
        self.assertEqual(result.complexity, "HIGH")
        self.assertIn("MIN", result.range_str)
        self.assertGreaterEqual(result.min_minutes, 3)
        self.assertGreaterEqual(result.max_minutes, result.min_minutes)
        self.assertIn(result.confidence, ("HIGH", "MEDIUM"))

    def test_pre_build_estimation_simple(self):
        tasks = [
            Task(id="t1", title="Task 1", phase="BUILD"),
            Task(id="t2", title="Task 2", phase="BUILD"),
        ]
        result = BuildEstimator.estimate_pre_build(
            goal="Simple CLI calculator in python",
            tech_stack="Python",
            tasks=tasks,
        )
        self.assertEqual(result.complexity, "LOW")
        self.assertIn("MIN", result.range_str)
        self.assertGreaterEqual(result.max_minutes, 1)

    def test_calculate_remaining_estimate(self):
        pre = BuildEstimator.estimate_pre_build(
            goal="Build a fullstack web app",
            tech_stack="React",
            tasks=[Task(id=f"t{i}", title=f"T{i}", phase="BUILD") for i in range(10)],
        )
        rem = BuildEstimator.calculate_remaining_estimate(
            pre_build=pre,
            elapsed_seconds=120.0,
            completed_tasks=5,
            total_tasks=10,
        )
        self.assertIn("MIN", rem)

    def test_formatting(self):
        self.assertEqual(BuildEstimator.format_elapsed(201), "03:21")
        self.assertEqual(BuildEstimator.format_actual(554), "9m 14s")
        self.assertEqual(BuildEstimator.format_actual(42), "42s")


class TestHistoryManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.history_file = os.path.join(self.temp_dir.name, "test_history.json")
        self.hm = HistoryManager(self.history_file)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_record_and_retrieve_history(self):
        self.hm.record_project(
            project_name="CarbonLeak",
            goal="FastAPI emissions tracker",
            tech_stack="Python / FastAPI",
            status="COMPLETED",
            duration_seconds=401.0,
            duration_str="6m 41s",
            estimate_range="~5–8 MIN",
            file_count=8,
        )
        records = self.hm.get_recent_projects()
        self.assertGreaterEqual(len(records), 1)
        self.assertEqual(records[0].project_name, "CarbonLeak")
        self.assertEqual(records[0].actual_duration_str, "6m 41s")


if __name__ == "__main__":
    unittest.main()
