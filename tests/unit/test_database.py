"""Unit tests for the SPIDY persistent SQLite database layer.

Verifies:
1. Database initialization
2. Database file creation
3. Table creation
4. Project insertion
5. Project retrieval
6. Build creation
7. Agent run persistence
8. Activity persistence
9. Runtime persistence
10. Verification persistence
11. Foreign-key relationships
12. Multiple projects
13. Persistence across application restart (re-opening same file)
14. Idempotent initialization
"""

import os
from pathlib import Path
import sqlite3
import tempfile
import unittest

from backend.database.connection import DatabaseConnectionFactory
from backend.database.database_manager import DatabaseManager
from backend.database.schema import CURRENT_SCHEMA_VERSION, get_current_schema_version, initialize_schema


class TestDatabaseLayer(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_spidy.db"
        self.db_manager = DatabaseManager(self.db_path)
        self.db_manager.initialize()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_01_database_initialization(self):
        """1. Database initialization succeeded."""
        self.assertTrue(self.db_manager.is_initialized())
        diagnostics = self.db_manager.get_diagnostics()
        self.assertEqual(diagnostics["status"], "HEALTHY")
        self.assertEqual(diagnostics["schema_version"], CURRENT_SCHEMA_VERSION)

    def test_02_database_file_creation(self):
        """2. Database file is physically created on disk."""
        self.assertTrue(self.db_path.exists())
        self.assertGreater(self.db_path.stat().st_size, 0)

    def test_03_table_creation(self):
        """3. All expected tables and indexes exist."""
        expected_tables = {
            "schema_version",
            "projects",
            "builds",
            "agent_runs",
            "activity",
            "runtime_sessions",
            "verification",
        }
        with self.db_manager.factory.connect() as conn:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table';")
            actual_tables = {row["name"] for row in cursor.fetchall()}
            self.assertTrue(expected_tables.issubset(actual_tables))

    def test_04_05_project_insertion_and_retrieval(self):
        """4 & 5. Project insertion, retrieval, and status updates."""
        project = self.db_manager.projects.ensure_project(
            project_id="proj_solar_01",
            name="Solar System 3D",
            description="Interactive 3D simulation with Three.js",
            workspace_path="/workspace/solar",
            detected_stack="React + Three.js",
            status="IDLE",
        )
        self.assertIsNotNone(project)
        self.assertEqual(project["project_id"], "proj_solar_01")
        self.assertEqual(project["name"], "Solar System 3D")
        self.assertEqual(project["status"], "IDLE")

        # Retrieve
        fetched = self.db_manager.projects.get_project("proj_solar_01")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["detected_stack"], "React + Three.js")

        # Update status
        updated = self.db_manager.projects.update_project_status(
            "proj_solar_01", status="BUILDING", detected_stack="React / Three.js / Vite"
        )
        self.assertTrue(updated)
        fetched_after = self.db_manager.projects.get_project("proj_solar_01")
        self.assertEqual(fetched_after["status"], "BUILDING")
        self.assertEqual(fetched_after["detected_stack"], "React / Three.js / Vite")

    def test_06_build_creation(self):
        """6. Build record creation, retrieval, and completion."""
        self.db_manager.projects.ensure_project(
            project_id="proj_api_01",
            name="FastAPI Service",
            status="IDLE",
        )

        build = self.db_manager.builds.create_build(
            build_id="build_001",
            project_id="proj_api_01",
            requirement="Create high-performance API with health checks",
            estimated_duration="~2-4 MIN",
            status="RUNNING",
        )
        self.assertEqual(build["build_id"], "build_001")
        self.assertEqual(build["status"], "RUNNING")

        # Finish build
        finished = self.db_manager.builds.finish_build(
            build_id="build_001",
            status="COMPLETED",
            duration=145.2,
            final_result="Success: 6/6 verification gates passed.",
        )
        self.assertTrue(finished)
        b = self.db_manager.builds.get_build("build_001")
        self.assertEqual(b["status"], "COMPLETED")
        self.assertEqual(b["duration"], 145.2)
        self.assertIn("6/6 verification", b["final_result"])

    def test_07_agent_run_persistence(self):
        """7. Agent run creation and completion tracking."""
        self.db_manager.projects.ensure_project(project_id="p1", name="Test P1")
        self.db_manager.builds.create_build(build_id="b1", project_id="p1", requirement="Req")

        agent_run = self.db_manager.agents.create_agent_run(
            build_id="b1",
            agent_name="Architect Agent",
            task_id="task_arch_1",
            status="WORKING",
        )
        run_id = agent_run["run_id"]
        self.assertIsNotNone(run_id)

        # Finish agent run
        ok = self.db_manager.agents.finish_agent_run(
            run_id=run_id,
            status="SUCCESS",
            duration=3.4,
        )
        self.assertTrue(ok)

        runs = self.db_manager.agents.get_runs_for_build("b1")
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["agent_name"], "Architect Agent")
        self.assertEqual(runs[0]["status"], "SUCCESS")
        self.assertEqual(runs[0]["duration"], 3.4)

    def test_08_activity_persistence(self):
        """8. Activity feed logging and chronological retrieval."""
        self.db_manager.projects.ensure_project(project_id="p1", name="Test P1")
        self.db_manager.builds.create_build(build_id="b1", project_id="p1", requirement="Req")

        self.db_manager.activity.record_activity(
            build_id="b1",
            message="Planner Agent activated",
            event_type="AGENT",
            agent="Planner",
            status="WORKING",
        )
        self.db_manager.activity.record_activity(
            build_id="b1",
            message="Dependency graph materialized",
            event_type="PIPELINE",
            agent="Orchestrator",
            status="SUCCESS",
        )

        activities = self.db_manager.activity.get_activities_for_build("b1")
        self.assertEqual(len(activities), 2)
        self.assertEqual(activities[0]["message"], "Planner Agent activated")
        self.assertEqual(activities[1]["message"], "Dependency graph materialized")

    def test_09_runtime_persistence(self):
        """9. Runtime process tracking, ports, and lifecycle states."""
        self.db_manager.projects.ensure_project(project_id="p1", name="Test P1")
        self.db_manager.builds.create_build(build_id="b1", project_id="p1", requirement="Req")

        session = self.db_manager.runtimes.create_session(
            build_id="b1",
            project_id="p1",
            framework="FastAPI",
            pid=28194,
            port=9000,
            url="http://localhost:9000",
            status="RUNNING",
            health_status="HEALTHY",
        )
        rid = session["runtime_id"]
        self.assertIsNotNone(rid)

        # Retrieve latest
        latest = self.db_manager.runtimes.get_latest_session("b1")
        self.assertIsNotNone(latest)
        self.assertEqual(latest["port"], 9000)
        self.assertEqual(latest["pid"], 28194)

        # Close session
        closed = self.db_manager.runtimes.close_session(rid, status="STOPPED")
        self.assertTrue(closed)
        closed_latest = self.db_manager.runtimes.get_latest_session("b1")
        self.assertEqual(closed_latest["status"], "STOPPED")

    def test_10_verification_persistence(self):
        """10. Six-gate verification records."""
        self.db_manager.projects.ensure_project(project_id="p1", name="Test P1")
        self.db_manager.builds.create_build(build_id="b1", project_id="p1", requirement="Req")

        gates = [
            ("build", "PASSED", "Files compiled without syntax errors"),
            ("process", "PASSED", "PID active and responsive"),
            ("port", "PASSED", "Port 9000 bound"),
            ("server", "PASSED", "Socket connection established"),
            ("http", "PASSED", "HTTP readiness returned 200 OK"),
            ("application", "PASSED", "Payload health check confirmed valid JSON"),
        ]

        for gate_name, status, msg in gates:
            self.db_manager.verification.record_gate_result(
                build_id="b1", gate_name=gate_name, status=status, message=msg
            )

        recorded = self.db_manager.verification.get_gates_for_build("b1")
        self.assertEqual(len(recorded), 6)
        gate_names = [g["gate_name"] for g in recorded]
        self.assertEqual(gate_names, ["build", "process", "port", "server", "http", "application"])

    def test_11_foreign_key_relationships(self):
        """11. Foreign keys cascade deletes appropriately."""
        self.db_manager.projects.ensure_project(project_id="p_cascade", name="Cascade Project")
        self.db_manager.builds.create_build(build_id="b_cascade", project_id="p_cascade", requirement="Req")
        self.db_manager.activity.record_activity(build_id="b_cascade", message="Evt 1")
        self.db_manager.agents.create_agent_run(build_id="b_cascade", agent_name="Agent 1")

        # Deleting project cascades to builds, activities, and agent runs
        deleted = self.db_manager.projects.delete_project("p_cascade")
        self.assertTrue(deleted)

        self.assertIsNone(self.db_manager.builds.get_build("b_cascade"))
        self.assertEqual(len(self.db_manager.activity.get_activities_for_build("b_cascade")), 0)
        self.assertEqual(len(self.db_manager.agents.get_runs_for_build("b_cascade")), 0)

    def test_12_multiple_projects(self):
        """12. Multiple projects maintain distinct build and activity histories."""
        self.db_manager.projects.ensure_project(project_id="proj_alpha", name="Project Alpha")
        self.db_manager.projects.ensure_project(project_id="proj_beta", name="Project Beta")

        self.db_manager.builds.create_build(build_id="b_alpha_1", project_id="proj_alpha", requirement="Req Alpha 1")
        self.db_manager.builds.create_build(build_id="b_alpha_2", project_id="proj_alpha", requirement="Req Alpha 2")
        self.db_manager.builds.create_build(build_id="b_beta_1", project_id="proj_beta", requirement="Req Beta 1")

        alpha_builds = self.db_manager.builds.get_builds_for_project("proj_alpha")
        beta_builds = self.db_manager.builds.get_builds_for_project("proj_beta")

        self.assertEqual(len(alpha_builds), 2)
        self.assertEqual(len(beta_builds), 1)
        self.assertEqual(alpha_builds[0]["build_id"], "b_alpha_2")
        self.assertEqual(beta_builds[0]["build_id"], "b_beta_1")

    def test_13_persistence_across_application_restart(self):
        """13. Data survives complete shutdown and re-initialization of DatabaseManager."""
        self.db_manager.projects.ensure_project(project_id="p_persist", name="Persistent App")
        self.db_manager.builds.create_build(
            build_id="b_persist", project_id="p_persist", requirement="Permanent spec"
        )
        self.db_manager.builds.finish_build(
            build_id="b_persist", status="COMPLETED", duration=42.0, final_result="Built and verified."
        )

        # Simulate restart by creating completely new manager pointing to the same file
        restarted_manager = DatabaseManager(self.db_path)
        upgraded, version = restarted_manager.initialize()
        self.assertFalse(upgraded)  # Should not need re-upgrade
        self.assertEqual(version, CURRENT_SCHEMA_VERSION)

        project = restarted_manager.projects.get_project("p_persist")
        self.assertIsNotNone(project)
        self.assertEqual(project["name"], "Persistent App")

        build = restarted_manager.builds.get_build("b_persist")
        self.assertIsNotNone(build)
        self.assertEqual(build["status"], "COMPLETED")
        self.assertEqual(build["duration"], 42.0)

    def test_14_database_initialization_is_idempotent(self):
        """14. Initializing multiple times does not destroy data or duplicate schema."""
        self.db_manager.projects.ensure_project(project_id="p_idem", name="Idempotent Test")

        # Run initialize multiple times
        for _ in range(3):
            upgraded, ver = self.db_manager.initialize()
            self.assertFalse(upgraded)
            self.assertEqual(ver, CURRENT_SCHEMA_VERSION)

        # Data remains intact
        proj = self.db_manager.projects.get_project("p_idem")
        self.assertIsNotNone(proj)
        self.assertEqual(proj["name"], "Idempotent Test")


if __name__ == "__main__":
    unittest.main()
